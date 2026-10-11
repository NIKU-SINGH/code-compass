"""Repository overview: totals, entry points and the hot spots of the graph.

Every list comes from one aggregate query. The riskiest-to-change list additionally
runs the reverse ``CALLS`` walk of ``impact_walk`` for a bounded set of candidates.
"""

from __future__ import annotations

from pathlib import Path

from compass_core.graph.db import GraphDB, Row, as_rows
from compass_core.index.locate import IndexLocation
from compass_core.query.impact_walk import walk_symbols
from compass_core.query.models import Caveat, SymbolRef
from compass_core.query.results import (
    IndexCounts,
    LibraryUsage,
    OverviewResult,
    RankedSymbol,
)
from compass_core.query.rows import count_value, file_from_row, function_from_row, text_value
from compass_core.query.status import index_status
from compass_core.query.types import CaveatCode, EdgeType

TOP_N = 5
"""Length of every ranked list."""

RISK_CANDIDATES = 30
"""How many most-called functions are walked to rank ``riskiest_to_change``.

Mirrored by ``RISK_CANDIDATES`` in ``apps/web/src/lib/limits.ts`` (card copy); keep in sync.
"""

RISK_DEPTH = 3
"""Traversal depth used to count the symbols affected by a change."""

_NODE_COUNTS = {
    "files": "MATCH (n:File) RETURN count(n)",
    "classes": "MATCH (n:Class) RETURN count(n)",
    "functions": "MATCH (n:Function) RETURN count(n)",
}
_EDGE_COUNT = "MATCH ()-[r:{edge}]->() RETURN count(r)"
_ENTRY_POINTS = (
    "MATCH (f:File) WHERE NOT EXISTS { MATCH (:File)-[:IMPORTS]->(f) } "
    "RETURN f.path, f.module_name ORDER BY f.path LIMIT $limit"
)
_MOST_IMPORTED = (
    "MATCH (i:File)-[:IMPORTS]->(f:File) "
    "RETURN f.path, f.module_name, count(DISTINCT i) AS n ORDER BY n DESC, f.path LIMIT $limit"
)
_MOST_CALLED = (
    "MATCH (c:Function)-[:CALLS]->(n:Function) "
    "RETURN n.id, n.name, n.file_path, n.line_start, n.line_end, n.signature, n.is_method, "
    "count(DISTINCT c) AS k ORDER BY k DESC, n.name, n.id LIMIT $limit"
)
_LIBRARIES = (
    "MATCH (:Function)-[e:CALLS_EXTERN]->(x:ExternalFunction) "
    "RETURN x.library, count(e) AS n ORDER BY n DESC, x.library LIMIT $limit"
)


def _count(db: GraphDB, query: str) -> int:
    rows = as_rows(db.execute(query))
    return count_value(rows[0][0]) if rows else 0


def _counts(db: GraphDB) -> IndexCounts:
    nodes = {name: _count(db, query) for name, query in _NODE_COUNTS.items()}
    edges = {edge: _count(db, _EDGE_COUNT.format(edge=edge.value)) for edge in EdgeType}
    return IndexCounts(
        files=nodes["files"],
        classes=nodes["classes"],
        functions=nodes["functions"],
        edges_by_type=edges,
    )


def _riskiest(db: GraphDB, called: list[Row], repo_root: Path) -> tuple[RankedSymbol, ...]:
    """Rank candidates (rows of ``_MOST_CALLED``) by symbols affected at ``RISK_DEPTH``."""
    ranked: list[RankedSymbol] = []
    for row in called:
        symbol: SymbolRef = function_from_row(row, repo_root)
        walk = walk_symbols(
            db,
            symbol,
            text_value(row[0], "id"),
            depth=RISK_DEPTH,
            min_confidence=0.0,
            repo_root=repo_root,
        )
        ranked.append(RankedSymbol(symbol=symbol, count=len(walk.reached)))
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
        location: Index location, used for ``repo_root`` and the ``IndexStatus``.

    Returns:
        An ``OverviewResult``. ``counts.edges_by_type`` has every ``EdgeType`` (zeros
        included) and ``counts.functions`` counts functions and methods. Each list holds
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
    repo_root = location.repo_root.resolve()
    limit = {"limit": TOP_N}
    counts = _counts(db)
    called = as_rows(db.execute(_MOST_CALLED, {"limit": RISK_CANDIDATES}))
    status = index_status(location, db)
    return OverviewResult(
        index=status,
        caveats=_caveats(counts, status.stale_file_count),
        counts=counts,
        entry_points=tuple(
            file_from_row(row, repo_root) for row in as_rows(db.execute(_ENTRY_POINTS, limit))
        ),
        most_imported_files=tuple(
            RankedSymbol(symbol=file_from_row(row, repo_root), count=count_value(row[2]))
            for row in as_rows(db.execute(_MOST_IMPORTED, limit))
        ),
        most_called_functions=tuple(
            RankedSymbol(symbol=function_from_row(row, repo_root), count=count_value(row[7]))
            for row in called[:TOP_N]
        ),
        riskiest_to_change=_riskiest(db, called, repo_root),
        top_external_libraries=tuple(
            LibraryUsage(library=text_value(row[0], "library"), call_count=count_value(row[1]))
            for row in as_rows(db.execute(_LIBRARIES, limit))
        ),
    )
