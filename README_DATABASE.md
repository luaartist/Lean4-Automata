# Alembic Database Setup for Lean4-Automata

This directory contains the complete Alembic migration setup for the Lean4-Automata project.

## Directory Structure

```
Lean4-Automata/
├── alembic.ini              # Alembic configuration
├── alembic/
│   ├── env.py               # Alembic environment (async-ready)
│   ├── script.py.mako       # Migration template
│   └── versions/            # Migration files
│       ├── 0001_initial_schema.py
│       ├── 0002_add_indexes.py
│       └── 0003_materialized_views.py
├── db/
│   └── queries.py           # Query functions with recursive CTEs
└── requirements/
    └── db.txt               # Database dependencies
```

## Prerequisites

1. PostgreSQL 18.4 running (via docker-compose)
2. Python 3.10+
3. DATABASE_URL environment variable set

## Installation

```bash
# Install dependencies
pip install -r requirements/db.txt

# Set environment variable (or add to .env file)
export DATABASE_URL="postgresql://lean4:lean4_dev_password@localhost:5432/lean4_automata"
```

## Running Migrations

### Apply All Migrations

```bash
# Run all pending migrations
alembic upgrade head

# Or step by step:
alembic upgrade +1  # Apply next migration
```

### Check Current Version

```bash
alembic current
```

### View Migration History

```bash
alembic history --verbose
```

### Rollback Migrations

```bash
# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade 0002

# Rollback all migrations
alembic downgrade base
```

## Migration Chain

1. **0001_initial_schema.py**
   - Creates enum types: `symbol_kind`, `dependency_type`
   - Creates tables: `projects`, `files`, `symbols`, `dependencies`, `file_dependencies`, `index_runs`
   - All tables include proper foreign keys with CASCADE deletes

2. **0002_add_indexes.py**
   - Creates B-tree indexes for common queries
   - Creates GIN indexes for JSONB columns (`imports`, `attributes`)
   - Creates full-text search GIN index on `symbols` table
   - All indexes created with `CONCURRENTLY` for zero-downtime

3. **0003_materialized_views.py**
   - `dependency_stats`: Per-symbol centrality metrics (outgoing/incoming edges)
   - `module_metrics`: Per-module aggregations (symbol counts by kind, documentation coverage)

## Schema Overview

### Core Tables

- **projects**: Root level project information
- **files**: Source files with imports and metadata
- **symbols**: Individual symbols (theorems, definitions, etc.)
- **dependencies**: Symbol-to-symbol dependencies
- **file_dependencies**: File-level import graph
- **index_runs**: Indexing job tracking

### Materialized Views

- **dependency_stats**: Symbol centrality and connection metrics
- **module_metrics**: Module-level complexity and documentation metrics

Refresh materialized views:
```sql
REFRESH MATERIALIZED VIEW dependency_stats;
REFRESH MATERIALIZED VIEW module_metrics;
```

## Using Query Functions

The `db/queries.py` module provides type-annotated asyncpg query functions:

```python
import asyncpg
from db.queries import (
    get_transitive_deps,
    get_reverse_deps,
    find_cycles,
    top_symbols_by_usage
)

# Create connection
conn = await asyncpg.connect(database_url)

# Get all dependencies of a symbol (up to depth 5)
deps = await get_transitive_deps(conn, 'Mathlib.Data.List.Basic.append', max_depth=5)

# Find symbols that depend on a given symbol
reverse_deps = await get_reverse_deps(conn, 'Mathlib.Data.List.Basic.length')

# Detect dependency cycles
cycles = await find_cycles(conn, project_id=1)

# Get most referenced symbols
top_symbols = await top_symbols_by_usage(conn, project_id=1, limit=10)

await conn.close()
```

## Database Connection

The system reads `DATABASE_URL` from environment variables. Format:

```bash
# For application code (asyncpg)
DATABASE_URL="postgresql+asyncpg://lean4:lean4_dev_password@localhost:5432/lean4_automata"

# Or standard PostgreSQL URL (will be converted automatically)
DATABASE_URL="postgresql://lean4:lean4_dev_password@localhost:5432/lean4_automata"
```

## Creating New Migrations

```bash
# Auto-generate migration (requires target_metadata in env.py)
alembic revision --autogenerate -m "description"

# Create empty migration
alembic revision -m "description"
```

## Troubleshooting

### Connection Issues

```bash
# Test PostgreSQL connection
psql "postgresql://lean4:lean4_dev_password@localhost:5432/lean4_automata" -c "SELECT version();"

# Check if database exists
docker compose ps postgres
docker compose logs postgres
```

### Migration Issues

```bash
# Check current migration status
alembic current

# View migration history
alembic history

# Stamp database to specific version (without running migrations)
alembic stamp head
```

### Index Creation Issues

If concurrent index creation fails, you can create indexes normally:
1. Remove `postgresql_concurrently=True` from the migration
2. Run migration during maintenance window

## Performance Considerations

1. **Indexes**: All indexes created with `CONCURRENTLY` for zero-downtime
2. **Materialized Views**: Refresh periodically for updated metrics
3. **Query Optimization**: Use prepared statements via asyncpg
4. **Connection Pooling**: Implement connection pooling for production

## Production Recommendations

1. Set up automated materialized view refresh (cron job or trigger)
2. Monitor index usage and table statistics
3. Implement connection pooling (asyncpg pool or pgbouncer)
4. Set up backup strategy for `alembic_version` table
5. Use read replicas for analytical queries
6. Configure autovacuum for optimal performance

## Example: Full Setup

```bash
# 1. Install dependencies
pip install -r requirements/db.txt

# 2. Start PostgreSQL
docker compose up -d postgres

# 3. Set environment variable
export DATABASE_URL="postgresql://lean4:lean4_dev_password@localhost:5432/lean4_automata"

# 4. Run migrations
alembic upgrade head

# 5. Verify
alembic current
psql $DATABASE_URL -c "\dt"  # List tables

# 6. Test queries
python db/queries.py
```

## License

Same as parent project (see LICENSE file in repository root).
