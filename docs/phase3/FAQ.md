# Phase 3 FAQ

## What cache strategy is used?
- Phase 3 uses **cache-aside** (read-through/write-through behavior at endpoint level).
- Query API first tries Redis, falls back to PostgreSQL on miss/error, then writes back with TTL.
- TTL is fixed at **3600 seconds (1 hour)** via Redis `SETEX` semantics (`set(..., ex=3600)`).
- This aligns with ADR-style goals in ADR-002/ADR-003: low-latency reads with safe degradation.

## Which keys are used?
- File-scoped payloads: `lean4:cache:file:{id}:*`
- Dependency graph payloads: `lean4:cache:deps:*`
- Symbol name lookup shortcut key: `lean4:cache:symbol:{full_name}` (plus file-scoped key copy)

## How does invalidation work?
- `parser/watcher.py` deletes cache patterns when file re-indexing/deletion occurs.
- It now invalidates:
  - `lean4:cache:file:{id}:*`
  - `lean4:cache:deps:*`
- Backward-compatible invalidation patterns are preserved (legacy rel-path/symbol patterns).
- Watcher publishes a Redis message on channel `lean4:invalidate`.

## How do clients consume invalidations?
- Subscribe to `GET /api/v1/events/invalidation` (SSE).
- Stream emits:
  - `event: invalidation` with JSON payload from watcher
  - heartbeat comments every ~15s while idle

## What happens when Redis fails?
- Query endpoints do **not** fail due to cache read/write errors.
- Cache exceptions are logged as warnings; API still serves DB-backed responses.
- SSE endpoint requires Redis pub/sub; if Redis is unavailable it returns `503`.

## What are expected failure modes?
- DB unavailable: query endpoints return `503`.
- Symbol/project not found: `404`.
- Bad params: FastAPI validation `422`.
- Redis cache unavailable: degraded performance, but successful query responses.
- Redis unavailable for SSE: explicit `503` with clear message.
