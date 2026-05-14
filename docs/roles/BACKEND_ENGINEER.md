# Backend Engineer — Role Anchor

> 10 most likely questions a Backend Engineer will ask, answered with file paths and code examples.

---

## Q1. How does a full-index request flow from the admin endpoint to the Celery worker?

The ingestion API receives a JWT-protected POST at `/admin/index/start`. The handler validates the token via `require_admin` (checks `role == "admin"` in JWT payload), then enqueues a Celery task:

**File:** `app/ingestion/router.py`

```python
@router.post("/index/start", status_code=202)
async def start_index(
    body: IndexStartRequest,
    _admin=Depends(require_admin),
):
    task = full_scan_task.delay(body.project_id, body.root_dir)
    return {"task_id": task.id, "status": "queued"}
```

The task `full_scan_task` lives in `workers/tasks.py`:

```python
@app.task(name="lean4.full_scan", bind=True, max_retries=2)
def full_scan_task(self, project_id: str, root_dir: str):
    scanner = FullScanner(project_id, root_dir)
    result = scanner.run()          # walks .lean files, calls parse_file(), upserts
    redis_client.publish("lean4:invalidate", json.dumps({...}))
    return result
```

The Celery app is configured in `workers/celery_app.py` with Redis as both broker and result backend, JSON serialization, and a 1-hour hard time limit.

---

## Q2. How do I add a new Alembic migration?

```bash
# Generate a new revision
alembic revision -m "add_my_new_column" --autogenerate

# Or write it manually
alembic revision -m "add_my_new_column"
```

All migrations live in `alembic/versions/`. The current chain is:

1. `0001_initial_schema.py` — core tables (`projects`, `files`, `symbols`, `dependencies`, `file_dependencies`, `index_runs`) + enums (`symbol_kind`, `dependency_type`)
2. `0002_add_indexes.py` — B-tree on most FK/filter columns, GIN on JSONB (`imports`, `attributes`), GIN full-text search on `symbols` (`tsvector` over `name || docstring`)
3. `0003_materialized_views.py` — `dependency_stats`, `module_metrics` (refreshed hourly by Celery beat)
4. `0004_enriched_metrics.py` — 15+ static-analysis columns on `files`, `has_sorry` on `symbols`, 3 SQL views

Set your `revision` string to the next sequential number, and link `down_revision` to the current head. Run `alembic upgrade head` to apply.

---

## Q3. How does the watcher daemon detect and process file changes?

**File:** `parser/watcher.py`

The watcher uses the `watchdog` library. It instantiates either a `PollingObserver` or a native `Observer` (inotify on Linux) depending on configuration.

`LeanFileHandler` inherits from `FileSystemEventHandler` and responds to `on_modified`, `on_created`, `on_deleted`, and `on_moved` for files matching `*.lean`.

**Debouncing:** Each event schedules a timer (`threading.Timer`, default 500 ms). If another event arrives for the same path, the old timer is cancelled and a new one is set. This collapses rapid saves into a single process call.

**Hash gate:** Before parsing, the handler computes SHA-256 of the file and compares it to the stored `file_hash` in PostgreSQL. If unchanged, processing is skipped entirely.

**Processing (`_process_file`):** Runs in a single database transaction:

```python
# 1. Parse the file
parsed = parse_file(path)

# 2. Upsert the file record
cursor.execute("""
    INSERT INTO files (project_id, relative_path, ...)
    VALUES (%s, %s, ...)
    ON CONFLICT (project_id, relative_path) DO UPDATE SET ...
    RETURNING id
""")

# 3. Delete old symbols for this file
cursor.execute("DELETE FROM symbols WHERE file_id = %s", (file_id,))

# 4. Insert new symbols
for sym in parsed.symbols:
    cursor.execute("INSERT INTO symbols (...) VALUES (...)")

# 5. Rebuild edges (file_dependencies)
# 6. Redis PUBLISH lean4:invalidate
```

---

