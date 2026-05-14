# Resilience Patterns

## Retry Policy

| Operation | Max retries | Back-off | Jitter |
|-----------|-------------|----------|--------|
| DB query (transient) | 3 | Exponential (100 ms base) | ±50 ms |
| Redis GET/SET | 2 | Fixed 50 ms | – |
| Celery task | 3 | Exponential (1 s base) | ±500 ms |
| Mathlib API call | 2 | Exponential (500 ms base) | ±200 ms |

Retries use **idempotent operations only**. Writes that have already
committed are not re-attempted; instead the Celery task is marked failed
and surfaced in `index_runs.errors`.

## Circuit Breaker

A lightweight circuit breaker wraps calls to external services (Mathlib
docs API, Wolfram Engine):

```
States:  CLOSED ──(N failures)──▶ OPEN ──(timeout)──▶ HALF-OPEN
                                    │                       │
                                    │◀──(probe fails)───────┘
                                    │
                                    └──(probe succeeds)──▶ CLOSED
```

| Parameter | Value |
|-----------|-------|
| Failure threshold (`N`) | 5 consecutive failures |
| Open timeout | 30 s |
| Half-open probes | 1 request |

When the circuit is **open**, calls return a cached fallback or a
`503 Service Unavailable` with `Retry-After` header.

## Back-Pressure

- **Celery queue depth** is monitored; if > 1 000 pending tasks, the
  Ingestion API returns `429 Too Many Requests` until the queue drains.
- **asyncpg pool exhaustion** raises `asyncpg.exceptions.TooManyConnectionsError`;
  the API returns `503` and a `Retry-After: 5` header.

## Graceful Degradation

| Component down | Behaviour |
|---------------|-----------|
| Redis | Queries fall through to PostgreSQL; latency increases but no errors |
| Celery queue | Ingestion requests queued in-memory; manual retry if lost |
| File Watcher | Incremental updates pause; next full scan catches up |
| Wolfram Engine | Enrichment skipped; symbol data remains complete otherwise |

## Transaction Safety

- Full-scan batches use a **single transaction** per batch; a parse error
  in one file rolls back only that batch, not the entire scan.
- Incremental updates use `SAVEPOINT` for per-file atomicity within a
  larger watcher loop.

## Timeout Hierarchy

```
Client ──(30 s)──▶ LB ──(25 s)──▶ API ──(20 s)──▶ DB
```

Each layer's timeout is strictly shorter than its caller's, preventing
zombie connections.
