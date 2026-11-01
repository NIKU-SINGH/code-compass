"""The whole graph as nodes and edges, for adapters that draw it.

Unlike the other operations this returns no ``ResultHeader``: a map answers no question
about the index, so it carries neither an ``IndexStatus`` nor caveats.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from compass_core.errors import IndexIncompatibleError
from compass_core.graph.db import GraphDB, as_rows
from compass_core.query.rows import (
    is_method_flag,
    public_definition_id,
    public_file_id,
    text_value,
)
from compass_core.query.types import SymbolId
from compass_core.shared_types import EdgeType, SymbolKind

logger = logging.getLogger(__name__)

_FILES = "MATCH (f:File) RETURN f.path"
_CLASSES = "MATCH (c:Class) RETURN c.id, c.name, c.file_path"
_FUNCTIONS = "MATCH (fn:Function) RETURN fn.id, fn.name, fn.file_path, fn.is_method"
_EDGES: tuple[tuple[str, EdgeType], ...] = (
    ("MATCH (a:File)-[:CONTAINS]->(b:Class) RETURN a.path, b.id", EdgeType.CONTAINS),
    ("MATCH (a:File)-[:CONTAINS]->(b:Function) RETURN a.path, b.id", EdgeType.CONTAINS),
    ("MATCH (a:Class)-[:CONTAINS]->(b:Function) RETURN a.id, b.id", EdgeType.CONTAINS),
    ("MATCH (a:File)-[:IMPORTS]->(b:File) RETURN a.path, b.path", EdgeType.IMPORTS),
    ("MATCH (a:Class)-[:INHERITS]->(b:Class) RETURN a.id, b.id", EdgeType.INHERITS),
    ("MATCH (a:Function)-[:CALLS]->(b:Function) RETURN a.id, b.id", EdgeType.CALLS),
)


@dataclass(frozen=True, slots=True, kw_only=True)
class MapNode:
    """One file, class, function or method in the map.

    Attributes:
        id: Stored id, the value ``MapEdge.source`` and ``MapEdge.target`` refer to.
        label: Short display name.
        kind: Kind of node; never ``EXTERNAL``.
        file_path: Path as stored in the graph.
        public_id: Public id, accepted wherever a query takes a reference.

    Example:
        ``def f(): ...`` in ``a.py`` becomes ``MapNode(id="py::a::f", label="f",
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


def _file_nodes(db: GraphDB, repo_root: Path) -> list[MapNode]:
    nodes: list[MapNode] = []
    for row in as_rows(db.execute(_FILES)):
        path = text_value(row[0], "path")
        nodes.append(
            MapNode(
                id=path,
                label=path.split("/")[-1],
                kind=SymbolKind.FILE,
                file_path=path,
                public_id=public_file_id(path, repo_root),
            )
        )
    return nodes


def _definition_node(
    stored_id: str, name: str, kind: SymbolKind, path: str, repo_root: Path
) -> MapNode | None:
    try:
        public_id = public_definition_id(stored_id, path, repo_root)
    except IndexIncompatibleError:
        return None
    return MapNode(id=stored_id, label=name, kind=kind, file_path=path, public_id=public_id)


def _definition_nodes(db: GraphDB, repo_root: Path) -> list[MapNode]:
    found: list[MapNode | None] = []
    for row in as_rows(db.execute(_CLASSES)):
        id_, name, path = (text_value(row[i], c) for i, c in enumerate(("id", "name", "file_path")))
        found.append(_definition_node(id_, name, SymbolKind.CLASS, path, repo_root))
    for row in as_rows(db.execute(_FUNCTIONS)):
        id_, name, path = (text_value(row[i], c) for i, c in enumerate(("id", "name", "file_path")))
        kind = SymbolKind.METHOD if is_method_flag(row[3]) else SymbolKind.FUNCTION
        found.append(_definition_node(id_, name, kind, path, repo_root))

    nodes = [node for node in found if node is not None]
    if len(nodes) < len(found):
        logger.warning(
            "graph map: skipped %d definition(s) with malformed stored ids",
            len(found) - len(nodes),
        )
    return nodes


def _edges(db: GraphDB) -> tuple[MapEdge, ...]:
    edges = (
        MapEdge(
            source=text_value(row[0], "source"), target=text_value(row[1], "target"), type=edge_type
        )
        for query, edge_type in _EDGES
        for row in as_rows(db.execute(query))
    )
    return tuple(dict.fromkeys(edges))


def graph_map(db: GraphDB, repo_root: Path) -> GraphMap:
    """Read every node and edge of an index.

    Args:
        db: Open, read-only graph database.
        repo_root: Absolute repository root, used to build public ids.

    Returns:
        The map. A definition whose stored id is malformed is left out and logged, so
        one odd row never hides the rest of the graph; its edges are kept.

    Raises:
        IndexIncompatibleError: A stored column has an unexpected type.

    Example:
        ``graph_map(db, root).nodes[0].public_id`` is ``"file::app/auth.py"`` when
        ``app/auth.py`` is the first indexed file.
    """
    nodes = (*_file_nodes(db, repo_root), *_definition_nodes(db, repo_root))
    return GraphMap(nodes=nodes, edges=_edges(db))
