"""`/api/repo/*` open the same index as the query routes, wherever the server starts."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from compass_core.index.locate import IndexLocation
from compass_core.settings import settings
from compass_server.main import app


@pytest.fixture
def from_subdirectory(fixture_index: IndexLocation, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default cwd-relative DB setting, server started inside ``app/`` of the repo."""
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", ".compass/graph.ladybug")
    monkeypatch.chdir(fixture_index.repo_root / "app")


@pytest.mark.usefixtures("from_subdirectory")
def test_graph_route_finds_index_from_subdirectory(fixture_index: IndexLocation) -> None:
    response = TestClient(app).get("/api/repo/graph")

    assert response.status_code == 200
    ids = {n["public_id"] for n in response.json()["nodes"]}
    assert "app/auth.py::decode_token" in ids
    assert not (fixture_index.repo_root / "app" / ".compass").exists()


@pytest.mark.usefixtures("from_subdirectory")
def test_repo_overview_route_finds_index_from_subdirectory() -> None:
    response = TestClient(app).get("/api/repo/overview")

    assert response.status_code == 200
    assert response.json()["file_count"] == 8


def test_graph_route_is_503_without_an_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", ".compass/graph.ladybug")
    monkeypatch.chdir(tmp_path)

    response = TestClient(app).get("/api/repo/graph")

    assert response.status_code == 503
