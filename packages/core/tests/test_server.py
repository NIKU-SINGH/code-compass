"""Tests for the FastAPI server."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from compass_core.index.locate import IndexLocation
from compass_core.server.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _located_index():
    """The repo routes locate the index first; GraphDB itself is mocked per test."""
    location = IndexLocation(
        repo_root=Path("/repo"),
        db_path=Path("/repo/.compass/graph.ladybug"),
        metadata_path=Path("/repo/.compass/metadata.json"),
    )
    with patch("compass_core.server.routers.repo.get_index", return_value=location):
        yield


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Code Compass Core API",
        "version": "0.1.0",
    }


def test_repo_overview_returns_shape():
    """Overview endpoint returns the expected JSON shape."""
    mock_db = MagicMock()

    def fake_execute(query, _params=None):
        result = MagicMock()
        if "count(" in query:
            result.get_all.return_value = [(10,)]
        else:
            # entry points query
            result.get_all.return_value = [
                ("/repo/main.py", "main"),
                ("/repo/server.py", "server"),
            ]
        return result

    mock_db.execute.side_effect = fake_execute
    mock_db.__enter__ = lambda s: mock_db
    mock_db.__exit__ = MagicMock(return_value=False)

    with patch("compass_core.server.routers.repo.GraphDB", return_value=mock_db):
        response = client.get("/api/repo/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["file_count"] == 10
    assert data["class_count"] == 10
    assert data["function_count"] == 10
    assert data["edge_count"] == 50
    assert len(data["entry_points"]) == 2
    assert data["entry_points"][0]["path"] == "main.py"
    assert data["entry_points"][0]["module_name"] == "main"


def test_repo_graph_returns_nodes_and_edges():
    """Graph endpoint returns nodes list and edges list."""
    mock_db = MagicMock()

    def fake_execute(query, **_kwargs):
        result = MagicMock()
        if ":File)" in query and "CONTAINS" not in query and "IMPORTS" not in query:
            result.get_all.return_value = [("/repo/a.py", "/repo/a.py", "File", "/repo/a.py")]
        else:
            result.get_all.return_value = []
        return result

    mock_db.execute.side_effect = fake_execute
    mock_db.__enter__ = lambda s: mock_db
    mock_db.__exit__ = MagicMock(return_value=False)

    with patch("compass_core.server.routers.repo.GraphDB", return_value=mock_db):
        response = client.get("/api/repo/graph")

    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "/repo/a.py"
    assert data["nodes"][0]["type"] == "File"


def test_repo_overview_503_when_db_unavailable():
    """Overview endpoint returns 503 if DB cannot be opened."""
    with patch(
        "compass_core.server.routers.repo.GraphDB",
        side_effect=Exception("DB not found"),
    ):
        response = client.get("/api/repo/overview")

    assert response.status_code == 503
