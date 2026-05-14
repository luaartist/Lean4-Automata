# Development Workflow

## Local Setup

```bash
# 1. Clone and install
git clone <repo-url> && cd lean-mapping
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Start infrastructure
docker compose up -d postgres redis

# 3. Run migrations
alembic upgrade head

# 4. Seed sample data (optional)
python scripts/seed_sample_project.py --project mathlib_subset

# 5. Start API
uvicorn app.query:app --reload --port 8000

# 6. Start frontend
cd frontend && npm install && npm run dev
```

## Branching Model

| Branch | Purpose | Merge target |
|--------|---------|-------------|
| `main` | Stable release | – |
| `develop` | Integration | `main` via release PR |
| `feat/<ticket>` | Feature work | `develop` |
| `fix/<ticket>` | Bug fixes | `develop` or `main` (hotfix) |

## CI Pipeline (GitHub Actions)

```
PR opened
  ├── Lint (ruff, mypy, eslint, tsc)
  ├── Unit tests (pytest, vitest)
  ├── Integration tests (testcontainers: PG + Redis)
  ├── Security scan (pip-audit, npm audit)
  └── Schema migration test (Alembic against seeded DB)

On merge to main
  ├── Build Docker images
  ├── Push to registry
  └── Deploy to staging
```

### Quality Gates

| Gate | Tool | Threshold |
|------|------|-----------|
| Python lint | Ruff | Zero errors |
| Python types | mypy (strict) | Zero errors |
| Python tests | pytest | 80 % line coverage |
| JS lint | ESLint | Zero errors |
| JS types | tsc --noEmit | Zero errors |
| JS tests | Vitest | 80 % line coverage |
| Dependency CVEs | pip-audit / npm audit | Zero high/critical |

## Code Style

- **Python**: Ruff replaces Black + isort + Flake8.
  Config in `pyproject.toml` under `[tool.ruff]`.
- **TypeScript**: ESLint + Prettier.
  Config in `.eslintrc.cjs` and `.prettierrc`.
- **SQL migrations**: one file per migration, named
  `YYYYMMDD_HHMMSS_<description>.py`.

## Pre-Commit Hooks

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [{ id: ruff }, { id: ruff-format }]
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks: [{ id: mypy }]
```

## Testing Strategy

| Level | Scope | Tooling |
|-------|-------|---------|
| Unit | Pure functions, transformers | pytest / vitest |
| Integration | API ↔ DB, cache, queue | testcontainers |
| E2E | Full user flows | Playwright |
| Load | Sustained throughput | Locust |
