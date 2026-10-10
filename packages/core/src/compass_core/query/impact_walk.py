"""Breadth-first reverse walks behind ``impact``.

Each walk expands one distance level at a time with a fixed set of parameterized,
single-hop queries (``WHERE x IN $ids``), so the cost is one query per level per edge
family, never one per node. Nodes are keyed by their stored id (definitions) or stored
path (files); a node is visited once, at its shortest distance, so cycles terminate and
the target never lists itself. ``CALLS`` edges below ``min_confidence`` are not traversed.

When several edges reach a new node at the same distance, the winner is chosen by via
kind (``IMPORTS`` before ``CALLS`` before ``INHERITS``), then by the higher path
confidence, then by the via symbol's id, so results are deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from compass_core.errors import IndexIncompatibleError
from compass_core.graph.db import GraphDB, QueryParams, Row, as_rows
from compass_core.query.models import EdgeRef, ResultItem, SymbolRef, Via
from compass_core.query.references import stored_paths
from compass_core.query.rows import (
    call_type_value,
    confidence_value,
    file_from_row,
    function_from_row,
    line_value,
    symbol_from_row,
    text_value,
)
from compass_core.query.types import EdgeType, SymbolId, SymbolKind, ViaKind

_FN = "{v}.id, {v}.name, {v}.file_path, {v}.line_start, {v}.line_end, {v}.signature, {v}.is_method"
_CLS = "{v}.id, {v}.name, {v}.file_path, {v}.line_start, {v}.line_end, '' AS {v}_sig"
_CALL = "r.confidence, r.call_type, r.line"

# Callers of the given functions: [caller x7, callee x7, confidence, call_type, line].
_CALLERS_OF_FUNCTIONS = (
    "MATCH (a:Function)-[r:CALLS]->(b:Function) "
    "WHERE b.id IN $ids AND r.confidence >= $minc "
    f"RETURN {_FN.format(v='a')}, {_FN.format(v='b')}, {_CALL}"
)
# Callers of methods of the given classes: as above plus the class id.
_CALLERS_OF_METHODS = (
    "MATCH (c:Class)-[:CONTAINS]->(b:Function)<-[r:CALLS]-(a:Function) "
    "WHERE c.id IN $ids AND r.confidence >= $minc "
    f"RETURN {_FN.format(v='a')}, {_FN.format(v='b')}, {_CALL}, c.id"
)
# Direct subclasses of the given classes: [child x6, parent x6].
_SUBCLASSES_OF = (
    "MATCH (a:Class)-[:INHERITS]->(b:Class) WHERE b.id IN $ids "
    f"RETURN {_CLS.format(v='a')}, {_CLS.format(v='b')}"
)
# File-target variants keyed by the stored file paths of the frontier.
_IMPORTERS_OF_FILES = (
    "MATCH (a:File)-[:IMPORTS]->(b:File) WHERE b.path IN $paths "
    "RETURN a.path, a.module_name, b.path, b.module_name"
)
_CALLERS_IN_FILES = (
    "MATCH (a:Function)-[r:CALLS]->(b:Function) "
    "WHERE b.file_path IN $paths AND r.confidence >= $minc "
    f"RETURN {_FN.format(v='a')}, {_FN.format(v='b')}, {_CALL}"
)
_SUBCLASSES_IN_FILES = (
    "MATCH (a:Class)-[:INHERITS]->(b:Class) WHERE b.file_path IN $paths "
    f"RETURN {_CLS.format(v='a')}, {_CLS.format(v='b')}"
)
_FILES = "MATCH (f:File) WHERE f.path IN $paths RETURN f.path, f.module_name"

_PRIORITY = {ViaKind.IMPORTS: 0, ViaKind.CALLS: 1, ViaKind.INHERITS: 2}


@dataclass(frozen=True, slots=True, kw_only=True)
class Reached:
    """A node the walk reached, with the item describing how.

    Attributes:
        key: Stored id (definitions) or stored path (files) of the node.
        item: Distance, via and path confidence of the node.

    Example:
        ``Reached(key="py::app.jobs::nightly", item=ResultItem(symbol=<nightly>,
        distance=1, via=Via(kind=ViaKind.CALLS, symbol=<decode_token>),
        min_confidence=1.0))``
    """

    key: str
    item: ResultItem


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnedEdge:
    """A traversed edge and the affected item it belongs to.

    Attributes:
        owner: Public id of the affected item that the edge pulled in or leaves from;
            used to drop edges of items cut by the result limit.
        edge: The traversed edge.

    Example:
        ``OwnedEdge(owner=SymbolId("file::app/api.py"), edge=<api.py IMPORTS auth.py>)``
    """

    owner: SymbolId
    edge: EdgeRef


@dataclass(frozen=True, slots=True, kw_only=True)
class Walk:
    """Everything a walk reached.

    Attributes:
        reached: Affected nodes in discovery order (the target is never included).
        edges: Traversed edges whose owner is an affected node, deduplicated.

    Example:
        Walking callers of ``decode_token`` at depth 1 yields three ``Reached`` items
        (``handle``, ``run``, ``nightly``) and their three ``CALLS`` edges.
    """

    reached: tuple[Reached, ...]
    edges: tuple[OwnedEdge, ...]


class _Walker:
    """Mutable BFS bookkeeping shared by the symbol and file walks."""

    def __init__(self, target_key: str, target: SymbolRef) -> None:
        self.symbols: dict[str, SymbolRef] = {target_key: target}
        self._visited: set[str] = {target_key}
        self._path_min: dict[str, float | None] = {target_key: None}
        self._reached: list[Reached] = []
        self._level: dict[str, tuple[tuple[int, float, str], Reached]] = {}
        self._edges: list[tuple[str, EdgeRef]] = []

    def offer(
        self,
        key: str,
        symbol: SymbolRef,
        distance: int,
        via: Via,
        parent_key: str,
        confidence: float | None,
    ) -> None:
        """Propose ``symbol`` at ``distance``; the best proposal per level wins."""
        if key in self._visited:
            return
        path = self._path_min.get(parent_key)
        if confidence is not None:
            path = confidence if path is None else min(path, confidence)
        rank = (_PRIORITY[via.kind], -(1.0 if path is None else path), via.symbol.id)
        current = self._level.get(key)
        if current is None or rank < current[0]:
            item = ResultItem(symbol=symbol, distance=distance, via=via, min_confidence=path)
            self._level[key] = (rank, Reached(key=key, item=item))

    def edge(self, owner_key: str, edge: EdgeRef) -> None:
        """Record a traversed edge owned by the node ``owner_key``."""
        self._edges.append((owner_key, edge))

    def close_level(self) -> list[str]:
        """Commit this level's proposals; return the new frontier keys, sorted."""
        new = sorted(self._level)
        for key in new:
            reached = self._level[key][1]
            self._visited.add(key)
            self._path_min[key] = reached.item.min_confidence
            self.symbols[key] = reached.item.symbol
            self._reached.append(reached)
        self._level = {}
        return new

    def result(self) -> Walk:
        """The walk so far; edges are kept only when their owner was reached."""
        owners = {r.key: r.item.symbol.id for r in self._reached}
        seen: set[tuple[SymbolId, EdgeRef]] = set()
        edges: list[OwnedEdge] = []
        for owner_key, edge in self._edges:
            owner = owners.get(owner_key)
            if owner is not None and (owner, edge) not in seen:
                seen.add((owner, edge))
                edges.append(OwnedEdge(owner=owner, edge=edge))
        return Walk(reached=tuple(self._reached), edges=tuple(edges))


