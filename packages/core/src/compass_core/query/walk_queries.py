"""The single-hop queries behind the impact walks, and the typed rows they return.

Each query expands one distance level for a whole frontier at once (``WHERE x IN $ids``
or ``$paths``). Rows carry the stored keys the walks match on next to the public
symbols they return.
"""

from __future__ import annotations

from dataclasses import dataclass

from compass_core.contract.models import EdgeRef, SymbolRef
from compass_core.graph.db import Row
from compass_core.query.cypher import Query
from compass_core.query.rows import (
    CLASS_FIELDS,
    CLASS_WIDTH,
    FILE_FIELDS,
    FILE_WIDTH,
    FUNCTION_FIELDS,
    FUNCTION_WIDTH,
    call_type_value,
    class_from_row,
    columns,
    confidence_value,
    file_from_row,
    function_from_row,
    line_value,
    text_value,
)
from compass_core.shared_types import EdgeType


@dataclass(frozen=True, slots=True, kw_only=True)
class CallRow:
    """A ``CALLS`` edge between two stored functions.

    Attributes:
        caller: The calling function.
        callee: The called function.
        confidence: Resolver confidence of the edge.
        edge: The edge as returned in results.

    Example:
        ``def handle(): decode_token(t)`` gives ``CallRow(caller=<handle>,
        callee=<decode_token>, confidence=1.0, edge=EdgeRef(type=EdgeType.CALLS, ...))``.
    """

    caller: SymbolRef
    callee: SymbolRef
    confidence: float
    edge: EdgeRef


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodCallRow:
    """A call to a method of a frontier class.

    Attributes:
        call: The ``CALLS`` edge to the method.
        class_key: Id of the class that owns the method.

    Example:
        ``User().save()`` resolved to ``User.save`` gives
        ``MethodCallRow(call=<caller CALLS User.save>, class_key="app/models.py::User")``.
    """

    call: CallRow
    class_key: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExternalCallRow:
    """A ``CALLS_EXTERN`` edge from a stored function.

    Attributes:
        caller: The calling function.
        line: 1-indexed call line, or ``None`` when unknown.

    Example:
        ``def encode(raw): return json.dumps(raw)`` gives
        ``ExternalCallRow(caller=<encode>, line=None)`` (call lines are not stored yet).
    """

    caller: SymbolRef
    line: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class PairRow:
    """Two nodes joined by a structural edge (``IMPORTS`` or ``INHERITS``).

    Attributes:
        source: The importing file or the subclass.
        target: The imported file or the base class.

    Example:
        ``class Admin(User)`` gives ``PairRow(source=<Admin>, target=<User>)``;
        ``from app.auth import decode_token`` in ``app/api.py`` gives
        ``PairRow(source=<app/api.py>, target=<app/auth.py>)``.
    """

    source: SymbolRef
    target: SymbolRef


_CALL_END = 2 * FUNCTION_WIDTH
_CALL_COLUMNS = "r.confidence, r.call_type, r.line"


def _call_row(row: Row) -> CallRow:
    caller = function_from_row(row[:FUNCTION_WIDTH])
    callee = function_from_row(row[FUNCTION_WIDTH:_CALL_END])
    confidence = confidence_value(row[_CALL_END])
    edge = EdgeRef(
        source_id=caller.id,
        target_id=callee.id,
        type=EdgeType.CALLS,
        confidence=confidence,
        call_type=call_type_value(row[_CALL_END + 1]),
        line=line_value(row[_CALL_END + 2], "line"),
    )
    return CallRow(caller=caller, callee=callee, confidence=confidence, edge=edge)


def _method_call_row(row: Row) -> MethodCallRow:
    return MethodCallRow(call=_call_row(row), class_key=text_value(row[_CALL_END + 3], "id"))


def _external_call_row(row: Row) -> ExternalCallRow:
    return ExternalCallRow(
        caller=function_from_row(row[:FUNCTION_WIDTH]),
        line=line_value(row[FUNCTION_WIDTH], "line"),
    )


def _class_pair(row: Row) -> PairRow:
    return PairRow(
        source=class_from_row(row[:CLASS_WIDTH]), target=class_from_row(row[CLASS_WIDTH:])
    )


def _file_pair(row: Row) -> PairRow:
    return PairRow(source=file_from_row(row[:FILE_WIDTH]), target=file_from_row(row[FILE_WIDTH:]))


_A_FUNCTION = columns("a", FUNCTION_FIELDS)
_B_FUNCTION = columns("b", FUNCTION_FIELDS)

CALLERS_OF_FUNCTIONS: Query[CallRow] = Query(
    f"""
    MATCH (a:Function)-[r:CALLS]->(b:Function)
    WHERE b.id IN $ids AND r.confidence >= $minc
    RETURN {_A_FUNCTION}, {_B_FUNCTION}, {_CALL_COLUMNS}
    """,
    _call_row,
)
CALLERS_OF_METHODS: Query[MethodCallRow] = Query(
    f"""
    MATCH (c:Class)-[:CONTAINS]->(b:Function)<-[r:CALLS]-(a:Function)
    WHERE c.id IN $ids AND r.confidence >= $minc
    RETURN {_A_FUNCTION}, {_B_FUNCTION}, {_CALL_COLUMNS}, c.id
    """,
    _method_call_row,
)
CALLERS_OF_EXTERNALS: Query[ExternalCallRow] = Query(
    f"""
    MATCH (a:Function)-[r:CALLS_EXTERN]->(e:ExternalFunction) WHERE e.full_ref IN $ids
    RETURN {_A_FUNCTION}, r.line
    """,
    _external_call_row,
)
SUBCLASSES_OF: Query[PairRow] = Query(
    f"""
    MATCH (a:Class)-[:INHERITS]->(b:Class) WHERE b.id IN $ids
    RETURN {columns("a", CLASS_FIELDS)}, {columns("b", CLASS_FIELDS)}
    """,
    _class_pair,
)
# File-target variants, keyed by the stored file paths of the frontier.
IMPORTERS_OF_FILES: Query[PairRow] = Query(
    f"""
    MATCH (a:File)-[:IMPORTS]->(b:File) WHERE b.path IN $paths
    RETURN {columns("a", FILE_FIELDS)}, {columns("b", FILE_FIELDS)}
    """,
    _file_pair,
)
CALLERS_IN_FILES: Query[CallRow] = Query(
    f"""
    MATCH (a:Function)-[r:CALLS]->(b:Function)
    WHERE b.file_path IN $paths AND r.confidence >= $minc
    RETURN {_A_FUNCTION}, {_B_FUNCTION}, {_CALL_COLUMNS}
    """,
    _call_row,
)
SUBCLASSES_IN_FILES: Query[PairRow] = Query(
    f"""
    MATCH (a:Class)-[:INHERITS]->(b:Class) WHERE b.file_path IN $paths
    RETURN {columns("a", CLASS_FIELDS)}, {columns("b", CLASS_FIELDS)}
    """,
    _class_pair,
)
