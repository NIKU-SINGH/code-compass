"""Integration tests for compass_core.graph.writer.

Each test creates an in-memory (tmp_path) LadybugDB, initialises the schema,
calls write, then queries the DB to verify the result.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from compass_core.graph.db import GraphDB
from compass_core.graph.schema import create_schema
from compass_core.graph.writer import write
from compass_core.parser.models import Import, ParsedClass, ParsedFile, ParsedFunction
from compass_core.resolver.models import (
    CallEdge,
    ExternalCallEdge,
    ImportEdge,
    InheritEdge,
    RESOLVED,
    ResolvedGraph,
)
from compass_core.resolver.symbol_table import class_id, function_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> GraphDB:  # type: ignore[misc]
    """Yield a fresh, schema-initialised GraphDB for each test."""
    _db = GraphDB(tmp_path / "test.ladybug")
    create_schema(_db)
    yield _db
    _db.close()


def make_file(
    path: str = "/repo/mod.py",
    module_name: str = "mod",
    imports: list[Import] | None = None,
    classes: list[ParsedClass] | None = None,
    functions: list[ParsedFunction] | None = None,
    content_hash: str = "abc123",
) -> ParsedFile:
    return ParsedFile(
        path=path,
        module_name=module_name,
        imports=imports or [],
        classes=classes or [],
        functions=functions or [],
        content_hash=content_hash,
    )


def make_function(
    name: str = "fn",
    file_path: str = "/repo/mod.py",
    is_method: bool = False,
    parent_class: str | None = None,
    raw_calls: list[str] | None = None,
) -> ParsedFunction:
    return ParsedFunction(
        name=name,
        signature=f"def {name}():",
        docstring=None,
        line_start=1,
        line_end=3,
        source=f"def {name}():\n    pass\n",
        file_path=file_path,
        raw_calls=raw_calls or [],
        decorators=[],
        is_method=is_method,
        parent_class=parent_class,
    )


def make_class(
    name: str = "MyClass",
    file_path: str = "/repo/mod.py",
    bases: list[str] | None = None,
    methods: list[ParsedFunction] | None = None,
) -> ParsedClass:
    return ParsedClass(
        name=name,
        bases=bases or [],
        methods=methods or [],
        docstring=None,
        line_start=1,
        line_end=5,
        source=f"class {name}:\n    pass\n",
        file_path=file_path,
    )


def _count(db: GraphDB, query: str, params: dict | None = None) -> int:
    result = db.execute(query, params)
    return int(result.get_next()[0]) if result.has_next() else 0


# ---------------------------------------------------------------------------
# Node write tests
# ---------------------------------------------------------------------------


def test_write_file_node(db: GraphDB) -> None:
    pf = make_file(path="/repo/a.py", module_name="a", content_hash="deadbeef")
    write(db, ResolvedGraph(files=[pf]))
    count = _count(db, "MATCH (n:File {path: '/repo/a.py'}) RETURN count(n)")
    assert count == 1


def test_write_file_node_fields(db: GraphDB) -> None:
    pf = make_file(path="/repo/a.py", module_name="mymod", content_hash="hash1")
    write(db, ResolvedGraph(files=[pf]))
    result = db.execute("MATCH (n:File {path: '/repo/a.py'}) RETURN n.module_name, n.content_hash")
    cols = result.get_column_names()
    row = dict(zip(cols, result.get_next()))
    assert row["n.module_name"] == "mymod"
    assert row["n.content_hash"] == "hash1"


def test_write_class_node(db: GraphDB) -> None:
    cls = make_class(name="Foo", file_path="/repo/a.py")
    pf = make_file(path="/repo/a.py", classes=[cls])
    write(db, ResolvedGraph(files=[pf]))
    count = _count(db, "MATCH (n:Class {name: 'Foo'}) RETURN count(n)")
    assert count == 1


def test_write_function_node(db: GraphDB) -> None:
    fn = make_function(name="do_work", file_path="/repo/a.py")
    pf = make_file(path="/repo/a.py", functions=[fn])
    write(db, ResolvedGraph(files=[pf]))
    count = _count(db, "MATCH (n:Function {name: 'do_work'}) RETURN count(n)")
    assert count == 1


def test_write_method_node(db: GraphDB) -> None:
    method = make_function(name="run", file_path="/repo/a.py", is_method=True, parent_class="Worker")
    cls = make_class(name="Worker", file_path="/repo/a.py", methods=[method])
    pf = make_file(path="/repo/a.py", classes=[cls])
    write(db, ResolvedGraph(files=[pf]))
    count = _count(db, "MATCH (n:Function {name: 'run', is_method: true}) RETURN count(n)")
    assert count == 1


# ---------------------------------------------------------------------------
# CONTAINS edge tests
# ---------------------------------------------------------------------------


def test_file_to_class_contains_edge(db: GraphDB) -> None:
    cls = make_class(name="Foo", file_path="/repo/a.py")
    pf = make_file(path="/repo/a.py", classes=[cls])
    write(db, ResolvedGraph(files=[pf]))
    count = _count(
        db,
        "MATCH (f:File {path: '/repo/a.py'})-[:CONTAINS]->(c:Class {name: 'Foo'}) RETURN count(*)"
    )
    assert count == 1


def test_file_to_function_contains_edge(db: GraphDB) -> None:
    fn = make_function(name="helper", file_path="/repo/a.py")
    pf = make_file(path="/repo/a.py", functions=[fn])
    write(db, ResolvedGraph(files=[pf]))
    count = _count(
        db,
        "MATCH (f:File {path: '/repo/a.py'})-[:CONTAINS]->(n:Function {name: 'helper'}) RETURN count(*)"
    )
    assert count == 1


def test_class_to_method_contains_edge(db: GraphDB) -> None:
    method = make_function(name="act", file_path="/repo/a.py", is_method=True, parent_class="Agent")
    cls = make_class(name="Agent", file_path="/repo/a.py", methods=[method])
    pf = make_file(path="/repo/a.py", classes=[cls])
    write(db, ResolvedGraph(files=[pf]))
    count = _count(
        db,
        "MATCH (c:Class {name: 'Agent'})-[:CONTAINS]->(m:Function {name: 'act'}) RETURN count(*)"
    )
    assert count == 1


# ---------------------------------------------------------------------------
# IMPORTS edge tests
# ---------------------------------------------------------------------------


def test_imports_edge_between_files(db: GraphDB) -> None:
    pf_a = make_file(path="/repo/a.py", module_name="a")
    pf_b = make_file(path="/repo/b.py", module_name="b")
    graph = ResolvedGraph(
        files=[pf_a, pf_b],
        import_edges=[ImportEdge(from_path="/repo/a.py", to_path="/repo/b.py")],
    )
    write(db, graph)
    count = _count(
        db,
        "MATCH (a:File {path: '/repo/a.py'})-[:IMPORTS]->(b:File {path: '/repo/b.py'}) RETURN count(*)"
    )
    assert count == 1


# ---------------------------------------------------------------------------
# INHERITS edge tests
# ---------------------------------------------------------------------------


def test_inherits_edge(db: GraphDB) -> None:
    base = make_class(name="Base", file_path="/repo/base.py")
    child = make_class(name="Child", file_path="/repo/child.py", bases=["Base"])
    pf_base = make_file(path="/repo/base.py", module_name="base", classes=[base])
    pf_child = make_file(path="/repo/child.py", module_name="child", classes=[child])
    graph = ResolvedGraph(
        files=[pf_base, pf_child],
        inherit_edges=[InheritEdge(child_id=class_id(child), parent_id=class_id(base))],
    )
    write(db, graph)
    count = _count(
        db,
        "MATCH (c:Class {name: 'Child'})-[:INHERITS]->(b:Class {name: 'Base'}) RETURN count(*)"
    )
    assert count == 1


def test_inherits_edge_unknown_base_no_crash(db: GraphDB) -> None:
    """A class with an unknown base should write without crashing."""
    cls = make_class(name="Child", file_path="/repo/a.py", bases=["UnknownExternal"])
    pf = make_file(path="/repo/a.py", classes=[cls])
    write(db, ResolvedGraph(files=[pf]))
    count = _count(db, "MATCH (n:Class {name: 'Child'}) RETURN count(n)")
    assert count == 1


# ---------------------------------------------------------------------------
# CALLS edge tests
# ---------------------------------------------------------------------------


def test_calls_edge_direct_import(db: GraphDB) -> None:
    """fn_a calls fn_b which is imported from b.py."""
    fn_a = make_function(name="fn_a", file_path="/repo/a.py", raw_calls=["fn_b"])
    fn_b = make_function(name="fn_b", file_path="/repo/b.py")
    pf_a = make_file(path="/repo/a.py", module_name="a", functions=[fn_a])
    pf_b = make_file(path="/repo/b.py", module_name="b", functions=[fn_b])
    graph = ResolvedGraph(
        files=[pf_a, pf_b],
        call_edges=[
            CallEdge(
                caller_id=function_id(fn_a),
                callee_id=function_id(fn_b),
                call_type=RESOLVED,
                confidence=1.0,
                line=0,
            )
        ],
    )
    write(db, graph)
    count = _count(
        db,
        "MATCH (a:Function {name: 'fn_a'})-[r:CALLS]->(b:Function {name: 'fn_b'}) RETURN count(*)"
    )
    assert count == 1


def test_calls_edge_unresolved_no_crash(db: GraphDB) -> None:
    """An unresolved call (no edge) must not crash; function node is still written."""
    fn = make_function(name="fn", file_path="/repo/a.py", raw_calls=["totally_unknown_xyz"])
    pf = make_file(path="/repo/a.py", functions=[fn])
    write(db, ResolvedGraph(files=[pf]))
    count = _count(db, "MATCH (n:Function {name: 'fn'}) RETURN count(n)")
    assert count == 1


def test_calls_extern_edge(db: GraphDB) -> None:
    """Calls to external libraries should produce CALLS_EXTERN edges."""
    fn = make_function(name="fetch", file_path="/repo/a.py", raw_calls=["requests.get"])
    pf = make_file(path="/repo/a.py", functions=[fn])
    graph = ResolvedGraph(
        files=[pf],
        external_call_edges=[
            ExternalCallEdge(
                caller_id=function_id(fn),
                full_ref="requests.get",
                library="requests",
                line=0,
            )
        ],
    )
    write(db, graph)
    count = _count(
        db,
        "MATCH (f:Function {name: 'fetch'})-[:CALLS_EXTERN]->(e:ExternalFunction) RETURN count(*)"
    )
    assert count == 1


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_idempotent_write(db: GraphDB) -> None:
    """Writing the same graph twice must not duplicate nodes."""
    fn = make_function(name="fn", file_path="/repo/a.py")
    pf = make_file(path="/repo/a.py", functions=[fn])
    graph = ResolvedGraph(files=[pf])
    write(db, graph)
    write(db, graph)
    count = _count(db, "MATCH (n:Function {name: 'fn'}) RETURN count(n)")
    assert count == 1


def test_empty_graph_no_crash(db: GraphDB) -> None:
    write(db, ResolvedGraph())
