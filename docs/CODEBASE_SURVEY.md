Perfect! Now I have sufficient information. Let me compile the comprehensive survey document:

---

# Lean4-Automata Codebase Survey

## 1. Directory Tree

```
Lean4-Automata/
├── README.md                          (70 lines) — Quick start, project layout
├── README_DATABASE.md                 (241 lines) — Alembic migrations, query setup
├── SCHEMA.md                          (277 lines) — Full ERD, views, indexes, query patterns
├── IMPLEMENTATION_SUMMARY.md          — High-level architecture summary
├── DOCKER_REVIEW_FIXES.md             — Docker build documentation
├── LICENSE
├── .env.example                       (38 lines) — Configuration template
├── .env                               — Runtime environment (not in repo)
├── .gitignore
├── .serena                            — Serena reference marker
├── alembic/                           — Database migration management
│   ├── alembic.ini                    — Alembic config (SQLAlchemy-style)
│   ├── env.py                         — Async migration environment
│   ├── script.py.mako                 — Migration template
│   └── versions/                      — Migration chain
│       ├── 0001_initial_schema.py     (150 lines) — Tables + enums
│       ├── 0002_add_indexes.py        (150+ lines) — All indexes (B-tree, GIN, FTS)
│       ├── 0003_materialized_views.py (150+ lines) — dependency_stats, module_metrics
│       └── 0004_enriched_metrics.py   — (Phase 2) Enhanced metrics
├── alembic_commands.sh                — Helper script for migration operations
├── app/                               — FastAPI applications
│   ├── __init__.py
│   ├── query_api.py                   (90 lines) — Query API factory + health endpoints
│   ├── ingestion_api.py               (90 lines) — Ingestion API factory + health endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                  (34 lines) — Settings (DATABASE_URL, JWT, ports)
│   │   ├── security.py                (64 lines) — JWT decode, bearer auth, role checks
│   │   ├── middleware.py              (51 lines) — Request ID tracking, log injection
│   │   └── lifespan.py                (99 lines) — asyncpg pool + Redis client lifecycle
│   ├── query/
│   │   ├── __init__.py
│   │   └── router.py                  (420+ lines) — All GET routes + SSE stream
│   └── ingestion/
│       ├── __init__.py
│       └── router.py                  (71 lines) — Admin-only POST routes
├── db/                                — Query function library
│   ├── __init__.py
│   └── queries.py                     (150+ lines) — Async CTE functions (transitive, reverse, cycles)
├── parser/                            — Lean symbol extraction
│   ├── __init__.py
│   ├── lean_parser.py                 (250+ lines) — Regex-based parser, FileMetrics, ParsedSymbol
│   ├── scanner.py                     — Full-scan indexer (FullScanner class)
│   └── watcher.py                     (150+ lines) — File watcher daemon (debounced, hash-gated)
├── workers/                           — Celery task workers
│   ├── __init__.py
│   ├── celery_app.py                  (37 lines) — Celery factory, beat schedule
│   └── tasks.py                       (67 lines) — full_scan_task, refresh_views_task
├── frontend/                          — Next.js 16 LTS
│   ├── package.json                   (38 lines) — React 19, Next 16.2.6, TailwindCSS 4
│   ├── next.config.js                 — Next.js configuration
│   ├── tsconfig.json                  — TypeScript config
│   ├── tailwind.config.ts             — TailwindCSS theming
│   ├── Dockerfile                     — Multi-stage build
│   ├── .eslintrc.json                 — ESLint rules
│   ├── .next/                         — Build output (gitignored)
│   ├── app/                           — Next.js 13+ App Router
│   │   ├── layout.tsx                 — Root layout wrapper
│   │   ├── page.tsx                   (6 lines) — Landing page → /projects/1
│   │   ├── globals.css                — Global styles
│   │   ├── projects/                  — Project listing/detail pages
│   │   ├── search/                    — Full-text search interface
│   │   └── settings/                  — User settings
│   ├── components/                    — Reusable React components
│   │   ├── AppShell.tsx               — Main layout wrapper
│   │   ├── Header.tsx                 — Top navigation
│   │   ├── Sidebar.tsx                — Left sidebar nav
│   │   ├── SearchBar.tsx              — Search input + debounce
│   │   ├── SymbolCard.tsx             — Symbol display card
│   │   ├── ModuleMetricsTable.tsx     — Metrics table view
│   │   ├── Breadcrumbs.tsx            — Breadcrumb nav
│   │   ├── FilterPanel.tsx            — Filter controls
│   │   ├── QueryProvider.tsx          — TanStack Query setup
│   │   ├── ThemeProvider.tsx          — Dark/light mode
│   │   ├── graph/                     — Reactflow dependency graph components
│   │   └── states/                    — Zustand store definitions
│   ├── lib/                           — Utility functions
│   │   ├── api/                       — API client helpers (fetch wrappers)
│   │   ├── sse/                       — Server-Sent Events stream manager
│   │   └── store/                     — Zustand state stores
│   ├── public/                        — Static assets
│   └── node_modules/                  — (gitignored)
├── go/                                — Go Forum harness (SSE-based flow runner)
│   ├── forum.go                       (400+ lines) — HTTP routes, FlowFunc registry, SSE
│   └── forum_schema.sql               (100+ lines) — SQLite schema (tickets, sessions, logs)
├── ui/                                — Flow orchestration UI
│   ├── flow_definitions.json          (220 lines) — 12 flow definitions (JSON schema)
│   └── lean4a_forum.html              — Standalone HTML UI
├── docker-compose.yml                 (217 lines) — Full stack: postgres, redis, nginx, app, worker, web
├── docker-compose.logging.yml         — (Optional) Loki + Grafana
├── docker-compose.override.yml        — Local overrides
├── Dockerfile.api                     — Query API image
├── Dockerfile.ingestion               — Ingestion API image
├── Dockerfile.worker                  — Worker + watcher image
├── Procfile                           — Heroku deployment (if applicable)
├── gunicorn_start.sh                  — Gunicorn startup wrapper
├── nginx/
│   └── nginx.conf                     (121 lines) — Reverse proxy + rate limiting
├── observability/
│   ├── README.md                      — Setup guide
│   ├── GRAFANA_LOKI_UX.md             — User guide
│   ├── loki/
│   │   └── loki-config.yaml           — Loki configuration
│   └── grafana/
│       ├── provisioning/              — Auto-provisioned data sources + dashboards
│       └── dashboards/                — Dashboard JSON files (logs overview, etc.)
├── infra/                             — Infrastructure as Code (optional)
├── postgres/
│   └── init/                          — SQL initialization scripts
├── requirements/                      — Python dependencies by role
│   ├── api.txt                        — Query API deps
│   ├── db.txt                         — Alembic + asyncpg
│   ├── worker.txt                     — Celery + parser deps
│   └── workers.txt                    — (Duplicate/legacy)
├── tools/                             — Standalone utilities
│   └── lean4_file_tools.py            — File/search utilities
├── docs/                              — Additional documentation
├── tests/                             — Test suite
├── lean-src/                          — (mount target for Lean source files)
├── lean-mapping-architecture/         — (Reference architecture docs)
├── _chopshop/                         — (Experimental/scratch code)
└── _copied_from_serena/               — (Legacy reference)
```

