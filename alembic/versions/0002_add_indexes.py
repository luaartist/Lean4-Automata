"""Add indexes for optimal query performance

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-01 12:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all indexes with CONCURRENTLY where possible."""
    
    # Projects indexes
    op.create_index(
        'idx_projects_name',
        'projects',
        ['name'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_projects_last_modified',
        'projects',
        ['last_modified'],
        unique=False,
        postgresql_concurrently=True
    )
    
    # Files indexes
    op.create_index(
        'idx_files_project_id',
        'files',
        ['project_id'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_files_module_name',
        'files',
        ['module_name'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_files_last_modified',
        'files',
        ['last_modified'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_files_hash',
        'files',
        ['file_hash'],
        unique=False,
        postgresql_concurrently=True
    )
    
    # GIN index for JSONB imports column
    op.execute(text("""
        CREATE INDEX CONCURRENTLY idx_files_imports_gin 
        ON files USING gin (imports)
    """))
    
    # Symbols indexes
    op.create_index(
        'idx_symbols_file_id',
        'symbols',
        ['file_id'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_symbols_project_id',
        'symbols',
        ['project_id'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_symbols_name',
        'symbols',
        ['name'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_symbols_full_name',
        'symbols',
        ['full_name'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_symbols_kind',
        'symbols',
        ['kind'],
        unique=False,
        postgresql_concurrently=True
    )
    
    # GIN index for JSONB attributes column
    op.execute(text("""
        CREATE INDEX CONCURRENTLY idx_symbols_attributes_gin 
        ON symbols USING gin (attributes)
    """))
    
    # Full-text search GIN index
    op.execute(text("""
        CREATE INDEX CONCURRENTLY idx_symbols_fts 
        ON symbols 
        USING gin (to_tsvector('english', coalesce(docstring, '') || ' ' || coalesce(name, '')))
    """))
    
    # Dependencies indexes
    op.create_index(
        'idx_deps_source',
        'dependencies',
        ['source_symbol_id'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_deps_target',
        'dependencies',
        ['target_symbol_id'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_deps_type',
        'dependencies',
        ['dependency_type'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_deps_composite',
        'dependencies',
        ['source_symbol_id', 'target_symbol_id'],
        unique=False,
        postgresql_concurrently=True
    )
    
    # File dependencies indexes
    op.create_index(
        'idx_file_deps_source',
        'file_dependencies',
        ['source_file_id'],
        unique=False,
        postgresql_concurrently=True
    )
    op.create_index(
        'idx_file_deps_target',
        'file_dependencies',
        ['target_file_id'],
        unique=False,
        postgresql_concurrently=True
    )


def downgrade() -> None:
    """Drop all indexes in reverse order."""
    
    # File dependencies indexes
    op.drop_index('idx_file_deps_target', table_name='file_dependencies', postgresql_concurrently=True)
    op.drop_index('idx_file_deps_source', table_name='file_dependencies', postgresql_concurrently=True)
    
    # Dependencies indexes
    op.drop_index('idx_deps_composite', table_name='dependencies', postgresql_concurrently=True)
    op.drop_index('idx_deps_type', table_name='dependencies', postgresql_concurrently=True)
    op.drop_index('idx_deps_target', table_name='dependencies', postgresql_concurrently=True)
    op.drop_index('idx_deps_source', table_name='dependencies', postgresql_concurrently=True)
    
    # Symbols indexes
    op.execute(text('DROP INDEX CONCURRENTLY IF EXISTS idx_symbols_fts'))
    op.execute(text('DROP INDEX CONCURRENTLY IF EXISTS idx_symbols_attributes_gin'))
    op.drop_index('idx_symbols_kind', table_name='symbols', postgresql_concurrently=True)
    op.drop_index('idx_symbols_full_name', table_name='symbols', postgresql_concurrently=True)
    op.drop_index('idx_symbols_name', table_name='symbols', postgresql_concurrently=True)
    op.drop_index('idx_symbols_project_id', table_name='symbols', postgresql_concurrently=True)
    op.drop_index('idx_symbols_file_id', table_name='symbols', postgresql_concurrently=True)
    
    # Files indexes
    op.execute(text('DROP INDEX CONCURRENTLY IF EXISTS idx_files_imports_gin'))
    op.drop_index('idx_files_hash', table_name='files', postgresql_concurrently=True)
    op.drop_index('idx_files_last_modified', table_name='files', postgresql_concurrently=True)
    op.drop_index('idx_files_module_name', table_name='files', postgresql_concurrently=True)
    op.drop_index('idx_files_project_id', table_name='files', postgresql_concurrently=True)
    
    # Projects indexes
    op.drop_index('idx_projects_last_modified', table_name='projects', postgresql_concurrently=True)
    op.drop_index('idx_projects_name', table_name='projects', postgresql_concurrently=True)
