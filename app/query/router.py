from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["query"])


@router.get(
    "/symbols",
    summary="Symbol search (Phase 2)",
    status_code=501,
    response_class=JSONResponse,
)
async def list_symbols() -> dict:
    """Placeholder — full symbol-search logic lands in Phase 2."""
    return JSONResponse(
        content={"message": "Query API — Phase 2"},
        status_code=501,
    )
