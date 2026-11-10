"""The graph stores public ids, repo-relative paths and qualified names."""

from __future__ import annotations

from compass_core.graph.db import GraphDB, as_rows
from compass_core.graph.stored_ids import public_id, qualified_name, with_stored_ids
from compass_core.ir.graph import CallEdge, ExternalCallEdge, InheritEdge, ResolvedGraph
from compass_core.ir.models import Definition, ParsedFile
from compass_core.shared_types import CallType, SymbolKind


def _definition(internal_id: str, name: str, path: str, parent_id: str | None = None) -> Definition:
    return Definition(
        id=internal_id,
        kind=SymbolKind.METHOD if parent_id else SymbolKind.FUNCTION,
        name=name,
        file_path=path,
        line_start=1,
        line_end=2,
        source="",
        docstring=None,
        bases=[],
        parent_id=parent_id,
        signature=None,
        decorators=[],
        raw_calls=[],
    )


def test_public_id_and_qualified_name() -> None:
    save = _definition("py::app.models::User.save", "save", "app/models.py")
    assert public_id(save) == "app/models.py::User.save"
    assert qualified_name(save) == "app.models.User.save"


def test_qualified_name_falls_back_to_the_file_path() -> None:
    init = _definition("app::setup", "setup", "app/__init__.py")
    assert qualified_name(init) == "app.setup"


def test_with_stored_ids_rekeys_definitions_and_edges() -> None:
    user = _definition("py::app.models::User", "User", "app/models.py")
    save = _definition("py::app.models::User.save", "save", "app/models.py", user.id)
    handle = _definition("py::app.api::handle", "handle", "app/api.py")
    graph = ResolvedGraph(
        files=[
            ParsedFile(
                path="app/models.py",
                language="python",
                module_name="app.models",
                content_hash="x",
                definitions=[user, save],
                imports=[],
                call_sites=[],
            ),
            ParsedFile(
                path="app/api.py",
                language="python",
                module_name="app.api",
                content_hash="y",
                definitions=[handle],
                imports=[],
                call_sites=[],
            ),
        ],
        call_edges=[CallEdge(handle.id, save.id, CallType.DIRECT_IMPORT, 1.0)],
        external_call_edges=[ExternalCallEdge(handle.id, "json.dumps", "json")],
        inherit_edges=[InheritEdge(user.id, "py::elsewhere::Unknown")],
    )
    stored = with_stored_ids(graph)
    models = stored.graph.files[0].definitions
    assert [d.id for d in models] == ["app/models.py::User", "app/models.py::User.save"]
    assert models[1].parent_id == "app/models.py::User"
    call = stored.graph.call_edges[0]
    assert (call.caller_id, call.callee_id) == ("app/api.py::handle", "app/models.py::User.save")
    assert stored.graph.external_call_edges[0].caller_id == "app/api.py::handle"
    # An endpoint that is not a definition keeps its value and still matches no node.
    assert stored.graph.inherit_edges[0].parent_id == "py::elsewhere::Unknown"
    assert stored.qualified_names["app/models.py::User.save"] == "app.models.User.save"
    # The input graph is not modified.
    assert save.id == "py::app.models::User.save"


def test_ingested_graph_stores_public_ids(fixture_db: GraphDB) -> None:
    rows = as_rows(
        fixture_db.execute(
            "MATCH (n:Function) RETURN n.id, n.file_path, n.qualified_name "
            "UNION ALL MATCH (n:Class) RETURN n.id, n.file_path, n.qualified_name"
        )
    )
    assert rows
    for node_id, path, qualified in rows:
        assert not path.startswith("/"), path
        assert node_id.startswith(f"{path}::"), node_id
        assert qualified.endswith(node_id.rsplit("::", 1)[1]), (node_id, qualified)
    row = as_rows(
        fixture_db.execute(
            "MATCH (f:Function {id: 'app/models.py::User.save'}) RETURN f.qualified_name"
        )
    )
    assert row == [["app.models.User.save"]]
