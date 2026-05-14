# Infrastructure Bootstrap (Phase 1)

This stack provides baseline local infrastructure:

- **PostgreSQL 18.4** with persistent storage and init scripts
- **Redis 8.0** with append-only persistence enabled
- **Nginx 1.30.1** reverse proxy configured for upstream `app:8000`

## Quick start

1. Copy environment defaults:

```bash
cp .env.example .env
```

2. Start infrastructure services:

```bash
docker compose up -d
```

3. Check status and health:

```bash
docker compose ps
```

4. Validate rendered compose configuration:

```bash
docker compose config
```

5. Stop services:

```bash
docker compose down
```

## Service URLs / endpoints

- Nginx reverse proxy: `http://localhost:${NGINX_HTTP_PORT:-8080}`
- PostgreSQL: `localhost:${POSTGRES_PORT:-5432}` (`${POSTGRES_DB:-lean4_automata}`)
- Redis: `localhost:${REDIS_PORT:-6379}`

## Notes / caveats

- Postgres and Redis data are persisted via named Docker volumes (`postgres_data`, `redis_data`).
- Nginx forwards traffic to `app:8000`; this Phase 1 stack does **not** include the app container yet.
- Baseline Postgres extensions are initialized from `postgres/init/`.
