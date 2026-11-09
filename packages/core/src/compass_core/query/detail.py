"""Node detail: everything the graph knows about one file, class, function or method.

The reference is resolved with ``references.resolve`` (a public id such as
``app/auth/permissions.py::Policy`` or ``file::app/auth/permissions.py`` resolves under the
exact-id rule). The resolved symbol is then enriched with its docstring and source text and
with the neighbours that make sense for its kind:

* class: base classes, subclasses and methods;
* function / method: callees and callers;
* file: the classes and functions it defines, the files it imports and the files that import it,
  and its text, read from the working tree (the index does not store file contents);
* external: nothing beyond the symbol.

User text only ever reaches Cypher as a ``$parameter``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from compass_core.contract.models import SymbolRef
from compass_core.contract.results import Lookup, NodeDetail
from compass_core.graph.db import GraphDB, QueryParams, Row
from compass_core.index.locate import IndexLocation
from compass_core.query.cypher import Query
from compass_core.query.references import ResolvedReference, resolve
from compass_core.query.rows import (
    CLASS_FIELDS,
    FILE_FIELDS,
    FUNCTION_FIELDS,
    class_from_row,
    columns,
    file_from_row,
    function_from_row,
)
from compass_core.query.status import index_status
from compass_core.shared_types import SymbolKind

MAX_FILE_BYTES = 512 * 1024
"""Largest file whose text is returned; bigger files are described without source."""
MAX_RELATED = 200
"""Most neighbours returned per relationship; the result is flagged ``truncated`` past it."""


def _is_definition(variable: str) -> str:
    """``WHERE`` condition selecting the definition ``$id`` (a primary-key match).

    Used only to compose the constants below, at import.
    """
    return f"{variable}.id = $id"


def _text_pair(row: Row) -> tuple[str | None, str | None]:
    return _text_or_none(row[0]), _text_or_none(row[1])


_CLASS = columns("r", CLASS_FIELDS)
_FUNCTION = columns("r", FUNCTION_FIELDS)

_BASES: Query[SymbolRef] = Query(
    f"MATCH (c:Class)-[:INHERITS]->(r:Class) WHERE {_is_definition('c')} RETURN DISTINCT {_CLASS}",
    class_from_row,
)
_SUBCLASSES: Query[SymbolRef] = Query(
    f"MATCH (r:Class)-[:INHERITS]->(c:Class) WHERE {_is_definition('c')} RETURN DISTINCT {_CLASS}",
    class_from_row,
)
_METHODS: Query[SymbolRef] = Query(
    f"MATCH (c:Class)-[:CONTAINS]->(r:Function) WHERE {_is_definition('c')} "
    f"RETURN DISTINCT {_FUNCTION}",
    function_from_row,
)
_CALLEES: Query[SymbolRef] = Query(
    f"MATCH (f:Function)-[:CALLS]->(r:Function) WHERE {_is_definition('f')} "
    f"RETURN DISTINCT {_FUNCTION}",
    function_from_row,
)
_CALLERS: Query[SymbolRef] = Query(
    f"MATCH (r:Function)-[:CALLS]->(f:Function) WHERE {_is_definition('f')} "
    f"RETURN DISTINCT {_FUNCTION}",
    function_from_row,
)
_FILE_CLASSES: Query[SymbolRef] = Query(
    f"MATCH (f:File)-[:CONTAINS]->(r:Class) WHERE f.path = $path RETURN DISTINCT {_CLASS}",
    class_from_row,
)
_FILE_FUNCTIONS: Query[SymbolRef] = Query(
    f"MATCH (f:File)-[:CONTAINS]->(r:Function) WHERE f.path = $path RETURN DISTINCT {_FUNCTION}",
    function_from_row,
)
_IMPORTS: Query[SymbolRef] = Query(
    f"MATCH (f:File)-[:IMPORTS]->(r:File) WHERE f.path = $path "
    f"RETURN DISTINCT {columns('r', FILE_FIELDS)}",
    file_from_row,
)
_IMPORTED_BY: Query[SymbolRef] = Query(
    f"MATCH (r:File)-[:IMPORTS]->(f:File) WHERE f.path = $path "
    f"RETURN DISTINCT {columns('r', FILE_FIELDS)}",
    file_from_row,
)
_CLASS_TEXT: Query[tuple[str | None, str | None]] = Query(
    f"MATCH (n:Class) WHERE {_is_definition('n')} RETURN n.docstring, n.source",
    _text_pair,
)
_FUNCTION_TEXT: Query[tuple[str | None, str | None]] = Query(
    f"MATCH (n:Function) WHERE {_is_definition('n')} RETURN n.docstring, n.source",
    _text_pair,
)


def _definition_params(symbol: SymbolRef) -> QueryParams:
    return {"id": symbol.id}


def _text_or_none(value: object) -> str | None:
    """Docstring/source column: ``None`` or empty means absent."""
    return value if isinstance(value, str) and value.strip() else None


def _ordered(symbols: list[SymbolRef]) -> list[SymbolRef]:
    """Stable display order: by file, line, then id."""
    return sorted(symbols, key=lambda s: (s.file_path or "", s.line_start or 0, s.id))


def _class_relations(
    db: GraphDB, params: QueryParams
) -> tuple[list[SymbolRef], list[SymbolRef], list[SymbolRef]]:
    return (
        _BASES.run(db, params),
        _SUBCLASSES.run(db, params),
        _METHODS.run(db, params),
    )


def _function_relations(
    db: GraphDB, params: QueryParams
) -> tuple[list[SymbolRef], list[SymbolRef]]:
    return _CALLEES.run(db, params), _CALLERS.run(db, params)


def _file_relations(
    db: GraphDB, symbol: SymbolRef
) -> tuple[list[SymbolRef], list[SymbolRef], list[SymbolRef]]:
    params: QueryParams = {"path": symbol.file_path}
    members = _FILE_CLASSES.run(db, params) + _FILE_FUNCTIONS.run(db, params)
    return members, _IMPORTS.run(db, params), _IMPORTED_BY.run(db, params)


def _cap(symbols: list[SymbolRef]) -> tuple[tuple[SymbolRef, ...], bool]:
    ordered = _ordered(symbols)
    return tuple(ordered[:MAX_RELATED]), len(ordered) > MAX_RELATED


def _docstring_and_source(db: GraphDB, symbol: SymbolRef) -> tuple[str | None, str | None]:
    if symbol.kind not in (SymbolKind.CLASS, SymbolKind.FUNCTION, SymbolKind.METHOD):
        return None, None
    query = _CLASS_TEXT if symbol.kind is SymbolKind.CLASS else _FUNCTION_TEXT
    return query.first(db, _definition_params(symbol)) or (None, None)


def _file_source(symbol: SymbolRef, root: Path) -> str | None:
    """Text of a file under ``root``, or ``None`` if it is gone, unreadable, binary-sized or outside.

    The text is what is on disk now, which can differ from what was indexed; the index status in
    the result says whether files changed since.
    """
    if not symbol.file_path:
        return None
    path = (root / symbol.file_path).resolve()
    try:
        if (
            not path.is_relative_to(root)
            or not path.is_file()
            or path.stat().st_size > MAX_FILE_BYTES
        ):
            return None
        return _text_or_none(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def describe(db: GraphDB, location: IndexLocation, ref: str) -> Lookup[NodeDetail]:
    """Describe one node of the graph.

    Args:
        db: Open graph database.
        location: Index location, used to build the result's ``IndexStatus``.
        ref: Reference to the node; a public id from the graph endpoint always resolves.

    Returns:
        A ``NodeDetail``; an ``AmbiguousReference`` or ``SymbolNotFound`` when ``ref`` does
        not resolve to exactly one node.

    Raises:
        IndexIncompatibleError: A stored row or the index metadata is unreadable.

    Example:
        ``describe(db, loc, "app/models.py::User")`` returns a ``NodeDetail`` whose ``symbol``
        has the class source, ``bases`` is empty and ``members`` lists ``User.save``.
    """
    status = index_status(location, db)  # first: rejects an incompatible index
    root = location.repo_root.resolve()
    resolved = resolve(db, ref, repo_root=root, allow_file=True)
    if not isinstance(resolved, ResolvedReference):
        return resolved

    symbol = resolved.symbol
    docstring, source = _docstring_and_source(db, symbol)
    if symbol.kind is SymbolKind.FILE:
        source = _file_source(symbol, root)
    bases: list[SymbolRef] = []
    subclasses: list[SymbolRef] = []
    members: list[SymbolRef] = []
    callees: list[SymbolRef] = []
    callers: list[SymbolRef] = []
    imports: list[SymbolRef] = []
    imported_by: list[SymbolRef] = []

    if symbol.kind is SymbolKind.CLASS:
        bases, subclasses, members = _class_relations(db, _definition_params(symbol))
    elif symbol.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD):
        callees, callers = _function_relations(db, _definition_params(symbol))
    elif symbol.kind is SymbolKind.FILE:
        members, imports, imported_by = _file_relations(db, symbol)

    capped = [_cap(x) for x in (bases, subclasses, members, callees, callers, imports, imported_by)]
    return NodeDetail(
        index=status,
        caveats=(),
        symbol=replace(symbol, source=source),
        docstring=docstring,
        bases=capped[0][0],
        subclasses=capped[1][0],
        members=capped[2][0],
        callees=capped[3][0],
        callers=capped[4][0],
        imports=capped[5][0],
        imported_by=capped[6][0],
        truncated=any(truncated for _, truncated in capped),
    )
