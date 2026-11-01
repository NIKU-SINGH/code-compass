"""``shared_types`` stays in step with the schema, the resolver and the writer."""

from __future__ import annotations

from typing import get_args

from compass_core.graph.db import GraphDB
from compass_core.graph.schema import create_schema
from compass_core.index.locate import IndexLocation
from compass_core.ir.graph import CONFIDENCE
from compass_core.query.rows import call_type_value
from compass_core.shared_types import (
    CallType,
    DefinitionKind,
    EdgeType,
    SymbolKind,
    UnlinkedCall,
)


def test_edge_types_are_exactly_the_relationship_tables(tmp_path) -> None:
    with GraphDB(tmp_path / "graph.ladybug") as db:
        create_schema(db)
        assert set(db.rel_table_names()) == {edge.value for edge in EdgeType}


def test_every_resolver_outcome_has_a_confidence() -> None:
    assert set(CONFIDENCE) == set(CallType) | set(UnlinkedCall)


def test_call_outcomes_do_not_overlap() -> None:
    assert not {c.value for c in CallType} & {u.value for u in UnlinkedCall}


def test_definition_kinds_are_symbol_kinds() -> None:
    assert set(get_args(DefinitionKind)) == {
        SymbolKind.CLASS,
        SymbolKind.FUNCTION,
        SymbolKind.METHOD,
    }


def test_written_call_types_read_back(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    rows = fixture_db.execute("MATCH ()-[c:CALLS]->() RETURN DISTINCT c.call_type").get_all()
    assert rows
    assert all(isinstance(call_type_value(row[0]), CallType) for row in rows)
