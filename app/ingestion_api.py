from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.middleware import request_id_middleware
from app.ingestion.router import router as ingestion_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

# ── Application factory ───────────────────────────────────────────────────────

app = FastAPI(
    title="Lean4 Ingestion API",
    description="Admin-only indexing and ingestion interface for the Lean4 Automata project.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if settings.ENV == "production" else "/docs",
    redoc_url=None if settings.ENV == "production" else "/redoc",
    openapi_url=None if settings.ENV == "production" else "/openapi.json",
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.middleware("http")(request_id_middleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(ingestion_router)


# ── Health endpoints ──────────────────────────────────────────────────────────

@app.get("/health/live", tags=["health"], summary="Liveness probe")
async def liveness() -> dict:
    """Returns 200 immediately — confirms the process is running."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"], summary="Readiness probe")
async def readiness(request: Request) -> JSONResponse:
    """Returns 200 only when DB and Redis are reachable."""
    db_ok: bool = False
    redis_ok: bool = False

    if request.app.state.db_pool is not None:
        try:
            async with request.app.state.db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_ok = True
        except Exception:
            pass

    if request.app.state.redis is not None:
        try:
            await request.app.state.redis.ping()
            redis_ok = True
        except Exception:
            pass

    status_code = 200 if (db_ok and redis_ok) else 503
    return JSONResponse(
        content={"db": db_ok, "redis": redis_ok},
        status_code=status_code,
    )