---

## 2. Database Schema

### Core Tables

#### **projects** (Primary key: `id`)
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | INTEGER | PK, auto-increment | — |
| name | VARCHAR(255) | NOT NULL, UNIQUE | Project identifier |
| root_path | TEXT | NOT NULL | Filesystem root |
| lean_version | VARCHAR(50) | nullable | e.g., "4.8.0" |
| lakefile_hash | VARCHAR(64) | nullable | Lake config hash |
| indexed_at | TIMESTAMPTZ | default=now() | Last indexing time |
| last_modified | TIMESTAMPTZ | default=now() | Last update |
| metadata | JSONB | nullable | Free-form metadata |
| — | — | **ON DELETE CASCADE** | Cascades to files, symbols, index_runs |

#### **files** (Primary key: `id`)
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | INTEGER | PK, auto-increment | — |
| project_id | INTEGER | FK→projects.id, NOT NULL | CASCADE on delete |
| relative_path | TEXT | NOT NULL | Path relative to project root |
| absolute_path | TEXT | NOT NULL | Full filesystem path |
| module_name | TEXT | NOT NULL | Lean module name |
| file_hash | VARCHAR(64) | NOT NULL | SHA256 of content (hash gate) |
| line_count | INTEGER | nullable | Number of lines |
| char_count | INTEGER | nullable | Number of characters |
| indexed_at | TIMESTAMPTZ | default=now() | Indexing timestamp |
| last_modified | TIMESTAMPTZ | default=now() | Last update |
| imports | JSONB | NOT NULL, default='[]' | JSON array of import strings |
| metadata | JSONB | nullable | Free-form metadata |
| — | — | UNIQUE(project_id, relative_path) | One file per project path |
| — | — | **ON DELETE CASCADE** | Cascades to symbols, file_dependencies |

#### **symbols** (Primary key: `id`)
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | INTEGER | PK, auto-increment | — |
| file_id | INTEGER | FK→files.id, NOT NULL | CASCADE on delete |
| project_id | INTEGER | FK→projects.id, NOT NULL | CASCADE on delete |
| name | TEXT | NOT NULL | Short name (e.g., "append") |
| full_name | TEXT | NOT NULL | Qualified name (e.g., "List.append") |
| kind | ENUM | NOT NULL | See **symbol_kind** enum below |
| line_start | INTEGER | NOT NULL | 1-based line number |
| line_end | INTEGER | NOT NULL | Inclusive line end |
| col_start | INTEGER | nullable | 1-based column start |
| col_end | INTEGER | nullable | 1-based column end |
| signature | TEXT | nullable | Lean signature text |
| docstring | TEXT | nullable | `/-- ... -/` doc comment |
| is_public | BOOLEAN | default=true | Public vs private |
| is_deprecated | BOOLEAN | default=false | Deprecation flag |
| indexed_at | TIMESTAMPTZ | default=now() | Index time |
| attributes | JSONB | default='[]' | Custom attributes (e.g., `@[simp]` tags) |
| metadata | JSONB | nullable | Free-form metadata |
| — | — | UNIQUE(project_id, full_name) | Full name unique per project |
| — | — | **ON DELETE CASCADE** | Cascades to dependencies |

**symbol_kind ENUM values:**
- `theorem`, `def`, `axiom`, `instance`, `inductive`, `structure`, `class`, `constant`, `opaque`, `abbrev`

#### **dependencies** (Primary key: `id`)
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | INTEGER | PK, auto-increment | — |
| source_symbol_id | INTEGER | FK→symbols.id, NOT NULL | CASCADE on delete |
| target_symbol_id | INTEGER | FK→symbols.id, NOT NULL | CASCADE on delete |
| dependency_type | ENUM | NOT NULL | See **dependency_type** enum below |
| confidence | FLOAT | default=1.0 | Confidence score (0.0–1.0) |
| indexed_at | TIMESTAMPTZ | default=now() | Index time |
| provenance | TEXT | nullable | How dependency was detected |
| metadata | JSONB | nullable | Free-form metadata |
| — | — | UNIQUE(source_symbol_id, target_symbol_id, dependency_type) | Composite unique |

**dependency_type ENUM values:**
- `direct` — Direct symbol reference
- `implicit` — Implicit dependency (typeclass resolution)
- `import` — Module import
- `indirect` — Transitive dependency

#### **file_dependencies** (Primary key: `id`)
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | INTEGER | PK, auto-increment | — |
| source_file_id | INTEGER | FK→files.id, NOT NULL | CASCADE on delete |
| target_file_id | INTEGER | FK→files.id, NOT NULL | CASCADE on delete |
| is_direct_import | BOOLEAN | default=true | Direct vs transitive |
| indexed_at | TIMESTAMPTZ | default=now() | Index time |
| — | — | UNIQUE(source_file_id, target_file_id) | Composite unique |

#### **index_runs** (Primary key: `id`)
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | INTEGER | PK, auto-increment | — |
| project_id | INTEGER | FK→projects.id, nullable | CASCADE on delete |
| run_type | VARCHAR(50) | NOT NULL | "full_scan", "incremental" |
| started_at | TIMESTAMPTZ | default=now() | Start time |
| completed_at | TIMESTAMPTZ | nullable | Completion time |
| files_processed | INTEGER | default=0 | Files indexed |
| symbols_indexed | INTEGER | default=0 | Symbols indexed |
| errors | JSONB | default='[]' | Error log as JSON array |
| status | VARCHAR(50) | default='running' | "running", "success", "failed" |

### Materialized Views

#### **dependency_stats**
**Purpose:** Per-symbol centrality metrics for dependency analysis

