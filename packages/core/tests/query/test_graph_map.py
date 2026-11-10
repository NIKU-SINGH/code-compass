"""``graph_map`` returns the whole index as typed nodes and edges."""

from __future__ import annotations

from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation
from compass_core.query.graph_map import MapEdge, graph_map
from compass_core.shared_types import EdgeType, SymbolKind


def test_nodes_are_ordered_and_typed(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    nodes = graph_map(fixture_db).nodes
    kinds = [node.kind for node in nodes]

    assert kinds[0] is SymbolKind.FILE
    assert kinds.index(SymbolKind.CLASS) == kinds.count(SymbolKind.FILE)
    assert set(kinds) == {
        SymbolKind.FILE,
        SymbolKind.CLASS,
        SymbolKind.FUNCTION,
        SymbolKind.METHOD,
    }


def test_public_ids_identify_each_kind(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    by_id = {n.public_id: n for n in graph_map(fixture_db).nodes}

    assert by_id["file::app/auth.py"].kind is SymbolKind.FILE
    assert by_id["app/auth.py::decode_token"].kind is SymbolKind.FUNCTION
    assert by_id["app/models.py::User.save"].kind is SymbolKind.METHOD


def test_edges_are_distinct_and_join_known_nodes(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    result = graph_map(fixture_db)
    ids = {node.id for node in result.nodes}

    assert len(set(result.edges)) == len(result.edges)
    assert all(e.source in ids and e.target in ids for e in result.edges)
    assert {e.type for e in result.edges} <= set(EdgeType) - {EdgeType.CALLS_EXTERN}


def test_map_edge_is_hashable_by_value() -> None:
    edge = MapEdge(source="a", target="b", type=EdgeType.CALLS)
    assert len({edge, MapEdge(source="a", target="b", type=EdgeType.CALLS)}) == 1
