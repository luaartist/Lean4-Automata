# API Specification

All endpoints live behind a versioned prefix: `/api/v1/`.

## Endpoint Catalogue

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/symbols/{full_name}` | – | Symbol lookup |
| GET | `/symbols/{full_name}/dependencies` | – | Forward dependencies |
| GET | `/symbols/{full_name}/usages` | – | Reverse dependencies |
| GET | `/search` | – | Full-text search |
| GET | `/files/{module_name}/imports` | – | Module import graph |
| GET | `/viz/project/{name}/graph` | – | Visualisation export |
| GET | `/charts/symbol-distribution` | – | Chart-ready analytics |
| POST | `/admin/index/start` | JWT | Trigger indexing job |
| GET | `/admin/index/status/{run_id}` | JWT | Job progress |
| GET | `/health` | – | Readiness + liveness |

## Symbol Lookup

```http
GET /api/v1/symbols/Mathlib.Data.List.Basic.append_assoc
```

### Response `200 OK`

```json
{
  "symbol": {
    "id": 12345,
    "name": "append_assoc",
    "full_name": "Mathlib.Data.List.Basic.append_assoc",
    "kind": "theorem",
    "signature": "∀ (α : Type) (l m n : List α), (l ++ m) ++ n = l ++ (m ++ n)",
    "docstring": "Associativity of list concatenation",
    "file": {
      "path": "Mathlib/Data/List/Basic.lean",
      "module": "Mathlib.Data.List.Basic",
      "line_start": 142,
      "line_end": 148
    },
    "attributes": ["@[simp]"],
    "is_public": true
  },
  "metadata": {
    "indexed_at": "2025-01-15T10:30:00Z",
    "cache_hit": false,
    "freshness": { "max_age_s": 3600, "source": "database" }
  }
}
```

Every response carries a `metadata.freshness` block (see §05).

## Dependency Query

```http
GET /api/v1/symbols/{full_name}/dependencies?transitive=true&depth=3
```

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `transitive` | bool | false | Include indirect deps |
| `depth` | int (1–10) | 3 | Max recursion depth |
| `types` | string[] | all | Filter: `direct`, `implicit`, `import`, `indirect` |

## Search

```http
GET /api/v1/search?q=associativity&kind=theorem&limit=20
```

| Param | Type | Default |
|-------|------|---------|
| `q` | string (required) | – |
| `kind` | string[] | all |
| `project` | string | all |
| `attributes` | string[] | all |
| `limit` | int (1–100) | 20 |
| `offset` | int | 0 |

## Error Envelope

All errors follow a consistent shape:

```json
{
  "error": {
    "code": "SYMBOL_NOT_FOUND",
    "message": "No symbol matches 'Foo.bar'",
    "request_id": "req-abc123"
  }
}
```

`request_id` corresponds to the `X-Request-ID` / correlation ID propagated
through traces (see §12).

## Common Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 202 | Accepted (async job) |
| 400 | Bad request / validation error |
| 401 | Missing or invalid JWT (admin endpoints) |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Internal error |
| 503 | Service unavailable (DB down) |