## Q4. How does the parser extract symbols from a Lean 4 file?

**File:** `parser/lean_parser.py`

The core function is `parse_text(content: str) -> ParsedFileContent`. It works in several stages:

1. **Strip comments and strings** — length-preservingly (replaced with spaces) so that line numbers remain correct. Handles `/- ... -/` (nested block comments), `-- ...` (line comments), and `"..."` strings.

2. **Track namespace blocks** — a stack of `(namespace_name, indent_level)` pairs. When `namespace Foo` is encountered, it's pushed; when the indent level returns to or below the parent, it's popped.

3. **Regex-based declaration scan** — matches against 11 kinds: `def`, `theorem`, `lemma`, `instance`, `class`, `structure`, `inductive`, `abbrev`, `axiom`, `example`, `opaque`. Each produces a `ParsedSymbol`:

```python
@dataclass
class ParsedSymbol:
    name: str
    kind: str               # "theorem", "def", etc.
    line_start: int
    namespace_path: list[str]
    is_private: bool
    signature_text: str
    mods: list[str]         # e.g. ["noncomputable", "protected"]
    has_sorry: bool          # sorry/admit found in body
```

4. **File-level metrics** — `FileMetrics` with 15+ fields computed via regex scans over the raw text (sorry_count, admit_count, native_decide_count, etc.).

`KIND_TO_DB` maps parser kinds to database enums: `lemma → theorem`, `example` is dropped entirely.

---

## Q5. How is the Go forum harness structured, and how do I add a new flow?

**File:** `go/forum.go`

The forum uses a **compile-time `FlowFunc` registry** (security decision from commit `10927ba` — eliminates command-template code-execution attack surface).

```go
type FlowFunc func(ctx context.Context, params map[string]any, emit func(string)) (any, error)

var flowRegistry = map[string]FlowFunc{
    "lean_sorry_scan":         leanSorryScan,
    "lean_float_scan":         leanFloatScan,
    "lean_file_interconnect":  leanFileInterconnect,
    "lean_db_health":          leanDBHealth,
    "quick_proof_report":      quickProofReport,
    "tph_inference":           tphInference,
    "tph_status":              tphStatus,
    "env_check":               envCheck,
    "gpu_check":               gpuCheck,
    "formula_match":           placeholderFlow,
    "wolfram_verify":          placeholderFlow,
    "lean_diff_mathlib":       placeholderFlow,
}
```

**To add a new flow:**

1. Write a Go function matching the `FlowFunc` signature in `forum.go`.
2. Register it in `flowRegistry`.
3. Add its definition to `ui/flow_definitions.json` for the UI button:

```json
{
  "name": "my_new_flow",
  "description": "Does something useful",
  "params_schema": { "type": "object", "properties": {} },
  "tags": ["lean"],
  "handler_type": "builtin"
}
```

4. Recompile: `go build -o forum forum.go`

---

## Q6. How does JWT authentication work on the ingestion API?

**File:** `app/core/security.py`

```python
def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

async def require_admin(authorization: str = Header(...)):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(401, "Bearer token required")
    payload = decode_token(token)
    if payload.get("role") != "admin":
        raise HTTPException(403, "Admin role required")
    return payload
```

The ingestion router uses `Depends(require_admin)` on all endpoints. The JWT must contain `{"role": "admin"}` in its payload.

Generate a token locally for testing:

```python
import jwt, datetime
token = jwt.encode(
    {"sub": "admin-user", "role": "admin", "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)},
    "YOUR_JWT_SECRET_KEY", algorithm="HS256"
)
```

Settings come from `app/core/config.py` via pydantic-settings (`JWT_SECRET_KEY`, `JWT_ALGORITHM`).

---

## Q7. How does cache invalidation work end-to-end?

Three components participate:

**1. Cache writes** — `app/query/router.py` caches responses in Redis:

```python
cache_key = f"lean4:cache:{request_fingerprint}"
cached = await redis.get(cache_key)
if cached:
    return json.loads(cached)
# ... query DB ...
await redis.setex(cache_key, 3600, json.dumps(result))
```

