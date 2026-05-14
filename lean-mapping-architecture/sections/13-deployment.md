# Deployment

## Container Architecture

Each service is packaged as a Docker image:

| Image | Base | Ports | Notes |
|-------|------|-------|-------|
| `lean-map-query` | `python:3.12-slim` | 8000 | Read-only API |
| `lean-map-ingest` | `python:3.12-slim` | 8001 | Ingestion API |
| `lean-map-admin` | `python:3.12-slim` | 8002 | Internal only |
| `lean-map-worker` | `python:3.12-slim` | – | Celery workers |
| `lean-map-watcher` | `python:3.12-slim` | – | File watcher daemon |
| `lean-map-frontend` | `node:20-slim` | 3000 | Next.js |
| `postgres` | `postgres:16-alpine` | 5432 | Primary DB |
| `redis` | `redis:7-alpine` | 6379 | Cache + broker |

## Docker Compose (Development)

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: lean_map
      POSTGRES_USER: lean
      POSTGRES_PASSWORD: dev_only
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  query-api:
    build: { context: ., dockerfile: Dockerfile.api }
    command: uvicorn app.query:app --host 0.0.0.0 --port 8000
    environment:
      DATABASE_URL: postgresql://lean:dev_only@postgres/lean_map
      REDIS_URL: redis://redis:6379/0
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
```

## Kubernetes (Production)

Recommended resources:

| Workload | Replicas | CPU req/limit | Memory req/limit |
|----------|----------|--------------|-----------------|
| Query API | 3 | 250 m / 1 | 256 Mi / 512 Mi |
| Ingestion API | 2 | 250 m / 1 | 256 Mi / 512 Mi |
| Worker | 4 | 500 m / 2 | 512 Mi / 1 Gi |
| File Watcher | 1 per project | 100 m / 500 m | 128 Mi / 256 Mi |
| Frontend | 2 | 200 m / 500 m | 256 Mi / 512 Mi |

### Zero-Downtime Deploy

- **Rolling update** with `maxUnavailable: 0`, `maxSurge: 1`.
- Readiness probe: `GET /health` returns 200 when DB pool is warm.
- Liveness probe: same endpoint, 30 s initial delay.

### Database Migrations

Run as a Kubernetes **Job** before the main deployment:

```bash
alembic upgrade head
```

Migrations are backwards-compatible for one release cycle so old pods
can still serve during rollout.

## Secrets

| Secret | K8s object | Mount |
|--------|-----------|-------|
| `DATABASE_URL` | `Secret/lean-map-db` | Env var |
| `REDIS_URL` | `Secret/lean-map-redis` | Env var |
| `JWT_SECRET` | `Secret/lean-map-jwt` | Env var |

## Backup

- **PostgreSQL**: daily `pg_dump` to object storage; WAL archiving for
  point-in-time recovery.
- **Redis**: no backup needed (ephemeral cache).
