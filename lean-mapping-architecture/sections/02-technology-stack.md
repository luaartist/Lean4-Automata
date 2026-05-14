# Technology Stack

## Core Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Primary DB | PostgreSQL | 16+ | JSONB, recursive CTEs, FTS, ACID |
| Cache | Redis | 7+ | Sub-ms lookups, TTL, pattern-based deletion |
| API framework | FastAPI | 0.110+ | Async, auto-OpenAPI, Pydantic v2 |
| ASGI server | Uvicorn | 0.29+ | High-perf async Python server |
| Task queue | Celery + Redis broker | 5.3+ | Mature distributed task processing |
| File watcher | Python `watchdog` | 4+ | Cross-platform FS event monitoring |
| Frontend | Next.js 15 (App Router) | 15+ | RSC, streaming, SSR |
| UI framework | React 19 | 19+ | Server/client component split |
| Graph viz | React Flow | 11+ | 1 000+ node perf, custom nodes |
| Charts | Recharts | 2.12+ | Composable, Tailwind-friendly |
| State mgmt | Zustand | 4+ | Minimal boilerplate, slices |
| Styling | Tailwind CSS | 3.4+ | Utility-first, dark mode |
| Load balancer | Nginx *or* Traefik | – | SSL termination, rate limiting |
| Containers | Docker / Compose | – | Reproducible dev + prod |

## Decision: PostgreSQL Over Alternatives

| Alternative | Reason rejected |
|-------------|----------------|
| MongoDB | No foreign keys; dependency integrity requires application enforcement |
| Neo4j only | Weak FTS, limited aggregation, licensing complexity |
| SQLite | Concurrent-write limitations; no network access |

PostgreSQL handles dependency-graph queries via `WITH RECURSIVE` while
providing superior structured-data management, JSONB flexibility, and
mature operational tooling.

## Decision: Redis as Ephemeral Cache Only

Redis is **never** the source of truth.  On total cache loss the system
degrades to database queries; no data is lost.  Cache-aside pattern with
conservative invalidation ensures consistency.

## Optional Components

| Component | When to adopt |
|-----------|--------------|
| Neo4j Community | If visual graph exploration becomes a priority |
| Wolfram Engine | For mathematical verification / LaTeX proof rendering |
| Grafana + Loki | When log aggregation exceeds stdout-based collection |

## Python & Node Versions

- Python ≥ 3.11 (for `asyncio` task groups, `tomllib`)
- Node.js ≥ 20 LTS (for Next.js 15 App Router)
