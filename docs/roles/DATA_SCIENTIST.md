# Data Scientist — Role Anchor

> 10 most likely questions a Data Scientist will ask, answered with SQL, Python, and file references.

---

## Q1. How do I connect to the database and what schema should I expect?

The primary database is PostgreSQL 17, connection details from `.env.example`:

```
host=localhost  port=5432  dbname=lean4_automata  user=lean4  password=lean4_dev_password
```

**Python (pandas + psycopg2):**

```python
import pandas as pd
import psycopg2

conn = psycopg2.connect(
    host="localhost", port=5432,
    dbname="lean4_automata", user="lean4", password="lean4_dev_password"
)

df = pd.read_sql("SELECT * FROM symbols LIMIT 10", conn)
print(df.columns.tolist())
# ['id', 'file_id', 'project_id', 'name', 'full_name', 'kind',
#  'line_start', 'line_end', 'signature', 'docstring', 'is_public',
#  'is_deprecated', 'has_sorry', 'attributes']
```

**SQLAlchemy (async — matches the app):**

```python
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine("postgresql+asyncpg://lean4:lean4_dev_password@localhost:5432/lean4_automata")
```

Core tables: `projects`, `files`, `symbols`, `dependencies`, `file_dependencies`, `index_runs`.
Views: `dependency_stats`, `module_metrics`, `v_proof_status`, `v_floating_symbols`, `v_file_interconnect`.

See `alembic/versions/` for the full DDL.

---

## Q2. How do I query proof completion across all files?

Use the **`v_proof_status`** view (created in migration 0004):

```sql
SELECT
    f.relative_path,
    vps.theorem_count,
    vps.sorry_in_proof_count,
    vps.proof_completion,
    vps.status                -- 'complete' | 'partial' | 'mostly_incomplete' | 'no_theorems'
FROM v_proof_status vps
JOIN files f ON f.id = vps.file_id
WHERE vps.status != 'no_theorems'
ORDER BY vps.proof_completion ASC;
```

**Status labels:**
- `complete` — `proof_completion = 1.0` (zero sorry-bearing theorems)
- `partial` — `0.5 ≤ proof_completion < 1.0`
- `mostly_incomplete` — `proof_completion < 0.5`
- `no_theorems` — file has zero theorems

**Export to pandas:**

```python
df = pd.read_sql("SELECT * FROM v_proof_status", conn)
df['status'].value_counts().plot(kind='bar', title='Proof Status Distribution')
```

---

## Q3. How do I find "floating" symbols (proved but never used)?

Use the **`v_floating_symbols`** view:

```sql
SELECT
    s.full_name,
    s.kind,
    f.relative_path,
    s.line_start,
    s.docstring
FROM v_floating_symbols vfs
JOIN symbols s ON s.id = vfs.symbol_id
JOIN files f ON f.id = s.file_id
ORDER BY f.relative_path, s.line_start;
```

This view selects public symbols of kind `theorem` or `def` that have **zero incoming cross-file dependencies** — they were proved/defined but are never referenced by another file. These are prime candidates for:
- Dead code removal
- Library export review
- Documentation priority (important but undiscovered results)

---

## Q4. How do I compute per-module complexity and documentation coverage?

Use the **`module_metrics`** materialized view (refreshed hourly):

```sql
SELECT
    module_name,
    total_symbols,
    theorem_count,
    def_count,
    instance_count,
    avg_symbol_length_lines,
    max_symbol_length_lines,
    documentation_coverage_pct
FROM module_metrics
ORDER BY total_symbols DESC
LIMIT 20;
```

**Documentation coverage** = `(symbols with non-null docstring) / total_symbols * 100`.

To force a refresh:

```bash
docker compose exec worker celery -A workers.celery_app call lean4.refresh_materialized_views
```

---

## Q5. How do I traverse the dependency graph for a specific symbol?

**File:** `db/queries.py` — contains recursive CTE queries.

```sql
-- Transitive forward dependencies (what does this symbol use?)
WITH RECURSIVE transitive AS (
    SELECT target_symbol_id AS id, 1 AS depth
    FROM dependencies
    WHERE source_symbol_id = :symbol_id
    UNION
    SELECT d.target_symbol_id, t.depth + 1
    FROM dependencies d
    JOIN transitive t ON d.source_symbol_id = t.id
    WHERE t.depth < :max_depth
)
SELECT DISTINCT s.full_name, s.kind, t.depth
FROM transitive t
JOIN symbols s ON s.id = t.id
ORDER BY t.depth, s.full_name;
```

```sql
-- Reverse dependencies (who uses this symbol?)
WITH RECURSIVE reverse_deps AS (
    SELECT source_symbol_id AS id, 1 AS depth
    FROM dependencies
    WHERE target_symbol_id = :symbol_id
    UNION
    SELECT d.source_symbol_id, r.depth + 1
    FROM dependencies d
    JOIN reverse_deps r ON d.target_symbol_id = r.id
    WHERE r.depth < :max_depth
)
SELECT DISTINCT s.full_name, s.kind, r.depth
FROM reverse_deps r
JOIN symbols s ON s.id = r.id
ORDER BY r.depth, s.full_name;
```

The API wraps these in `GET /api/v1/dependencies/graph?full_name=...&max_depth=5`.

---

## Q6. How do I export the full symbol table for analysis in a notebook?

