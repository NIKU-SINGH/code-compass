"""The health route answers without an index."""

from fastapi.testclient import TestClient

from compass_core.package_version import installed_version
from compass_server.main import app


def test_health_check() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Code Compass Core API",
        "version": installed_version(),
    }
