"""`/api/repo/graph` exposes query-layer public ids on every node."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass_core.errors import IndexIncompatibleError
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation
from compass_core.query.references import ResolvedReference, resolve
from compass_core.server.main import app
from compass_core.server.routers import repo
from compass_core.settings import settings


@pytest.fixture
def nodes(fixture_index: IndexLocation, monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Any]]:
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", str(fixture_index.db_path))
    response = TestClient(app).get("/api/repo/graph")
    assert response.status_code == 200
    yield response.json()["nodes"]


def test_every_node_has_unique_public_id(nodes: list[Any]) -> None:
    ids = [n["public_id"] for n in nodes]
    assert nodes
    assert all(ids)
    assert len(set(ids)) == len(ids)


def test_expected_public_ids(nodes: list[Any]) -> None:
    ids = {n["public_id"] for n in nodes}
    assert {"file::app/auth.py", "app/auth.py::decode_token", "app/models.py::User.save"} <= ids


def test_ids_follow_stored_format_and_kind(nodes: list[Any]) -> None:
    for n in nodes:
        if n["type"] == "File":
            assert n["id"] == n["file_path"]
            assert n["public_id"] == f"file::{n['file_path']}"
        else:
            assert n["id"].startswith("py::")
            assert n["public_id"].startswith(f"{n['file_path']}::")


def test_malformed_definition_id_is_skipped(
    fixture_index: IndexLocation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", str(fixture_index.db_path))
    real = repo.public_definition_id

    def flaky(stored_id: str, stored_path: str, root: Any) -> Any:
        if stored_id.endswith("::decode_token"):
            raise IndexIncompatibleError("bad id")
        return real(stored_id, stored_path, root)

    monkeypatch.setattr(repo, "public_definition_id", flaky)
    response = TestClient(app).get("/api/repo/graph")
    assert response.status_code == 200
    ids = {n["public_id"] for n in response.json()["nodes"]}
    assert "app/auth.py::decode_token" not in ids
    assert "app/models.py::User.save" in ids


def test_public_ids_round_trip_through_resolve(
    nodes: list[Any], fixture_index: IndexLocation
) -> None:
    with GraphDB(fixture_index.db_path, read_only=True) as db:
        for n in nodes:
            found = resolve(db, n["public_id"], repo_root=fixture_index.repo_root, allow_file=True)
            assert isinstance(found, ResolvedReference), n["public_id"]
            assert found.symbol.id == n["public_id"]
