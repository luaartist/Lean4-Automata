# Data Model

## Entity-Relationship Overview

```
projects 1──* files 1──* symbols
                │              │
                │              ├──* dependencies (source → target)
                │              └──* external_refs
                │
                └──* file_dependencies (source_file → target_file)

index_runs *──1 projects
```

## Core Tables

### `projects`

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| name | VARCHAR(255) UNIQUE | e.g. `mathlib4` |
| root_path | TEXT | Absolute FS path |
| lean_version | VARCHAR(50) | `4.8.0` |
| lakefile_hash | VARCHAR(64) | SHA-256 of `lakefile.lean` |
| metadata | JSONB | Toolchain, git commit |

### `files`

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| project_id | FK → projects | CASCADE delete |
| relative_path | TEXT | `Mathlib/Data/List/Basic.lean` |
| module_name | TEXT | `Mathlib.Data.List.Basic` |
| file_hash | VARCHAR(64) | SHA-256 content hash |
| imports | JSONB | `["Mathlib.Init.Data.List"]` |

**Unique**: `(project_id, relative_path)`.

### `symbols`

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| file_id | FK → files | CASCADE |
| project_id | FK → projects | Denormalised for join avoidance |
| full_name | TEXT UNIQUE per project | `Mathlib.Data.List.Basic.append_assoc` |
| kind | ENUM | `theorem`, `def`, `axiom`, `instance`, … |
| signature | TEXT | Full type signature |
| docstring | TEXT | |
| attributes | JSONB | `["@[simp]"]` |

### `dependencies`

| Column | Type | Notes |
|--------|------|-------|
| source_symbol_id | FK → symbols | CASCADE |
| target_symbol_id | FK → symbols | CASCADE |
| dependency_type | ENUM | `direct`, `implicit`, `import`, `indirect` |
| confidence | FLOAT | 0.0–1.0 |

**Unique**: `(source_symbol_id, target_symbol_id, dependency_type)`.

## Indexing Strategy

| Index | Type | Purpose |
|-------|------|---------|
| `symbols(full_name)` | B-tree | O(1) lookup |
| `symbols(attributes)` | GIN | `@>` containment queries |
| `symbols(docstring ‖ name)` | GIN/tsvector | Full-text search |
| `dependencies(source, target)` | Composite B-tree | Bidirectional lookup |
| `files(imports)` | GIN | Import containment |

## Materialised Views

- **`dependency_stats`** – per-symbol dependency count, usage count, centrality.
- **`module_metrics`** – per-module symbol count by kind, average length.

Both refreshed concurrently on an hourly schedule (see §15).

## Migration Strategy

Alembic manages schema versions from day one. Every migration is:
1. Forward-only in production.
2. Tested in CI against a seeded database.
3. Backwards-compatible for at least one release cycle.
