"""The whole graph as nodes and edges, for adapters that draw it.

Unlike the other operations this returns no ``ResultHeader``: a map answers no question
about the index, so it carries neither an ``IndexStatus`` nor caveats.
"""

from __future__ import annotations

from dataclasses import dataclass

from compass_core.contract.types import SymbolId
from compass_core.graph.db import GraphDB, Row
from compass_core.query.cypher import Query
from compass_core.query.rows import (
    is_method_flag,
    public_file_id,
    text_value,
)
from compass_core.shared_types import EdgeType, SymbolKind


@dataclass(frozen=True, slots=True, kw_only=True)
class _StoredDefinition:
    """A class or function as stored: id, name and path.

    Attributes:
        id: Public id.
        name: Unqualified name.
        kind: ``CLASS``, ``FUNCTION`` or ``METHOD``.
        path: Stored ``file_path``.

    Example:
        ``class User`` in ``app/models.py`` gives ``_StoredDefinition(id="app/models.py::User",
        name="User", kind=SymbolKind.CLASS, path="app/models.py")``.
    """

    id: str
    name: str
    kind: SymbolKind
    path: str


def _definition(row: Row, kind: SymbolKind) -> _StoredDefinition:
    return _StoredDefinition(
        id=text_value(row[0], "id"),
        name=text_value(row[1], "name"),
        kind=kind,
        path=text_value(row[2], "file_path"),
    )


def _edge_query(cypher: str, edge_type: EdgeType) -> Query[MapEdge]:
    return Query(
        cypher,
        lambda row: MapEdge(
            source=text_value(row[0], "source"), target=text_value(row[1], "target"), type=edge_type
        ),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class MapNode:
    """One file, class, function or method in the map.

    Attributes:
        id: What ``MapEdge.source`` and ``MapEdge.target`` refer to: the public id of a
            class or function, the path of a file.
        label: Short display name.
        kind: Kind of node; never ``EXTERNAL``.
        file_path: Repo-relative path.
        public_id: Public id, accepted wherever a query takes a reference.

    Example:
        ``def f(): ...`` in ``a.py`` becomes ``MapNode(id="a.py::f", label="f",
        kind=SymbolKind.FUNCTION, file_path="a.py", public_id=SymbolId("a.py::f"))``.
    """

    id: str
    label: str
    kind: SymbolKind
    file_path: str
    public_id: SymbolId


@dataclass(frozen=True, slots=True, kw_only=True)
class MapEdge:
    """One relationship between two ``MapNode`` values.

    Attributes:
        source: ``MapNode.id`` the edge leaves.
        target: ``MapNode.id`` the edge enters.
        type: Kind of edge; never ``CALLS_EXTERN``, whose targets are not in the map.

    Example:
        ``a.py`` importing ``b.py`` becomes ``MapEdge(source="a.py", target="b.py",
        type=EdgeType.IMPORTS)``.
    """

    source: str
    target: str
    type: EdgeType


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphMap:
    """Every indexed node and the deduplicated edges between them.

    Attributes:
        nodes: Files, then classes, then functions and methods.
        edges: Distinct ``(source, target, type)`` edges, grouped by type.

    Example:
        A repo with one file holding one function has two nodes and one ``CONTAINS``
        edge.
    """

    nodes: tuple[MapNode, ...]
    edges: tuple[MapEdge, ...]


_FILE_PATHS: Query[str] = Query(
    "MATCH (f:File) RETURN f.path", lambda row: text_value(row[0], "path")
)
_CLASSES: Query[_StoredDefinition] = Query(
    "MATCH (c:Class) RETURN c.id, c.name, c.file_path",
    lambda row: _definition(row, SymbolKind.CLASS),
)
_FUNCTIONS: Query[_StoredDefinition] = Query(
    "MATCH (fn:Function) RETURN fn.id, fn.name, fn.file_path, fn.is_method",
    lambda row: _definition(
        row, SymbolKind.METHOD if is_method_flag(row[3]) else SymbolKind.FUNCTION
    ),
)
_EDGES: tuple[Query[MapEdge], ...] = (
    _edge_query("MATCH (a:File)-[:CONTAINS]->(b:Class) RETURN a.path, b.id", EdgeType.CONTAINS),
    _edge_query("MATCH (a:File)-[:CONTAINS]->(b:Function) RETURN a.path, b.id", EdgeType.CONTAINS),
    _edge_query("MATCH (a:Class)-[:CONTAINS]->(b:Function) RETURN a.id, b.id", EdgeType.CONTAINS),
    _edge_query("MATCH (a:File)-[:IMPORTS]->(b:File) RETURN a.path, b.path", EdgeType.IMPORTS),
    _edge_query("MATCH (a:Class)-[:INHERITS]->(b:Class) RETURN a.id, b.id", EdgeType.INHERITS),
    _edge_query("MATCH (a:Function)-[:CALLS]->(b:Function) RETURN a.id, b.id", EdgeType.CALLS),
)


def _file_nodes(db: GraphDB) -> list[MapNode]:
    return [
        MapNode(
            id=path,
            label=path.split("/")[-1],
            kind=SymbolKind.FILE,
            file_path=path,
            public_id=public_file_id(path),
        )
        for path in _FILE_PATHS.run(db)
    ]


def _definition_nodes(db: GraphDB) -> list[MapNode]:
    return [
        MapNode(id=d.id, label=d.name, kind=d.kind, file_path=d.path, public_id=SymbolId(d.id))
        for d in (*_CLASSES.run(db), *_FUNCTIONS.run(db))
    ]


def _edges(db: GraphDB) -> tuple[MapEdge, ...]:
    edges = (edge for query in _EDGES for edge in query.run(db))
    return tuple(dict.fromkeys(edges))


def graph_map(db: GraphDB) -> GraphMap:
    """Read every node and edge of an index.

    Args:
        db: Open, read-only graph database.

    Returns:
        The map: files, then classes, then functions and methods, and the distinct
        edges between them.

    Raises:
        IndexIncompatibleError: A stored column has an unexpected type.

    Example:
        ``graph_map(db).nodes[0].public_id`` is ``"file::app/auth.py"`` when
        ``app/auth.py`` is the first indexed file.
    """
    return GraphMap(nodes=(*_file_nodes(db), *_definition_nodes(db)), edges=_edges(db))
