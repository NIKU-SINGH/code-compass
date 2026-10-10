"""HTTP tests for the query routes, error handlers and OpenAPI schema."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compass_core.errors import IndexBusyError, IndexNotFoundError, QueryTimeoutError
from compass_core.index.locate import IndexLocation
from compass_core.server.main import app
from compass_core.server.routers.query import get_index

QUERY_ROUTES = ("/api/search", "/api/impact", "/api/overview")


@pytest.fixture
def client(fixture_index: IndexLocation) -> Iterator[TestClient]:
    app.dependency_overrides[get_index] = lambda: fixture_index
    yield TestClient(app)
    app.dependency_overrides.clear()


def _client_raising(exc: Exception) -> TestClient:
    def boom() -> IndexLocation:
        raise exc

    app.dependency_overrides[get_index] = boom
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def test_impact_ok_shape(client: TestClient) -> None:
    r = client.get("/api/impact", params={"ref": "app/auth.py", "depth": 1})
    body = r.json()
    assert r.status_code == 200
    assert body["outcome"] == "ok"
    assert body["operation"] == "IMPACT"
    assert body["affected_file_count"] == 4
    assert isinstance(body["index"]["repo_root"], str)
    assert r.headers["content-type"].startswith("application/json")


def test_impact_transitive(client: TestClient) -> None:
    r = client.get("/api/impact", params={"ref": "app/auth.py::decode_token", "depth": 3})
    names = {(g["distance"], i["symbol"]["name"]) for g in r.json()["groups"] for i in g["items"]}
    assert (2, "tick") in names


@pytest.mark.parametrize(
    ("params", "name"),
    [
        ({"ref": "app/auth.py", "depth": "0"}, "depth"),
        ({"ref": "app/auth.py", "depth": "11"}, "depth"),
        ({"ref": "app/auth.py", "depth": "abc"}, "depth"),
        ({"ref": "app/auth.py", "min_confidence": "1.5"}, "min_confidence"),
        ({"ref": "app/auth.py", "limit": "0"}, "limit"),
        ({}, "ref"),
    ],
)
def test_bad_impact_args_are_422_error_response(
    client: TestClient, params: dict[str, str], name: str
) -> None:
    r = client.get("/api/impact", params=params)
    body = r.json()
    assert r.status_code == 422
    assert body["code"] == "INVALID_ARGUMENT"
    assert any(name in d["key"] for d in body["details"])


def test_empty_search_query_is_422(client: TestClient) -> None:
    r = client.get("/api/search", params={"q": ""})
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_ARGUMENT"
    assert any("q" in d["key"] for d in r.json()["details"])


def test_ambiguous_ref_is_409(client: TestClient) -> None:
    r = client.get("/api/impact", params={"ref": "run"})
    assert r.status_code == 409
    assert r.json()["outcome"] == "ambiguous"
    assert len(r.json()["candidates"]) == 2


def test_unknown_ref_is_404(client: TestClient) -> None:
    r = client.get("/api/impact", params={"ref": "decode"})
    assert r.status_code == 404
    assert r.json()["outcome"] == "not_found"
    assert any(s["name"] == "decode_token" for s in r.json()["suggestions"])


def test_missing_index_is_503(tmp_path: Path) -> None:
    c = _client_raising(IndexNotFoundError(searched_from=tmp_path))
    r = c.get("/api/overview")
    assert r.status_code == 503
    assert r.json()["code"] == "INDEX_NOT_FOUND"


def test_busy_index_is_503_with_retry_after() -> None:
    r = _client_raising(IndexBusyError(retry_after_s=2)).get("/api/overview")
    assert r.status_code == 503
    assert r.json()["code"] == "INDEX_BUSY"
    assert r.headers["retry-after"] == "2"


def test_timeout_is_504() -> None:
    r = _client_raising(QueryTimeoutError(timeout_ms=10)).get("/api/overview")
    assert r.status_code == 504
    assert r.json()["code"] == "QUERY_TIMEOUT"


def test_unexpected_error_is_500_without_leak() -> None:
    r = _client_raising(RuntimeError("boom")).get("/api/overview")
    assert r.status_code == 500
    assert r.json()["code"] == "INTERNAL"
    assert "boom" not in r.text


def test_search(client: TestClient) -> None:
    body = client.get("/api/search", params={"q": "parse"}).json()
    assert body["operation"] == "FIND"
    assert body["hits"]
    limited = client.get("/api/search", params={"q": "a", "limit": 1}).json()
    assert limited["truncated"] is True


def test_overview(client: TestClient) -> None:
    body = client.get("/api/overview").json()
    assert body["operation"] == "OVERVIEW"
    assert body["riskiest_to_change"][0]["symbol"]["name"] == "decode_token"
    assert body["most_imported_files"][0]["count"] == 4
    assert isinstance(body["counts"]["edges_by_type"], dict)


def test_no_absolute_paths_leak(client: TestClient, fixture_index: IndexLocation) -> None:
    root = str(fixture_index.repo_root)
    for url, params in (
        ("/api/overview", {}),
        ("/api/search", {"q": "a"}),
        ("/api/impact", {"ref": "app/auth.py"}),
    ):
        body = client.get(url, params=params).json()
        body["index"].pop("repo_root")
        assert root not in str(body)


def test_openapi_covers_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for p in QUERY_ROUTES:
        responses = paths[p]["get"]["responses"]
        assert "200" in responses
        assert {"422", "503", "504"} <= set(responses)
    assert {"404", "409"} <= set(paths["/api/impact"]["get"]["responses"])


def test_existing_routes_unchanged(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"