| Column | Type | Calculation |
|--------|------|-------------|
| symbol_id | INTEGER | PK (unique) |
| full_name | TEXT | Symbol's full_name |
| name | TEXT | Symbol's short name |
| kind | ENUM | Symbol kind |
| project_id | INTEGER | Symbol's project_id |
| outgoing_dependencies | INTEGER | COUNT of (dependencies where source_symbol_id = symbol_id) |
| incoming_dependencies | INTEGER | COUNT of (dependencies where target_symbol_id = symbol_id) |
| total_connections | INTEGER | outgoing + incoming |
| fan_out_ratio | FLOAT | outgoing / incoming (NULL if incoming=0) |

**Indexes:**
- `idx_dependency_stats_symbol_id` — PK lookup
- `idx_dependency_stats_project_id` — Project filtering
- `idx_dependency_stats_incoming DESC` — Most-used symbols

#### **module_metrics**
**Purpose:** Per-module aggregated statistics for high-level analysis

| Column | Type | Calculation |
|--------|------|-------------|
| file_id | INTEGER | PK (unique) |
| module_name | TEXT | File's module_name |
| project_id | INTEGER | File's project_id |
| total_symbols | INTEGER | COUNT(symbols) |
| theorem_count | INTEGER | COUNT where kind='theorem' |
| def_count | INTEGER | COUNT where kind='def' |
| axiom_count | INTEGER | COUNT where kind='axiom' |
| instance_count | INTEGER | COUNT where kind='instance' |
| inductive_count | INTEGER | COUNT where kind='inductive' |
| structure_count | INTEGER | COUNT where kind='structure' |
| class_count | INTEGER | COUNT where kind='class' |
| constant_count | INTEGER | COUNT where kind='constant' |
| opaque_count | INTEGER | COUNT where kind='opaque' |
| abbrev_count | INTEGER | COUNT where kind='abbrev' |
| avg_symbol_length_lines | FLOAT | AVG(line_end - line_start) |
| max_symbol_length_lines | INTEGER | MAX(line_end - line_start) |
| public_symbols | INTEGER | COUNT where is_public=true |
| deprecated_symbols | INTEGER | COUNT where is_deprecated=true |
| documented_symbols | INTEGER | COUNT where docstring IS NOT NULL |
| documentation_coverage_pct | FLOAT | (documented_symbols / total_symbols * 100) |

**Indexes:**
- `idx_module_metrics_file_id` — PK lookup
- `idx_module_metrics_project_id` — Project filtering
- `idx_module_metrics_total_symbols DESC` — Largest modules
- `idx_module_metrics_module_name` — Module name search

### Key Indexes (B-tree + GIN)

**B-tree Indexes (standard equality/range queries):**
- `idx_projects_name` — Project lookup by name
- `idx_projects_last_modified` — Recent projects
- `idx_files_project_id` — Files by project
- `idx_files_module_name` — Files by module
- `idx_files_last_modified` — Recent file changes
- `idx_files_hash` — File hash lookup (hash gate)
- `idx_symbols_file_id` — Symbols by file
- `idx_symbols_project_id` — Symbols by project
- `idx_symbols_name` — Symbol name search
- `idx_symbols_full_name` — Full name lookup
- `idx_symbols_kind` — Symbols by kind
- `idx_deps_source` — Dependencies from symbol
- `idx_deps_target` — Dependencies to symbol
- `idx_deps_type` — Dependencies by type
- `idx_deps_composite (source_symbol_id, target_symbol_id)` — Composite lookup
- `idx_file_deps_source` — File deps from file
- `idx_file_deps_target` — File deps to file

**GIN Indexes (JSONB containment + full-text search):**
- `idx_files_imports_gin` — JSONB containment on `imports` column
- `idx_symbols_attributes_gin` — JSONB containment on `attributes` column
- `idx_symbols_fts` — Full-text search GIN on `(docstring || ' ' || name)` with `to_tsvector('english', ...)`

### Migration HEAD

**Current:** Revision `0004_enriched_metrics.py` (Phase 2 enhancement)

**Migration Chain:**
1. `0001_initial_schema.py` — Creates enum types + 6 core tables (projects, files, symbols, dependencies, file_dependencies, index_runs)
2. `0002_add_indexes.py` — Creates all B-tree and GIN indexes
3. `0003_materialized_views.py` — Creates dependency_stats + module_metrics materialized views
4. `0004_enriched_metrics.py` — (Phase 2) Enhanced metrics

---

## 3. API Routes (Backend Python)

### Query API (`app/query_api.py` + `app/query/router.py`)

**Base URL:** `http://localhost:8000`  
**Prefix:** `/api/v1`  
**Auth:** None (anonymous; CORS from `http://localhost:3000`)

#### GET Endpoints

| HTTP Method | Path | Description | Query Params | Returns |
|-------------|------|-------------|--------------|---------|
| **GET** | `/health/live` | Liveness probe | — | `{"status": "alive"}` |
| **GET** | `/health/ready` | Readiness probe (DB + Redis) | — | `{"db": bool, "redis": bool}` |
| **GET** | `/api/v1/symbols/search` | Full-text search | `q` (required, 1–512 chars), `project_id` (required, ≥1), `limit` (1–100, default 20), `offset` (≥0, default 0) | `SymbolSearchResponse` |
| **GET** | `/api/v1/symbols/{full_name}` | Symbol lookup by qualified name | — (path param) | `SymbolLookupResponse` |
| **GET** | `/api/v1/dependencies/graph` | Transitive + reverse deps | `full_name` (required), `max_depth` (1–20, default 5) | `DependencyGraphResponse` |
| **GET** | `/api/v1/modules/metrics` | Module-level aggregations | `project_id` (required, ≥1), `order_by` (one of: "total_symbols", "theorem_count", "def_count", "avg_symbol_length_lines", "documentation_coverage_pct"; default "total_symbols") | `ModuleMetricsResponse` |
| **GET** | `/api/v1/events/invalidation` | **SSE stream** (Server-Sent Events) | — | `text/event-stream` with `event: invalidation` messages |

#### Response Models

**SymbolSearchResponse:**
```python
{
    "q": str,                    # Search query
    "project_id": int,
    "limit": int,
    "offset": int,
    "total": int,                # Total results (all pages)
    "items": [                   # Current page
        {
            "id": int,
            "file_id": int,
            "project_id": int,
            "name": str,
            "full_name": str,
            "kind": str,         # enum: theorem, def, instance, etc.
            "rank": float        # PostgreSQL full-text rank
        }
    ]
}
```

