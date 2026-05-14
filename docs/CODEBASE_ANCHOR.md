# Lean4-Automata — Codebase Anchor

> **Authoritative reference for all builder roles.**
> Last generated from commit `10927ba` on branch `main`.

---

## System Overview

Lean4-Automata is a full-stack code-intelligence platform that parses, indexes, and analyzes Lean 4 proof-assistant source files. It extracts symbols (theorems, definitions, instances, etc.), tracks inter-symbol dependencies, computes static-analysis metrics (sorry count, proof completion, floating symbols), and serves the results through a query API, a cache-invalidating SSE stream, and a Go-powered forum harness with a single-page HTML UI. The stack runs entirely in Docker Compose with PostgreSQL for persistence, Redis for caching/pub-sub, Celery for background task processing, Nginx as a reverse proxy, and optional Grafana+Loki for observability.

---

## Architecture Diagram

```
                         ┌────────────────────────────────────┐
                         │         Nginx  :8080 (HTTP)        │
                         │  reverse proxy / rate-limit / SSE  │
                         └──────┬──────────────┬──────────────┘
                                │              │
                   ┌────────────▼──┐    ┌──────▼──────────────┐
                   │  Query API    │    │  Ingestion API      │
                   │  :8000        │    │  :8001              │
                   │  FastAPI      │    │  FastAPI (admin)    │
                   │  GET /api/v1/*│    │  POST /admin/index/*│
                   └──┬─────┬─────┘    └──────┬──────────────┘
                      │     │                  │
            ┌─────────▼─┐ ┌─▼──────────┐  ┌───▼──────────────┐
            │ PostgreSQL │ │   Redis    │  │  Celery Worker   │
            │ :5432      │ │   :6379   │  │  (full_scan,     │
            │ lean4_     │ │  cache +  │  │   refresh_views) │
            │ automata   │ │  pub/sub  │  └──────────────────┘
            └────────────┘ └───────────┘
                                │
         ┌──────────────────────┤
         │                      │
   ┌─────▼─────────┐    ┌──────▼─────────────────┐
   │  Watcher       │    │  Flower  :5555          │
   │  (inotify)     │    │  Celery task monitor    │
   │  parser.watcher│    └────────────────────────┘
   └───────────────┘
                                 ┌─────────────────────────┐
   ┌───────────────────┐         │  Next.js Frontend :3000 │
   │ Go_Red Forum      │         │  (optional dashboard)   │
   │ :8443  (ext.)     │         └─────────────────────────┘
   │ SQLite tickets    │
   │ SSE flow exec     │    ┌──────────────────────────────┐
   │ lean4a_forum.html │    │  Grafana :3001 + Loki :3100  │
   └───────────────────┘    │  (profile: observability)    │
                            └──────────────────────────────┘
```

### Data Flows

1. **Ingestion (batch):** Admin → POST `/admin/index/start` → Celery `full_scan_task` → `FullScanner` walks `.lean` files → `parse_file()` → upsert into `files` + `symbols` + `dependencies` → Redis PUBLISH `lean4:invalidate`.
2. **Ingestion (incremental):** Watcher daemon detects `.lean` change via watchdog → debounce 500 ms → SHA-256 hash gate → `parse_file()` → single-transaction upsert → Redis PUBLISH.
3. **Query:** Client → GET `/api/v1/symbols/search` → Nginx → Query API → Redis cache check → PostgreSQL full-text query → cache result → JSON response.
4. **SSE Invalidation:** Client → GET `/api/v1/events/invalidation` → long-lived SSE stream → Redis SUBSCRIBE `lean4:invalidate` → push `event: invalidation` on file changes.
5. **Forum:** User → `lean4a_forum.html` → POST `/run/flow/:name` → Go_Red looks up `flowRegistry[name]` → execute compiled Go function → SSE stream log/result/done → store ticket in SQLite.

---

## Service Directory