def _calls_edge(caller: SymbolRef, callee: SymbolRef, row: Row) -> tuple[float, EdgeRef]:
    """The confidence and ``CALLS`` edge from a row whose columns 14..16 are the call."""
    confidence = confidence_value(row[14])
    edge = EdgeRef(
        source_id=caller.id,
        target_id=callee.id,
        type=EdgeType.CALLS,
        confidence=confidence,
        call_type=call_type_value(row[15]),
        line=line_value(row[16], "line"),
    )
    return confidence, edge


def _structural_edge(source: SymbolRef, target: SymbolRef, kind: EdgeType) -> EdgeRef:
    """An ``IMPORTS`` or ``INHERITS`` edge (no confidence, call type or line)."""
    return EdgeRef(
        source_id=source.id,
        target_id=target.id,
        type=kind,
        confidence=None,
        call_type=None,
        line=None,
    )


def _rows(db: GraphDB, query: str, params: QueryParams) -> Sequence[Row]:
    return as_rows(db.execute(query, params))


def _class(row: Row, repo_root: Path) -> SymbolRef:
    return symbol_from_row(row, SymbolKind.CLASS, repo_root)


def stored_target_key(db: GraphDB, target: SymbolRef, repo_root: Path) -> str:
    """Find the stored id (or, for a file, the stored path) of a resolved target.

    Args:
        db: Open graph database.
        target: A resolved file, class, function or method.
        repo_root: Absolute repository root.

    Returns:
        The stored key the walks use for ``target``.

    Raises:
        IndexIncompatibleError: The resolved symbol is not in the graph any more.

    Example:
        ``<app/auth.py::parse>`` maps to ``"py::app.auth::parse"``; ``<file::app/a.py>``
        maps to ``"app/a.py"`` (or its absolute spelling, if stored that way).
    """
    paths = stored_paths(target.file_path or "", repo_root)
    if target.kind is SymbolKind.FILE:
        rows = _rows(db, _FILES, {"paths": paths})
    else:
        label = "Class" if target.kind is SymbolKind.CLASS else "Function"
        rows = _rows(
            db,
            f"MATCH (n:{label}) WHERE n.file_path IN $paths AND n.id ENDS WITH $tail RETURN n.id",
            {"paths": paths, "tail": "::" + target.id.rsplit("::", 1)[1]},
        )
    if not rows:
        raise IndexIncompatibleError(f"resolved symbol is missing from the graph: {target.id}")
    return text_value(rows[0][0], "id")