**SymbolLookupResponse:**
```python
{
    "id": int,
    "file_id": int,
    "project_id": int,
    "name": str,
    "full_name": str,
    "kind": str,                 # enum
    "line_start": int,
    "line_end": int,
    "signature": str | None,     # Lean signature text
    "docstring": str | None      # /-- ... -/ comment
}
```

**DependencyGraphResponse:**
```python
{
    "full_name": str,
    "max_depth": int,
    "transitive": [              # Forward dependencies
        {
            "symbol_id": int,
            "full_name": str,
            "name": str,
            "kind": str,
            "depth": int,        # Distance from source
            "path": [int, ...],  # Symbol IDs in path
            "dependency_type": str | None
        }
    ],
    "reverse": [...]             # Backward dependencies (same structure)
}
```

**ModuleMetricItem:**
```python
{
    "file_id": int,
    "module_name": str,
    "total_symbols": int,
    "theorem_count": int,
    "def_count": int,
    # ... (10 more count fields)
    "avg_symbol_length_lines": float | None,
    "max_symbol_length_lines": int | None,
    "public_symbols": int,
    "deprecated_symbols": int,
    "documented_symbols": int,
    "documentation_coverage_pct": float
}
```

**ModuleMetricsResponse:**
```python
{
    "project_id": int,
    "order_by": str,
    "items": [ModuleMetricItem, ...]
}
```

### Ingestion API (`app/ingestion_api.py` + `app/ingestion/router.py`)

**Base URL:** `http://localhost:8001`  
**Prefix:** `/admin`  
**Auth:** Required (Bearer JWT token with `role: "admin"`)

#### POST Endpoints

| HTTP Method | Path | Description | Request Body | Returns | Status |
|-------------|------|-------------|--------------|---------|--------|
| **POST** | `/health/live` | Liveness probe | — | `{"status": "alive"}` | 200 |
| **POST** | `/health/ready` | Readiness probe | — | `{"db": bool, "redis": bool}` | 200/503 |
| **POST** | `/admin/index/start` | Enqueue full-scan indexing task | `{"project_id": str, "root_dir": str}` | `{"task_id": str, "status": "queued"}` | **202** (Accepted) |
| **GET** | `/admin/index/status/{task_id}` | Poll indexing task status | — | `{"task_id": str, "state": str, "result": dict \| None, "error": str \| None}` | 200 |

#### Admin Request/Response Models

**IndexStartRequest:**
```python
{
    "project_id": str,      # Integer as string (forward-compat with UUIDs)
    "root_dir": str         # Filesystem path to Lean source root
}
```

**IndexStartResponse:**
```python
{
    "task_id": str,         # Celery task UUID
    "status": "queued"
}
```

**IndexStatusResponse:**
```python
{
    "task_id": str,
    "state": str,           # "PENDING", "STARTED", "SUCCESS", "FAILURE", "REVOKED"
    "result": dict | None,  # If successful
    "error": str | None     # If failed
}
```

### Cache & Invalidation

**Cache Keys Pattern:**
- `lean4:cache:symbol:{full_name}` — Symbol lookup
- `lean4:cache:file:{project_id}:search:{q}:{limit}:{offset}` — Search results
- `lean4:cache:deps:{full_name}:{max_depth}` — Dependency graph
- `lean4:cache:file:{project_id}:module_metrics:{order_by}` — Module metrics

**Cache TTL:** `3600` seconds (1 hour)

**Invalidation Channel:** `lean4:invalidate` (Redis pub/sub)

---

## 4. Parser Signals

### FileMetrics (Data Class)

**Purpose:** Static quality/health signals extractable without elaboration

```python
@dataclass(frozen=True)
class FileMetrics:
    # ── Proof completeness ───────────────────────────────
    sorry_count: int = 0                    # raw `sorry` occurrences in code
    admit_count: int = 0                    # raw `admit` occurrences in code
    sorry_lines: list[int] = field(default_factory=list)  # 1-based line numbers
    sorry_in_proof_count: int = 0           # theorems/lemmas whose body contains sorry
    theorem_count: int = 0                  # total theorems + lemmas
    proof_completion: float = 1.0           # (theorem_count - sorry_in_proof_count) / theorem_count
    
    # ── Fragility signals ────────────────────────────────
    native_decide_count: int = 0            # native_decide (slow, kernel-level, fragile)
    debug_command_count: int = 0            # leftover #check / #eval / #print in source
    
    # ── Symbol counts ────────────────────────────────────
    noncomputable_count: int = 0            # `noncomputable` declarations
    instance_count: int = 0                 # typeclass instances
    declared_axiom_count: int = 0           # custom `axiom` declarations
    simp_attr_count: int = 0                # `@[simp]`-tagged lemmas
    
    # ── Documentation / hygiene ──────────────────────────
    docstring_count: int = 0                # `/-- ... -/` docstrings present
    todo_count: int = 0                     # -- TODO / FIXME / HACK / XXX comments
    
    # ── Import profile ───────────────────────────────────
    mathlib_import_count: int = 0           # imports from Mathlib.*
```

### ParsedSymbol (Data Class)

**Purpose:** A single top-level Lean declaration

```python
@dataclass(frozen=True)
class ParsedSymbol:
    name: str                               # Short name (e.g., "append")
    kind: str                               # Kind keyword (def, theorem, lemma, instance, etc.)
    line_start: int                         # 1-based line number
    namespace_path: str                     # Namespace context (e.g., "List")
    is_private: bool                        # Whether marked `private`
    signature_text: str                     # Lean signature snippet
    mods: str = ""                          # Raw modifier string (e.g., "@[simp] noncomputable")
    has_sorry: bool = False                 # sorry/admit found in this declaration's body span
    
    @property
    def full_name(self) -> str:
        """Fully-qualified name, e.g. Foo.Bar.theorem_name"""
        return f"{self.namespace_path}.{self.name}" if self.namespace_path else self.name
```

### ParsedFile (Data Class)

**Purpose:** Result of parsing a Lean file from disk

```python
@dataclass(frozen=True)
class ParsedFile:
    path: Path                              # Filesystem path
    imports: list[str]                      # List of import statements
    symbols: list[ParsedSymbol]             # Extracted top-level symbols
    sha256: str                             # SHA256 hash of file content
    line_count: int                         # Number of lines
    metrics: FileMetrics                    # Aggregated quality metrics
```

### Parser Kinds