| Service | Container | Port (host) | Image / Dockerfile | Purpose | Health Endpoint |
|---|---|---|---|---|---|
| **postgres** | `postgres` | `5432` | `postgres:17` | Primary data store — files, symbols, deps | `pg_isready` |
| **redis** | `redis` | `6379` | `redis:7` | Cache-aside, Celery broker, SSE pub/sub | `redis-cli ping` |
| **nginx** | `nginx` | `8080` | `nginx:stable` | Reverse proxy, rate-limiting, SSE buffering off | `nginx -t` |
| **app** (Query API) | `app` | `8000` | `Dockerfile.api` | Public symbol query, search, deps, SSE | `GET /health/ready` |
| **app_ingestion** | `app_ingestion` | `8001` | `Dockerfile.ingestion` | Admin-only indexing (JWT-protected) | `GET /health/ready` |
| **worker** | `worker` | — | `Dockerfile.worker` | Celery worker — `full_scan`, `refresh_views` | — |
| **watcher** | `watcher` | — | `Dockerfile.worker` | inotify daemon — incremental re-index | — |
| **flower** | `flower` | `5555` | `mher/flower:2.0` | Celery task monitoring UI | — |
| **web** | `web` | `3000` | `frontend/Dockerfile` | Next.js 16 dashboard | `wget localhost:3000/` |
| **loki** | `loki` | `3100` | `grafana/loki:3.4.2` | Log aggregation (profile: observability) | `wget localhost:3100/ready` |
| **grafana** | `grafana` | `3001` | `grafana/grafana:11.6.0` | Dashboards & log viewer (profile: observability) | `wget localhost:3000/api/health` |
| **Go_Red** (external) | — | `8443` | `go build` | Forum harness — flow execution, tickets, SSE | — |

---

## Data Model

### PostgreSQL Tables (Alembic-managed)

#### `projects`
| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | Auto-increment |
| `name` | `varchar(255) UNIQUE` | Human label |
| `root_path` | `text` | Filesystem root |
| `lean_version` | `varchar(50)` | e.g. `4.8.0` |
| `lakefile_hash` | `varchar(64)` | SHA-256 of lakefile |
| `indexed_at` | `timestamptz` | Last full index |
| `metadata` | `jsonb` | Extensible |

#### `files`
| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `project_id` | `int FK → projects` | CASCADE delete |
| `relative_path` | `text` | Unique with project_id |
| `absolute_path` | `text` | |
| `module_name` | `text` | Dot-separated |
| `file_hash` | `varchar(64)` | SHA-256 for hash gate |
| `line_count` | `int` | |
| `imports` | `jsonb` | Array of import strings |
| `sorry_count` | `int` | Raw `sorry` occurrences |
| `admit_count` | `int` | Raw `admit` occurrences |
| `sorry_lines` | `jsonb` | 1-based line numbers |
| `sorry_in_proof_count` | `int` | Theorems with sorry |
| `theorem_count` | `int` | Theorems + lemmas |
| `proof_completion` | `float` | `(theorems - sorry_proofs) / theorems` |
| `native_decide_count` | `int` | Fragility signal |
| `debug_command_count` | `int` | `#check`, `#eval`, etc. |
| `noncomputable_count` | `int` | |
| `instance_count` | `int` | |
| `declared_axiom_count` | `int` | |
| `simp_attr_count` | `int` | `@[simp]` tagged |
| `docstring_count` | `int` | `/-- ... -/` |
| `todo_count` | `int` | `-- TODO` comments |
| `mathlib_import_count` | `int` | `import Mathlib.*` |

#### `symbols`
| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `file_id` | `int FK → files` | CASCADE |
| `project_id` | `int FK → projects` | CASCADE |
| `name` | `text` | Short name |
| `full_name` | `text` | Fully-qualified (unique per project) |
| `kind` | `symbol_kind enum` | theorem, def, axiom, instance, inductive, structure, class, constant, opaque, abbrev |
| `line_start` / `line_end` | `int` | Source location |
| `signature` | `text` | Declaration head |
| `docstring` | `text` | Extracted docstring |
| `is_public` | `bool` | Default `true` |
| `is_deprecated` | `bool` | Default `false` |
| `has_sorry` | `bool` | sorry/admit in body |
| `attributes` | `jsonb` | e.g. `["simp"]` |

#### `dependencies`
| Column | Type | Notes |
|---|---|---|
| `id` | `serial PK` | |
| `source_symbol_id` | `int FK → symbols` | Who depends |
| `target_symbol_id` | `int FK → symbols` | Depended upon |
| `dependency_type` | `dependency_type enum` | direct, implicit, import, indirect |
| `confidence` | `float` | Default 1.0 |

#### `file_dependencies`
| Column | Type | Notes |
|---|---|---|
| `source_file_id` | `int FK → files` | |
| `target_file_id` | `int FK → files` | |
| `is_direct_import` | `bool` | |

#### `index_runs`
Audit log of batch indexing operations.

### Materialized Views (migration 0003)

| View | Refreshed | Purpose |
|---|---|---|
| `dependency_stats` | Hourly (Celery beat) | Per-symbol fan-in/fan-out, total connections, fan-out ratio |
| `module_metrics` | Hourly (Celery beat) | Per-module symbol counts by kind, avg/max symbol length, documentation coverage |

### SQL Views (migration 0004)

