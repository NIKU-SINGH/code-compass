"""Repository overview: totals, entry points and the hot spots of the graph.

Every list comes from one aggregate query. The riskiest-to-change list additionally
runs the reverse ``CALLS`` walk of ``impact_walk`` for a bounded set of candidates.
"""

from __future__ import annotations

from compass_core.contract.models import Caveat, SymbolRef
from compass_core.contract.results import (
    CallResolution,
    IndexCounts,
    LibraryUsage,
    OverviewResult,
    RankedSymbol,
)
from compass_core.contract.types import CaveatCode
from compass_core.graph.db import GraphDB, Row
from compass_core.index.locate import IndexLocation
from compass_core.query.cypher import Query
from compass_core.query.impact import RAW_CALLERS, bare_call_name
from compass_core.query.impact_walk import walk_symbols
from compass_core.query.rows import (
    FILE_FIELDS,
    FILE_WIDTH,
    FUNCTION_FIELDS,
    FUNCTION_WIDTH,
    columns,
    count_value,
    file_from_row,
    function_from_row,
    text_value,
)
from compass_core.query.status import index_status
from compass_core.shared_types import EdgeType

TOP_N = 5
"""Length of every ranked list."""

RISK_CANDIDATES = 30
"""How many most-called functions are walked to rank ``riskiest_to_change``.

Mirrored by ``RISK_CANDIDATES`` in ``apps/web/src/lib/limits.ts`` (card copy); keep in sync.
"""

RISK_DEPTH = 3
"""Traversal depth used to count the symbols affected by a change."""


def _count(row: Row) -> int:
    return count_value(row[0])


_FILE_COUNT: Query[int] = Query("MATCH (n:File) RETURN count(n)", _count)
_CLASS_COUNT: Query[int] = Query("MATCH (n:Class) RETURN count(n)", _count)
_FUNCTION_COUNT: Query[int] = Query("MATCH (n:Function) RETURN count(n)", _count)
_EDGE_COUNTS: dict[EdgeType, Query[int]] = {
    edge: Query(f"MATCH ()-[r:{edge.value}]->() RETURN count(r)", _count) for edge in EdgeType
}
"""One count query per relationship table; ``EdgeType`` values are the table names."""
_ENTRY_POINTS: Query[SymbolRef] = Query(
    f"""
    MATCH (f:File) WHERE NOT EXISTS {{ MATCH (:File)-[:IMPORTS]->(f) }}
    RETURN {columns("f", FILE_FIELDS)} ORDER BY f.path LIMIT $limit
    """,
    file_from_row,
)
_MOST_IMPORTED: Query[RankedSymbol] = Query(
    f"""
    MATCH (i:File)-[:IMPORTS]->(f:File)
    RETURN {columns("f", FILE_FIELDS)}, count(DISTINCT i) AS n
    ORDER BY n DESC, f.path LIMIT $limit
    """,
    lambda row: RankedSymbol(symbol=file_from_row(row), count=count_value(row[FILE_WIDTH])),
)
_MOST_CALLED: Query[tuple[SymbolRef, int]] = Query(
    f"""
    MATCH (c:Function)-[:CALLS]->(n:Function)
    RETURN {columns("n", FUNCTION_FIELDS)}, count(DISTINCT c) AS k
    ORDER BY k DESC, n.name, n.id LIMIT $limit
    """,
    lambda row: (function_from_row(row), count_value(row[FUNCTION_WIDTH])),
)
_LIBRARIES: Query[LibraryUsage] = Query(
    """
    MATCH (:Function)-[e:CALLS_EXTERN]->(x:ExternalFunction)
    RETURN x.library, count(e) AS n ORDER BY n DESC, x.library LIMIT $limit
    """,
    lambda row: LibraryUsage(library=text_value(row[0], "library"), call_count=count_value(row[1])),
)


def index_counts(db: GraphDB) -> IndexCounts:
    """Count the nodes of an index and its edges of every type.

    Args:
        db: Open, read-only graph database.

    Returns:
        The totals. ``edges_by_type`` has every ``EdgeType``, zeros included, and
        ``functions`` counts functions and methods.

    Raises:
        IndexIncompatibleError: A stored count is not an integer.

    Example:
        A repo with one file holding one function has ``files=1``, ``functions=1`` and
        ``edges_by_type[EdgeType.CONTAINS] == 1``.
    """
    return IndexCounts(
        files=_FILE_COUNT.first(db) or 0,
        classes=_CLASS_COUNT.first(db) or 0,
        functions=_FUNCTION_COUNT.first(db) or 0,
        edges_by_type={edge: query.first(db) or 0 for edge, query in _EDGE_COUNTS.items()},
    )


