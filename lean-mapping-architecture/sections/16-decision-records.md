# Architecture Decision Records

## ADR-001: PostgreSQL as Primary Store

- **Status**: Accepted
- **Context**: The system needs to store symbol metadata, dependency edges,
  and file import graphs with strong referential integrity.
- **Decision**: Use PostgreSQL 16+ as the sole primary store. JSONB covers
  flexible metadata; recursive CTEs handle graph traversal; GIN indexes
  power full-text search.
- **Alternatives rejected**:
  - *MongoDB*: No FK enforcement; dependency integrity requires app-level checks.
  - *Neo4j only*: Weak FTS/aggregation; licensing concerns.
  - *SQLite*: Concurrent-write limitations.
- **Consequences**: Single operational database to manage. Graph queries
  limited to recursive CTEs (acceptable for depth ≤ 10).

## ADR-002: Redis as Ephemeral Cache

- **Status**: Accepted
- **Context**: Symbol lookups must be < 50 ms at p95.
- **Decision**: Redis 7+ as a cache-aside layer with TTL-based expiry.
  Redis is **never** the source of truth.
- **Consequences**: On Redis failure the system degrades gracefully to
  DB-only latency (~50 ms). Conservative cache invalidation prevents
  stale reads at the cost of occasional extra DB hits.

## ADR-003: Conservative Cache Invalidation

- **Status**: Accepted
- **Context**: Stale dependency data is worse than a cache miss.
- **Decision**: On any file change, delete the file's cache entry **and**
  all symbol/dependency caches for that module, plus the global `deps:*`
  pattern.
- **Consequences**: Cache hit rate may be lower than optimal (~70–80 %);
  acceptable given correctness priority.

## ADR-004: SSE for Real-Time Invalidation

- **Status**: Accepted
- **Context**: Frontends using React Query need to know when cached data
  is stale without polling.
- **Decision**: Expose `/api/v1/events/invalidation` as a Server-Sent
  Events stream. The frontend invalidates matching React Query keys on
  receipt.
- **Consequences**: Adds a long-lived connection per client. Graceful
  fallback: if SSE disconnects, React Query's `staleTime` still governs
  refetches.

## ADR-005: JWT Auth for Admin Endpoints Only

- **Status**: Accepted
- **Context**: Read-only query endpoints are public; write/admin endpoints
  need access control.
- **Decision**: HS256 JWT tokens for Admin/Ingestion APIs. Query endpoints
  use IP-based rate limiting only.
- **Consequences**: Simple to implement; no user-management overhead. If
  per-user query quotas are needed later, add API-key auth as an additive
  change.

## ADR-006: Correlation IDs Across Services

- **Status**: Accepted
- **Context**: Debugging distributed request flows requires end-to-end
  traceability.
- **Decision**: Generate or propagate `X-Request-ID` on every request.
  Include in all log lines, Celery task metadata, and API responses.
- **Consequences**: Enables grep-based log correlation without a full
  tracing backend. When OpenTelemetry is adopted, the correlation ID
  maps to the trace's root span.

## ADR-007: Circuit Breaker for External Services

- **Status**: Accepted
- **Context**: Mathlib docs API and Wolfram Engine are external; transient
  failures should not cascade.
- **Decision**: Lightweight circuit breaker (5 failures → 30 s open →
  half-open probe).
- **Consequences**: Enrichment may be delayed during outages; core
  symbol/dependency data is unaffected.

## ADR-008: Wolfram Integration as Optional

- **Status**: Accepted
- **Context**: Wolfram Engine adds mathematical enrichment but requires a
  commercial licence and heavyweight runtime.
- **Decision**: Keep Wolfram as a separately deployed, optional service.
  No core API, worker, or frontend feature depends on it.
- **Consequences**: System is fully functional without Wolfram. Enrichment
  results stored in `symbols.metadata` JSONB for consumers that want them.
