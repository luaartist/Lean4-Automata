from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.query.router import router


class _AcquireCtx:
    def __init__(self, conn: "FakeConn") -> None:
        self._conn = conn

    async def __aenter__(self) -> "FakeConn":
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN002, ANN003
        return None


class FakePool:
    def __init__(self, conn: "FakeConn") -> None:
        self._conn = conn

    def acquire(self) -> _AcquireCtx:
        return _AcquireCtx(self._conn)


class FakeConn:
    def __init__(
        self,
        *,
        fetchrow_impl: Callable[..., Any] | None = None,
        fetch_impl: Callable[..., Any] | None = None,
        fetchval_impl: Callable[..., Any] | None = None,
    ) -> None:
        self.fetchrow_impl = fetchrow_impl
        self.fetch_impl = fetch_impl
        self.fetchval_impl = fetchval_impl
        self.fetchrow_calls = 0
        self.fetch_calls = 0
        self.fetchval_calls = 0

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self.fetchrow_calls += 1
        if self.fetchrow_impl is None:
            return None
        return self.fetchrow_impl(query, *args)

    async def fetch(self, query: str, *args: Any) -> Any:
        self.fetch_calls += 1
        if self.fetch_impl is None:
            return []
        return self.fetch_impl(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        self.fetchval_calls += 1
        if self.fetchval_impl is None:
            return None
        return self.fetchval_impl(query, *args)


class FakeRedis:
    def __init__(self, *, fail_get: bool = False, fail_set: bool = False) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.fail_get = fail_get
        self.fail_set = fail_set

    async def get(self, key: str) -> str | None:
        if self.fail_get:
            raise RuntimeError("redis read failure")
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        if self.fail_set:
            raise RuntimeError("redis write failure")
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True


def _build_client(conn: FakeConn, redis: FakeRedis | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.db_pool = FakePool(conn)
    app.state.redis = redis
    return TestClient(app)


def test_symbol_lookup_cached_then_db_fallback() -> None:
    row = {
        "id": 7,
        "file_id": 42,
        "project_id": 1,
        "name": "map",
        "full_name": "Mathlib.List.map",
        "kind": "def",
        "line_start": 10,
        "line_end": 12,
        "signature": "def map",
        "docstring": "List map",
    }
    conn = FakeConn(fetchrow_impl=lambda *_: row)
    redis = FakeRedis()
    client = _build_client(conn, redis)

    first = client.get("/api/v1/symbols/Mathlib.List.map")
    assert first.status_code == 200
    assert first.json()["full_name"] == "Mathlib.List.map"
    assert conn.fetchrow_calls == 1
    assert "lean4:cache:file:42:symbol:Mathlib.List.map" in redis.store
    assert redis.ttls["lean4:cache:symbol:Mathlib.List.map"] == 3600

    conn.fetchrow_impl = lambda *_: (_ for _ in ()).throw(AssertionError("DB should not be used on cache hit"))
    second = client.get("/api/v1/symbols/Mathlib.List.map")
    assert second.status_code == 200
    assert second.json()["id"] == 7
    assert conn.fetchrow_calls == 1


def test_search_returns_expected_json_shape() -> None:
    rows = [
        {
            "id": 1,
            "file_id": 11,
            "project_id": 3,
            "name": "foldl",
            "full_name": "Std.List.foldl",
            "kind": "def",
            "rank": 0.87,
            "total_count": 2,
        },
        {
            "id": 2,
            "file_id": 11,
            "project_id": 3,
            "name": "foldr",
            "full_name": "Std.List.foldr",
            "kind": "def",
            "rank": 0.74,
            "total_count": 2,
        },
    ]
    conn = FakeConn(fetch_impl=lambda *_: rows)
    client = _build_client(conn, FakeRedis())
    response = client.get("/api/v1/symbols/search", params={"q": "fold", "project_id": 3, "limit": 10, "offset": 0})
    assert response.status_code == 200
    payload = response.json()
    assert payload["q"] == "fold"
    assert payload["project_id"] == 3
    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert set(payload["items"][0].keys()) >= {"id", "file_id", "project_id", "name", "full_name", "kind", "rank"}


def test_deps_graph_endpoint_shape(monkeypatch) -> None:  # noqa: ANN001
    conn = FakeConn(fetchval_impl=lambda *_: True)
    client = _build_client(conn, FakeRedis())

    async def _fake_transitive(_conn: Any, _full_name: str, max_depth: int = 5) -> list[dict[str, Any]]:
        return [
            {
                "symbol_id": 10,
                "full_name": "A.B",
                "name": "B",
                "kind": "def",
                "depth": max_depth - 1,
                "path": [1, 10],
                "dependency_type": "direct",
            }
        ]

    async def _fake_reverse(_conn: Any, _full_name: str, max_depth: int = 5) -> list[dict[str, Any]]:
        return [
            {
                "symbol_id": 21,
                "full_name": "X.Y",
                "name": "Y",
                "kind": "theorem",
                "depth": max_depth - 2,
                "path": [21, 1],
                "dependency_type": "indirect",
            }
        ]

    monkeypatch.setattr("app.query.router.get_transitive_deps", _fake_transitive)
    monkeypatch.setattr("app.query.router.get_reverse_deps", _fake_reverse)

    response = client.get("/api/v1/dependencies/graph", params={"full_name": "Root.Symbol", "max_depth": 4})
    assert response.status_code == 200
    payload = response.json()
    assert payload["full_name"] == "Root.Symbol"
    assert payload["max_depth"] == 4
    assert payload["transitive"][0]["dependency_type"] == "direct"
    assert payload["reverse"][0]["kind"] == "theorem"


def test_module_metrics_endpoint_shape(monkeypatch) -> None:  # noqa: ANN001
    conn = FakeConn(fetchval_impl=lambda *_: True)
    client = _build_client(conn, FakeRedis())

    async def _fake_metrics(_conn: Any, project_id: int, order_by: str) -> list[dict[str, Any]]:
        return [
            {
                "file_id": 100,
                "module_name": "Mathlib.Algebra.Group",
                "total_symbols": 12,
                "theorem_count": 3,
                "def_count": 6,
                "instance_count": 1,
                "inductive_count": 0,
                "structure_count": 1,
                "class_count": 1,
                "avg_symbol_length_lines": 3.5,
                "max_symbol_length_lines": 9,
                "public_symbols": 11,
                "deprecated_symbols": 0,
                "documented_symbols": 7,
                "documentation_coverage_pct": 58.3,
            }
        ]

    monkeypatch.setattr("app.query.router.get_module_complexity", _fake_metrics)

    response = client.get("/api/v1/modules/metrics", params={"project_id": 2, "order_by": "total_symbols"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == 2
    assert payload["order_by"] == "total_symbols"
    assert payload["items"][0]["module_name"] == "Mathlib.Algebra.Group"
    assert "documentation_coverage_pct" in payload["items"][0]


def test_cache_graceful_degradation_redis_exception_does_not_fail_endpoint() -> None:
    row = {
        "id": 9,
        "file_id": 77,
        "project_id": 1,
        "name": "length",
        "full_name": "Std.List.length",
        "kind": "def",
        "line_start": 2,
        "line_end": 4,
        "signature": "def length",
        "docstring": None,
    }
    conn = FakeConn(fetchrow_impl=lambda *_: row)
    redis = FakeRedis(fail_get=True)
    client = _build_client(conn, redis)

    response = client.get("/api/v1/symbols/Std.List.length")
    assert response.status_code == 200
    assert response.json()["full_name"] == "Std.List.length"
    assert conn.fetchrow_calls == 1


def test_symbol_not_found_returns_404() -> None:
    conn = FakeConn(fetchrow_impl=lambda *_: None)
    client = _build_client(conn, FakeRedis())
    response = client.get("/api/v1/symbols/Nope.Symbol")
    assert response.status_code == 404
    assert "Symbol not found" in json.dumps(response.json())
