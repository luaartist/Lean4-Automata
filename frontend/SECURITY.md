# Frontend Security Notes (Phase 4)

This document records the security posture, the deliberate tradeoffs made
during the Phase 4 hardening pass, and the production deployment requirements
that the application code does **not** enforce on its own.

## 1. Content Security Policy

Configured in `next.config.js` and applied to every route via the
`headers()` hook.

```
default-src 'self';
script-src 'self' 'unsafe-inline';
style-src 'self' 'unsafe-inline';
connect-src 'self' ${NEXT_PUBLIC_API_BASE_URL};
img-src 'self' data:;
font-src 'self';
frame-ancestors 'none';
object-src 'none';
base-uri 'self';
form-action 'self';
```

### Tradeoffs

- **`script-src 'unsafe-inline'`** — Next.js injects small inline bootstrap
  `<script>` blocks for hydration and route data. The proper fix is a
  per-request nonce injected by middleware and propagated to every inline
  script. That refactor is intentionally **out of scope for Phase 4**. A
  follow-up should:
  1. Add a `middleware.ts` that generates a per-request nonce.
  2. Switch to `script-src 'self' 'nonce-<value>' 'strict-dynamic'`.
  3. Drop `'unsafe-inline'` entirely (modern browsers ignore it once a nonce
     is present).
- **`style-src 'unsafe-inline'`** — required by Tailwind / runtime style
  injection. Acceptable, low-risk.
- **`connect-src` includes `NEXT_PUBLIC_API_BASE_URL`** — required for `fetch`
  and the SSE invalidation stream to reach the backend.

## 2. Other security headers

| Header                          | Value                                                         |
| ------------------------------- | ------------------------------------------------------------- |
| `Strict-Transport-Security`     | `max-age=63072000; includeSubDomains; preload`                |
| `X-Content-Type-Options`        | `nosniff`                                                     |
| `X-Frame-Options`               | `DENY`                                                        |
| `Referrer-Policy`               | `strict-origin-when-cross-origin`                             |
| `Permissions-Policy`            | `camera=(), microphone=(), geolocation=(), interest-cohort=()`|
| `Cross-Origin-Opener-Policy`    | `same-origin`                                                 |
| `Cross-Origin-Resource-Policy`  | `same-origin`                                                 |

`X-Frame-Options: DENY` is duplicated by `frame-ancestors 'none'`; both are
emitted for legacy browser coverage.

## 3. JWT / secret hygiene

**Rule: no secrets in the client bundle.** The frontend MUST NOT contain:

- Any hard-coded `JWT_SECRET`, signing key, or admin token.
- Any literal `Authorization: Bearer ...` token.
- Any non-`NEXT_PUBLIC_*` env reference (Next.js inlines those into the
  client bundle by design — only public values belong there).

The Ingestion API (admin) is JWT-protected; tokens are user-supplied at the
admin UI boundary and held only in memory. They are never persisted to
`localStorage` and never embedded at build time. The Query API is anonymous
and requires no credentials.

## 4. XSS posture

- The codebase is free of `dangerouslySetInnerHTML`, `innerHTML`, `eval`, and
  `new Function` (audited Phase 4). React's default escaping is the only
  rendering path for user-derived content.
- All future use of `dangerouslySetInnerHTML` MUST go through DOMPurify and
  MUST be reviewed.

## 5. Subresource Integrity (SRI)

`app/layout.tsx` does not load any external `<script>` or `<link>` from a
third-party origin — Next.js bundles everything from `'self'`. If a future
change adds an external resource, it MUST include `integrity="sha384-..."`
and `crossOrigin="anonymous"`.

## 6. Production rate limiting (Nginx)

The application enforces a defense-in-depth per-IP cap (10 concurrent SSE
connections per worker process), but production deployments **MUST** put
Nginx in front and rely on it as the authoritative limiter. The relevant
snippet, already present in `nginx/nginx.conf`:

```nginx
http {
  # Per-IP zones — sized for ~160k unique IPs each.
  limit_conn_zone   $binary_remote_addr zone=sse_conn:10m;
  limit_req_zone    $binary_remote_addr zone=search_req:10m rate=60r/m;

  server {
    location /api/v1/events/ {
      proxy_buffering off;          # MANDATORY for SSE
      proxy_read_timeout 1h;
      proxy_send_timeout 1h;
      limit_conn sse_conn 10;       # 10 concurrent SSE per IP
      limit_conn_status 429;
      # ... proxy_pass to backend ...
    }

    location /api/v1/symbols/search {
      limit_req zone=search_req burst=20 nodelay;  # 60 r/m + burst 20
      limit_req_status 429;
      # ... proxy_pass to backend ...
    }
  }
}
```

`proxy_buffering off` is **required** for the SSE location — without it,
Nginx will buffer the stream and clients will never receive events in
real-time.

## 7. CORS

Backend (`app/query_api.py`, `app/ingestion_api.py`) reads
`ALLOWED_ORIGINS` (comma-separated) from the environment. Default in dev:
`http://localhost:3000`. `allow_credentials=False` — the client never sends
cookies; admin auth flows the JWT through the `Authorization` header only.

## 8. Environment variables

`frontend/.env.example` lists ONLY `NEXT_PUBLIC_*` variables. Anything
non-public belongs in the backend `.env`, never the frontend.
