"""Admin ingestion router.

Phase 2: ``POST /admin/index/start`` enqueues a Celery ``full_scan`` task
and ``GET /admin/index/status/{task_id}`` reports its state.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import require_admin
from workers.celery_app import celery_app
from workers.tasks import full_scan_task

router = APIRouter(
    prefix="/admin",
    tags=["ingestion"],
    dependencies=[Depends(require_admin)],
)


class IndexStartRequest(BaseModel):
    """Body of ``POST /admin/index/start``."""

    project_id: str = Field(
        ...,
        description="Integer project id (string-encoded for forward-compat with UUIDs).",
    )
    root_dir: str = Field(..., description="Filesystem path to the Lean source root.")


class IndexStartResponse(BaseModel):
    task_id: str
    status: str


class IndexStatusResponse(BaseModel):
    task_id: str
    state: str
    result: dict | None = None
    error: str | None = None


@router.post(
    "/index/start",
    status_code=202,
    response_model=IndexStartResponse,
    summary="Enqueue a full-scan indexing task",
)
async def start_index(req: IndexStartRequest) -> IndexStartResponse:
    """Enqueue ``lean4.full_scan`` on Celery and return its task id."""
    result = full_scan_task.delay(req.project_id, req.root_dir)
    return IndexStartResponse(task_id=result.id, status="queued")


@router.get(
    "/index/status/{task_id}",
    response_model=IndexStatusResponse,
    summary="Poll the state of an enqueued indexing task",
)
async def index_status(task_id: str) -> IndexStatusResponse:
    """Return the current Celery state and (if available) the result/error."""
    res = celery_app.AsyncResult(task_id)
    return IndexStatusResponse(
        task_id=task_id,
        state=res.state,
        result=res.result if res.successful() else None,
        error=str(res.info) if res.failed() else None,
    )
