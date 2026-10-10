"""Symbol search: files, classes, functions and methods by name or path.

Matching is case-insensitive substring matching done in the graph with
``lower(x) CONTAINS lower($q)``; the user text only ever reaches Cypher as a
``$parameter``, so ``%``, ``_``, quotes and backslashes are literal. Each candidate is
then classified (see ``SearchMatch``) and ranked by match class, fan-in, then name.
"""

from __future__ import annotations

from pathlib import Path

from compass_core.graph.db import GraphDB, QueryParams, as_rows
from compass_core.index.locate import IndexLocation
from compass_core.query.models import SymbolRef
from compass_core.query.params import SearchParams
from compass_core.query.results import SearchHit, SearchResult
from compass_core.query.rows import (
    count_value,
    file_from_row,
    is_method_flag,
    symbol_from_row,
    to_repo_path,
)
from compass_core.query.status import index_status
from compass_core.query.types import SearchMatch, SymbolKind

_RANK = {match: i for i, match in enumerate(SearchMatch)}

# Candidates are fetched by the last dotted segment of the query ("User.save" -> "save"),
# then classified in Python against the full qualified name.
_DEFINITION_WHERE = "lower(n.name) CONTAINS lower($last)"
_FUNCTION_QUERY = (
    "MATCH (n:Function) WHERE " + _DEFINITION_WHERE + " "
    "OPTIONAL MATCH (c:Function)-[:CALLS]->(n) "
    "RETURN n.id, n.name, n.file_path, n.line_start, n.line_end, n.signature, n.is_method, "
    "count(c)"
)
_CLASS_QUERY = (
    "MATCH (n:Class) WHERE " + _DEFINITION_WHERE + " "
    "RETURN n.id, n.name, n.file_path, n.line_start, n.line_end, '' AS signature, 0"
)
_FILE_QUERY = (
    "MATCH (n:File) WHERE lower(n.path) CONTAINS lower($q) "
    "OPTIONAL MATCH (i:File)-[:IMPORTS]->(n) "
    "RETURN n.path, n.module_name, count(i)"
)


def _classify_definition(symbol: SymbolRef, query: str) -> SearchMatch | None:
    """Match class of a function/class for a lower-cased ``query``, or ``None``."""
    name = symbol.name.lower()
    qualified = symbol.qualified_name.lower()
    if name == query or qualified == query:
        return SearchMatch.EXACT
    if qualified.endswith("." + query):
        return SearchMatch.QUALIFIED_SUFFIX
    if name.startswith(query):
        return SearchMatch.PREFIX
    if query in name:
        return SearchMatch.SUBSTRING
    return None


def _classify_file(symbol: SymbolRef, query: str) -> SearchMatch | None:
    """Match class of a file for a lower-cased ``query``, or ``None``."""
    path = (symbol.file_path or "").lower()
    name = symbol.name.lower()
    if path == query or name == query:
        return SearchMatch.EXACT
    if path.endswith("/" + query):
        return SearchMatch.QUALIFIED_SUFFIX
    if path.startswith(query) or name.startswith(query):
        return SearchMatch.PREFIX
    if query in path:
        return SearchMatch.SUBSTRING
    return None


def _definition_hits(
    db: GraphDB, kind: SymbolKind | None, text: str, repo_root: Path
) -> list[SearchHit]:
    params: QueryParams = {"last": text.rsplit(".", 1)[-1]}
    lowered = text.lower()
    hits: list[SearchHit] = []

    def add(symbol: SymbolRef, fan_in: int) -> None:
        match = _classify_definition(symbol, lowered)
        if match is not None:
            hits.append(SearchHit(symbol=symbol, match=match, fan_in=fan_in))

    if kind in (None, SymbolKind.CLASS):
        for row in as_rows(db.execute(_CLASS_QUERY, params)):
            add(symbol_from_row(row, SymbolKind.CLASS, repo_root), 0)
    if kind in (None, SymbolKind.FUNCTION, SymbolKind.METHOD):
        for row in as_rows(db.execute(_FUNCTION_QUERY, params)):
            row_kind = SymbolKind.METHOD if is_method_flag(row[6]) else SymbolKind.FUNCTION
            if kind in (None, row_kind):
                add(symbol_from_row(row, row_kind, repo_root), count_value(row[7]))
    return hits


def _file_hits(db: GraphDB, text: str, repo_root: Path) -> list[SearchHit]:
    lowered = text.lower()
    hits: list[SearchHit] = []
    for row in as_rows(db.execute(_FILE_QUERY, {"q": text})):
        symbol = file_from_row(row, repo_root)
        # Stored paths may be absolute; classify on the repo-relative path so the
        # repo root directory never matches.
        symbol_path = to_repo_path(row[0], repo_root)
        match = _classify_file(symbol, lowered) if symbol_path == symbol.file_path else None
        if match is not None:
            hits.append(SearchHit(symbol=symbol, match=match, fan_in=count_value(row[2])))
    return hits


def find_symbols(db: GraphDB, location: IndexLocation, params: SearchParams) -> SearchResult:
    """Search files, classes, functions and methods.

    Args:
        db: Open graph database.
        location: Index location, used to build the result's ``IndexStatus``. (Adds
            ``location`` to the parent spec's signature; recorded ruling.)
        params: Query text, optional kind filter and limit.

    Returns:
        Hits best first: ``EXACT`` > ``QUALIFIED_SUFFIX`` > ``PREFIX`` > ``SUBSTRING``,
        ties broken by fan-in (incoming ``CALLS`` for functions, incoming ``IMPORTS``
        for files, 0 for classes) then name. ``total`` counts matches before the limit.

    Raises:
        IndexIncompatibleError: A stored row or the index metadata is unreadable.

    Note:
        Cost is O(matches of the last dotted segment of the query) because an exact
        ``total`` is required. Qualified-prefix queries such as ``auth.decode`` are not
        supported: dotted queries match only exactly or as a suffix of the qualified
        name. A query whose last dotted segment is empty (``"."``, ``"a."``) matches
        nothing. ``index_status`` stats every indexed file per call; callers may cache.
        Fan-in counts edges (not distinct callers), as in ``references``.

    Example:
        ``find_symbols(db, loc, SearchParams(query="User.save"))`` returns
        ``app/models.py::User.save`` first with ``SearchMatch.QUALIFIED_SUFFIX``.
    """
    repo_root = location.repo_root.resolve()
    text = params.query.strip()
    hits: list[SearchHit] = []
    if text.endswith("."):
        # Empty last segment: a CONTAINS '' scan would match everything.
        return _result(db, location, params, hits)
    if params.kind in (None, SymbolKind.FILE):
        hits += _file_hits(db, text, repo_root)
    hits += _definition_hits(db, params.kind, text, repo_root)
    return _result(db, location, params, hits)


def _result(
    db: GraphDB, location: IndexLocation, params: SearchParams, hits: list[SearchHit]
) -> SearchResult:
    hits.sort(key=lambda h: (_RANK[h.match], -h.fan_in, h.symbol.name, h.symbol.id))
    return SearchResult(
        index=index_status(location, db),
        caveats=(),
        query=params.query,
        kind=params.kind,
        hits=tuple(hits[: params.limit]),
        total=len(hits),
        truncated=len(hits) > params.limit,
    )
