from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.query_api import app


def test_query_api_mounts_audit_routes() -> None:
    routes = {route.path: route for route in app.routes}

    assert "/api/v1/audit/summary" in routes
    assert "/api/v1/audit/millennium" in routes
    assert "/api/v1/audit/ranking" in routes
    assert "/api/v1/audit/execute" in routes
    assert "POST" in routes["/api/v1/audit/execute"].methods


def test_millennium_route_forwards_target(monkeypatch) -> None:  # noqa: ANN001
    calls: list[tuple[str, dict[str, Any]]] = []
    target = "MassGapTheorem.lean"

    paths = {
        "Target": target,
        "DependencyClosureSize": 1,
        "DependencyClosure": [target],
        "MillenniumCoreClosureSize": 0,
        "MillenniumCoreClosure": [],
        "AllModulesReachMillennium": False,
        "ModulesOffMillenniumPath": [],
        "PathCountToMillennium": 0,
    }

    def _fake_execute_flow(flow_name: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append((flow_name, params))
        return {
            "status": "ok",
            "ticket": {
                "title": "Lean Millennium Path Analysis",
                "description": "Dependency path smoke test",
                "created_at": "2026-05-15T00:00:00+00:00",
                "type": "lean_audit",
                "data": paths,
                "metadata": {},
            },
            "paths": paths,
        }

    monkeypatch.setattr("app.audit.router.execute_flow", _fake_execute_flow)

    client = TestClient(app)
    response = client.get("/api/v1/audit/millennium", params={"target": target})

    assert response.status_code == 200
    assert calls == [("lean_millennium_paths", {"target": target})]
    assert response.json()["paths"]["Target"] == target