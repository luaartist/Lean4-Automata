# Observability Engineer — Role Anchor

> 10 most likely questions an Observability Engineer will ask, answered with configuration details and commands.

---

## Q1. What observability stack is available and how do I enable it?

Lean4-Automata includes an optional observability profile in `docker-compose.yml`:

| Service | Port | Image | Purpose |
|---|---|---|---|
| **Loki** | `3100` | `grafana/loki:3.4.2` | Log aggregation |
| **Grafana** | `3001` | `grafana/grafana:11.6.0` | Dashboards, log exploration |
| **Flower** | `5555` | `mher/flower:2.0` | Celery task monitoring |

Enable the full observability profile:

```bash
docker compose --profile observability up -d
```

This starts Loki and Grafana alongside the core stack. Flower is always enabled (not behind the profile).

Access:
- **Grafana:** `http://localhost:3001` (login: `admin` / `admin`)
- **Loki:** `http://localhost:3100` (internal, queried by Grafana)
- **Flower:** `http://localhost:5555`

---

## Q2. How are container logs routed to Loki?

The `docker-compose.yml` configures the Docker Loki logging driver for all services:

```yaml
x-logging: &loki-logging
  driver: loki
  options:
    loki-url: "http://localhost:3100/loki/api/v1/push"
    loki-batch-size: "100"
    loki-retries: "2"
    loki-timeout: "2s"
    labels: "service"
```

Each service applies `<<: *loki-logging` under its `logging:` key. This means:

- All `stdout`/`stderr` from containers flows to Loki automatically.
- Each log entry is labeled with `service=<container_name>`.
- No sidecar agent or fluentd is required.

**Note:** The Docker Loki driver plugin must be installed on the host:

```bash
docker plugin install grafana/loki-docker-driver:2.9.2 --alias loki --grant-all-permissions
```

---

## Q3. How do I query logs in Grafana?

1. Open Grafana at `http://localhost:3001`.
2. Navigate to **Explore** → select **Loki** data source.
3. Use LogQL:

```logql
# All logs from the query API
{service="app"}

# Error-level logs from the worker
{service="worker"} |= "ERROR"

# Parse JSON logs and filter
{service="app"} | json | status_code >= 500

# Celery task failures
{service="worker"} |= "Task lean4.full_scan" |= "raised"

# Watcher activity
{service="watcher"} |= "processing"
```

---

## Q4. What health endpoints exist and how should I monitor them?

Both FastAPI services expose two health endpoints:

| Endpoint | Service | Checks | Healthy Response | Unhealthy |
|---|---|---|---|---|
| `GET /health/live` | Query (`:8000`), Ingestion (`:8001`) | Process alive | `200 {"status": "alive"}` | — (process down) |
| `GET /health/ready` | Query (`:8000`), Ingestion (`:8001`) | DB + Redis connectivity | `200 {"db": true, "redis": true}` | `503 {"db": false, "redis": false}` |

**File:** `app/query_api.py` and `app/ingestion_api.py`

```python
@app.get("/health/ready", status_code=200)
async def health_ready(request: Request):
    db_ok = await check_db(request.app.state.pool)
    redis_ok = await check_redis(request.app.state.redis)
    status_code = 200 if (db_ok and redis_ok) else 503
    return JSONResponse({"db": db_ok, "redis": redis_ok}, status_code=status_code)
```

Docker Compose uses these for dependency ordering:

```yaml
app:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health/live"]
    interval: 10s
    timeout: 5s
    retries: 3
```

**Recommended monitoring:**
- Poll `/health/ready` every 30s.
- Alert if `db: false` or `redis: false` persists for > 2 minutes.
- Track response latency of `/health/ready` as a proxy for DB connection pool pressure.

---

## Q5. How do I monitor Celery workers and tasks?

### Flower (`:5555`)

Flower provides a web UI and REST API:

- **Dashboard:** `http://localhost:5555` — active workers, queued tasks, success/failure rates
- **API:** `http://localhost:5555/api/workers` — JSON worker status
- **Task API:** `http://localhost:5555/api/tasks` — recent tasks with state

### Key Celery tasks to monitor:

| Task Name | Schedule | Purpose | SLO |
|---|---|---|---|
| `lean4.full_scan` | On-demand (POST) | Full project re-index | < 5 min for 10k files |
| `lean4.refresh_materialized_views` | Hourly (Celery beat) | Refresh `dependency_stats` + `module_metrics` | < 30s |

### Worker health via CLI:

```bash
# Active workers
docker compose exec worker celery -A workers.celery_app inspect active

# Registered tasks
docker compose exec worker celery -A workers.celery_app inspect registered

# Ping workers
docker compose exec worker celery -A workers.celery_app inspect ping
```

### Log-based monitoring:

```logql
# Task completions
{service="worker"} |= "Task lean4.full_scan" |= "succeeded"

# Task failures (alert on this)
{service="worker"} |= "raised" |= "Traceback"
```