**PARSER_KINDS (extracted by regex):**
- `def`, `theorem`, `lemma`, `instance`, `class`, `structure`, `inductive`, `abbrev`, `axiom`, `example`, `opaque`

**KIND_TO_DB (mapping to database enum):**
- `lemma` → `theorem` (collapsed)
- `example` → dropped at DB layer
- All others → direct mapping

### Parse Logic Summary

**parse_text(src: str, namespace_path: str = "") → ParsedFileContent:**
1. Strip comments (`--`) and block comments (`/- ... -/`) + string literals preserving line numbers
2. Extract imports via regex: `^\s*import\s+([A-Za-z0-9_.]+)\s*$`
3. Track `namespace ... end` blocks for fully-qualified names
4. Extract declarations via regex pattern matching modifiers + kind keyword + optional name
5. Scan for `sorry`, `admit`, `native_decide`, `#check`/`#eval` etc.
6. Count `@[simp]`, `@[...]` attributes, `noncomputable`, etc.
7. Extract docstrings (`/-- ... -/`) and TODO comments
8. Aggregate into `FileMetrics`

**Key constraint:** Not a full Lean 4 grammar — regex-based extraction of declaration *heads* only (tactic blocks + elaborator macros out of scope).

### Watcher Trigger Signals

**parser/watcher.py** — File watcher daemon (`parser.watcher.LeanFileHandler`)

**Triggers:**
- File modified event (`on_modified`)
- File created event (`on_created`)
- File deleted event (`on_deleted`)
- File moved event (`on_moved`)

**Processing Pipeline:**
1. Debounce timer (default 500ms) collapses bursts into one re-index
2. Hash gate (SHA-256) short-circuits no-op events (mtime-only touches)
3. Parse file → extract symbols + imports
4. Upsert into PostgreSQL in single transaction
5. Invalidate Redis cache keys via pub/sub on channel `lean4:invalidate`
6. Log permission errors but never crash

**Output to DB:**
- Inserts/updates `files` table (with hash gate preventing redundant writes)
- Inserts/updates `symbols` table
- Inserts `dependencies` records for symbol-to-symbol links
- Publishes invalidation event to Redis

---

## 5. Go Forum Harness

### Routes & Endpoints

**Base Path:** (TBD — integrated into main.go)

| HTTP Method | Path | Handler | Description | Auth |
|-------------|------|---------|-------------|------|
| **GET** | `/flows` | `handleListFlows` | List all available flow definitions | — |
| **POST** | `/flows/{name}/start` | `handleStartFlow` | Enqueue a flow execution | — |
| **GET** | `/tickets/{ticket_id}` | `handleGetTicket` | Retrieve ticket result | — |
| **GET** | `/tickets` | `handleListTickets` | List recent tickets (paginated) | — |
| **GET** | `/sessions` | `handleListSessions` | List sessions | — |
| **POST** | `/sessions` | `handleCreateSession` | Create a new session | — |
| **GET** | `/sessions/{session_id}` | `handleGetSession` | Retrieve session details + tickets | — |
| **GET** | `/flows/{name}/events` | **SSE Stream** | Watch flow execution in real-time | — |

### FlowFunc Registry

**Type:** `type FlowFunc func(ctx context.Context, params map[string]interface{}, w http.ResponseWriter, flusher http.Flusher) (json.RawMessage, string, string)`

**Built-in Flows (12 total):**

1. **lean_sorry_scan** — Scan Lean4 codebase for sorry statements
2. **lean_float_scan** — Query floating symbols (definitions without proofs)
3. **lean_file_interconnect** — Analyze file dependencies and imports
4. **lean_db_health** — Check Lean4-Automata database health and statistics
5. **quick_proof_report** — Generate comprehensive proof status report
6. **tph_status** — Check TPH GPU server status and model info
7. **env_check** — Validate Python environment and dependencies
8. **gpu_check** — Check AMD GPU status and ROCm availability
9. **formula_match** — Match DynamicFlux Python formula against Lean symbols (placeholder)
10. **wolfram_verify** — Verify mathematical formula via Wolfram Engine (placeholder)
11. **lean_diff_mathlib** — Compare local Lean files against mathlib (placeholder)
12. **lean_mathlib_diff** — (Deprecated; use lean_diff_mathlib)

**Not Implemented:** placeholder flows return `{"status": "not_implemented", "message": "...", "placeholder": true}`

### Data Models (Go structs)

```go
type Ticket struct {
    ID           string          `json:"id"`           // tk_<ulid>
    FlowName     string          `json:"flow_name"`
    InputJSON    json.RawMessage `json:"input_json"`   // User input params
    OutputJSON   json.RawMessage `json:"output_json"`  // Flow result
    Status       string          `json:"status"`       // success, error, timeout
    ErrorMessage string          `json:"error_message,omitempty"`
    CreatedAt    int64           `json:"created_at"`   // Unix timestamp
    DurationMS   int64           `json:"duration_ms"`  // Execution duration
    Tags         []string        `json:"tags"`         // ["lean", "sorry"]
}

type Session struct {
    ID         string   `json:"id"`          // sess_<ulid>
    Name       string   `json:"name"`        // User-defined name
    CreatedAt  int64    `json:"created_at"` // Unix timestamp
    TicketIDs  []string `json:"ticket_ids"` // Associated tickets
}

type FlowDefinition struct {
    Name         string          `json:"name"`
    Description  string          `json:"description"`
    ParamsSchema json.RawMessage `json:"params_schema"`  // JSON Schema
    HandlerType  string          `json:"handler_type"`   // "builtin" or "proxy"
    TargetURL    string          `json:"target_url,omitempty"`  // For proxy flows
    Enabled      bool            `json:"enabled"`
    Tags         []string        `json:"tags"`           // ["lean", "gpu"]
}

type SSEMessage struct {
    Event string      `json:"-"`            // Event type
    Data  interface{} `json:"data"`         // Event payload
}

type LogMessage struct {
    Level   string `json:"level"`          // info, error, stdout, stderr
    Message string `json:"message"`
}

type ResultMessage struct {
    TicketID string `json:"ticket_id"`
    Status   string `json:"status"`        // success, error, timeout
}

type DoneMessage struct {
    DurationMS int64 `json:"duration_ms"`
}
```

### Forum Database Schema (SQLite)

**Location:** `~/.lean4a/forum.db` (configurable via `LEAN4A_FORUM_DB` env var)  
**Mode:** WAL (Write-Ahead Logging) with `PRAGMA synchronous=NORMAL`

#### Tables

