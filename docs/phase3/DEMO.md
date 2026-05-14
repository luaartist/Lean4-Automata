# Phase 3 Demo

Assume Query API base URL:

```bash
export BASE_URL="http://localhost:8000"
```

## 1) Symbol lookup

```bash
curl -s "$BASE_URL/api/v1/symbols/Mathlib.List.map" | jq
```

## 2) Symbol full-text search

```bash
curl -sG "$BASE_URL/api/v1/symbols/search" \
  --data-urlencode "q=monad" \
  --data-urlencode "project_id=1" \
  --data-urlencode "limit=20" \
  --data-urlencode "offset=0" | jq
```

## 3) Dependency graph

```bash
curl -sG "$BASE_URL/api/v1/dependencies/graph" \
  --data-urlencode "full_name=Mathlib.List.map" \
  --data-urlencode "max_depth=5" | jq
```

## 4) Module metrics

```bash
curl -sG "$BASE_URL/api/v1/modules/metrics" \
  --data-urlencode "project_id=1" \
  --data-urlencode "order_by=total_symbols" | jq
```

## 5) SSE invalidation stream

```bash
curl -N "$BASE_URL/api/v1/events/invalidation"
```

Expected:
- `event: invalidation` messages with watcher payloads
- heartbeat comments every ~15s when idle

---

## Frontend EventSource sample (React Query stale-key handling)

```ts
const es = new EventSource("/api/v1/events/invalidation");

es.addEventListener("invalidation", (evt) => {
  try {
    const payload = JSON.parse((evt as MessageEvent).data);
    const fileId = payload.file_id;
    const symbols = payload.symbols ?? [];

    // Example React Query invalidations
    queryClient.invalidateQueries({ queryKey: ["deps"] }); // lean4:cache:deps:* analog
    if (fileId != null) {
      queryClient.invalidateQueries({ queryKey: ["file", fileId] });
      queryClient.invalidateQueries({ queryKey: ["moduleMetrics"] });
    }
    for (const fullName of symbols) {
      queryClient.invalidateQueries({ queryKey: ["symbol", fullName] });
    }
  } catch (err) {
    console.warn("Bad SSE payload", err);
  }
});

es.onerror = () => {
  // Optional backoff/reconnect UI handling
  console.warn("SSE disconnected; browser will auto-reconnect.");
};
```
