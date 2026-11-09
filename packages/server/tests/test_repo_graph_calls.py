"""`/api/repo/graph` exposes internal CALLS edges between function and method nodes."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from compass_core.index.locate import IndexLocation
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
def graph(
    fixture_index: IndexLocation, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, Any]]:
    monkeypatch.setattr(settings, "LADYBUG_DB_PATH", str(fixture_index.db_path))
    response = TestClient(app).get("/api/repo/graph")
    assert response.status_code == 200
    yield response.json()


def test_graph_includes_call_edges(graph: dict[str, Any]) -> None:
    calls = {(e["source"], e["target"]) for e in graph["edges"] if e["type"] == "CALLS"}

    assert calls == EXPECTED_CALLS


def test_call_edges_connect_emitted_nodes(graph: dict[str, Any]) -> None:
    node_ids = {n["id"] for n in graph["nodes"]}
    calls = [e for e in graph["edges"] if e["type"] == "CALLS"]

    assert calls
    assert all(e["source"] in node_ids and e["target"] in node_ids for e in calls)


def test_method_call_edge_present(graph: dict[str, Any]) -> None:
    types = {n["id"]: n["type"] for n in graph["nodes"]}
    source, target = "app/models.py::User.save", "app/models.py::Base.save"

    assert any(
        e["type"] == "CALLS" and e["source"] == source and e["target"] == target
        for e in graph["edges"]
    )
    assert types[source] == "Method"
    assert types[target] == "Method"


def test_edge_ids_unique(graph: dict[str, Any]) -> None:
    ids = [e["id"] for e in graph["edges"]]

    assert len(set(ids)) == len(ids)