---

## Q6. How does Redis caching work and how do I monitor cache hit rates?

**File:** `app/query/router.py`

Cache strategy: **cache-aside** with 1-hour TTL.

```
Key format:  lean4:cache:<sha256(request_params)>
TTL:         3600 seconds
Invalidation: Redis PUBLISH on lean4:invalidate channel
```

### Monitor with redis-cli:

```bash
docker compose exec redis redis-cli

# Key count
DBSIZE

# All cache keys
KEYS lean4:cache:*

# Memory usage for a key
MEMORY USAGE lean4:cache:<key>

# Overall stats (hits, misses, memory)
INFO stats
# Look for: keyspace_hits, keyspace_misses
# Hit rate = hits / (hits + misses)

# Monitor pub/sub activity
SUBSCRIBE lean4:invalidate
```

### Grafana dashboard (if using Redis exporter):

Key metrics to visualize:
- `redis_keyspace_hits_total` / `redis_keyspace_misses_total` → hit rate
- `redis_connected_clients` → connection pool health
- `redis_used_memory_bytes` → memory pressure

---

## Q7. What rate limits exist and how are they configured?

**File:** `nginx/nginx.conf`

```nginx
# Rate limit zone: 60 requests/minute per IP on search
limit_req_zone $binary_remote_addr zone=search_limit:10m rate=60r/m;

# SSE connection limit: 10 per IP
limit_conn_zone $binary_remote_addr zone=sse_zone:10m;
```

Applied to routes:

```nginx
location /api/v1/symbols/search {
    limit_req zone=search_limit burst=20 nodelay;
    proxy_pass http://app;
}

location /api/v1/events/ {
    limit_conn sse_zone 10;
    proxy_buffering off;
    proxy_read_timeout 3600s;
    proxy_pass http://app;
}
```

**Monitor rate limiting:**

```logql
{service="nginx"} |= "limiting requests"
```

Or from Nginx access logs:

```logql
{service="nginx"} | json | status = 429
```

---

## Q8. What metrics would I get from the materialized views?

Two materialized views are refreshed hourly by Celery beat:

### `dependency_stats`
Per-symbol dependency metrics:

```sql
SELECT
    s.full_name,
    ds.fan_in,              -- symbols depending on this
    ds.fan_out,             -- symbols this depends on
    ds.total_connections,
    ds.fan_out_ratio
FROM dependency_stats ds
JOIN symbols s ON s.id = ds.symbol_id
ORDER BY ds.fan_in DESC LIMIT 10;
```

### `module_metrics`
Per-module (file) aggregated stats:

```sql
SELECT
    module_name,
    total_symbols,
    theorem_count,
    def_count,
    documentation_coverage_pct,
    avg_symbol_length_lines,
    max_symbol_length_lines
FROM module_metrics
ORDER BY total_symbols DESC LIMIT 10;
```

**To expose as Prometheus metrics**, create a scrape endpoint that queries these views and formats the results.

---

## Q9. How do I set up alerting for critical failures?

### Priority 1 — Infrastructure

| Alert | Condition | Check Method |
|---|---|---|
| **DB down** | `/health/ready` returns `db: false` for 2+ min | HTTP probe |
| **Redis down** | `/health/ready` returns `redis: false` for 2+ min | HTTP probe |
| **Worker offline** | `celery inspect ping` fails | CLI or Flower API |

### Priority 2 — Application

| Alert | Condition | Check Method |
|---|---|---|
| **Full scan failure** | Task state = FAILURE | Flower API or Loki query |
| **MV refresh stale** | `module_metrics` not refreshed in 2+ hours | Query `index_runs` or Celery beat logs |
| **Rate-limit spike** | > 100 429s in 5 min | Loki query on nginx status |
| **SSE connection saturation** | > 80% of limit_conn cap | Nginx connection metrics |

### Grafana Alert Configuration

In Grafana, create alert rules using Loki as the data source:

```logql
# Alert: Celery task failure
count_over_time({service="worker"} |= "raised" |= "Traceback" [5m]) > 0
```

Set evaluation interval to 1 minute, pending period to 2 minutes.

---

## Q10. How do I add structured logging to the FastAPI services?

Currently the FastAPI services use Python's standard `logging` module. To add structured JSON logging:

**File to modify:** `app/core/config.py` or create `app/core/logging.py`

```python
import logging
import json
import sys

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "query-api",  # or "ingestion-api"
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        return json.dumps(log_entry)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)
```

This makes logs parseable by Loki's JSON pipeline:

```logql
{service="app"} | json | level = "ERROR"
{service="app"} | json | request_id = "abc-123"
```

The Request-ID middleware (`app/core/middleware.py`) already injects `X-Request-ID` into the request state — extend it to add `request_id` to the log context.