| View | Purpose |
|---|---|
| `v_proof_status` | Per-file proof completeness: `theorem_count`, `sorry_in_proof_count`, `proof_completion`, status label (`complete`, `partial`, `mostly_incomplete`, `no_theorems`) |
| `v_floating_symbols` | Public theorems/defs with zero incoming cross-file dependencies — "proved but never used" |
| `v_file_interconnect` | File-level fan-in/fan-out, Mathlib vs local imports, health metrics |

### SQLite (Go Forum — `~/.lean4a/forum.db`)

| Table | Key Columns |
|---|---|
| `tickets` | `id` (tk_ULID), `flow_name`, `input_json`, `output_json`, `status` (success/error/timeout), `duration_ms`, `tags` (JSON array) |
| `sessions` | `id` (sess_ULID), `name`, `ticket_ids_json` |
| `flow_definitions` | `name` PK, `description`, `params_schema` (JSON), `enabled`, `tags` |
| `flow_logs` | Circular buffer (max 1000 rows), `level`, `message`, `timestamp` |

---

## API Reference

### Query API (`:8000`)

| Method | Path | Auth | Params | Response |
|---|---|---|---|---|
| `GET` | `/health/live` | None | — | `{"status": "alive"}` |
| `GET` | `/health/ready` | None | — | `{"db": bool, "redis": bool}` (503 if either false) |
| `GET` | `/api/v1/symbols/search` | None | `q` (str), `project_id` (int), `limit` (1–100), `offset` (≥0) | `SymbolSearchResponse` with paginated results and `total` |
| `GET` | `/api/v1/symbols/{full_name}` | None | path param: fully-qualified name | `SymbolLookupResponse` — id, kind, signature, docstring, lines |
| `GET` | `/api/v1/dependencies/graph` | None | `full_name` (str), `max_depth` (1–20) | `DependencyGraphResponse` — transitive + reverse arrays |
| `GET` | `/api/v1/modules/metrics` | None | `project_id` (int), `order_by` (total_symbols\|theorem_count\|def_count\|avg_symbol_length_lines\|documentation_coverage_pct) | `ModuleMetricsResponse` |
| `GET` | `/api/v1/events/invalidation` | None | — | SSE stream: `event: invalidation`, heartbeats every 15s |

### Ingestion API (`:8001`)

| Method | Path | Auth | Body / Params | Response |
|---|---|---|---|---|
| `GET` | `/health/live` | None | — | `{"status": "alive"}` |
| `GET` | `/health/ready` | None | — | `{"db": bool, "redis": bool}` |
| `POST` | `/admin/index/start` | JWT (admin) | `{"project_id": "1", "root_dir": "/path"}` | `202 {"task_id": "...", "status": "queued"}` |
| `GET` | `/admin/index/status/{task_id}` | JWT (admin) | path param | `{"task_id": "...", "state": "...", "result": {...}, "error": "..."}` |

### Go Forum API (`:8443`)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/flows` | List all enabled flow definitions |
| `POST` | `/run/flow/{name}` | Execute a named flow; returns SSE stream (log → result → done) |
| `GET` | `/tickets` | List stored tickets |
| `GET` | `/tickets/{id}` | Get single ticket detail |

---

## Git History (recent 5 commits)

| SHA (short) | Summary |
|---|---|
| `10927ba` | **refactor:** Eliminate CommandTemplate code-exec surface — compile-time FlowFunc registry |
| `4a3c84a` | **security:** Audit pass — fix XSS, proxy DoS, JWT leakage, SSE method mismatch |
| `855b7b9` | **feat:** Forum-style UI + Go_Red CLI harness |
| `c40a94a` | **feat:** Full stack — ingestion service, parser enrichment, static-analysis metrics |
| `07fc8b3` | **feat:** Add optional Grafana Loki log aggregation |

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `APP_PORT` | `8000` | Query API host port |
| `INGESTION_PORT` | `8001` | Ingestion API host port |
| `NGINX_HTTP_PORT` | `8080` | Nginx proxy host port |
| `POSTGRES_PORT` | `5432` | PostgreSQL host port |
| `POSTGRES_DB` | `lean4_automata` | Database name |
| `POSTGRES_USER` | `lean4` | Database user |
| `POSTGRES_PASSWORD` | `lean4_dev_password` | Database password |
| `REDIS_PORT` | `6379` | Redis host port |
| `REDIS_URL` | `redis://localhost:6379` | Full Redis DSN |
| `DATABASE_URL` | *(see .env.example)* | asyncpg DSN for FastAPI |
| `JWT_SECRET_KEY` | `CHANGE_ME_...` | HMAC secret for admin JWT |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ENV` | `development` | Set `production` to disable `/docs` |
| `LEAN_WATCH_ROOT` | `./lean-src` | Directory the watcher monitors |
| `LEAN_PROJECT_ID` | `1` | Project ID for watcher upserts |
| `CELERY_BROKER_URL` | `${REDIS_URL}` | Celery broker |
| `CELERY_RESULT_BACKEND` | `${REDIS_URL}` | Celery result backend |
| `FLOWER_PORT` | `5555` | Flower UI port |
| `FRONTEND_PORT` | `3000` | Next.js host port |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS allowed origins (comma-separated) |
| `LEAN4A_FORUM_DB` | `~/.lean4a/forum.db` | SQLite path for Go forum |
| `LEAN_DB_URL` | `http://localhost:8000` | Go forum → Python query API |
| `TPH_SERVER_URL` | `http://localhost:5000` | Go forum → TPH GPU server |
| `FLOW_TIMEOUT_SEC` | `30` | Per-flow execution timeout |
| `MAX_CONCURRENT_FLOWS` | `5` | Semaphore cap on parallel flows |
| `GRAFANA_PORT` | `3001` | Grafana host port |
| `GRAFANA_ADMIN_USER` | `admin` | Grafana login |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Grafana password |
| `LOKI_PORT` | `3100` | Loki host port |

