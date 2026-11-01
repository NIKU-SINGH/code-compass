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

from compass_core.graph.db import GraphDB, QueryParams, as_rows
from compass_core.index.locate import IndexLocation
from compass_core.query.models import SymbolRef
from compass_core.query.references import ResolvedReference, resolve, stored_paths
from compass_core.query.results import Lookup, NodeDetail
from compass_core.query.rows import file_from_row, is_method_flag, symbol_from_row
from compass_core.query.status import index_status
from compass_core.shared_types import SymbolKind

_SEP = "::"
MAX_FILE_BYTES = 512 * 1024
"""Largest file whose text is returned; bigger files are described without source."""
MAX_RELATED = 200
"""Most neighbours returned per relationship; the result is flagged ``truncated`` past it."""

_CLASS_COLUMNS = "{v}.id, {v}.name, {v}.file_path, {v}.line_start, {v}.line_end, '' AS signature"
_FUNCTION_COLUMNS = (
    "{v}.id, {v}.name, {v}.file_path, {v}.line_start, {v}.line_end, {v}.signature, {v}.is_method"
)
# Selects the one definition node `n` a symbol refers to: stored paths may be absolute or
# relative, and the stored id always ends with "::<[Class.]name>".
_DEFINITION_WHERE = "n.file_path IN $paths AND n.id ENDS WITH $tail"


def _definition_params(symbol: SymbolRef, repo_root: Path) -> QueryParams:
    return {
        "paths": stored_paths(symbol.file_path or "", repo_root),
        "tail": _SEP + symbol.id.rsplit(_SEP, 1)[1],
    }


def _text_or_none(value: object) -> str | None:
    """Docstring/source column: ``None`` or empty means absent."""
    return value if isinstance(value, str) and value.strip() else None


def _classes(db: GraphDB, query: str, params: QueryParams, root: Path) -> list[SymbolRef]:
    return [symbol_from_row(r, SymbolKind.CLASS, root) for r in as_rows(db.execute(query, params))]


def _functions(db: GraphDB, query: str, params: QueryParams, root: Path) -> list[SymbolRef]:
    return [
        symbol_from_row(r, SymbolKind.METHOD if is_method_flag(r[6]) else SymbolKind.FUNCTION, root)
        for r in as_rows(db.execute(query, params))
    ]


def _ordered(symbols: list[SymbolRef]) -> list[SymbolRef]:
    """Stable display order: by file, line, then id."""
    return sorted(symbols, key=lambda s: (s.file_path or "", s.line_start or 0, s.id))


def _class_relations(
    db: GraphDB, params: QueryParams, root: Path
) -> tuple[list[SymbolRef], list[SymbolRef], list[SymbolRef]]:
    where = "WHERE " + _DEFINITION_WHERE.replace("n.", "c.")
    bases = _classes(
        db,
        f"MATCH (c:Class)-[:INHERITS]->(b:Class) {where} "
        f"RETURN DISTINCT {_CLASS_COLUMNS.format(v='b')}",
        params,
        root,
    )
    subclasses = _classes(
        db,
        f"MATCH (b:Class)-[:INHERITS]->(c:Class) {where} "
        f"RETURN DISTINCT {_CLASS_COLUMNS.format(v='b')}",
        params,
        root,
    )
    members = _functions(
        db,
        f"MATCH (c:Class)-[:CONTAINS]->(m:Function) {where} "
        f"RETURN DISTINCT {_FUNCTION_COLUMNS.format(v='m')}",
        params,
        root,
    )
    return bases, subclasses, members


def _function_relations(
    db: GraphDB, params: QueryParams, root: Path
) -> tuple[list[SymbolRef], list[SymbolRef]]:
    where = "WHERE " + _DEFINITION_WHERE.replace("n.", "f.")
    callees = _functions(
        db,
        f"MATCH (f:Function)-[:CALLS]->(g:Function) {where} "
        f"RETURN DISTINCT {_FUNCTION_COLUMNS.format(v='g')}",
        params,
        root,
    )
    callers = _functions(
        db,
        f"MATCH (g:Function)-[:CALLS]->(f:Function) {where} "
        f"RETURN DISTINCT {_FUNCTION_COLUMNS.format(v='g')}",
        params,
        root,
    )
    return callees, callers


def _file_relations(
    db: GraphDB, symbol: SymbolRef, root: Path
) -> tuple[list[SymbolRef], list[SymbolRef], list[SymbolRef]]:
    params: QueryParams = {"paths": stored_paths(symbol.file_path or "", root)}
    members = _classes(
        db,
        f"MATCH (f:File)-[:CONTAINS]->(n:Class) WHERE f.path IN $paths "
        f"RETURN DISTINCT {_CLASS_COLUMNS.format(v='n')}",
        params,
        root,
    ) + _functions(
        db,
        f"MATCH (f:File)-[:CONTAINS]->(n:Function) WHERE f.path IN $paths "
        f"RETURN DISTINCT {_FUNCTION_COLUMNS.format(v='n')}",
        params,
        root,
    )
    imports = [
        file_from_row(r, root)
        for r in as_rows(
            db.execute(
                "MATCH (f:File)-[:IMPORTS]->(g:File) WHERE f.path IN $paths "
                "RETURN DISTINCT g.path, g.module_name",
                params,
            )
        )
    ]
    imported_by = [
        file_from_row(r, root)
        for r in as_rows(
            db.execute(
                "MATCH (g:File)-[:IMPORTS]->(f:File) WHERE f.path IN $paths "
                "RETURN DISTINCT g.path, g.module_name",
                params,
            )
        )
    ]
    return members, imports, imported_by


def _cap(symbols: list[SymbolRef]) -> tuple[tuple[SymbolRef, ...], bool]:
    ordered = _ordered(symbols)
    return tuple(ordered[:MAX_RELATED]), len(ordered) > MAX_RELATED


def _docstring_and_source(
    db: GraphDB, symbol: SymbolRef, root: Path
) -> tuple[str | None, str | None]:
    if symbol.kind not in (SymbolKind.CLASS, SymbolKind.FUNCTION, SymbolKind.METHOD):
        return None, None
    label = "Class" if symbol.kind is SymbolKind.CLASS else "Function"
    rows = as_rows(
        db.execute(
            f"MATCH (n:{label}) WHERE {_DEFINITION_WHERE} RETURN n.docstring, n.source",
            _definition_params(symbol, root),
        )
    )
    if not rows:
        return None, None
    return _text_or_none(rows[0][0]), _text_or_none(rows[0][1])


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
    root = location.repo_root.resolve()
    resolved = resolve(db, ref, repo_root=root, allow_file=True)
    if not isinstance(resolved, ResolvedReference):
        return resolved

    symbol = resolved.symbol
    docstring, source = _docstring_and_source(db, symbol, root)
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
        bases, subclasses, members = _class_relations(db, _definition_params(symbol, root), root)
    elif symbol.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD):
        callees, callers = _function_relations(db, _definition_params(symbol, root), root)
    elif symbol.kind is SymbolKind.FILE:
        members, imports, imported_by = _file_relations(db, symbol, root)

    capped = [_cap(x) for x in (bases, subclasses, members, callees, callers, imports, imported_by)]
    return NodeDetail(
        index=index_status(location, db),
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
