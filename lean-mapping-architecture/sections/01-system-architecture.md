# System Architecture

## Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     Load Balancer (Nginx / Traefik)              │
│                   SSL termination · rate limiting                │
└──────────┬──────────────────────────────────────┬────────────────┘
           │                                       │
  ┌────────▼────────┐                    ┌────────▼────────┐
  │  Query API       │                    │  Ingestion API  │
  │  :8000 (R/O)     │                    │  :8001 (R/W)    │
  │  N replicas       │                    │  N replicas     │
  └────────┬────────┘                    └────────┬────────┘
           │                                       │
      ┌────▼────┐                            ┌─────▼──────┐
      │  Redis   │◄── invalidation ──────────│ Task Queue │
      │  Cache   │                            │  (Celery)  │
      └────┬────┘                            └─────┬──────┘
           │                                       │
  ┌────────▼───────────────────────────────────────▼───────┐
  │                   PostgreSQL 16+                        │
  │           Primary (writes) · Replicas (reads)          │
  └────────────────────────────────────────────────────────┘
                              │
       ┌──────────────────────┼──────────────────────┐
       │                      │                      │
  ┌────▼─────────┐   ┌───────▼───────┐   ┌─────────▼────────┐
  │ Full Scan    │   │ File Watcher  │   │ Metrics Worker   │
  │ Workers      │   │ (daemon)      │   │ (cron)           │
  └──────────────┘   └───────────────┘   └──────────────────┘
```

## Service Boundaries

| Service | Responsibility | Scaling model |
|---------|---------------|---------------|
| **Query API** | Read-only symbol lookup, search, graph export | Stateless, horizontal |
| **Ingestion API** | Accept index/reindex requests, job status | Stateless, horizontal |
| **Admin API** (:8002, internal) | Cache control, migrations, health | Single instance |
| **Full Scan Worker** | Complete project indexing | Pool via Celery |
| **File Watcher** | Detect `.lean` changes, incremental update | One per project dir |
| **Metrics Worker** | Refresh materialised views | Cron-scheduled |
| **Wolfram Service** | *[Optional]* Mathematical enrichment | Separate container |

## Data Flow: Read Path

1. Client → Load Balancer → Query API
2. Query API checks **Redis** (L1 cache).
3. On miss: Query API executes **PostgreSQL** query, caches result in Redis
   (`SETEX`, TTL 1 h), returns response.
4. Response includes `metadata.cache_hit` and `metadata.indexed_at` for
   freshness transparency.

## Data Flow: Write Path (Incremental)

1. File system event → File Watcher detects `.lean` modification.
2. Watcher debounces (500 ms), computes SHA-256 hash.
3. If hash differs from `files.file_hash`:
   - `BEGIN` transaction
   - Delete old symbols/dependencies for that `file_id`
   - Re-parse file, batch-insert new symbols and edges
   - `COMMIT`
4. Invalidate Redis keys: `file:{id}:*`, `symbol:{module}:*`, `deps:*`.
5. Optionally enqueue dependent-file re-validation.

## Data Flow: Write Path (Full Scan)

1. Admin/Ingestion API enqueues a Celery `full_scan` task.
2. Worker discovers all `.lean` files, creates `projects` + `files` rows.
3. Two-pass parsing: fast import extraction, then deep symbol extraction.
4. Dependency edges inserted in batch.
5. `index_runs` row updated with completion stats.
6. Post-scan: Mathlib enrichment job enqueued; materialised views refreshed.

## External Integrations

| Integration | Protocol | Direction | Notes |
|-------------|----------|-----------|-------|
| Lean 4 LSP / regex parser | Local process | Inbound | Symbol extraction |
| Mathlib docs API | HTTPS | Outbound | External reference enrichment |
| Wolfram Engine | CLI (`wolframscript`) | Outbound | *Optional*, non-core |
| Prometheus | HTTP scrape | Outbound | Metrics export |
