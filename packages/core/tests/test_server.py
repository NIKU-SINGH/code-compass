"""Tests for the FastAPI server."""

from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from compass_core.server.main import app

client = TestClient(app)


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

    def fake_execute(query, **_kwargs):
        result = MagicMock()
        if "count(*)" in query:
            result.has_next.return_value = True
            result.get_next.return_value = (10,)
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
    assert "edge_count" in data
    assert len(data["entry_points"]) == 2
    assert data["entry_points"][0]["path"] == "/repo/main.py"
    assert data["entry_points"][0]["module_name"] == "main"


def test_repo_overview_503_when_db_unavailable():
    """Overview endpoint returns 503 if DB cannot be opened."""
    with patch(
        "compass_core.server.routers.repo.GraphDB",
        side_effect=Exception("DB not found"),
    ):
        response = client.get("/api/repo/overview")

    assert response.status_code == 503
