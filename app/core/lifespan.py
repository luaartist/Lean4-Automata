from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Optional heavy imports — tolerate absence during early development / testing.
try:
    import asyncpg  # type: ignore[import-untyped]
    _HAS_ASYNCPG = True
except ModuleNotFoundError:
    _HAS_ASYNCPG = False

try:
    import redis.asyncio as aioredis  # type: ignore[import-untyped]
    _HAS_REDIS = True
except ModuleNotFoundError:
    _HAS_REDIS = False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown resources.

    Both the DB pool and Redis client are created on startup and attached to
    ``app.state`` so they are available anywhere a ``Request`` object is
    accessible (``request.app.state.db_pool`` / ``request.app.state.redis``).

    Missing credentials or unreachable services are logged as warnings rather
    than crashing the process — Phase 1 tolerance.
    """
    from app.core.config import settings  # local import avoids circular deps

    logger.info("Starting up — initialising resources …")

    # ── asyncpg connection pool ────────────────────────────────────────────────
    app.state.db_pool = None
    if _HAS_ASYNCPG and settings.DATABASE_URL:
        try:
            app.state.db_pool = await asyncpg.create_pool(
                settings.DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
            logger.info("Database pool created successfully.")
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not create DB pool (non-fatal): %s", exc)
    else:
        logger.warning(
            "Database pool skipped: %s",
            "asyncpg not installed" if not _HAS_ASYNCPG else "DATABASE_URL not set",
        )

    # ── Redis client ──────────────────────────────────────────────────────────
    app.state.redis = None
    if _HAS_REDIS:
        try:
            app.state.redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            # Verify connectivity eagerly so bad URLs surface at startup.
            await app.state.redis.ping()
            logger.info("Redis client connected successfully.")
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not connect to Redis (non-fatal): %s", exc)
            app.state.redis = None
    else:
        logger.warning("Redis client skipped: redis package not installed.")

    logger.info("Startup complete.")

    yield  # ── application runs here ──────────────────────────────────────────

    logger.info("Shutting down — releasing resources …")

    if app.state.db_pool is not None:
        try:
            await app.state.db_pool.close()
            logger.info("Database pool closed.")
        except Exception as exc:  # pragma: no cover
            logger.warning("Error closing DB pool: %s", exc)

    if app.state.redis is not None:
        try:
            await app.state.redis.aclose()
            logger.info("Redis client closed.")
        except Exception as exc:  # pragma: no cover
            logger.warning("Error closing Redis client: %s", exc)

    logger.info("Shut down.")
