# Backend Services

## Service Decomposition

| Service | Port | Responsibility | Data access |
|---------|------|---------------|-------------|
| **Query API** | 8000 | Read-only symbol/search/viz | PG read replica + Redis |
| **Ingestion API** | 8001 | Accept index requests, job status | PG + Celery queue |
| **Admin API** | 8002 (internal) | Cache control, migrations, health | PG + Redis + queue |
| **Full Scan Worker** | – | Complete project indexing | PG (write-heavy) |
| **File Watcher** | – | Incremental updates on FS events | PG + Redis |
| **Metrics Worker** | – | Refresh materialised views | PG |
| **Wolfram Service** | – | *[Optional]* Math enrichment | PG metadata JSONB |

## Query API

Stateless, horizontally scalable. Typical request lifecycle:

1. Parse + validate request (Pydantic v2).
2. Generate cache key → check Redis.
3. On miss: execute parameterised SQL, cache result.
4. Attach `metadata.freshness` block (§05).
5. Return JSON with `X-Request-ID`.

Connection pool: `asyncpg` with `min_size=10`, `max_size=50`,
`command_timeout=30 s`.

## Ingestion API

Accepts `POST /admin/index/start` with project path and mode
(`full_scan` | `incremental`). Immediately returns `202 Accepted` with a
`run_id` and `status_url`. Actual work is delegated to Celery.

## Full Scan Worker

Five-phase pipeline:

1. **Discover** – `rglob("*.lean")`.
2. **Import pass** – regex-based import extraction → `file_dependencies`.
3. **Symbol pass** – Lean LSP or regex parser → `symbols` (batch insert).
4. **Dependency pass** – extract edges → `dependencies` (batch insert).
5. **Finalise** – update `index_runs`, enqueue Mathlib enrichment.

All phases run inside a single PostgreSQL transaction per batch to ensure
atomicity.

## File Watcher

Long-running daemon using Python `watchdog`.

- **Debounce**: 500 ms timer per path to absorb rapid saves.
- **Hash gate**: SHA-256 comparison; skip if unchanged.
- **Transactional update**: delete old symbols → reparse → insert new →
  commit → invalidate cache.
- **Dependent notification**: enqueue re-validation jobs for files that
  import the changed module.

## Metrics Worker

Cron-scheduled (hourly):

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY dependency_stats;
REFRESH MATERIALIZED VIEW CONCURRENTLY module_metrics;
```

`CONCURRENTLY` avoids locking readers during refresh.

## Wolfram Service [Optional – Non-Core]

Receives a symbol signature, shells out to `wolframscript`, stores the
analysis result in `symbols.metadata` JSONB. Deployed in a separate
container with the Wolfram Engine. **No other service depends on it.**
