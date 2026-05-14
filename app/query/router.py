from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from db.queries import get_module_complexity, get_reverse_deps, get_transitive_deps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])

_CACHE_TTL_SECONDS = 3600
_INVALIDATION_CHANNEL = "lean4:invalidate"
_MODULE_ORDER_FIELDS = {
    "total_symbols",
    "theorem_count",
    "def_count",
    "avg_symbol_length_lines",
    "documentation_coverage_pct",
}


class SymbolLookupResponse(BaseModel):
    id: int
    file_id: int
    project_id: int
    name: str
    full_name: str
    kind: str
    line_start: int
    line_end: int
    signature: str | None = None
    docstring: str | None = None


class SymbolSearchItem(BaseModel):
    id: int
    file_id: int
    project_id: int
    name: str
    full_name: str
    kind: str
    rank: float = Field(..., description="PostgreSQL full-text rank")


class SymbolSearchResponse(BaseModel):
    q: str
    project_id: int
    limit: int
    offset: int
    total: int
    items: list[SymbolSearchItem]


class DependencyNode(BaseModel):
    symbol_id: int
    full_name: str
    name: str
    kind: str
    depth: int
    path: list[int]
    dependency_type: str | None = None


class DependencyGraphResponse(BaseModel):
    full_name: str
    max_depth: int
    transitive: list[DependencyNode]
    reverse: list[DependencyNode]


class ModuleMetricItem(BaseModel):
    file_id: int
    module_name: str
    total_symbols: int
    theorem_count: int
    def_count: int
    instance_count: int
    inductive_count: int
    structure_count: int
    class_count: int
    avg_symbol_length_lines: float | None = None
    max_symbol_length_lines: int | None = None
    public_symbols: int
    deprecated_symbols: int
    documented_symbols: int
    documentation_coverage_pct: float


class ModuleMetricsResponse(BaseModel):
    project_id: int
    order_by: str
    items: list[ModuleMetricItem]


class QueryCache:
    """Cache-aside helper with graceful degradation on Redis failures."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    async def get_json(self, key: str) -> Any | None:
        if self._redis is None:
            return None
        try:
            raw = await asyncio.wait_for(self._redis.get(key), timeout=0.5)
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache read failed for key=%s: %s", key, exc)
            return None

    async def set_json(self, key: str, payload: Any, ttl_seconds: int = _CACHE_TTL_SECONDS) -> None:
        if self._redis is None:
            return
        try:
            await asyncio.wait_for(
                self._redis.set(key, json.dumps(payload), ex=ttl_seconds),
                timeout=0.5,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cache write failed for key=%s: %s", key, exc)


def _require_db_pool(request: Request) -> Any:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is unavailable")
    return pool


def _cache(request: Request) -> QueryCache:
    return QueryCache(getattr(request.app.state, "redis", None))


@router.get(
    "/symbols/search",
    response_model=SymbolSearchResponse,
    summary="Full-text symbol search",
)
async def search_symbols(
    request: Request,
    q: str = Query(..., min_length=1, max_length=512),
    project_id: int = Query(..., ge=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> SymbolSearchResponse:
    cache_key = f"lean4:cache:file:{project_id}:search:{q}:{limit}:{offset}"
    cache = _cache(request)
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return SymbolSearchResponse.model_validate(cached)

    pool = _require_db_pool(request)
    query = """
        SELECT
            id,
            file_id,
            project_id,
            name,
            full_name,
            kind::text AS kind,
            ts_rank(
                to_tsvector('english', coalesce(docstring, '') || ' ' || coalesce(name, '')),
                plainto_tsquery('english', $1)
            ) AS rank,
            COUNT(*) OVER() AS total_count
        FROM symbols
        WHERE
            project_id = $2
            AND to_tsvector('english', coalesce(docstring, '') || ' ' || coalesce(name, ''))
                @@ plainto_tsquery('english', $1)
        ORDER BY rank DESC, full_name
        LIMIT $3 OFFSET $4
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, q, project_id, limit, offset)

    items = [SymbolSearchItem(**dict(row)) for row in rows]
    total = int(rows[0]["total_count"]) if rows else 0
    payload = SymbolSearchResponse(
        q=q,
        project_id=project_id,
        limit=limit,
        offset=offset,
        total=total,
        items=items,
    )
    await cache.set_json(cache_key, payload.model_dump(mode="json"))
    return payload