def entry_points(db: GraphDB) -> tuple[SymbolRef, ...]:
    """List the files nobody imports, by path.

    Args:
        db: Open, read-only graph database.

    Returns:
        At most ``TOP_N`` ``FILE`` symbols.

    Raises:
        IndexIncompatibleError: A stored row is unreadable.

    Example:
        If ``app/main.py`` imports ``app/auth.py``, only ``app/main.py`` is returned.
    """
    return tuple(_ENTRY_POINTS.run(db, {"limit": TOP_N}))


def _call_resolution(db: GraphDB) -> CallResolution:
    """Count call sites, and those whose called name matches a resolved callee of the caller."""
    total = resolved = 0
    for caller in RAW_CALLERS.run(db):
        for raw in caller.raw_calls:
            total += 1
            resolved += bare_call_name(raw) in caller.reached
    return CallResolution(total=total, resolved=resolved)


def _riskiest(db: GraphDB, called: list[tuple[SymbolRef, int]]) -> tuple[RankedSymbol, ...]:
    """Rank candidates (results of ``_MOST_CALLED``) by symbols affected at ``RISK_DEPTH``."""
    ranked = [
        RankedSymbol(
            symbol=symbol,
            count=len(walk_symbols(db, symbol, depth=RISK_DEPTH, min_confidence=0.0).reached),
        )
        for symbol, _ in called
    ]
    ranked.sort(key=lambda r: (-r.count, r.symbol.name, r.symbol.id))
    return tuple(ranked[:TOP_N])


def _caveats(counts: IndexCounts, stale: int) -> tuple[Caveat, ...]:
    caveats: list[Caveat] = []
    if stale:
        noun = "file has" if stale == 1 else "files have"
        message = f"{stale} indexed {noun} changed since the last ingest; run `compass ingest`"
        caveats.append(Caveat(code=CaveatCode.STALE_INDEX, message=message, count=stale))
    if counts.functions and not counts.edges_by_type[EdgeType.CALLS]:
        message = (
            "no function-to-function calls were resolved among the "
            f"{counts.functions} indexed functions; symbol-level lists may be empty"
        )
        caveats.append(
            Caveat(code=CaveatCode.UNRESOLVED_CALLS, message=message, count=counts.functions)
        )
    return tuple(caveats)


def overview(db: GraphDB, location: IndexLocation) -> OverviewResult:
    """Summarise an index: totals, entry points and ranked hot spots.

    Args:
        db: Open, read-only graph database.
        location: Index location, used for the ``IndexStatus``.

    Returns:
        An ``OverviewResult``. ``counts.edges_by_type`` has every ``EdgeType`` (zeros
        included) and ``counts.functions`` counts functions and methods.
        ``call_resolution`` counts every call site and those matching a callee the caller
        has an edge to (a constructor call such as ``User()`` has no edge, so it counts as
        unresolved). Each list holds
        at most 5 entries: ``entry_points`` are files nobody imports, by path;
        ``most_imported_files`` ranks files by importing files; ``most_called_functions``
        ranks functions and methods by distinct callers; ``top_external_libraries`` ranks
        libraries by ``CALLS_EXTERN`` edges; ``riskiest_to_change`` ranks functions and
        methods by the number of symbols a change affects within 3 hops of reverse
        ``CALLS``. To bound the cost only the 30 most-called functions (fan-in at least
        1) are walked, so a rarely called function with a deep caller chain can be
        missed. Ties break by name. Caveats: ``STALE_INDEX`` when indexed files changed,
        and ``UNRESOLVED_CALLS`` (count = functions) when functions exist but no call
        was resolved, which is why the symbol-level lists may be empty.

    Raises:
        IndexIncompatibleError: A stored row or the index metadata is unreadable.

    Example:
        On a repo where ``handle``, ``run`` and ``nightly`` call ``decode_token`` and
        ``tick`` calls ``nightly``, ``riskiest_to_change[0]`` is ``decode_token`` with
        ``count=4``.
    """
    status = index_status(location, db)  # first: rejects an incompatible index
    limit = {"limit": TOP_N}
    counts = index_counts(db)
    called = _MOST_CALLED.run(db, {"limit": RISK_CANDIDATES})
    return OverviewResult(
        index=status,
        caveats=_caveats(counts, status.stale_file_count),
        counts=counts,
        call_resolution=_call_resolution(db),
        entry_points=entry_points(db),
        most_imported_files=tuple(_MOST_IMPORTED.run(db, limit)),
        most_called_functions=tuple(
            RankedSymbol(symbol=symbol, count=count) for symbol, count in called[:TOP_N]
        ),
        riskiest_to_change=_riskiest(db, called),
        top_external_libraries=tuple(_LIBRARIES.run(db, limit)),
    )
