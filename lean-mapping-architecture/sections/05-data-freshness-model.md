# Data Freshness Model

## Design Principle

Every API response includes **freshness metadata** so consumers can make
informed decisions about data currency.

```json
"metadata": {
  "indexed_at": "2025-07-13T08:00:00Z",
  "cache_hit": true,
  "freshness": {
    "max_age_s": 3600,
    "age_s": 842,
    "source": "redis"
  }
}
```

## Cache-Control Strategy

| Resource | TTL | Invalidation trigger |
|----------|-----|---------------------|
| Symbol metadata | 1 h | File hash change (watcher) |
| Dependency subgraph | 1 h | Source or target symbol change |
| Search results | 15 min | Any symbol mutation |
| Module import graph | 1 h | File dependency change |
| Materialised views | 1 h (refresh) | Cron (`REFRESH … CONCURRENTLY`) |
| Chart analytics | 1 h | Materialised view refresh |

### HTTP Cache Headers

Query API responses include:
```
Cache-Control: public, max-age=60, stale-while-revalidate=300
ETag: "sha256:<hash>"
```

Clients may use `If-None-Match` for conditional requests; the API returns
`304 Not Modified` when the ETag matches.

## SSE Invalidation Channel

An optional Server-Sent Events endpoint allows frontends to receive
real-time invalidation signals:

```http
GET /api/v1/events/invalidation
Accept: text/event-stream
```

```
event: symbol_updated
data: {"module":"Mathlib.Data.List.Basic","symbols":["append_assoc"]}

event: index_complete
data: {"run_id":42,"files_processed":1234}
```

The frontend React Query cache listens to this stream and calls
`queryClient.invalidateQueries({ queryKey: ['symbol', name] })` on
receipt.

## Staleness Alerting

| Condition | Action |
|-----------|--------|
| `indexed_at` older than 24 h | Warning badge in UI |
| `indexed_at` older than 48 h | Prometheus alert `index_stale` |
| Redis unavailable | Fallback to DB; log `cache_miss_fallback` metric |

## Consistency Guarantees

- **Within a transaction** the database is strongly consistent (serialisable
  isolation for index writes).
- **Cache reads** are eventually consistent; worst-case staleness equals the
  TTL of the cached entry.
- **SSE invalidation** reduces effective staleness to sub-second for
  connected clients.