@router.get(
    "/symbols/{full_name:path}",
    response_model=SymbolLookupResponse,
    summary="Symbol lookup by fully-qualified name",
)
async def get_symbol(request: Request, full_name: str) -> SymbolLookupResponse:
    cache = _cache(request)
    lookup_key = f"lean4:cache:symbol:{full_name}"
    cached = await cache.get_json(lookup_key)
    if cached is not None:
        return SymbolLookupResponse.model_validate(cached)

    pool = _require_db_pool(request)
    query = """
        SELECT
            id,
            file_id,
            project_id,
            name,
            full_name,
            kind::text AS kind,
            line_start,
            line_end,
            signature,
            docstring
        FROM symbols
        WHERE full_name = $1
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, full_name)

    if row is None:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {full_name}")

    payload = SymbolLookupResponse(**dict(row))
    file_scoped_key = f"lean4:cache:file:{payload.file_id}:symbol:{full_name}"
    dump = payload.model_dump(mode="json")
    await cache.set_json(lookup_key, dump)
    await cache.set_json(file_scoped_key, dump)
    return payload


@router.get(
    "/dependencies/graph",
    response_model=DependencyGraphResponse,
    summary="Dependency graph (transitive + reverse)",
)
async def dependencies_graph(
    request: Request,
    full_name: str = Query(..., min_length=1),
    max_depth: int = Query(5, ge=1, le=20),
) -> DependencyGraphResponse:
    cache_key = f"lean4:cache:deps:{full_name}:{max_depth}"
    cache = _cache(request)
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return DependencyGraphResponse.model_validate(cached)

    pool = _require_db_pool(request)
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM symbols WHERE full_name = $1)",
            full_name,
        )
        if not exists:
            raise HTTPException(status_code=404, detail=f"Symbol not found: {full_name}")

        transitive = await get_transitive_deps(conn, full_name, max_depth=max_depth)
        reverse = await get_reverse_deps(conn, full_name, max_depth=max_depth)

    payload = DependencyGraphResponse(
        full_name=full_name,
        max_depth=max_depth,
        transitive=[DependencyNode(**row) for row in transitive],
        reverse=[DependencyNode(**row) for row in reverse],
    )
    await cache.set_json(cache_key, payload.model_dump(mode="json"))
    return payload


@router.get(
    "/modules/metrics",
    response_model=ModuleMetricsResponse,
    summary="Module-level aggregated metrics",
)
async def module_metrics(
    request: Request,
    project_id: int = Query(..., ge=1),
    order_by: Literal[
        "total_symbols",
        "theorem_count",
        "def_count",
        "avg_symbol_length_lines",
        "documentation_coverage_pct",
    ] = "total_symbols",
) -> ModuleMetricsResponse:
    if order_by not in _MODULE_ORDER_FIELDS:
        raise HTTPException(status_code=422, detail=f"Unsupported order_by: {order_by}")

    cache_key = f"lean4:cache:file:{project_id}:module_metrics:{order_by}"
    cache = _cache(request)
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return ModuleMetricsResponse.model_validate(cached)

    pool = _require_db_pool(request)
    async with pool.acquire() as conn:
        project_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM projects WHERE id = $1)",
            project_id,
        )
        if not project_exists:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        rows = await get_module_complexity(conn, project_id=project_id, order_by=order_by)

    payload = ModuleMetricsResponse(
        project_id=project_id,
        order_by=order_by,
        items=[ModuleMetricItem(**row) for row in rows],
    )
    await cache.set_json(cache_key, payload.model_dump(mode="json"))
    return payload


@router.get(
    "/events/invalidation",
    summary="SSE invalidation stream",
    response_model=None,
)
async def invalidation_events(request: Request) -> Any:
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "Redis unavailable: invalidation stream requires Redis"},
        )

    async def event_stream():
        pubsub = redis_client.pubsub()
        heartbeat_at = time.monotonic()
        try:
            await pubsub.subscribe(_INVALIDATION_CHANNEL)
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                now = time.monotonic()
                if message and message.get("type") == "message":
                    raw = message.get("data", "")
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", errors="replace")
                    yield f"event: invalidation\ndata: {raw}\n\n"
                    heartbeat_at = now
                elif now - heartbeat_at >= 15:
                    yield ": heartbeat\n\n"
                    heartbeat_at = now
        finally:
            try:
                await pubsub.unsubscribe(_INVALIDATION_CHANNEL)
            except Exception:  # noqa: BLE001
                logger.debug("SSE pubsub unsubscribe failed", exc_info=True)
            try:
                await pubsub.aclose()
            except Exception:  # noqa: BLE001
                logger.debug("SSE pubsub close failed", exc_info=True)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
