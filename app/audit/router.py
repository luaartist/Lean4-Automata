"""
FastAPI router for Lean proof audit flows.

Provides REST API endpoints for forum-callable audit operations.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
import json
import logging
import sys
import os
import time

from app.core.config import settings

# Add tools to path so we can import forum_handlers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))

from forum_handlers import execute_flow
from mapping_backfill import persist_audit_ticket_result

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditSummaryResponse(BaseModel):
    """Response for audit summary."""

    ActualSrcFiles: int = Field(..., description="Number of .lean files found in src/")
    DocumentedEntries: int = Field(..., description="Number of entries in Lean_Proof_Map.txt")
    CommonFiles: int = Field(..., description="Number of files in both actual and documented")
    MissingInDoc: int = Field(..., description="Files in src/ but not documented")
    MissingInSrc: int = Field(..., description="Files documented but not in src/")
    MismatchCount: int = Field(..., description="Number of files with differing imports")


class MismatchDetail(BaseModel):
    """Details of a single file import mismatch."""

    Actual: List[str] = Field(..., description="Actual imports from source file")
    Documented: List[str] = Field(..., description="Documented imports from Lean_Proof_Map.txt")
    OnlyInActual: List[str] = Field(..., description="Imports in source but not documented")
    OnlyInDoc: List[str] = Field(..., description="Imports documented but not in source")


class FullAuditResponse(BaseModel):
    """Response for full audit with mismatch details."""

    ActualFiles: List[str]
    DocumentedFiles: List[str]
    CommonFiles: List[str]
    MissingInDoc: List[str]
    MissingInSrc: List[str]
    Mismatches: Dict[str, MismatchDetail]


class MillenniumPathResponse(BaseModel):
    """Response for Millennium.lean path analysis."""

    Target: str
    DependencyClosureSize: int
    DependencyClosure: List[str]
    MillenniumCoreClosureSize: int
    MillenniumCoreClosure: List[str]
    AllModulesReachMillennium: bool
    ModulesOffMillenniumPath: List[str]
    PathCountToMillennium: int


class CohesionRankItem(BaseModel):
    """Single module cohesion rank item."""

    File: str
    Imports: int
    Dependents: int
    DocDrift: int
    Score: int


class Ticket(BaseModel):
    """Forum ticket response."""

    ticket_id: Optional[str] = None
    title: str
    description: str
    created_at: str
    type: str
    data: Any
    metadata: Dict[str, Any]


class AuditTicketResponse(BaseModel):
    """Response with ticket and audit data."""

    status: str
    ticket: Ticket
    audit: Optional[AuditSummaryResponse] = None
    ranking: Optional[List[CohesionRankItem]] = None
    paths: Optional[MillenniumPathResponse] = None


@router.get(
    "/summary",
    response_model=AuditTicketResponse,
    summary="Audit summary: file counts and mismatch stats",
)
async def get_audit_summary(
    report_type: Literal["summary", "full"] = Query(
        "summary", description="Type of report"
    ),
) -> AuditTicketResponse:
    """Get audit summary of Lean proof map."""
    result = _execute_flow_with_ticket_persistence(
        "lean_proof_audit", {"report_type": report_type}
    )

    if result.get("status") != "ok":
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    return AuditTicketResponse(**result)


@router.get(
    "/millennium",
    response_model=AuditTicketResponse,
    summary="Dependency paths to Millennium.lean",
)
async def get_millennium_paths(
    target: str = Query("Millennium.lean", description="Target module"),
) -> AuditTicketResponse:
    """Analyze dependency paths to Millennium.lean."""
    result = _execute_flow_with_ticket_persistence(
        "lean_millennium_paths", {"target": target}
    )

    if result.get("status") != "ok":
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    return AuditTicketResponse(**result)


@router.get(
    "/ranking",
    response_model=AuditTicketResponse,
    summary="Module cohesion ranking",
)
async def get_cohesion_ranking(
    limit: int = Query(15, ge=1, le=100, description="Top N modules to return"),
) -> AuditTicketResponse:
    """Get modules ranked by cohesion score."""
    result = _execute_flow_with_ticket_persistence(
        "lean_cohesion_ranking", {"limit": limit}
    )

    if result.get("status") != "ok":
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    return AuditTicketResponse(**result)


@router.post(
    "/execute",
    response_model=Dict[str, Any],
    summary="Execute arbitrary audit flow",
)
async def execute_audit_flow(
    flow_name: str = Query(..., description="Flow name to execute"),
    params: Optional[str] = Query(None, description="JSON parameters"),
) -> Dict[str, Any]:
    """Execute a named audit flow with optional parameters."""
    flow_params = {}
    if params:
        try:
            flow_params = json.loads(params)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=422, detail="Invalid JSON in params parameter"
            )

    result = _execute_flow_with_ticket_persistence(flow_name, flow_params)

    if result.get("status") != "ok":
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    return result


def _execute_flow_with_ticket_persistence(
    flow_name: str, params: Dict[str, Any]
) -> Dict[str, Any]:
    started = time.perf_counter()
    result = execute_flow(flow_name, params)
    duration_ms = int((time.perf_counter() - started) * 1000)

    try:
        project_id = _project_id_from_params_or_env(params)
        persist_audit_ticket_result(
            database_url=settings.DATABASE_URL,
            flow_name=flow_name,
            params=params,
            result=result,
            duration_ms=duration_ms,
            project_id=project_id,
            origin="fastapi",
        )
    except Exception:  # noqa: BLE001
        log.exception("Failed to persist audit ticket for flow=%s", flow_name)

    return result


def _project_id_from_params_or_env(params: Dict[str, Any]) -> int | None:
    raw_project_id = params.get("project_id") or os.getenv("LEAN_PROJECT_ID")
    if raw_project_id in (None, ""):
        return None
    try:
        return int(raw_project_id)
    except (TypeError, ValueError):
        log.warning("Ignoring invalid audit project_id=%r", raw_project_id)
        return None
