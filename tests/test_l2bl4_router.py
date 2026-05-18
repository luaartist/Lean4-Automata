from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.l2bl4.router import router
from app.query_api import app as query_api_app


class _AcquireCtx:
    def __init__(self, conn: "FakeL2BL4Conn") -> None:
        self._conn = conn

    async def __aenter__(self) -> "FakeL2BL4Conn":
        return self._conn

    async def __aexit__(
        self,
        exc_type,  # noqa: ANN001
        exc,  # noqa: ANN001
        tb,  # noqa: ANN001
    ) -> None:
        return None


class _TransactionCtx:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type,  # noqa: ANN001
        exc,  # noqa: ANN001
        tb,  # noqa: ANN001
    ) -> None:
        return None


class FakePool:
    def __init__(self, conn: "FakeL2BL4Conn") -> None:
        self._conn = conn

    def acquire(self) -> _AcquireCtx:
        return _AcquireCtx(self._conn)


class FakeL2BL4Conn:
    def __init__(self, contract_rows: list[dict[str, Any]]) -> None:
        self.contract_rows = contract_rows
        self.contract_calls = 0
        self.ots_insert_args: tuple[Any, ...] | None = None
        self.badge_insert_args: tuple[Any, ...] | None = None
        self.badge_id: str | None = None
        self.latest_contract: dict[str, Any] | None = None

    def transaction(self) -> _TransactionCtx:
        return _TransactionCtx()

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        if "FROM audit_tickets at" in query:
            if self.contract_calls >= len(self.contract_rows):
                raise AssertionError("unexpected extra contract fetch")
            row = dict(self.contract_rows[self.contract_calls])
            self.contract_calls += 1
            self.latest_contract = row
            return row

        if "INSERT INTO ots_stamps" in query:
            self.ots_insert_args = args
            return {"id": 81}

        if "INSERT INTO l2bl4_badges" in query:
            self.badge_insert_args = args
            self.badge_id = str(args[0])
            return {"badge_id": self.badge_id}

        if "FROM v_l2bl4_badge_validity" in query:
            if self.badge_insert_args is None:
                return None
            badge_id = str(args[0])
            issuance_status = str(self.badge_insert_args[7])
            badge_class = str(self.badge_insert_args[12])
            contract_error = (
                None
                if issuance_status == "issued"
                else self.latest_contract.get("contract_error")
            )
            contract_status = (
                "keepsake_unverified"
                if issuance_status == "issued"
                else "not_issued"
            )
            return {
                "badge_id": badge_id,
                "project_id": self.badge_insert_args[1],
                "ticket_id": self.badge_insert_args[2],
                "subject_type": self.badge_insert_args[3],
                "subject_key": self.badge_insert_args[4],
                "subject_digest": self.badge_insert_args[5],
                "badge_type": self.badge_insert_args[6],
                "badge_class": badge_class,
                "issuance_status": issuance_status,
                "ots_stamp_id": self.badge_insert_args[13],
                "bitcoin_block": self.latest_contract.get("bitcoin_block"),
                "composite_sig_hash": self.badge_insert_args[14],
                "contract_version": "l2bl4.v1",
                "contract_error": contract_error,
                "contract_status": contract_status,
                "is_currently_valid": issuance_status == "issued",
                "evidence_contract": self.latest_contract.get(
                    "evidence_contract"
                ),
                "issued_to": self.badge_insert_args[8],
                "issued_by": self.badge_insert_args[9],
                "evidence": json.loads(self.badge_insert_args[10]),
                "metadata": json.loads(self.badge_insert_args[11]),
            }

        raise AssertionError(f"unexpected query: {query}")


def _contract_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "ticket_id": "tk_success",
        "project_id": 1,
        "status": "success",
        "audit_success": True,
        "keepsake_ready": True,
        "public_ready": False,
        "has_ticket_ots_stamp": False,
        "has_confirmed_ots_stamp": False,
        "ots_stamp_id": None,
        "bitcoin_block": None,
        "evidence_contract": {
            "contract_version": "l2bl4.v1",
            "audit_success": True,
        },
        "contract_error": None,
    }
    row.update(overrides)
    return row


def _build_client(conn: FakeL2BL4Conn) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.db_pool = FakePool(conn)
    return TestClient(app)


def test_query_api_mounts_l2bl4_routes() -> None:
    routes = {route.path: route for route in query_api_app.routes}

    assert "/api/v1/l2bl4/issue" in routes
    assert "POST" in routes["/api/v1/l2bl4/issue"].methods
    assert "/api/v1/l2bl4/badges/{badge_id}" in routes
    assert "/api/v1/l2bl4/verify/{badge_id}" in routes


def test_keepsake_issue_inserts_issued_badge_without_ots() -> None:
    conn = FakeL2BL4Conn([_contract_row()])
    client = _build_client(conn)

    response = client.post(
        "/api/v1/l2bl4/issue",
        json={
            "ticket_id": "tk_success",
            "badge_class": "keepsake",
            "issued_to": "auditor@example.test",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["badge_id"].startswith("bdg_")
    assert payload["verification_url"].endswith(
        f"/api/v1/l2bl4/verify/{payload['badge_id']}"
    )
    assert payload["issuance_status"] == "issued"
    assert payload["contract_status"] == "keepsake_unverified"
    assert payload["contract_error"] is None
    assert "keepsake badges mark successful audit output" in "\n".join(
        payload["readable_summary"]
    )
    assert conn.ots_insert_args is None
    assert conn.badge_insert_args is not None
    assert conn.badge_insert_args[7] == "issued"
    assert conn.badge_insert_args[12] == "keepsake"


def test_public_issue_stores_draft_when_ots_unconfirmed() -> None:
    conn = FakeL2BL4Conn(
        [
            _contract_row(contract_error="ots_stamp_required"),
            _contract_row(
                has_ticket_ots_stamp=True,
                ots_stamp_id=81,
                contract_error="bitcoin_block_required",
            ),
        ]
    )
    client = _build_client(conn)

    response = client.post(
        "/api/v1/l2bl4/issue",
        json={"ticket_id": "tk_success", "badge_class": "public"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["issuance_status"] == "draft"
    assert payload["contract_error"] == "bitcoin_block_required"
    assert payload["ots_stamp_id"] == 81
    assert "confirm the pending OTS stamp" in "\n".join(
        payload["readable_summary"]
    )
    assert conn.ots_insert_args is not None
    stamp_payload = json.loads(conn.ots_insert_args[6])
    assert stamp_payload["pending_only"] is True
    assert conn.badge_insert_args is not None
    assert conn.badge_insert_args[7] == "draft"
    metadata = json.loads(conn.badge_insert_args[11])
    assert metadata["created_pending_ots"] is True
