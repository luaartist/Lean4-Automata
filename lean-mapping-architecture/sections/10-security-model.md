# Security Model

## Authentication Context

| Endpoint group | Auth requirement |
|---------------|-----------------|
| Query / Search / Viz | None (public, rate-limited) |
| Ingestion / Admin | JWT bearer token (HS256) |
| Health | None |

### JWT Structure

```json
{
  "sub": "admin@lean-mapping",
  "role": "admin",
  "iat": 1720000000,
  "exp": 1720003600
}
```

Tokens are validated by middleware on every Admin/Ingestion request.
Signing key is loaded from `LEAN_MAP_JWT_SECRET` environment variable—
**never committed to source**.

### Auth Middleware (FastAPI)

```python
async def require_admin(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    payload = jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"])
    if payload.get("role") != "admin":
        raise HTTPException(403, "Insufficient privileges")
    return payload
```

## Rate Limiting

| Tier | Limit | Scope |
|------|-------|-------|
| Anonymous | 60 req / min | Per IP |
| Authenticated | 600 req / min | Per JWT `sub` |

Implemented via Redis sliding-window counter in the load balancer or
FastAPI middleware.

## Input Validation

- All path/query parameters validated by Pydantic v2 models.
- `full_name` parameter: regex `^[A-Za-z_][A-Za-z0-9_.]*$` (prevents
  injection via crafted symbol names).
- `depth` clamped to `[1, 10]`; `limit` to `[1, 100]`.

## SQL Injection Prevention

All queries use **parameterised statements** (`$1`, `$2`, …) via `asyncpg`.
No string interpolation is used in any SQL path.

## Secrets Management

| Secret | Storage |
|--------|---------|
| `DATABASE_URL` | Environment variable |
| `REDIS_URL` | Environment variable |
| `LEAN_MAP_JWT_SECRET` | Environment variable |
| Wolfram licence key | *[Optional]* mounted file |

In Kubernetes, secrets are stored in `Secret` objects and mounted as env
vars or volume files—never baked into images.

## Network Segmentation

- Admin API (`:8002`) is **not** exposed to the public load balancer;
  accessible only from the internal cluster network.
- PostgreSQL and Redis listen only on the private subnet.
- Egress is restricted to Mathlib docs API and (optionally) Wolfram Cloud.

## Dependency Scanning

CI runs `pip-audit` and `npm audit` on every PR to catch known CVEs in
transitive dependencies (see §14).