---

## Stack Commands

```bash
# ── Bring the core stack up ──────────────────────────────────────────────────
docker compose up -d

# ── Include observability (Grafana + Loki) ───────────────────────────────────
docker compose --profile observability up -d

# ── Tail logs ────────────────────────────────────────────────────────────────
docker compose logs -f app worker watcher

# ── Stop everything ──────────────────────────────────────────────────────────
docker compose down

# ── Stop + delete volumes (DESTRUCTIVE) ──────────────────────────────────────
docker compose down -v

# ── Run Alembic migrations ───────────────────────────────────────────────────
# From inside the app or worker container, or locally with DATABASE_URL set:
alembic upgrade head

# ── Trigger a full re-scan via API ───────────────────────────────────────────
curl -X POST http://localhost:8001/admin/index/start \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "1", "root_dir": "/lean-src"}'

# ── Check scan status ────────────────────────────────────────────────────────
curl http://localhost:8001/admin/index/status/<task_id> \
  -H "Authorization: Bearer $ADMIN_JWT"

# ── Refresh materialized views manually ──────────────────────────────────────
docker compose exec worker celery -A workers.celery_app call lean4.refresh_materialized_views

# ── Start the Go forum harness (outside Docker) ─────────────────────────────
cd go && go run forum.go
```

---

## Key File Locations

| Path | Description |
|---|---|
| `app/query_api.py` | Query API app factory |
| `app/ingestion_api.py` | Ingestion API app factory |
| `app/query/router.py` | `/api/v1/*` endpoints — search, lookup, deps, metrics, SSE |
| `app/ingestion/router.py` | `/admin/index/*` endpoints — start, status |
| `app/core/config.py` | `Settings` (pydantic-settings) |
| `app/core/security.py` | JWT decode, `require_admin` dependency |
| `app/core/lifespan.py` | asyncpg pool + Redis client startup/shutdown |
| `app/core/middleware.py` | Request-ID middleware with log-injection protection |
| `parser/lean_parser.py` | `ParsedSymbol`, `FileMetrics`, `parse_text()`, `parse_file()` |
| `parser/scanner.py` | `FullScanner` — batch walk + upsert |
| `parser/watcher.py` | `LeanFileHandler` — debounced inotify re-index |
| `workers/celery_app.py` | Celery app factory + beat schedule |
| `workers/tasks.py` | `full_scan_task`, `refresh_views_task` |
| `db/queries.py` | Recursive CTE queries — `get_transitive_deps`, `get_reverse_deps`, `get_module_complexity` |
| `alembic/versions/0001_initial_schema.py` | projects, files, symbols, dependencies, file_dependencies, index_runs |
| `alembic/versions/0002_add_indexes.py` | B-tree + GIN + FTS indexes |
| `alembic/versions/0003_materialized_views.py` | `dependency_stats`, `module_metrics` |
| `alembic/versions/0004_enriched_metrics.py` | Enriched file columns + `v_proof_status`, `v_floating_symbols`, `v_file_interconnect` |
| `go/forum.go` | Go forum harness — FlowFunc registry, HTTP handlers, SSE, SQLite |
| `go/forum_schema.sql` | SQLite DDL for tickets, sessions, flow_definitions, flow_logs |
| `ui/lean4a_forum.html` | Single-page forum UI (Bootstrap 5, SSE, JSON highlighting) |
| `ui/flow_definitions.json` | 12 named flow definitions with schemas and tags |
| `nginx/nginx.conf` | Reverse proxy config — rate limits, SSE passthrough, admin rewrite |
| `docker-compose.yml` | All services, volumes, healthchecks |
| `.env.example` | Documented environment template |
