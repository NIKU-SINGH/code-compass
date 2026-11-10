"""``/api/graph/map`` returns the contract ``GraphMap`` of the located index."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation
from compass_core.query.references import ResolvedReference, resolve
from compass_core.settings import settings
from compass_server.main import app

EXPECTED_CALLS = {
    ("app/api.py::handle", "app/auth.py::decode_token"),
    ("app/cli.py::run", "app/auth.py::decode_token"),
    ("app/jobs.py::nightly", "app/auth.py::decode_token"),
    ("app/scheduler.py::tick", "app/jobs.py::nightly"),
    ("app/models.py::User.save", "app/models.py::Base.save"),
}


@pytest.fixture
def graph(fixture_index: IndexLocation, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", str(fixture_index.db_path))
    response = TestClient(app).get("/api/graph/map")
    assert response.status_code == 200
    yield response.json()


def test_every_node_has_a_unique_public_id(graph: Any) -> None:
    ids = [n["public_id"] for n in graph["nodes"]]
    assert ids and all(ids)
    assert len(set(ids)) == len(ids)
    assert {"file::app/auth.py", "app/auth.py::decode_token", "app/models.py::User.save"} <= set(
        ids
    )


def test_node_ids_and_kinds(graph: Any) -> None:
    for n in graph["nodes"]:
        if n["kind"] == "file":
            assert n["id"] == n["file_path"] and n["public_id"] == f"file::{n['file_path']}"
        else:
            assert n["kind"] in {"class", "function", "method"}
            assert n["id"] == n["public_id"] and n["public_id"].startswith(f"{n['file_path']}::")


def test_call_edges_join_emitted_nodes(graph: Any) -> None:
    kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
    calls = {(e["source"], e["target"]) for e in graph["edges"] if e["type"] == "CALLS"}
    assert calls == EXPECTED_CALLS
    assert all(s in kinds and t in kinds for s, t in calls)
    assert kinds["app/models.py::User.save"] == kinds["app/models.py::Base.save"] == "method"


def test_edges_are_distinct(graph: Any) -> None:
    edges = [(e["source"], e["target"], e["type"]) for e in graph["edges"]]
    assert len(set(edges)) == len(edges)


def test_public_ids_round_trip_through_resolve(graph: Any, fixture_index: IndexLocation) -> None:
    with GraphDB(fixture_index.db_path, read_only=True) as db:
        for n in graph["nodes"]:
            found = resolve(db, n["public_id"], repo_root=fixture_index.repo_root, allow_file=True)
            assert isinstance(found, ResolvedReference), n["public_id"]
            assert found.symbol.id == n["public_id"]


def test_finds_the_index_from_a_subdirectory(
    fixture_index: IndexLocation, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", ".compass/graph.ladybug")
    monkeypatch.chdir(fixture_index.repo_root / "app")
    response = TestClient(app).get("/api/graph/map")
    assert response.status_code == 200
    assert "app/auth.py::decode_token" in {n["public_id"] for n in response.json()["nodes"]}


def test_is_503_without_an_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", ".compass/graph.ladybug")
    monkeypatch.chdir(tmp_path)
    response = TestClient(app).get("/api/graph/map")
    assert response.status_code == 503
    assert response.json()["code"] == "INDEX_NOT_FOUND"
