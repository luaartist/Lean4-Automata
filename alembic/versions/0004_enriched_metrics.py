"""Add enriched static-analysis metrics to files and symbols.

New columns on ``files``:
  - Proof completeness:  sorry_count, admit_count, sorry_lines, sorry_in_proof_count,
                         theorem_count, proof_completion
  - Fragility:           native_decide_count, debug_command_count
  - Symbol breakdown:    noncomputable_count, instance_count, declared_axiom_count,
                         simp_attr_count
  - Hygiene:             docstring_count, todo_count
  - Import profile:      mathlib_import_count

New column on ``symbols``:
  - has_sorry BOOL       -- sorry/admit found in this declaration's body span

New views:
  - v_proof_status       -- per-file proof completeness at a glance
  - v_floating_symbols   -- public theorems/defs with zero incoming dependencies
  - v_file_interconnect  -- file-level fan-in / fan-out / health summary

Revision ID: 0004
Revises: 0003
Create Date: 2024-01-01 12:00:03.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── files: proof-completeness columns ────────────────────────────────────
    op.add_column("files", sa.Column("sorry_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("files", sa.Column("admit_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("files", sa.Column("sorry_lines", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("files", sa.Column("sorry_in_proof_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("files", sa.Column("theorem_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("files", sa.Column("proof_completion", sa.Float(), server_default=sa.text("1.0"), nullable=False))

    # ── files: fragility signals ──────────────────────────────────────────────
    op.add_column("files", sa.Column("native_decide_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("files", sa.Column("debug_command_count", sa.Integer(), server_default=sa.text("0"), nullable=False))

    # ── files: symbol breakdown ───────────────────────────────────────────────
    op.add_column("files", sa.Column("noncomputable_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("files", sa.Column("instance_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("files", sa.Column("declared_axiom_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("files", sa.Column("simp_attr_count", sa.Integer(), server_default=sa.text("0"), nullable=False))

    # ── files: hygiene ────────────────────────────────────────────────────────
    op.add_column("files", sa.Column("docstring_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("files", sa.Column("todo_count", sa.Integer(), server_default=sa.text("0"), nullable=False))

    # ── files: import profile ─────────────────────────────────────────────────
    op.add_column("files", sa.Column("mathlib_import_count", sa.Integer(), server_default=sa.text("0"), nullable=False))

    # ── symbols: per-declaration sorry flag ───────────────────────────────────
    op.add_column("symbols", sa.Column("has_sorry", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    # ── indexes for common agent queries ─────────────────────────────────────
    op.execute(text("CREATE INDEX idx_files_sorry_count ON files (sorry_count DESC) WHERE sorry_count > 0"))
    op.execute(text("CREATE INDEX idx_files_proof_completion ON files (proof_completion) WHERE proof_completion < 1.0"))
    op.execute(text("CREATE INDEX idx_symbols_has_sorry ON symbols (has_sorry) WHERE has_sorry = true"))

    # ── v_proof_status: per-file proof completeness ───────────────────────────
    op.execute(text("""
        CREATE VIEW v_proof_status AS
        SELECT
            f.id,
            f.relative_path,
            f.module_name,
            f.theorem_count,
            f.sorry_in_proof_count,
            f.proof_completion,
            f.sorry_count,
            f.admit_count,
            f.sorry_lines,
            f.debug_command_count,
            f.native_decide_count,
            CASE
                WHEN f.theorem_count = 0    THEN 'no_theorems'
                WHEN f.proof_completion = 1.0 THEN 'complete'
                WHEN f.proof_completion >= 0.5 THEN 'partial'
                ELSE 'mostly_incomplete'
            END AS proof_status
        FROM files f
        ORDER BY f.proof_completion, f.sorry_count DESC
    """))

    # ── v_floating_symbols: public symbols never referenced from other files ──
    # A symbol is "floating" if no dependency edge points to it FROM a symbol
    # in a *different* file.  These are theorems proved but never used.
    op.execute(text("""
        CREATE VIEW v_floating_symbols AS
        SELECT
            s.id,
            s.full_name,
            s.kind,
            s.line_start,
            s.has_sorry,
            f.relative_path,
            f.module_name,
            f.proof_completion
        FROM symbols s
        JOIN files f ON f.id = s.file_id
        WHERE s.kind IN ('theorem', 'def')
          AND s.is_public = true
          AND NOT EXISTS (
              SELECT 1
              FROM dependencies d
              JOIN symbols src ON src.id = d.source_symbol_id
              WHERE d.target_symbol_id = s.id
                AND src.file_id <> s.file_id
          )
        ORDER BY f.relative_path, s.line_start
    """))

    # ── v_file_interconnect: fan-in/fan-out + health per file ─────────────────
    op.execute(text("""
        CREATE VIEW v_file_interconnect AS
        SELECT
            f.id,
            f.relative_path,
            f.module_name,
            jsonb_array_length(f.imports)          AS import_fan_out,
            COUNT(DISTINCT fd_in.source_file_id)   AS import_fan_in,
            f.mathlib_import_count,
            jsonb_array_length(f.imports)
                - f.mathlib_import_count            AS local_import_count,
            f.theorem_count,
            f.sorry_count,
            f.proof_completion,
            f.todo_count,
            f.debug_command_count,
            f.noncomputable_count,
            f.instance_count,
            f.declared_axiom_count
        FROM files f
        LEFT JOIN file_dependencies fd_in ON fd_in.target_file_id = f.id
        GROUP BY f.id, f.relative_path, f.module_name, f.imports,
                 f.mathlib_import_count, f.theorem_count, f.sorry_count,
                 f.proof_completion, f.todo_count, f.debug_command_count,
                 f.noncomputable_count, f.instance_count, f.declared_axiom_count
    """))


def downgrade() -> None:
    op.execute(text("DROP VIEW IF EXISTS v_file_interconnect"))
    op.execute(text("DROP VIEW IF EXISTS v_floating_symbols"))
    op.execute(text("DROP VIEW IF EXISTS v_proof_status"))

    op.execute(text("DROP INDEX IF EXISTS idx_symbols_has_sorry"))
    op.execute(text("DROP INDEX IF EXISTS idx_files_proof_completion"))
    op.execute(text("DROP INDEX IF EXISTS idx_files_sorry_count"))

    for col in (
        "mathlib_import_count", "todo_count", "docstring_count",
        "simp_attr_count", "declared_axiom_count", "instance_count",
        "noncomputable_count", "debug_command_count", "native_decide_count",
        "proof_completion", "theorem_count", "sorry_in_proof_count",
        "sorry_lines", "admit_count", "sorry_count",
    ):
        op.drop_column("files", col)

    op.drop_column("symbols", "has_sorry")