def walk_symbols(
    db: GraphDB,
    target: SymbolRef,
    target_key: str,
    *,
    depth: int,
    min_confidence: float,
    repo_root: Path,
) -> Walk:
    """Walk reverse ``CALLS`` (and, for classes, reverse ``INHERITS``) from a symbol.

    A function or method in the frontier pulls in its callers (``Via(CALLS, callee)``).
    A class in the frontier pulls in its subclasses (``Via(INHERITS, class)``) and the
    callers of its methods (``Via(CALLS, method)``).

    Args:
        db: Open graph database.
        target: The resolved class, function or method.
        target_key: Its stored id.
        depth: Maximum distance.
        min_confidence: ``CALLS`` edges below this are not traversed.
        repo_root: Absolute repository root.

    Returns:
        The affected symbols and the edges traversed.

    Raises:
        IndexIncompatibleError: A stored row does not have the expected shape.

    Example:
        From ``decode_token`` at depth 2 the walk reaches ``handle``, ``run`` and
        ``nightly`` at distance 1 and ``tick`` (which calls ``nightly``) at distance 2.
    """
    walker = _Walker(target_key, target)
    frontier = [target_key]
    for distance in range(1, depth + 1):
        functions = [k for k in frontier if walker.symbols[k].kind is not SymbolKind.CLASS]
        classes = [k for k in frontier if walker.symbols[k].kind is SymbolKind.CLASS]
        if functions:
            params: QueryParams = {"ids": functions, "minc": min_confidence}
            for row in _rows(db, _CALLERS_OF_FUNCTIONS, params):
                _offer_caller(walker, row, distance, text_value(row[7], "id"), repo_root)
        if classes:
            params = {"ids": classes, "minc": min_confidence}
            for row in _rows(db, _CALLERS_OF_METHODS, params):
                _offer_caller(walker, row, distance, text_value(row[17], "id"), repo_root)
            for row in _rows(db, _SUBCLASSES_OF, {"ids": classes}):
                child, parent = _class(row[:6], repo_root), _class(row[6:], repo_root)
                child_key = text_value(row[0], "id")
                parent_key = text_value(row[6], "id")
                via = Via(kind=ViaKind.INHERITS, symbol=parent)
                walker.offer(child_key, child, distance, via, parent_key, None)
                walker.edge(child_key, _structural_edge(child, parent, EdgeType.INHERITS))
        frontier = walker.close_level()
        if not frontier:
            break
    return walker.result()