**2. Invalidation publish** — When the watcher or full-scan task modifies data, it publishes to `lean4:invalidate`:

```python
redis_client.publish("lean4:invalidate", json.dumps({
    "type": "file_changed",
    "project_id": project_id,
    "path": relative_path,
}))
```

**3. SSE broadcast** — The SSE endpoint (`GET /api/v1/events/invalidation`) subscribes to the Redis channel and forwards messages to connected clients:

```python
@router.get("/events/invalidation")
async def invalidation_stream(request: Request):
    pubsub = redis.pubsub()
    await pubsub.subscribe("lean4:invalidate")
    async def event_generator():
        while True:
            msg = await pubsub.get_message(timeout=1.0)
            if msg and msg["type"] == "message":
                yield f"event: invalidation\ndata: {msg['data']}\n\n"
            # heartbeat every 15s
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

Nginx caps SSE connections to 10 per IP (`limit_conn sse_zone 10`) and disables proxy buffering.

---

## Q8. How do I run the Celery beat scheduler and what tasks does it schedule?

**File:** `workers/celery_app.py`

```python
app.conf.beat_schedule = {
    "refresh-materialized-views-hourly": {
        "task": "lean4.refresh_materialized_views",
        "schedule": crontab(minute=0),   # every hour on the hour
    },
}
```

The `refresh_views_task` in `workers/tasks.py` runs:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY dependency_stats;
REFRESH MATERIALIZED VIEW CONCURRENTLY module_metrics;
```

Start the beat scheduler:

```bash
celery -A workers.celery_app beat --loglevel=info
```

Or combined with a worker (development only):

```bash
celery -A workers.celery_app worker --beat --loglevel=info --concurrency=4
```

---

## Q9. What security hardening has been applied and where?

Per the security audit in commit `4a3c84a`:

| Area | Mitigation | File |
|---|---|---|
| **XSS** | Go forum escapes HTML in SSE output; CSP headers | `go/forum.go` |
| **Proxy DoS** | Nginx rate-limit 60 req/min on search, 10 SSE/IP | `nginx/nginx.conf` |
| **JWT leakage** | Swagger/Redoc disabled when `ENV=production`; no token echo in responses | `app/query_api.py`, `app/ingestion_api.py` |
| **SSE method** | SSE endpoint restricted to GET only | `app/query/router.py` |
| **CORS** | Strict `ALLOWED_ORIGINS`, GET+OPTIONS only on query API | `app/query_api.py` |
| **Request-ID injection** | Regex-validated (`^[a-zA-Z0-9-]{1,64}$`) | `app/core/middleware.py` |
| **Code execution** | Compile-time FlowFunc registry (no DB-driven command templates) | `go/forum.go` |
| **Body size** | 1 MB request body limit on Go forum | `go/forum.go` |
| **Server tokens** | `server_tokens off` in Nginx | `nginx/nginx.conf` |

---

## Q10. How do I debug a failed Celery task?

**Step 1: Check task state via API**

```bash
curl http://localhost:8001/admin/index/status/<task_id> \
  -H "Authorization: Bearer $JWT"
# Returns {"task_id": "...", "state": "FAILURE", "error": "..."}
```

**Step 2: Check Flower**

Open `http://localhost:5555` — Flower shows task history, worker status, and exception traces.

**Step 3: Check worker logs**

```bash
docker compose logs -f worker
```

**Step 4: Inspect Redis directly**

```bash
docker compose exec redis redis-cli
> KEYS celery-task-meta-*
> GET celery-task-meta-<task_id>
```

**Step 5: Manually retry**

```bash
docker compose exec worker celery -A workers.celery_app call lean4.full_scan \
  --args='["1", "/lean-src"]'
```

The Celery app sets `max_retries=2` with exponential backoff. Check that PostgreSQL and Redis are both healthy first (hit `/health/ready` on either API).
