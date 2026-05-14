from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.security import require_admin

router = APIRouter(
    prefix="/admin",
    tags=["ingestion"],
    dependencies=[Depends(require_admin)],
)


@router.post(
    "/index/start",
    summary="Start indexing run (Phase 2)",
    status_code=501,
    response_class=JSONResponse,
)
async def index_start(
    _admin: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict:
    """Placeholder — indexing pipeline lands in Phase 2."""
    return JSONResponse(
        content={"message": "Ingestion API — Phase 2"},
        status_code=501,
    )


@router.get(
    "/index/status/{run_id}",
    summary="Query indexing run status (Phase 2)",
    status_code=501,
    response_class=JSONResponse,
)
async def index_status(
    run_id: str,
    _admin: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict:
    """Placeholder — run-status tracking lands in Phase 2."""
    return JSONResponse(
        content={"message": "Ingestion API — Phase 2", "run_id": run_id},
        status_code=501,
    )
