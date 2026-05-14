# Operational Runbook

## Routine Operations

### Trigger Full Reindex

```bash
curl -X POST https://internal/api/v1/admin/index/start \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"project_path":"/data/mathlib4","mode":"full_scan"}'
# Returns: {"run_id": 42, "status_url": "/api/v1/admin/index/status/42"}
```

Monitor progress:
```bash
watch -n5 'curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://internal/api/v1/admin/index/status/42 | jq .progress'
```

### Refresh Materialised Views Manually

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY dependency_stats;
REFRESH MATERIALIZED VIEW CONCURRENTLY module_metrics;
```

### Invalidate All Caches

```bash
redis-cli -h $REDIS_HOST FLUSHDB
```

Or via Admin API:
```bash
curl -X POST https://internal/api/v1/admin/cache/flush \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Incident Playbooks

### 1. High Query Latency (p95 > 500 ms)

1. Check Grafana "Database" dashboard for slow queries.
2. Run `pg_stat_activity` to find long-running queries.
3. If a single query dominates: `SELECT pg_cancel_backend(pid)`.
4. Check `asyncpg` pool utilisation; consider scaling replicas.
5. Verify Redis is healthy (`redis-cli PING`).

### 2. Index Staleness Alert (> 48 h)

1. Check `index_runs` for last completed run:
   ```sql
   SELECT * FROM index_runs ORDER BY started_at DESC LIMIT 5;
   ```
2. If status = `failed`: inspect `errors` JSONB column.
3. If status = `running` for > 1 h: likely stuck. Kill worker, re-trigger.
4. Verify file watcher is running: `systemctl status lean-map-watcher`.

### 3. Redis Unavailable

1. System auto-degrades to DB-only (higher latency, no data loss).
2. Check Redis logs / pod status.
3. Once Redis recovers, caches self-warm on read; no manual action needed.
4. Verify cache hit rate recovers in Grafana within 15 min.

### 4. Database Connection Exhaustion

1. Check `SELECT count(*) FROM pg_stat_activity;`.
2. Identify idle-in-transaction connections:
   ```sql
   SELECT pid, state, query FROM pg_stat_activity
   WHERE state = 'idle in transaction' AND query_start < now() - interval '5 min';
   ```
3. Terminate with `SELECT pg_terminate_backend(pid)`.
4. Consider deploying PgBouncer if recurring.

## Backup & Restore

### Backup

```bash
pg_dump -Fc -h $PG_HOST -U lean lean_map > lean_map_$(date +%Y%m%d).dump
```

Automated daily via cron or Kubernetes CronJob.

### Restore

```bash
pg_restore -h $PG_HOST -U lean -d lean_map --clean lean_map_20250713.dump
```

### Point-in-Time Recovery

Requires WAL archiving enabled. Restore to a specific timestamp:

```bash
recovery_target_time = '2025-07-13 10:00:00 UTC'
```

## Health Checks

| Endpoint | Expected | Frequency |
|----------|----------|-----------|
| `GET /health` | `{"status":"healthy"}` | Every 10 s (K8s probe) |
| `redis-cli PING` | `PONG` | Every 30 s |
| `pg_isready` | exit 0 | Every 30 s |
