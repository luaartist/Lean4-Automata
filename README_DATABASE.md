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
│       ├── 0003_materialized_views.py
│       ├── 0004_enriched_metrics.py
│       ├── 0005_mapping_audit_context.py
│       └── 0006_l2bl4_evidence_contract.py
├── db/
│   └── queries.py           # Query functions with recursive CTEs
└── requirements/
    └── db.txt               # Database dependencies
```

## Prerequisites

1. PostgreSQL 17 running (via docker-compose)
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

4. **0004_enriched_metrics.py**
   - Adds proof-completeness, fragility, symbol-breakdown, hygiene, and import-profile columns to `files`
   - Adds `symbols.has_sorry`
   - Adds views: `v_proof_status`, `v_floating_symbols`, `v_file_interconnect`

5. **0005_mapping_audit_context.py**
   - Adds external Lean import references, Wolfram companion maps, audit tickets, proof obligations, OTS stamps, and L2BL4 badge tables
   - Adds views: `v_module_import_edges`, `v_module_json_lookup`, `v_cohesion_ranking`, `v_unresolved_obligations`

6. **0006_l2bl4_evidence_contract.py**
   - Adds L2BL4 contract fields: `ots_stamps.bitcoin_block`, `l2bl4_badges.badge_class`, `ots_stamp_id`, `composite_sig_hash`, and `contract_version`
   - Adds views/functions: `v_l2bl4_ticket_evidence_contract`, `v_l2bl4_badge_validity`, `l2bl4_ticket_evidence_snapshot`, and `l2bl4_badge_contract_error`
   - Adds an issuance trigger that validates `issued` badges while allowing draft badges and pending OTS stamps

## Schema Overview

### Core Tables

- **projects**: Root level project information
- **files**: Source files with imports and metadata
- **symbols**: Individual symbols (theorems, definitions, etc.)
- **dependencies**: Symbol-to-symbol dependencies
- **file_dependencies**: File-level import graph
- **index_runs**: Indexing job tracking

### Mapping and Audit Tables

- **lean_import_references**: Mathlib, lake package, external repo, and unknown Lean imports that do not resolve to project-local `files`
- **wolfram_companion_maps**: Parsed `../wolfram_lean_maps/*.wl` companion data keyed by Lean module
- **audit_tickets**: Postgres home for ULID-shaped flow tickets (`tk_<ulid>`) currently produced by audit/forum flows
- **proof_obligations**: Materialized unresolved obligations from sorries, admits, axioms, doc drift, import drift, and companion-map gaps
- **ots_stamps**: Future OpenTimestamps attestations over modules, tickets, maps, or badge evidence; `bitcoin_block` is nullable so stamps can be pending before later confirmation
- **l2bl4_badges**: Badge issuance records linked to evidence, tickets, optional OTS stamps, and one `badge_class` in `public`, `sovereign`, or `keepsake`

### L2BL4 Evidence Contract

The generic badge contract is project-agnostic and does not encode Yang-Mills, Millennium, or any current proof-flow name. Existing audit flows can still produce project-specific evidence inside `audit_tickets.output_json` and `l2bl4_badges.evidence`.

`v_l2bl4_ticket_evidence_contract` exposes the per-ticket readiness check:

- all badge classes require `audit_tickets.status = 'success'`
- `public` additionally requires at least one `ots_stamps` row for the ticket, `ots_stamps.bitcoin_block IS NOT NULL`, and matching reported/row-oriented sorry obligation counts
- `sovereign` has the same requirements as `public` plus `l2bl4_badges.composite_sig_hash IS NOT NULL`
- `keepsake` requires only the successful audit ticket; the issuance trigger adds a `keepsake_unverified` marker to the stored evidence

For the current schema, the sorry check is represented as `reported_sorry_gated_count` from `audit_tickets.output_json` compared to summed sorry-like `proof_obligations` rows linked by `ticket_id`. If no `sorry_gated` or `sorry_count` key is present, the count must be zero. Endpoint code should call `l2bl4_badge_contract_error(ticket_id, badge_class, composite_sig_hash)` before insert and can embed `l2bl4_ticket_evidence_snapshot(ticket_id)` in badge evidence.

Optional Wolfram LLM synthesis enrichment is intentionally manual and out of
band from the FastAPI audit routes. After `wolfram_companion_maps` has been
backfilled, run:

```bash
python tools/wolfram_llm_synthesis.py --project-id 1 --limit 5
```

The tool writes structured results to `wolfram_companion_maps.llm_synthesis`.
If `wolframscript` is missing, it prints a JSON `wolfram_unavailable` summary
and exits without opening a database connection. Use `--dry-run` to list rows,
`--module <module_name>` to target one map, and `--force` to reprocess populated
rows.

### Materialized Views

- **dependency_stats**: Symbol centrality and connection metrics
- **module_metrics**: Module-level complexity and documentation metrics
- **v_module_import_edges**: Union of project-local `file_dependencies` and external `lean_import_references`
- **v_module_json_lookup**: One JSONB object per module for module detail endpoints and charts
- **v_cohesion_ranking**: Module fan-in/fan-out, proof-health, Wolfram-map, and obligation ranking surface
- **v_unresolved_obligations**: Open/acknowledged proof and mapping obligations
- **v_l2bl4_ticket_evidence_contract**: Per-ticket L2BL4 audit, OTS, and obligation-count readiness
- **v_l2bl4_badge_validity**: Per-badge current validity and contract status after issuance

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
