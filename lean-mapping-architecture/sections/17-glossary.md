# Glossary

| Term | Definition |
|------|-----------|
| **ADR** | Architecture Decision Record – a short document capturing a significant design choice and its rationale. |
| **Cache-aside** | Caching pattern where the application checks the cache before the database and populates the cache on miss. |
| **Celery** | Distributed task queue for Python; used here for async indexing jobs. |
| **Circuit breaker** | Resilience pattern that stops calling a failing service after *N* consecutive errors, allowing recovery time. |
| **Correlation ID** | A unique identifier (`X-Request-ID`) propagated through all services for a single logical request. |
| **CTE** | Common Table Expression – a named temporary result set in SQL, used here with `WITH RECURSIVE` for transitive dependency queries. |
| **Dependency (direct)** | A symbol explicitly referenced in the body of another symbol's definition or proof. |
| **Dependency (implicit)** | A symbol resolved via typeclass inference, not explicitly named. |
| **Dependency (transitive)** | A symbol reachable through a chain of direct/implicit dependencies. |
| **FTS** | Full-Text Search – PostgreSQL's built-in text indexing via `tsvector` / `tsquery`. |
| **GIN index** | Generalised Inverted Index – PostgreSQL index type efficient for JSONB containment and FTS queries. |
| **Lean 4** | A functional programming language and interactive theorem prover. |
| **Materialised view** | A PostgreSQL view whose results are stored on disk and refreshed on demand. |
| **Mathlib** | The community mathematical library for Lean 4; contains ~100 K+ theorems. |
| **Module** | A Lean namespace corresponding to a `.lean` file (e.g., `Mathlib.Data.List.Basic`). |
| **React Flow** | React library for building interactive node-based graphs. |
| **React Query** | Data-fetching and caching library for React (TanStack Query). |
| **RSC** | React Server Components – components rendered on the server, reducing client JS. |
| **SSE** | Server-Sent Events – HTTP-based one-way streaming from server to client. |
| **Symbol** | A named Lean entity: theorem, definition, axiom, instance, structure, class, constant, opaque, or abbreviation. |
| **TTL** | Time-To-Live – duration before a cached entry expires. |
| **Wolfram** | *[Optional]* Wolfram Engine / Mathematica; used for mathematical verification, not on the critical path. |
| **Zustand** | Lightweight React state-management library using a hook-based API. |