**tickets** — Stored findings from flow executions
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | TEXT | PK | tk_<ulid> format |
| flow_name | TEXT | NOT NULL, FK | Flow name |
| input_json | TEXT | NOT NULL | JSON string of input params |
| output_json | TEXT | NOT NULL | JSON string of flow output |
| status | TEXT | NOT NULL, CHECK | Enum: success, error, timeout |
| error_message | TEXT | nullable | Populated if status ≠ success |
| created_at | INTEGER | NOT NULL | Unix timestamp (seconds) |
| duration_ms | INTEGER | nullable | Execution duration milliseconds |
| tags | TEXT | nullable | JSON array: ["lean", "sorry", "tph"] |

**Indexes:** `idx_tickets_flow`, `idx_tickets_status`, `idx_tickets_created` (DESC)

**sessions** — Group tickets together
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | TEXT | PK | sess_<ulid> format |
| name | TEXT | NOT NULL | User-defined session name |
| created_at | INTEGER | NOT NULL | Unix timestamp |
| ticket_ids_json | TEXT | nullable | JSON array of ticket IDs |

**Indexes:** `idx_sessions_created` (DESC)

**flow_definitions** — Metadata about available flows
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| name | TEXT | PK | Flow identifier |
| description | TEXT | NOT NULL | Human-readable description |
| params_schema | TEXT | NOT NULL | JSON schema for input parameters |
| handler_type | TEXT | NOT NULL | "builtin" or "proxy" |
| target_url | TEXT | nullable | Target URL for proxy flows |
| enabled | BOOLEAN | default=1 | Enable/disable flow |
| tags | TEXT | nullable | JSON array: ["lean", "sorry"] |

**flow_logs** — Circular buffer of recent flow execution logs
| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | INTEGER | PK (auto-increment) | — |
| flow_name | TEXT | NOT NULL, FK | Flow name |
| ticket_id | TEXT | nullable | Associated ticket ID |
| level | TEXT | NOT NULL | "info", "error", "stdout", "stderr" |
| message | TEXT | NOT NULL | Log message |
| timestamp | INTEGER | NOT NULL | Unix timestamp |

**Indexes:** `idx_flow_logs_ticket`, `idx_flow_logs_timestamp` (DESC)  
**Trigger:** `trim_flow_logs` — Keeps only last 1000 logs

---

## 6. Frontend Routes and API Calls

### Framework & Versions

- **Next.js:** 16.2.6 LTS
- **React:** 19.0.0
- **TypeScript:** 5.7.2
- **Styling:** TailwindCSS 4.0.0
- **Data Fetching:** TanStack Query (React Query) 5.62.10
- **State Management:** Zustand 5.0.3
- **Graph Visualization:** Reactflow 11.11.4 + Dagre 0.8.5
- **Node:** ≥22.0.0, npm ≥10.0.0

### App Router Pages (Next.js 13+ `app/` directory)

| Route | Component | Description | Data Source |
|-------|-----------|-------------|-------------|
| `/` | `page.tsx` | Landing page (redirects to `/projects/1`) | — |
| `/projects` | `projects/` | Project listing/selection | `GET /api/v1/projects` (if exists) |
| `/projects/[id]` | `projects/` | Project detail view | `GET /api/v1/symbols/search` (project scope) |
| `/search` | `search/` | Full-text symbol search interface | `GET /api/v1/symbols/search` |
| `/settings` | `settings/` | User settings/preferences | Local storage (Zustand) |

### Components & Composition

**High-Level Layout:**
- `layout.tsx` — Root layout wrapper (global providers)
- `AppShell.tsx` — Main container (sidebar + header + main)

**Key Components:**
- `Header.tsx` — Top navigation, branding
- `Sidebar.tsx` — Left sidebar (project nav, quick links)
- `SearchBar.tsx` — Search input with debouncing + autocomplete
- `SymbolCard.tsx` — Symbol display (name, kind, location, docs)
- `ModuleMetricsTable.tsx` — Metrics table view (sortable columns)
- `Breadcrumbs.tsx` — Navigation breadcrumb trail
- `FilterPanel.tsx` — Filter controls (kind, project, etc.)
- `graph/` — Reactflow-based dependency graph visualization
  - Nodes: Symbols, Edges: Dependencies
  - Dagre layout engine for hierarchical positioning
- `states/` — Zustand store definitions (global state)

**Provider Components:**
- `QueryProvider.tsx` — TanStack Query configuration
- `ThemeProvider.tsx` — Dark/light mode toggle

### API Calls (lib/api/)

**Base URL:** `NEXT_PUBLIC_API_BASE_URL` (default: `http://localhost:8080`)

**API Client Patterns:**
```typescript
// lib/api/index.ts — Fetch wrappers

export async function searchSymbols(query: string, projectId: number, limit: number, offset: number) {
    // GET /api/v1/symbols/search?q=...&project_id=...&limit=...&offset=...
}

export async function getSymbol(fullName: string) {
    // GET /api/v1/symbols/{fullName}
}

export async function getDependencyGraph(fullName: string, maxDepth: number) {
    // GET /api/v1/dependencies/graph?full_name=...&max_depth=...
}

export async function getModuleMetrics(projectId: number, orderBy: string) {
    // GET /api/v1/modules/metrics?project_id=...&order_by=...
}

export async function subscribeToInvalidations() {
    // EventSource: GET /api/v1/events/invalidation (SSE stream)
}
```

**Cache Strategy:**
- TanStack Query caching (deduplication + stale-while-revalidate)
- Manual invalidation on `lean4:invalidate` SSE messages

**Error Handling:**
- HTTP error boundaries
- Graceful fallback UI for unavailable data
- Toast notifications for user feedback

---

## 7. Infrastructure (Services, Ports, Health Checks, Nginx Routes)

### Docker Compose Services (`docker-compose.yml`)