def _offer_caller(
    walker: _Walker, row: Row, distance: int, parent_key: str, repo_root: Path
) -> None:
    caller = function_from_row(row[:7], repo_root)
    callee = function_from_row(row[7:14], repo_root)
    confidence, edge = _calls_edge(caller, callee, row)
    caller_key = text_value(row[0], "id")
    via = Via(kind=ViaKind.CALLS, symbol=callee)
    walker.offer(caller_key, caller, distance, via, parent_key, confidence)
    walker.edge(caller_key, edge)


def walk_files(
    db: GraphDB,
    target: SymbolRef,
    target_key: str,
    *,
    depth: int,
    min_confidence: float,
    repo_root: Path,
) -> Walk:
    """Walk dependent files: importers, files of callers and files of subclasses.

    Each affected file is one ``FILE`` item. Its via is ``IMPORTS`` (symbol: the
    imported file), ``CALLS`` (symbol: the called function) or ``INHERITS`` (symbol:
    the base class), whichever reaches it first.

    Args:
        db: Open graph database.
        target: The resolved file.
        target_key: Its stored path.
        depth: Maximum distance.
        min_confidence: ``CALLS`` edges below this are not traversed.
        repo_root: Absolute repository root.

    Returns:
        The affected files and the edges traversed (``IMPORTS`` between files,
        ``CALLS`` and ``INHERITS`` between the definitions involved).

    Raises:
        IndexIncompatibleError: A stored row does not have the expected shape.

    Example:
        From ``app/auth.py`` at depth 2: ``app/api.py``, ``app/cli.py``,
        ``app/jobs.py`` and ``app/__init__.py`` at distance 1 (they import it) and
        ``app/scheduler.py`` at distance 2 (it imports ``app/jobs.py``).
    """
    walker = _Walker(target_key, target)
    frontier = [target_key]
    for distance in range(1, depth + 1):
        # (owner path, via, parent path, confidence) per proposal; files resolved below.
        pending: list[tuple[str, Via, str, float | None]] = []
        for row in _rows(db, _IMPORTERS_OF_FILES, {"paths": frontier}):
            importer, imported = (
                file_from_row(row[:2], repo_root),
                file_from_row(row[2:], repo_root),
            )
            owner = text_value(row[0], "path")
            walker.symbols.setdefault(owner, importer)
            via = Via(kind=ViaKind.IMPORTS, symbol=imported)
            pending.append((owner, via, text_value(row[2], "path"), None))
            walker.edge(owner, _structural_edge(importer, imported, EdgeType.IMPORTS))
        params: QueryParams = {"paths": frontier, "minc": min_confidence}
        for row in _rows(db, _CALLERS_IN_FILES, params):
            caller = function_from_row(row[:7], repo_root)
            callee = function_from_row(row[7:14], repo_root)
            confidence, edge = _calls_edge(caller, callee, row)
            owner = text_value(row[2], "file_path")
            via = Via(kind=ViaKind.CALLS, symbol=callee)
            pending.append((owner, via, text_value(row[9], "file_path"), confidence))
            walker.edge(owner, edge)
        for row in _rows(db, _SUBCLASSES_IN_FILES, {"paths": frontier}):
            child, parent = _class(row[:6], repo_root), _class(row[6:], repo_root)
            owner = text_value(row[2], "file_path")
            via = Via(kind=ViaKind.INHERITS, symbol=parent)
            pending.append((owner, via, text_value(row[8], "file_path"), None))
            walker.edge(owner, _structural_edge(child, parent, EdgeType.INHERITS))
        _load_files(db, walker, [p[0] for p in pending], repo_root)
        for owner, via, parent_path, path_confidence in pending:
            walker.offer(owner, walker.symbols[owner], distance, via, parent_path, path_confidence)
        frontier = walker.close_level()
        if not frontier:
            break
    return walker.result()


def _load_files(db: GraphDB, walker: _Walker, paths: list[str], repo_root: Path) -> None:
    """Make sure every stored path in ``paths`` has a ``FILE`` symbol (one query)."""
    missing = sorted({p for p in paths if p not in walker.symbols})
    if not missing:
        return
    for row in _rows(db, _FILES, {"paths": missing}):
        walker.symbols[text_value(row[0], "path")] = file_from_row(row, repo_root)
    absent = [p for p in missing if p not in walker.symbols]
    if absent:
        raise IndexIncompatibleError(f"definitions reference unindexed files: {absent}")
