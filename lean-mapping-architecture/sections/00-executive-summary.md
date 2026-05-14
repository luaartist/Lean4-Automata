# Executive Summary

## Purpose

The Lean Mapping Architecture provides a production-grade system for indexing,
querying, and visualising dependency relationships across Lean 4 codebases
(including Mathlib). It integrates with Serena as a specialised data layer,
enabling symbol resolution, transitive dependency analysis, and interactive
graph exploration.

## Business Goals

| Goal | Metric |
|------|--------|
| Index a 10 K-file Lean project | < 5 min full scan |
| Symbol lookup latency (p95) | < 50 ms |
| Incremental file update | < 2 s end-to-end |
| Transitive dependency query (depth 5) | < 200 ms |
| System availability | 99.9 % monthly |

## Key Architectural Decisions

1. **PostgreSQL 16+ as primary store** – JSONB + recursive CTEs + FTS cover
   all query patterns without a secondary graph DB.
2. **Redis 7+ as ephemeral cache** – sub-millisecond hot-path lookups; the
   system degrades gracefully if Redis is unavailable.
3. **FastAPI service tier** – three stateless API services (Query, Ingestion,
   Admin) behind a load balancer, scaling horizontally.
4. **Next.js 15 frontend** – server components for data-heavy renders,
   React Flow for graph visualisation.
5. **Wolfram integration is optional** – enrichment-only; no critical path
   depends on a Wolfram Engine installation.

## Constraints

- All data at rest lives in PostgreSQL; Redis is never the source of truth.
- Cache invalidation follows a *conservative delete* strategy – on any file
  change the affected file cache, symbol caches, and dependent query caches
  are removed.
- Authentication is required only for Admin/Ingestion endpoints; read-only
  Query endpoints use rate limiting.

## Phased Rollout

| Phase | Weeks | Deliverable |
|-------|-------|-------------|
| 1 – Foundation | 1–3 | Schema, full-scan ingestion |
| 2 – Incremental | 4–5 | File watcher, Redis caching |
| 3 – API layer | 6–8 | Query/Search/Viz endpoints |
| 4 – Frontend | 9–10 | Three-layer exploration UI |
| 5 – Hardening | 11–12 | Observability, runbooks, load tests |
| 6 – Optional | Post-MVP | Neo4j export, Wolfram enrichment |
