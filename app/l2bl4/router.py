from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/l2bl4", tags=["l2bl4"])

BadgeClass = Literal["keepsake", "public", "sovereign"]
IssuanceStatus = Literal["draft", "issued"]


class L2BL4IssueRequest(BaseModel):
    ticket_id: str = Field(..., min_length=1, max_length=64)
    badge_class: BadgeClass = Field("keepsake")
    issuance_status: IssuanceStatus = Field("issued")
    project_id: int | None = Field(None, ge=1)
    subject_type: str = Field("ticket", min_length=1, max_length=64)
    subject_key: str | None = Field(None, min_length=1)
    subject_digest: str | None = Field(None, min_length=1, max_length=128)
    badge_type: str = Field("l2bl4", min_length=1, max_length=64)
    issued_to: str | None = None
    issued_by: str | None = Field("lean4-automata")
    issuer: dict[str, Any] = Field(default_factory=dict)
    recipient: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    composite_sig_hash: str | None = Field(None, max_length=128)
    create_pending_ots: bool | None = Field(
        None,
        description=(
            "When omitted, public and sovereign badges create a pending "
            "OTS row "
            "if no ticket stamp exists."
        ),
    )
    draft_on_contract_error: bool = Field(
        True,
        description=(
            "Store a draft badge instead of failing when an issued badge is "
            "not contract-ready."
        ),
    )
    stamp_provider: str = Field("opentimestamps", min_length=1, max_length=64)


class L2BL4BadgeResponse(BaseModel):
    badge_id: str
    verification_url: str
    ticket_id: str | None
    project_id: int
    badge_class: BadgeClass
    badge_type: str
    issuance_status: str
    subject_type: str
    subject_key: str
    subject_digest: str | None = None
    issued_to: str | None = None
    issued_by: str | None = None
    ots_stamp_id: int | None = None
    bitcoin_block: int | None = None
    composite_sig_hash: str | None = None
    contract_version: str = "l2bl4.v1"
    contract_status: str
    contract_error: str | None = None
    is_currently_valid: bool
    evidence_contract: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    readable_summary: list[str] = Field(default_factory=list)


def _require_db_pool(request: Request) -> Any:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is unavailable")
    return pool


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _subject_digest(payload: dict[str, Any]) -> str:
    canonical = _canonical_json(payload).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return f"sha256:{digest}"


def _badge_id() -> str:
    return f"bdg_{uuid4().hex}"


def _verification_url(request: Request, badge_id: str) -> str:
    return str(request.url_for("verify_l2bl4_badge", badge_id=badge_id))


def _readable_badge_summary(
    row: dict[str, Any],
    *,
    verification_url: str,
) -> list[str]:
    lines = [
        "L2BL4 Badge",
        f"Badge ID: {row.get('badge_id')}",
        f"Ticket ID: {row.get('ticket_id')}",
        f"Class: {row.get('badge_class')}",
        f"Issuance status: {row.get('issuance_status')}",
        f"Contract status: {row.get('contract_status')}",
        f"Valid now: {'yes' if row.get('is_currently_valid') else 'no'}",
    ]
    contract_error = row.get("contract_error")
    if contract_error:
        lines.append(f"Contract blocker: {contract_error}")

    bitcoin_block = row.get("bitcoin_block")
    ots_stamp_id = row.get("ots_stamp_id")
    if bitcoin_block:
        lines.append(f"OTS: confirmed in Bitcoin block {bitcoin_block}")
    elif ots_stamp_id:
        lines.append(f"OTS: pending stamp {ots_stamp_id}")
    else:
        lines.append("OTS: none linked")

    if row.get("badge_class") == "keepsake":
        lines.append(
            "Note: keepsake badges mark successful audit output only; "
            "they are not public OTS attestations."
        )
    elif contract_error == "bitcoin_block_required":
        lines.append(
            "Next step: confirm the pending OTS stamp and record "
            "bitcoin_block before issuing publicly."
        )
    elif contract_error == "composite_sig_hash_required":
        lines.append(
            "Next step: attach a composite signature hash before issuing "
            "a sovereign badge."
        )
    elif contract_error:
        lines.append(
            "Next step: resolve the listed contract blocker and refresh "
            "the badge."
        )

    lines.append(f"Verify URL: {verification_url}")
    return lines


