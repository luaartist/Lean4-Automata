"""Add materialized views for aggregated metrics

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-01 12:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create materialized views for performance optimization."""
    
    # Dependency stats materialized view
    # Calculates centrality metrics: outgoing and incoming edge counts per symbol
    op.execute(text("""
        CREATE MATERIALIZED VIEW dependency_stats AS
        SELECT
            s.id AS symbol_id,
            s.full_name,
            s.name,
            s.kind,
            s.project_id,
            COALESCE(outgoing.count, 0) AS outgoing_dependencies,
            COALESCE(incoming.count, 0) AS incoming_dependencies,
            COALESCE(outgoing.count, 0) + COALESCE(incoming.count, 0) AS total_connections,
            CASE 
                WHEN COALESCE(incoming.count, 0) > 0 
                THEN COALESCE(outgoing.count, 0)::float / COALESCE(incoming.count, 0)::float
                ELSE NULL
            END AS fan_out_ratio
        FROM symbols s
        LEFT JOIN (
            SELECT source_symbol_id, COUNT(*) as count
            FROM dependencies
            GROUP BY source_symbol_id
        ) outgoing ON s.id = outgoing.source_symbol_id
        LEFT JOIN (
            SELECT target_symbol_id, COUNT(*) as count
            FROM dependencies
            GROUP BY target_symbol_id
        ) incoming ON s.id = incoming.target_symbol_id
    """))
    
    # Create index on materialized view for fast lookups
    op.execute(text("""
        CREATE INDEX idx_dependency_stats_symbol_id 
        ON dependency_stats (symbol_id)
    """))
    
    op.execute(text("""
        CREATE INDEX idx_dependency_stats_project_id 
        ON dependency_stats (project_id)
    """))
    
    op.execute(text("""
        CREATE INDEX idx_dependency_stats_incoming 
        ON dependency_stats (incoming_dependencies DESC)
    """))
    
    # Module metrics materialized view
    # Per-module aggregations: symbol counts by kind, average symbol length
    op.execute(text("""
        CREATE MATERIALIZED VIEW module_metrics AS
        SELECT
            f.id AS file_id,
            f.module_name,
            f.project_id,
            COUNT(s.id) AS total_symbols,
            COUNT(s.id) FILTER (WHERE s.kind = 'theorem') AS theorem_count,
            COUNT(s.id) FILTER (WHERE s.kind = 'def') AS def_count,
            COUNT(s.id) FILTER (WHERE s.kind = 'axiom') AS axiom_count,
            COUNT(s.id) FILTER (WHERE s.kind = 'instance') AS instance_count,
            COUNT(s.id) FILTER (WHERE s.kind = 'inductive') AS inductive_count,
            COUNT(s.id) FILTER (WHERE s.kind = 'structure') AS structure_count,
            COUNT(s.id) FILTER (WHERE s.kind = 'class') AS class_count,
            COUNT(s.id) FILTER (WHERE s.kind = 'constant') AS constant_count,
            COUNT(s.id) FILTER (WHERE s.kind = 'opaque') AS opaque_count,
            COUNT(s.id) FILTER (WHERE s.kind = 'abbrev') AS abbrev_count,
            AVG(s.line_end - s.line_start + 1) AS avg_symbol_length_lines,
            MAX(s.line_end - s.line_start + 1) AS max_symbol_length_lines,
            COUNT(s.id) FILTER (WHERE s.is_public = true) AS public_symbols,
            COUNT(s.id) FILTER (WHERE s.is_deprecated = true) AS deprecated_symbols,
            COUNT(s.id) FILTER (WHERE s.docstring IS NOT NULL) AS documented_symbols,
            CASE 
                WHEN COUNT(s.id) > 0 
                THEN (COUNT(s.id) FILTER (WHERE s.docstring IS NOT NULL)::float / COUNT(s.id)::float) * 100
                ELSE 0
            END AS documentation_coverage_pct
        FROM files f
        LEFT JOIN symbols s ON f.id = s.file_id
        GROUP BY f.id, f.module_name, f.project_id
    """))
    
    # Create indexes on module_metrics materialized view
    op.execute(text("""
        CREATE INDEX idx_module_metrics_file_id 
        ON module_metrics (file_id)
    """))
    
    op.execute(text("""
        CREATE INDEX idx_module_metrics_project_id 
        ON module_metrics (project_id)
    """))
    
    op.execute(text("""
        CREATE INDEX idx_module_metrics_total_symbols 
        ON module_metrics (total_symbols DESC)
    """))
    
    op.execute(text("""
        CREATE INDEX idx_module_metrics_module_name 
        ON module_metrics (module_name)
    """))


def downgrade() -> None:
    """Drop materialized views and their indexes."""
    
    # Drop module_metrics materialized view (indexes drop automatically)
    op.execute(text('DROP MATERIALIZED VIEW IF EXISTS module_metrics CASCADE'))
    
    # Drop dependency_stats materialized view (indexes drop automatically)
    op.execute(text('DROP MATERIALIZED VIEW IF EXISTS dependency_stats CASCADE'))
