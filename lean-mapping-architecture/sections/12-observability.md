# Observability

## Three Pillars

| Pillar | Tool | Notes |
|--------|------|-------|
| **Metrics** | Prometheus + Grafana | Histogram per endpoint, cache hit ratio |
| **Logs** | Structured JSON → stdout | Collected by container runtime |
| **Traces** | OpenTelemetry → Jaeger | Distributed trace per request |

## Correlation IDs

Every inbound request receives (or propagates) a unique `X-Request-ID`
header. This ID is:

1. Attached to all log lines as `request_id`.
2. Propagated to downstream services via HTTP headers.
3. Stored in Celery task metadata for async job tracing.
4. Returned in every API response and error envelope.

```python
@app.middleware("http")
async def correlation_id_middleware(request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    ctx_request_id.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

## Key Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `api_request_duration_seconds` | Histogram | `method`, `endpoint`, `status` |
| `db_query_duration_seconds` | Histogram | `query_type` |
| `cache_operations_total` | Counter | `operation` (`hit`, `miss`, `set`, `delete`) |
| `index_run_duration_seconds` | Histogram | `run_type` |
| `index_staleness_seconds` | Gauge | `project` |
| `celery_queue_depth` | Gauge | `queue_name` |

## Alerting Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| `HighQueryLatency` | p95 > 500 ms for 5 min | Warning |
| `CacheHitRateLow` | < 70 % for 15 min | Warning |
| `IndexStale` | `index_staleness_seconds` > 172 800 (48 h) | Critical |
| `ErrorRateHigh` | 5xx rate > 1 % for 5 min | Critical |
| `QueueBacklog` | `celery_queue_depth` > 1 000 for 10 min | Warning |

## Structured Logging

```json
{
  "timestamp": "2025-07-13T10:30:00Z",
  "level": "info",
  "request_id": "req-abc123",
  "service": "query-api",
  "event": "symbol_lookup",
  "full_name": "List.append_assoc",
  "cache_hit": true,
  "duration_ms": 4
}
```

All services log to **stdout** in JSON. Container runtimes (Docker,
Kubernetes) collect and forward to the chosen log aggregator.

## Dashboards

A pre-built Grafana dashboard ships in `deploy/grafana/`:

- **Overview** – request rate, error rate, p50/p95 latency.
- **Cache** – hit/miss ratio, key count, memory usage.
- **Indexing** – job duration, files processed, error count.
- **Database** – active connections, query latency by type.