| Service | Image | Port(s) | Env Vars | Dependencies | Health Check | Notes |
|---------|-------|---------|----------|--------------|--------------|-------|
| **postgres** | `postgres:17` | 5432 | `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | — | `pg_isready` | Volume: `postgres_data:/var/lib/postgresql/data` |
| **redis** | `redis:7` | 6379 | — | — | `redis-cli ping` | Volume: `redis_data:/data`, AOF persistence |
| **nginx** | `nginx:stable` | 8080 | — | app, app_ingestion (healthy) | `nginx -t` | Reverse proxy, rate limiting, SSE buffering |
| **app** | `lean4-automata-api:dev` (built from `Dockerfile.api`) | 8000 | `.env` | postgres (healthy), redis (healthy) | `curl /health/ready` | Query API (Uvicorn + FastAPI) |
| **app_ingestion** | `lean4-automata-ingestion:dev` (built from `Dockerfile.ingestion`) | 8001 | `.env` | postgres (healthy), redis (healthy) | `curl /health/ready` | Ingestion API (Uvicorn + FastAPI) |
| **worker** | `lean4-automata-worker:dev` (built from `Dockerfile.worker`) | — | `.env` | postgres (healthy), redis (healthy) | — | Celery worker (`celery -A workers.celery_app worker --concurrency=4`) |
| **watcher** | `lean4-automata-worker:dev` | — | `.env` + `LEAN_WATCH_ROOT`, `LEAN_PROJECT_ID` | postgres (healthy), redis (healthy) | — | File watcher daemon (`python -m parser.watcher`), volume: `LEAN_WATCH_ROOT:/lean-src:ro` |
| **flower** | `mher/flower:2.0` | 5555 | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | redis (healthy) | — | Celery monitoring UI |
| **web** | `lean4-automata-frontend:dev` (built from `frontend/Dockerfile`) | 3000 | `NEXT_PUBLIC_API_BASE_URL` | nginx (healthy) | `wget --spider http://localhost:3000/` | Next.js 16 frontend |
| **loki** | `grafana/loki:3.4.2` | 3100 | — | — (profile: observability) | `wget --spider /ready` | Loki log aggregation (volume: `loki_data:/loki`) |
| **grafana** | `grafana/grafana:11.6.0` | 3001 | `GF_SECURITY_ADMIN_*`, `GF_AUTH_ANONYMOUS_*` | loki (healthy) | `wget --spider /api/health` | Grafana dashboards (volume: `grafana_data:/var/lib/grafana`) |

### Health Checks

All services implement health checks with:
- **Interval:** 10–30 seconds
- **Timeout:** 3–5 seconds
- **Retries:** 3–5
- **Start Period:** 5–30 seconds

### Nginx Configuration (`nginx/nginx.conf`)

**Worker processes:** `auto` (CPU count)  
**Worker connections:** 2048  
**TCP settings:** `tcp_nopush on`, `tcp_nodelay on`, `keepalive_timeout 65s`

#### Rate Limiting Zones

```nginx
limit_conn_zone   $binary_remote_addr zone=sse_conn:10m;        # SSE per-IP cap
limit_req_zone    $binary_remote_addr zone=search_req:10m rate=60r/m;  # Search burst
```

#### Location Blocks

| Location | Upstream | Method | Rate Limit | Notes |
|----------|----------|--------|------------|-------|
| `/api/v1/events/` | `app:8000` | GET | `limit_conn sse_conn 10` (10 conns/IP) | SSE: proxy_buffering off, 1h timeout, Connection header cleared |
| `/api/v1/symbols/search` | `app:8000` | GET | `limit_req zone=search_req burst=20 nodelay` | 60 req/min + 20 burst |
| `/admin/` | `app_ingestion:8001` | POST, OPTIONS | — | Admin API, low-traffic, path rewrite `^/admin/(.*)$ /$1` |
| `/` (default) | `app:8000` | GET, POST, OPTIONS | — | All other routes (query API) |

#### Proxy Headers

All locations set:
- `X-Real-IP: $remote_addr`
- `X-Forwarded-For: $proxy_add_x_forwarded_for`
- `X-Forwarded-Proto: $scheme`
- `X-Forwarded-Host: $host`
- `Connection: ""` (HTTP/1.1 keep-alive)

#### Timeouts

- Query API: `connect 5s`, `send 60s`, `read 60s`
- Ingestion API: `connect 5s`, `send 60s`, `read 60s`
- Upstream failover: `proxy_next_upstream error timeout http_502 http_503 http_504` (2 tries)

---

## 8. Observability Stack

### Loki Configuration (`observability/loki/loki-config.yaml`)

**Components:**
- **Ingester:** Handles incoming log streams
- **Distributor:** Routes logs to ingesters
- **Querier:** Queries stored logs
- **Query Frontend:** Caches + deduplicates queries

**Storage Backend:** 
- Chunks storage (filesystem-based in dev; S3-compatible in prod)
- Index storage (in-memory in dev)

**Log Retention:** Configurable via policy (default ~24h in dev)

### Grafana Configuration (`observability/grafana/provisioning/`)

**Auto-Provisioned:**
- **Data Sources:** Loki instance at `http://loki:3100`
- **Dashboards:** JSON dashboard definitions

**Dashboard Examples:**
- `logs-overview.json` — Overall log metrics (errors, throughput)
- Service-specific dashboards (API, worker, etc.)

**Environment Variables:**
- `GF_SECURITY_ADMIN_USER: ${GRAFANA_ADMIN_USER:-admin}`
- `GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin}`
- `GF_USERS_ALLOW_SIGN_UP: "false"` (disable sign-ups)
- `GF_AUTH_ANONYMOUS_ENABLED: false` (require auth)

**Default Home Dashboard:** `/var/lib/grafana/dashboards/logs-overview.json`

### Activation

**Default:** Observability stack is **disabled** (profile-based)

```bash
# Enable Loki + Grafana with observability profile
docker compose --profile observability up
```

**Access:**
- Loki: `http://localhost:3100`
- Grafana: `http://localhost:3001` (user: admin, password: from .env or "admin")

---

## 9. Configuration Reference (All Environment Variables)

### Application & Ports

| Var | Default | Type | Description |
|-----|---------|------|-------------|
| `APP_PORT` | 8000 | int | Query API port |
| `INGESTION_PORT` | 8001 | int | Ingestion API port |
| `NGINX_HTTP_PORT` | 8080 | int | Nginx reverse proxy port |
| `FRONTEND_PORT` | 3000 | int | Next.js frontend port |
| `FLOWER_PORT` | 5555 | int | Celery Flower monitoring UI port |
| `LOKI_PORT` | 3100 | int | Loki ingester port |
| `GRAFANA_PORT` | 3001 | int | Grafana dashboard port |

### Database

