# Backend Performance

## Connection Pooling

| Setting | Value | Rationale |
|---------|-------|-----------|
| `min_size` | 10 | Warm pool for steady-state load |
| `max_size` | 50 | Cap to prevent PG connection exhaustion |
| `max_queries` | 50 000 | Recycle long-lived connections |
| `max_inactive_connection_lifetime` | 300 s | Free idle resources |
| `command_timeout` | 30 s | Prevent runaway queries |

For production with > 50 concurrent API replicas, introduce **PgBouncer**
in transaction-pooling mode.

## Query Optimisation

### Recursive CTE for Transitive Dependencies

```sql
WITH RECURSIVE dep_tree AS (
    SELECT source_symbol_id, target_symbol_id, 1 AS depth
    FROM dependencies
    WHERE target_symbol_id = $1
  UNION
    SELECT d.source_symbol_id, d.target_symbol_id, dt.depth + 1
    FROM dependencies d
    JOIN dep_tree dt ON d.target_symbol_id = dt.source_symbol_id
    WHERE dt.depth < $2          -- depth param (max 10)
)
SELECT DISTINCT s.full_name, s.kind
FROM dep_tree dt
JOIN symbols s ON dt.source_symbol_id = s.id;
```

**Key indexes**: composite `(source_symbol_id, target_symbol_id)` B-tree;
partial index on `dependencies WHERE dependency_type = 'direct'`.

### Full-Text Search

GIN index on `to_tsvector('english', coalesce(docstring,'') || ' ' || name)`.
Query uses `plainto_tsquery` for natural language input,
`to_tsquery` for structured search with `&` / `|`.

## Caching Tiers

| Tier | Technology | TTL | Scope |
|------|-----------|-----|-------|
| L1 | Redis | 1 h (symbols), 15 min (search) | Cluster-wide |
| L2 | HTTP `Cache-Control` | 60 s + `stale-while-revalidate=300` | CDN / browser |
| L3 | React Query (client) | 5–10 min | Per browser tab |

## Batch Insert Strategy

Symbol and dependency rows are inserted using `asyncpg.executemany` in
batches of 500 rows. This reduces round-trips by ~100× compared to
row-at-a-time inserts.

## Performance Targets

| Operation | p95 target | Current bottleneck |
|-----------|------------|-------------------|
| Symbol lookup (cached) | 5 ms | Redis RTT |
| Symbol lookup (uncached) | 50 ms | PG query + serialisation |
| Transitive deps (depth 5) | 200 ms | Recursive CTE |
| Full-text search (10 K symbols) | 100 ms | GIN scan |
| Full scan (10 K files) | 5 min | I/O + parsing |
| Incremental update (1 file) | 2 s | Parse + transaction |

## Monitoring Hooks

Every DB query is wrapped in a Prometheus histogram:

```python
query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['query_type']   # symbol_lookup, search, dependency, ...
)
```

Slow-query alerts fire at p95 > 500 ms (see §12).
