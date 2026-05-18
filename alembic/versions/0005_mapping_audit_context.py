"""Add Lean/Wolfram mapping and audit context tables.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create mapping, audit-ticket, obligation, and attestation tables."""

    op.create_table(
        "lean_import_references",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("source_file_id", sa.Integer(), nullable=False),
        sa.Column("import_name", sa.Text(), nullable=False),
        sa.Column("target_scope", sa.String(32), server_default=sa.text("'unknown'"), nullable=False),
        sa.Column("package_name", sa.Text(), nullable=True),
        sa.Column("resolved_path", sa.Text(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("indexed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_file_id"], ["files.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "source_file_id", "import_name", name="uq_lean_import_refs_source_import"),
        sa.CheckConstraint(
            "target_scope IN ('mathlib', 'lake_package', 'external_repo', 'unknown')",
            name="ck_lean_import_refs_target_scope",
        ),
    )

    op.create_table(
        "wolfram_companion_maps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("module_name", sa.Text(), nullable=False),
        sa.Column("wolfram_path", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("parsed_map", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("llm_synthesis", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("indexed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modified", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", "module_name", "wolfram_path", name="uq_wolfram_maps_project_module_path"),
    )

    op.create_table(
        "audit_tickets",
        sa.Column("ticket_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("flow_name", sa.String(100), nullable=False),
        sa.Column("ticket_type", sa.String(64), server_default=sa.text("'lean_audit'"), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("ticket_id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'error', 'timeout', 'cancelled')",
            name="ck_audit_tickets_status",
        ),
    )

    op.create_table(
        "proof_obligations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("symbol_id", sa.Integer(), nullable=True),
        sa.Column("ticket_id", sa.String(64), nullable=True),
        sa.Column("module_name", sa.Text(), nullable=True),
        sa.Column("obligation_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), server_default=sa.text("'medium'"), nullable=False),
        sa.Column("status", sa.String(16), server_default=sa.text("'open'"), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["audit_tickets.ticket_id"], ondelete="SET NULL"),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="ck_proof_obligations_severity"),
        sa.CheckConstraint("status IN ('open', 'acknowledged', 'resolved', 'wontfix')", name="ck_proof_obligations_status"),
    )

    op.create_table(
        "ots_stamps",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.String(64), nullable=True),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_key", sa.Text(), nullable=False),
        sa.Column("subject_digest", sa.String(128), nullable=False),
        sa.Column("stamp_provider", sa.String(64), server_default=sa.text("'opentimestamps'"), nullable=False),
        sa.Column("stamp_payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("verification_status", sa.String(32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("stamped_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["audit_tickets.ticket_id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "verification_status IN ('pending', 'stamped', 'verified', 'failed')",
            name="ck_ots_stamps_verification_status",
        ),
    )

    op.create_table(
        "l2bl4_badges",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("badge_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("ticket_id", sa.String(64), nullable=True),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_key", sa.Text(), nullable=False),
        sa.Column("subject_digest", sa.String(128), nullable=True),
        sa.Column("badge_type", sa.String(64), nullable=False),
        sa.Column("issuance_status", sa.String(32), server_default=sa.text("'issued'"), nullable=False),
        sa.Column("issued_to", sa.Text(), nullable=True),
        sa.Column("issued_by", sa.Text(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("issued_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("badge_id", name="uq_l2bl4_badges_badge_id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["audit_tickets.ticket_id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "issuance_status IN ('draft', 'issued', 'revoked', 'superseded')",
            name="ck_l2bl4_badges_issuance_status",
        ),
    )

    op.create_index("idx_lean_import_refs_source", "lean_import_references", ["source_file_id"])
    op.create_index("idx_lean_import_refs_import_name", "lean_import_references", ["project_id", "import_name"])
    op.create_index("idx_lean_import_refs_scope", "lean_import_references", ["project_id", "target_scope"])
    op.execute(text("CREATE INDEX idx_lean_import_refs_metadata_gin ON lean_import_references USING gin (metadata)"))

    op.create_index("idx_wolfram_maps_module", "wolfram_companion_maps", ["project_id", "module_name"])
    op.create_index("idx_wolfram_maps_file", "wolfram_companion_maps", ["file_id"])
    op.execute(text("CREATE INDEX idx_wolfram_maps_parsed_gin ON wolfram_companion_maps USING gin (parsed_map)"))
    op.execute(text("CREATE INDEX idx_wolfram_maps_synthesis_gin ON wolfram_companion_maps USING gin (llm_synthesis)"))

    op.create_index("idx_audit_tickets_flow", "audit_tickets", ["project_id", "flow_name"])
    op.create_index("idx_audit_tickets_status", "audit_tickets", ["status"])
    op.execute(text("CREATE INDEX idx_audit_tickets_created ON audit_tickets (created_at DESC)"))
    op.execute(text("CREATE INDEX idx_audit_tickets_tags_gin ON audit_tickets USING gin (tags)"))
    op.execute(text("CREATE INDEX idx_audit_tickets_output_gin ON audit_tickets USING gin (output_json)"))

    op.create_index("idx_proof_obligations_ticket", "proof_obligations", ["ticket_id"])
    op.create_index("idx_proof_obligations_file_status", "proof_obligations", ["file_id", "status"])
    op.create_index("idx_proof_obligations_symbol_status", "proof_obligations", ["symbol_id", "status"])
    op.create_index("idx_proof_obligations_type", "proof_obligations", ["project_id", "obligation_type"])
    op.execute(text("CREATE INDEX idx_proof_obligations_open ON proof_obligations (project_id, file_id, obligation_type) WHERE status IN ('open', 'acknowledged')"))
    op.execute(text("CREATE INDEX idx_proof_obligations_evidence_gin ON proof_obligations USING gin (evidence)"))

    op.create_index("idx_ots_stamps_subject", "ots_stamps", ["project_id", "subject_type", "subject_key"])
    op.create_index("idx_ots_stamps_ticket", "ots_stamps", ["ticket_id"])
    op.create_index("idx_ots_stamps_digest", "ots_stamps", ["subject_digest"])
    op.execute(text("CREATE INDEX idx_ots_stamps_payload_gin ON ots_stamps USING gin (stamp_payload)"))

    op.create_index("idx_l2bl4_badges_subject", "l2bl4_badges", ["project_id", "subject_type", "subject_key"])
    op.create_index("idx_l2bl4_badges_ticket", "l2bl4_badges", ["ticket_id"])
    op.create_index("idx_l2bl4_badges_type_status", "l2bl4_badges", ["project_id", "badge_type", "issuance_status"])
    op.execute(text("CREATE INDEX idx_l2bl4_badges_evidence_gin ON l2bl4_badges USING gin (evidence)"))

    op.execute(text("""
        CREATE VIEW v_module_import_edges AS
        SELECT
            source.project_id,
            fd.source_file_id,
            source.module_name AS source_module,
            fd.target_file_id,
            target.module_name AS target_module,
            'project'::text AS target_scope,
            true AS is_resolved,
            fd.is_direct_import,
            'file_dependencies'::text AS provenance,
            jsonb_build_object('file_dependency_id', fd.id) AS metadata
        FROM file_dependencies fd
        JOIN files source ON source.id = fd.source_file_id
        JOIN files target ON target.id = fd.target_file_id
        UNION ALL
        SELECT
            lir.project_id,
            lir.source_file_id,
            source.module_name AS source_module,
            NULL::integer AS target_file_id,
            lir.import_name AS target_module,
            lir.target_scope::text,
            lir.is_resolved,
            true AS is_direct_import,
            lir.provenance,
            lir.metadata
        FROM lean_import_references lir
        JOIN files source ON source.id = lir.source_file_id
    """))

    op.execute(text("""
        CREATE VIEW v_unresolved_obligations AS
        SELECT
            po.*,
            f.relative_path,
            f.module_name AS file_module_name,
            s.full_name AS symbol_full_name
        FROM proof_obligations po
        LEFT JOIN files f ON f.id = po.file_id
        LEFT JOIN symbols s ON s.id = po.symbol_id
        WHERE po.status IN ('open', 'acknowledged')
    """))

    op.execute(text("""
        CREATE VIEW v_cohesion_ranking AS
        SELECT
            f.project_id,
            f.id AS file_id,
            f.relative_path,
            f.module_name,
            COUNT(DISTINCT fd_out.target_file_id) AS outbound_local_edges,
            COUNT(DISTINCT fd_in.source_file_id) AS inbound_local_edges,
            COUNT(DISTINCT lir.id) AS external_import_refs,
            COUNT(DISTINCT wcm.id) AS wolfram_map_count,
            COUNT(DISTINCT po.id) FILTER (WHERE po.status IN ('open', 'acknowledged')) AS unresolved_obligation_count,
            f.sorry_count,
            f.proof_completion,
            (
                COUNT(DISTINCT fd_in.source_file_id) * 2
                + COUNT(DISTINCT fd_out.target_file_id)
                + COUNT(DISTINCT lir.id)
                + COUNT(DISTINCT wcm.id)
                + COUNT(DISTINCT po.id) FILTER (WHERE po.status IN ('open', 'acknowledged')) * 4
                + COALESCE(f.sorry_count, 0) * 3
                + (1.0 - COALESCE(f.proof_completion, 1.0)) * 10
            )::double precision AS cohesion_score
        FROM files f
        LEFT JOIN file_dependencies fd_out ON fd_out.source_file_id = f.id
        LEFT JOIN file_dependencies fd_in ON fd_in.target_file_id = f.id
        LEFT JOIN lean_import_references lir ON lir.source_file_id = f.id
        LEFT JOIN wolfram_companion_maps wcm ON wcm.file_id = f.id OR (wcm.file_id IS NULL AND wcm.module_name = f.module_name AND wcm.project_id = f.project_id)
        LEFT JOIN proof_obligations po ON po.file_id = f.id
        GROUP BY f.project_id, f.id, f.relative_path, f.module_name, f.sorry_count, f.proof_completion
    """))

    op.execute(text("""
        CREATE VIEW v_module_json_lookup AS
        SELECT
            f.project_id,
            f.id AS file_id,
            f.module_name,
            f.relative_path,
            jsonb_build_object(
                'file_id', f.id,
                'module_name', f.module_name,
                'relative_path', f.relative_path,
                'file_hash', f.file_hash,
                'imports', f.imports,
                'metrics', jsonb_build_object(
                    'line_count', f.line_count,
                    'theorem_count', f.theorem_count,
                    'sorry_count', f.sorry_count,
                    'proof_completion', f.proof_completion,
                    'mathlib_import_count', f.mathlib_import_count
                ),
                'outbound_edges', COALESCE(outbound.edges, '[]'::jsonb),
                'inbound_edges', COALESCE(inbound.edges, '[]'::jsonb),
                'external_refs', COALESCE(external_refs.refs, '[]'::jsonb),
                'wolfram_maps', COALESCE(wolfram_maps.maps, '[]'::jsonb),
                'unresolved_obligations', COALESCE(obligations.items, '[]'::jsonb)
            ) AS module_json
        FROM files f
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'target_file_id', target.id,
                    'target_module', target.module_name,
                    'target_path', target.relative_path,
                    'is_direct_import', fd.is_direct_import
                ) ORDER BY target.module_name
            ) AS edges
            FROM file_dependencies fd
            JOIN files target ON target.id = fd.target_file_id
            WHERE fd.source_file_id = f.id
        ) outbound ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'source_file_id', source.id,
                    'source_module', source.module_name,
                    'source_path', source.relative_path,
                    'is_direct_import', fd.is_direct_import
                ) ORDER BY source.module_name
            ) AS edges
            FROM file_dependencies fd
            JOIN files source ON source.id = fd.source_file_id
            WHERE fd.target_file_id = f.id
        ) inbound ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'import_name', lir.import_name,
                    'target_scope', lir.target_scope,
                    'package_name', lir.package_name,
                    'resolved_path', lir.resolved_path,
                    'is_resolved', lir.is_resolved,
                    'metadata', lir.metadata
                ) ORDER BY lir.import_name
            ) AS refs
            FROM lean_import_references lir
            WHERE lir.source_file_id = f.id
        ) external_refs ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', wcm.id,
                    'wolfram_path', wcm.wolfram_path,
                    'file_hash', wcm.file_hash,
                    'parsed_map', wcm.parsed_map,
                    'llm_synthesis', wcm.llm_synthesis
                ) ORDER BY wcm.wolfram_path
            ) AS maps
            FROM wolfram_companion_maps wcm
            WHERE wcm.file_id = f.id OR (wcm.file_id IS NULL AND wcm.module_name = f.module_name AND wcm.project_id = f.project_id)
        ) wolfram_maps ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'id', po.id,
                    'obligation_type', po.obligation_type,
                    'severity', po.severity,
                    'status', po.status,
                    'line_start', po.line_start,
                    'line_end', po.line_end,
                    'title', po.title,
                    'ticket_id', po.ticket_id,
                    'evidence', po.evidence
                ) ORDER BY po.severity DESC, po.created_at DESC
            ) AS items
            FROM proof_obligations po
            WHERE po.file_id = f.id AND po.status IN ('open', 'acknowledged')
        ) obligations ON true
    """))


def downgrade() -> None:
    op.execute(text("DROP VIEW IF EXISTS v_module_json_lookup"))
    op.execute(text("DROP VIEW IF EXISTS v_cohesion_ranking"))
    op.execute(text("DROP VIEW IF EXISTS v_unresolved_obligations"))
    op.execute(text("DROP VIEW IF EXISTS v_module_import_edges"))

    op.drop_table("l2bl4_badges")
    op.drop_table("ots_stamps")
    op.drop_table("proof_obligations")
    op.drop_table("audit_tickets")
    op.drop_table("wolfram_companion_maps")
    op.drop_table("lean_import_references")