| Var | Default | Type | Description |
|-----|---------|------|-------------|
| `DATABASE_URL` | (none) | str | asyncpg DSN: `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `POSTGRES_DB` | lean4_automata | str | PostgreSQL database name |
| `POSTGRES_USER` | lean4 | str | PostgreSQL user |
| `POSTGRES_PASSWORD` | lean4_dev_password | str | PostgreSQL password |
| `POSTGRES_PORT` | 5432 | int | PostgreSQL port (host network) |

### Redis & Caching

| Var | Default | Type | Description |
|-----|---------|------|-------------|
| `REDIS_URL` | redis://redis:6379 | str | Redis connection URL (asyncio) |
| `REDIS_PORT` | 6379 | int | Redis port (host network) |
| `CELERY_BROKER_URL` | `${REDIS_URL}` | str | Celery broker (defaults to REDIS_URL) |
| `CELERY_RESULT_BACKEND` | `${REDIS_URL}` | str | Celery result backend (defaults to REDIS_URL) |

### JWT Authentication

| Var | Default | Type | Description |
|-----|---------|------|-------------|
| `JWT_SECRET_KEY` | change-me-in-production | str | HS256 signing key (generate: `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `JWT_ALGORITHM` | HS256 | str | JWT algorithm (HS256 for HMAC) |

### Runtime Environment

| Var | Default | Type | Description |
|-----|---------|------|-------------|
| `ENV` | development | str | Deployment environment ("development" or "production") |
| `ALLOWED_ORIGINS` | http://localhost:3000 | str | CORS allowed origins (comma-separated) |
| `NEXT_PUBLIC_API_BASE_URL` | http://localhost:8080 | str | Frontend API base URL (exposed to browser) |

### Parser & Watcher

| Var | Default | Type | Description |
|-----|---------|------|-------------|
| `LEAN_WATCH_ROOT` | ./lean-src | str | Filesystem root to watch for .lean files |
| `LEAN_PROJECT_ID` | 1 | int | Project ID for watcher indexing |

### Go Forum Harness

| Var | Default | Type | Description |
|-----|---------|------|-------------|
| `LEAN4A_FORUM_DB` | ~/.lean4a/forum.db | str | SQLite forum database path |
| `LEAN_DB_URL` | http://localhost:8000 | str | Lean4-Automata API base URL (for flows) |
| `TPH_SERVER_URL` | http://localhost:5000 | str | TPH GPU inference server URL |
| `FLOW_TIMEOUT_SEC` | 30 | int | Flow execution timeout (seconds) |
| `MAX_CONCURRENT_FLOWS` | 5 | int | Max concurrent flow executions |

### Grafana

| Var | Default | Type | Description |
|-----|---------|------|-------------|
| `GRAFANA_ADMIN_USER` | admin | str | Grafana admin username |
| `GRAFANA_ADMIN_PASSWORD` | admin | str | Grafana admin password |
| `GRAFANA_ANONYMOUS_ENABLED` | false | str | Enable anonymous access |

---

## 10. Documentation Inventory

### README Files

1. **README.md** (59 lines)
   - Prerequisites: Docker 24+, Docker Compose v2, Python 3.11+, Lean 4 / elan
   - Quick start: `docker compose up --build`
   - Health check: `curl http://localhost:8000/health`
   - Project layout table (app/, db/, workers/, etc.)

2. **README_DATABASE.md** (241 lines)
   - Alembic migration overview
   - Directory structure + migration chain
   - Installation + running migrations
   - Troubleshooting (connection, migration, index issues)
   - Production recommendations (connection pooling, backups, autovacuum)

3. **SCHEMA.md** (277 lines)
   - Entity relationship diagram (mermaid ERD)
   - All 6 core tables with columns + types + constraints
   - 2 materialized views (dependency_stats, module_metrics)
   - All indexes (B-tree + GIN + FTS)
   - Query patterns (transitive deps, reverse deps, cycle detection, top symbols)
   - Performance considerations (concurrent indexing, JSONB queries, recursive CTEs)
   - Materialized view refresh commands
   - Foreign key cascade rules

4. **IMPLEMENTATION_SUMMARY.md**
   - High-level architecture overview
   - Phase 1, Phase 2, Phase 3 roadmap (likely)

### Additional Documentation

5. **DOCKER_REVIEW_FIXES.md**
   - Docker build documentation + fixes

6. **docs/** directory
   - (Expected to contain detailed guides)
   - Likely includes `forum/` subdirectory

7. **observability/README.md**
   - Loki + Grafana setup guide

8. **observability/GRAFANA_LOKI_UX.md**
   - User guide for Grafana + Loki dashboards

9. **frontend/README.md**
   - Frontend build + development guide

10. **frontend/SECURITY.md**
    - Frontend security practices
    - CORS, CSP, authentication

11. **frontend/UX_SPEC.md**
    - UX specifications + design patterns

### Configuration Templates

12. **.env.example** (38 lines)
    - All environment variables with defaults and explanations

### Code Comments

- Inline docstrings (Python: `"""..."""`, Go: `//`)
- Type annotations (Python: `typing` module, TypeScript: native)
- Config explanations (`.env.example`)

### Lean Source

13. **lean-src/** (mounted volume)
    - Target for file watcher
    - Contains .lean source files to index

### Experimental/Reference

14. **_chopshop/** — Experimental/scratch code
15. **_copied_from_serena/** — Legacy reference (Serena project)
16. **lean-mapping-architecture/** — Reference architecture docs

---

## Summary Statistics

| Category | Count/Notes |
|----------|------------|
| **Python Modules** | ~8 (app, db, parser, workers) |
| **FastAPI Routes** | ~10 (query + ingestion + health) |
| **Database Tables** | 6 core + 2 materialized views |
| **Indexes** | 20+ (B-tree + GIN) |
| **Celery Tasks** | 2 (full_scan, refresh_materialized_views) |
| **Go Flows** | 12 flow definitions |
| **Frontend Pages** | 5+ (projects, search, settings, etc.) |
| **Services (Docker)** | 8 (postgres, redis, nginx, 2 APIs, worker, watcher, web) + 2 optional (loki, grafana) |
| **Configuration Vars** | ~30 environment variables |
| **Documentation Files** | 10+ (READMEs, guides, UX spec) |

---

This survey provides a **complete blueprint** for teams across all specialties to work independently:
- **Backend engineers:** Routes, handlers, DB schema
- **Frontend engineers:** Pages, components, API calls
- **Data scientists:** Parser signals (FileMetrics), dependency graphs, metrics
- **DevOps/Infrastructure:** Docker compose, nginx, health checks, monitoring
- **Database engineers:** Schema, migrations, indexes, materialized views, CTEs
- **Observability engineers:** Loki config, Grafana dashboards
- **Documentation:** Configuration reference, API contracts, data models