async def _fetch_ticket_contract(
    conn: Any,
    *,
    ticket_id: str,
    badge_class: BadgeClass,
    composite_sig_hash: str | None,
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        SELECT
            at.ticket_id,
            at.project_id,
            at.status,
            c.audit_success,
            c.keepsake_ready,
            c.public_ready,
            c.has_ticket_ots_stamp,
            c.has_confirmed_ots_stamp,
            c.ots_stamp_id,
            c.bitcoin_block,
            c.evidence_contract,
            l2bl4_badge_contract_error(at.ticket_id, $2, $3) AS contract_error
        FROM audit_tickets at
        LEFT JOIN v_l2bl4_ticket_evidence_contract c
            ON c.ticket_id = at.ticket_id
        WHERE at.ticket_id = $1
        """,
        ticket_id,
        badge_class,
        composite_sig_hash,
    )
    if row is None:
        return None
    payload = dict(row)
    payload["evidence_contract"] = _json_value(
        payload.get("evidence_contract")
    )
    return payload


async def _create_pending_ots_stamp(
    conn: Any,
    *,
    project_id: int,
    ticket_id: str,
    subject_type: str,
    subject_key: str,
    subject_digest: str,
    stamp_provider: str,
    evidence_contract: dict[str, Any] | None,
    badge_class: BadgeClass,
) -> int:
    stamp_payload = {
        "contract_version": "l2bl4.v1",
        "created_by": "l2bl4_issue_endpoint",
        "pending_only": True,
        "badge_class": badge_class,
        "evidence_contract": evidence_contract or {},
    }
    row = await conn.fetchrow(
        """
        INSERT INTO ots_stamps
            (project_id, ticket_id, subject_type, subject_key, subject_digest,
             stamp_provider, stamp_payload, verification_status)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 'pending')
        RETURNING id
        """,
        project_id,
        ticket_id,
        subject_type,
        subject_key,
        subject_digest,
        stamp_provider,
        json.dumps(stamp_payload),
    )
    return int(row["id"])


async def _insert_badge(
    conn: Any,
    *,
    badge_id: str,
    project_id: int,
    ticket_id: str,
    subject_type: str,
    subject_key: str,
    subject_digest: str | None,
    badge_type: str,
    issuance_status: str,
    issued_to: str | None,
    issued_by: str | None,
    evidence: dict[str, Any],
    metadata: dict[str, Any],
    badge_class: BadgeClass,
    ots_stamp_id: int | None,
    composite_sig_hash: str | None,
) -> None:
    await conn.fetchrow(
        """
        INSERT INTO l2bl4_badges
            (badge_id, project_id, ticket_id, subject_type, subject_key,
             subject_digest, badge_type, issuance_status, issued_to, issued_by,
             evidence, metadata, badge_class, ots_stamp_id, composite_sig_hash)
        VALUES ($1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10,
                $11::jsonb, $12::jsonb, $13, $14, $15)
        RETURNING badge_id
        """,
        badge_id,
        project_id,
        ticket_id,
        subject_type,
        subject_key,
        subject_digest,
        badge_type,
        issuance_status,
        issued_to,
        issued_by,
        json.dumps(evidence),
        json.dumps(metadata),
        badge_class,
        ots_stamp_id,
        composite_sig_hash,
    )


async def _fetch_badge_validity(
    conn: Any,
    *,
    badge_id: str,
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """
        SELECT
            v.badge_id,
            v.project_id,
            v.ticket_id,
            v.subject_type,
            v.subject_key,
            v.subject_digest,
            v.badge_type,
            v.badge_class,
            v.issuance_status,
            v.ots_stamp_id,
            v.bitcoin_block,
            v.composite_sig_hash,
            v.contract_version,
            v.contract_error,
            v.contract_status,
            v.is_currently_valid,
            v.evidence_contract,
            b.issued_to,
            b.issued_by,
            b.evidence,
            b.metadata
        FROM v_l2bl4_badge_validity v
        JOIN l2bl4_badges b ON b.id = v.id
        WHERE v.badge_id = $1
        """,
        badge_id,
    )
    if row is None:
        return None
    payload = dict(row)
    for key in ("evidence_contract", "evidence", "metadata"):
        payload[key] = _json_value(payload.get(key))
    return payload


def _contract_conflict_detail(
    *,
    ticket_id: str,
    badge_class: BadgeClass,
    contract_error: str,
    evidence_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "ticket_id": ticket_id,
        "badge_class": badge_class,
        "contract_error": contract_error,
        "evidence_contract": evidence_contract,
    }


@router.post(
    "/issue",
    response_model=L2BL4BadgeResponse,
    summary="Issue or stage an L2BL4 badge from an audit ticket",
)
async def issue_l2bl4_badge(
    payload: L2BL4IssueRequest,
    request: Request,
    response: Response,
) -> L2BL4BadgeResponse:
    pool = _require_db_pool(request)
    composite_sig_hash = _clean_optional_text(payload.composite_sig_hash)
    subject_key = payload.subject_key or payload.ticket_id
    should_create_pending_ots = (
        payload.create_pending_ots
        if payload.create_pending_ots is not None
        else payload.badge_class in {"public", "sovereign"}
    )
    badge_id = _badge_id()
    created_pending_ots = False

    async with pool.acquire() as conn:
        async with conn.transaction():
            contract = await _fetch_ticket_contract(
                conn,
                ticket_id=payload.ticket_id,
                badge_class=payload.badge_class,
                composite_sig_hash=composite_sig_hash,
            )
            if contract is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Audit ticket not found: {payload.ticket_id}",
                )

            ticket_failed = contract.get("status") != "success"
            contract_failed = (
                contract.get("contract_error") == "audit_ticket_must_succeed"
            )
            if ticket_failed or contract_failed:
                raise HTTPException(
                    status_code=409,
                    detail=_contract_conflict_detail(
                        ticket_id=payload.ticket_id,
                        badge_class=payload.badge_class,
                        contract_error="audit_ticket_must_succeed",
                        evidence_contract=contract.get("evidence_contract"),
                    ),
                )

            ticket_project_id = contract.get("project_id")
            project_mismatch = (
                payload.project_id is not None
                and ticket_project_id is not None
                and payload.project_id != ticket_project_id
            )
            if project_mismatch:
                raise HTTPException(
                    status_code=422,
                    detail="project_id does not match audit ticket",
                )
            project_id = payload.project_id or ticket_project_id
            if project_id is None:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "project_id is required when the audit ticket has no "
                        "project_id"
                    ),
                )

            evidence_contract = contract.get("evidence_contract")
            subject_digest = payload.subject_digest or _subject_digest(
                {
                    "ticket_id": payload.ticket_id,
                    "subject_type": payload.subject_type,
                    "subject_key": subject_key,
                    "evidence_contract": evidence_contract or {},
                }
            )

            ots_stamp_id = contract.get("ots_stamp_id")
            needs_pending_ots = (
                should_create_pending_ots
                and not contract.get("has_ticket_ots_stamp")
            )
            if needs_pending_ots:
                ots_stamp_id = await _create_pending_ots_stamp(
                    conn,
                    project_id=int(project_id),
                    ticket_id=payload.ticket_id,
                    subject_type=payload.subject_type,
                    subject_key=subject_key,
                    subject_digest=subject_digest,
                    stamp_provider=payload.stamp_provider,
                    evidence_contract=evidence_contract,
                    badge_class=payload.badge_class,
                )
                created_pending_ots = True
                contract = await _fetch_ticket_contract(
                    conn,
                    ticket_id=payload.ticket_id,
                    badge_class=payload.badge_class,
                    composite_sig_hash=composite_sig_hash,
                )
                if contract is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Audit ticket not found: {payload.ticket_id}",
                    )
                evidence_contract = contract.get("evidence_contract")

            contract_error = contract.get("contract_error")
            issuance_status = payload.issuance_status
            if issuance_status == "issued" and contract_error is not None:
                if not payload.draft_on_contract_error:
                    raise HTTPException(
                        status_code=409,
                        detail=_contract_conflict_detail(
                            ticket_id=payload.ticket_id,
                            badge_class=payload.badge_class,
                            contract_error=str(contract_error),
                            evidence_contract=evidence_contract,
                        ),
                    )
                issuance_status = "draft"

            evidence = {
                "contract_version": "l2bl4.v1",
                "ticket_id": payload.ticket_id,
                "badge_class": payload.badge_class,
                "evidence_contract": evidence_contract or {},
                "user_evidence": payload.evidence,
            }
            metadata = {
                **payload.metadata,
                "issuer": payload.issuer,
                "recipient": payload.recipient,
                "requested_issuance_status": payload.issuance_status,
                "created_pending_ots": created_pending_ots,
            }

            try:
                await _insert_badge(
                    conn,
                    badge_id=badge_id,
                    project_id=int(project_id),
                    ticket_id=payload.ticket_id,
                    subject_type=payload.subject_type,
                    subject_key=subject_key,
                    subject_digest=subject_digest,
                    badge_type=payload.badge_type,
                    issuance_status=issuance_status,
                    issued_to=payload.issued_to,
                    issued_by=payload.issued_by,
                    evidence=evidence,
                    metadata=metadata,
                    badge_class=payload.badge_class,
                    ots_stamp_id=ots_stamp_id,
                    composite_sig_hash=composite_sig_hash,
                )
            except Exception as exc:  # noqa: BLE001
                if "L2BL4 badge contract violation" in str(exc):
                    log.info("L2BL4 badge trigger rejected insert: %s", exc)
                    raise HTTPException(
                        status_code=409,
                        detail=_contract_conflict_detail(
                            ticket_id=payload.ticket_id,
                            badge_class=payload.badge_class,
                            contract_error=str(contract_error or exc),
                            evidence_contract=evidence_contract,
                        ),
                    ) from exc
                raise

            row = await _fetch_badge_validity(conn, badge_id=badge_id)

    if row is None:
        raise HTTPException(
            status_code=500,
            detail="Issued badge could not be loaded",
        )

    response.status_code = 201 if row["issuance_status"] == "issued" else 202
    verification_url = _verification_url(request, badge_id)
    return L2BL4BadgeResponse(
        **row,
        verification_url=verification_url,
        readable_summary=_readable_badge_summary(
            row,
            verification_url=verification_url,
        ),
    )


@router.get(
    "/badges/{badge_id}",
    response_model=L2BL4BadgeResponse,
    summary="Get L2BL4 badge issuance and contract status",
)
async def get_l2bl4_badge(
    request: Request,
    badge_id: str,
) -> L2BL4BadgeResponse:
    pool = _require_db_pool(request)
    async with pool.acquire() as conn:
        row = await _fetch_badge_validity(conn, badge_id=badge_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Badge not found: {badge_id}",
        )
    verification_url = _verification_url(request, badge_id)
    return L2BL4BadgeResponse(
        **row,
        verification_url=verification_url,
        readable_summary=_readable_badge_summary(
            row,
            verification_url=verification_url,
        ),
    )


@router.get(
    "/verify/{badge_id}",
    response_model=L2BL4BadgeResponse,
    summary="Verify L2BL4 badge contract status",
    name="verify_l2bl4_badge",
)
async def verify_l2bl4_badge(
    request: Request,
    badge_id: str,
) -> L2BL4BadgeResponse:
    return await get_l2bl4_badge(request, badge_id)