```python
import pandas as pd
import psycopg2

conn = psycopg2.connect(
    host="localhost", port=5432,
    dbname="lean4_automata", user="lean4", password="lean4_dev_password"
)

# Symbols with file paths
df = pd.read_sql("""
    SELECT
        s.id, s.full_name, s.name, s.kind,
        s.line_start, s.line_end,
        (s.line_end - s.line_start + 1) AS length_lines,
        s.has_sorry, s.is_public, s.docstring IS NOT NULL AS has_docstring,
        f.relative_path, f.module_name,
        f.proof_completion, f.sorry_count, f.mathlib_import_count
    FROM symbols s
    JOIN files f ON f.id = s.file_id
    ORDER BY f.relative_path, s.line_start
""", conn)

# Quick stats
print(f"Total symbols: {len(df)}")
print(f"Kinds:\n{df['kind'].value_counts()}")
print(f"Symbols with sorry: {df['has_sorry'].sum()}")
print(f"Documentation coverage: {df['has_docstring'].mean():.1%}")

# Save for later
df.to_parquet("lean4_symbols.parquet", index=False)
```

---

## Q7. What static-analysis metrics are available per file?

**File:** `alembic/versions/0004_enriched_metrics.py` adds these columns to `files`:

| Column | Type | Description |
|---|---|---|
| `sorry_count` | `int` | Total `sorry` tokens |
| `admit_count` | `int` | Total `admit` tokens |
| `sorry_lines` | `jsonb` | 1-based line numbers of `sorry` |
| `sorry_in_proof_count` | `int` | Theorems containing `sorry` |
| `theorem_count` | `int` | Theorems + lemmas |
| `proof_completion` | `float` | `(theorems - sorry_proofs) / theorems` |
| `native_decide_count` | `int` | Uses of `native_decide` (fragility signal) |
| `debug_command_count` | `int` | `#check`, `#eval`, `#print`, etc. |
| `noncomputable_count` | `int` | `noncomputable` declarations |
| `instance_count` | `int` | Type class instances |
| `declared_axiom_count` | `int` | Declared axioms |
| `simp_attr_count` | `int` | `@[simp]` attributes |
| `docstring_count` | `int` | Lean docstrings (`/-- ... -/`) |
| `todo_count` | `int` | `-- TODO` comments |
| `mathlib_import_count` | `int` | `import Mathlib.*` lines |

Query for a "code health" dashboard:

```sql
SELECT
    relative_path,
    sorry_count + admit_count AS total_sorry,
    proof_completion,
    debug_command_count,
    native_decide_count,
    docstring_count,
    todo_count
FROM files
WHERE project_id = 1
ORDER BY sorry_count + admit_count DESC;
```

---

## Q8. How do I compute a dependency centrality ranking?

Use the **`dependency_stats`** materialized view:

```sql
SELECT
    s.full_name,
    s.kind,
    ds.fan_in,             -- how many symbols depend on this
    ds.fan_out,            -- how many symbols this depends on
    ds.total_connections,  -- fan_in + fan_out
    ds.fan_out_ratio       -- fan_out / total_connections
FROM dependency_stats ds
JOIN symbols s ON s.id = ds.symbol_id
ORDER BY ds.fan_in DESC
LIMIT 20;
```

**High fan-in** = heavily-relied-upon foundation symbols (high-impact if changed).
**High fan-out** = symbols with many dependencies (complex, potentially fragile).
**fan-out ratio near 1.0** = "leaf" symbols that consume but aren't consumed.

For PageRank-style centrality, export the edge list:

```python
edges = pd.read_sql("""
    SELECT source_symbol_id, target_symbol_id
    FROM dependencies
    WHERE dependency_type = 'direct'
""", conn)

import networkx as nx
G = nx.from_pandas_edgelist(edges, 'source_symbol_id', 'target_symbol_id',
                             create_using=nx.DiGraph)
pr = nx.pagerank(G)
```

---

## Q9. How does the full-text search work and what does it index?

**File:** `alembic/versions/0002_add_indexes.py`

A GIN full-text search index is created on the `symbols` table:

```sql
CREATE INDEX ix_symbols_fts ON symbols USING GIN (
    to_tsvector('english', coalesce(name, '') || ' ' || coalesce(docstring, ''))
);
```

It indexes both the **symbol name** and the **docstring**. Queries use `ts_query`:

```sql
SELECT s.full_name, s.kind, ts_rank(
    to_tsvector('english', coalesce(s.name, '') || ' ' || coalesce(s.docstring, '')),
    plainto_tsquery('english', :query)
) AS rank
FROM symbols s
WHERE to_tsvector('english', coalesce(s.name, '') || ' ' || coalesce(s.docstring, ''))
    @@ plainto_tsquery('english', :query)
AND s.project_id = :project_id
ORDER BY rank DESC
LIMIT :limit OFFSET :offset;
```

The API endpoint is `GET /api/v1/symbols/search?q=...&project_id=1&limit=20&offset=0`.

---

## Q10. How do I set up a reproducible analysis environment?

```bash
# 1. Start the database (and optionally the full stack)
docker compose up -d postgres redis

# 2. Run migrations
DATABASE_URL="postgresql+asyncpg://lean4:lean4_dev_password@localhost:5432/lean4_automata" \
  alembic upgrade head

# 3. Index a Lean project
docker compose up -d app_ingestion worker
curl -X POST http://localhost:8001/admin/index/start \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "1", "root_dir": "/lean-src"}'

# 4. Create a Python virtualenv for analysis
python -m venv .venv && source .venv/bin/activate
pip install pandas psycopg2-binary sqlalchemy networkx matplotlib seaborn jupyterlab pyarrow

# 5. Start Jupyter
jupyter lab --port 8888
```

**Snapshot the database for reproducibility:**

```bash
docker compose exec postgres pg_dump -U lean4 lean4_automata > snapshot_$(date +%Y%m%d).sql
```

**Restore:**

```bash
docker compose exec -T postgres psql -U lean4 lean4_automata < snapshot_20250101.sql
```
