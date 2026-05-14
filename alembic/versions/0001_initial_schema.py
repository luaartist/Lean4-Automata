"""Initial schema with enum types and core tables

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create enum types and core tables."""
    
    # Create enum types
    op.execute(text("""
        CREATE TYPE symbol_kind AS ENUM (
            'theorem',
            'def',
            'axiom',
            'instance',
            'inductive',
            'structure',
            'class',
            'constant',
            'opaque',
            'abbrev'
        )
    """))
    
    op.execute(text("""
        CREATE TYPE dependency_type AS ENUM (
            'direct',
            'implicit',
            'import',
            'indirect'
        )
    """))
    
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('root_path', sa.Text(), nullable=False),
        sa.Column('lean_version', sa.String(50), nullable=True),
        sa.Column('lakefile_hash', sa.String(64), nullable=True),
        sa.Column('indexed_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_modified', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('metadata', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create files table
    op.create_table(
        'files',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('relative_path', sa.Text(), nullable=False),
        sa.Column('absolute_path', sa.Text(), nullable=False),
        sa.Column('module_name', sa.Text(), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('line_count', sa.Integer(), nullable=True),
        sa.Column('char_count', sa.Integer(), nullable=True),
        sa.Column('indexed_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_modified', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('imports', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('metadata', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('project_id', 'relative_path')
    )
    
    # Create symbols table
    op.create_table(
        'symbols',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('full_name', sa.Text(), nullable=False),
        sa.Column('kind', sa.Enum(
            'theorem', 'def', 'axiom', 'instance', 'inductive', 'structure',
            'class', 'constant', 'opaque', 'abbrev',
            name='symbol_kind'
        ), nullable=False),
        sa.Column('line_start', sa.Integer(), nullable=False),
        sa.Column('line_end', sa.Integer(), nullable=False),
        sa.Column('col_start', sa.Integer(), nullable=True),
        sa.Column('col_end', sa.Integer(), nullable=True),
        sa.Column('signature', sa.Text(), nullable=True),
        sa.Column('docstring', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('is_deprecated', sa.Boolean(), server_default=sa.text('false'), nullable=True),
        sa.Column('indexed_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('attributes', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('metadata', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('project_id', 'full_name')
    )
    
    # Create dependencies table
    op.create_table(
        'dependencies',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('source_symbol_id', sa.Integer(), nullable=False),
        sa.Column('target_symbol_id', sa.Integer(), nullable=False),
        sa.Column('dependency_type', sa.Enum(
            'direct', 'implicit', 'import', 'indirect',
            name='dependency_type'
        ), nullable=False),
        sa.Column('confidence', sa.Float(), server_default=sa.text('1.0'), nullable=True),
        sa.Column('indexed_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('provenance', sa.Text(), nullable=True),
        sa.Column('metadata', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_symbol_id'], ['symbols.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_symbol_id'], ['symbols.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('source_symbol_id', 'target_symbol_id', 'dependency_type')
    )
    
    # Create file_dependencies table
    op.create_table(
        'file_dependencies',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('source_file_id', sa.Integer(), nullable=False),
        sa.Column('target_file_id', sa.Integer(), nullable=False),
        sa.Column('is_direct_import', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('indexed_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_file_id'], ['files.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('source_file_id', 'target_file_id')
    )
    
    # Create index_runs table
    op.create_table(
        'index_runs',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('run_type', sa.String(50), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('files_processed', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('symbols_indexed', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.Column('errors', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
        sa.Column('status', sa.String(50), server_default=sa.text("'running'"), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE')
    )


def downgrade() -> None:
    """Drop all tables and enum types in reverse order."""
    
    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_table('index_runs')
    op.drop_table('file_dependencies')
    op.drop_table('dependencies')
    op.drop_table('symbols')
    op.drop_table('files')
    op.drop_table('projects')
    
    # Drop enum types
    op.execute(text('DROP TYPE IF EXISTS dependency_type'))
    op.execute(text('DROP TYPE IF EXISTS symbol_kind'))
