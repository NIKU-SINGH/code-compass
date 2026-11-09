"""Symbol search: files, classes, functions and methods by name or path.

Matching is case-insensitive substring matching done in the graph with
``lower(x) CONTAINS lower($q)``; the user text only ever reaches Cypher as a
``$parameter``, so ``%``, ``_``, quotes and backslashes are literal. Each candidate is
then classified (see ``SearchMatch``) and ranked by match class, fan-in, then name.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from compass_core.contract.models import SymbolRef
from compass_core.contract.params import SearchParams
from compass_core.contract.results import SearchHit, SearchResult
from compass_core.contract.types import SearchMatch
from compass_core.graph.db import GraphDB, Row
from compass_core.index.locate import IndexLocation
from compass_core.query.cypher import Query
from compass_core.query.rows import (
    CLASS_FIELDS,
    FILE_FIELDS,
    FILE_WIDTH,
    FUNCTION_FIELDS,
    FUNCTION_WIDTH,
    class_from_row,
    columns,
    count_value,
    file_from_row,
    function_from_row,
)
from compass_core.query.status import index_status
from compass_core.shared_types import SymbolKind

_RANK = {match: i for i, match in enumerate(SearchMatch)}


def _with_fan_in(
    decode: Callable[[Row, Path], SymbolRef], width: int
) -> Callable[[Row, Path], tuple[SymbolRef, int]]:
    """Decoder for rows of symbol columns followed by one count column."""
    return lambda row, root: (decode(row, root), count_value(row[width]))


# Candidates are fetched by the last dotted segment of the query ("User.save" -> "save"),
# then classified in Python against the full qualified name.
_FUNCTIONS_NAMED: Query[tuple[SymbolRef, int]] = Query(
    f"""
    MATCH (n:Function) WHERE lower(n.name) CONTAINS lower($last)
    OPTIONAL MATCH (c:Function)-[:CALLS]->(n)
    RETURN {columns("n", FUNCTION_FIELDS)}, count(c)
    """,
    _with_fan_in(function_from_row, FUNCTION_WIDTH),
)
_CLASSES_NAMED: Query[SymbolRef] = Query(
    f"""
    MATCH (n:Class) WHERE lower(n.name) CONTAINS lower($last)
    RETURN {columns("n", CLASS_FIELDS)}
    """,
    class_from_row,
)
_FILES_WITH_PATH: Query[tuple[SymbolRef, int]] = Query(
    f"""
    MATCH (n:File) WHERE lower(n.path) CONTAINS lower($q)
    OPTIONAL MATCH (i:File)-[:IMPORTS]->(n)
    RETURN {columns("n", FILE_FIELDS)}, count(i)
    """,
    _with_fan_in(file_from_row, FILE_WIDTH),
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
    params = {"last": text.rsplit(".", 1)[-1]}
    lowered = text.lower()
    hits: list[SearchHit] = []

    def add(symbol: SymbolRef, fan_in: int) -> None:
        match = _classify_definition(symbol, lowered)
        if match is not None:
            hits.append(SearchHit(symbol=symbol, match=match, fan_in=fan_in))

    if kind in (None, SymbolKind.CLASS):
        for symbol in _CLASSES_NAMED.run(db, repo_root, params):
            add(symbol, 0)
    if kind in (None, SymbolKind.FUNCTION, SymbolKind.METHOD):
        for symbol, fan_in in _FUNCTIONS_NAMED.run(db, repo_root, params):
            if kind in (None, symbol.kind):
                add(symbol, fan_in)
    return hits


def _file_hits(db: GraphDB, text: str, repo_root: Path) -> list[SearchHit]:
    lowered = text.lower()
    hits: list[SearchHit] = []
    for symbol, fan_in in _FILES_WITH_PATH.run(db, repo_root, {"q": text}):
        match = _classify_file(symbol, lowered)
        if match is not None:
            hits.append(SearchHit(symbol=symbol, match=match, fan_in=fan_in))
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
