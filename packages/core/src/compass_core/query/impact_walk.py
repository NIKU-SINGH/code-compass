"""Breadth-first reverse walks behind ``impact``.

Each walk expands one distance level at a time with a fixed set of parameterized,
single-hop queries (``WHERE x IN $ids``), so the cost is one query per level per edge
family, never one per node. Nodes are keyed by their stored id (definitions) or stored
path (files); a node is visited once, at its shortest distance, so cycles terminate and
the target never lists itself. ``CALLS`` edges below ``min_confidence`` are not traversed;
stored confidences are float32, so the threshold is compared with a ``1e-6`` tolerance
(a stored ``0.9`` reads back as ``0.8999999761``).

The recorded edges are every edge traversed from an affected node, including non-tree
edges (a second, equally short or longer route) and, for file targets, the function- and
class-level edges behind a file dependency, so an edge endpoint may not be an item.

When several edges reach a new node at the same distance, the winner is chosen by via
kind (``IMPORTS`` before ``CALLS`` before ``INHERITS``), then by the higher path
confidence, then by the via symbol's id, so results are deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from compass_core.contract.models import EdgeRef, ResultItem, SymbolRef, Via
from compass_core.contract.types import SymbolId, ViaKind
from compass_core.errors import IndexIncompatibleError
from compass_core.graph.db import GraphDB
from compass_core.query.references import BY_PATH_AND_TAIL, FILES_AT_PATHS, stored_paths
from compass_core.query.walk_queries import (
    CALLERS_IN_FILES,
    CALLERS_OF_EXTERNALS,
    CALLERS_OF_FUNCTIONS,
    CALLERS_OF_METHODS,
    EXTERNAL_KEY,
    IMPORTERS_OF_FILES,
    SUBCLASSES_IN_FILES,
    SUBCLASSES_OF,
    CallRow,
    ExternalCallRow,
)
from compass_core.shared_types import EdgeType, SymbolKind

_PRIORITY = {ViaKind.IMPORTS: 0, ViaKind.CALLS: 1, ViaKind.INHERITS: 2}
_CONFIDENCE_TOLERANCE = 1e-6


def _threshold(min_confidence: float) -> float:
    """The ``$minc`` parameter: ``min_confidence`` lowered by the float32 tolerance."""
    return min_confidence - _CONFIDENCE_TOLERANCE


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


def stored_target_key(db: GraphDB, target: SymbolRef, repo_root: Path) -> str:
    """Find the stored id (or, for a file, the stored path) of a resolved target.

    Args:
        db: Open graph database.
        target: A resolved file, class, function, method or external function.
        repo_root: Absolute repository root.

    Returns:
        The stored key the walks use for ``target``.

    Raises:
        IndexIncompatibleError: The resolved symbol is not in the graph any more.

    Example:
        ``<app/auth.py::parse>`` maps to ``"py::app.auth::parse"``; ``<file::app/a.py>``
        maps to ``"app/a.py"`` (or its absolute spelling, if stored that way);
        ``<ext::json.dumps>`` maps to ``"json.dumps"``.
    """
    params = {"paths": stored_paths(target.file_path or "", repo_root)}
    key: str | None
    if target.kind is SymbolKind.EXTERNAL:
        key = EXTERNAL_KEY.first(db, repo_root, {"ref": target.id.removeprefix("ext::")})
    elif target.kind is SymbolKind.FILE:
        node = FILES_AT_PATHS.first(db, repo_root, params)
        key = node.key if node else None
    else:
        queries = BY_PATH_AND_TAIL
        query = queries.classes if target.kind is SymbolKind.CLASS else queries.functions
        node = query.first(db, repo_root, {**params, "tail": "::" + target.id.rsplit("::", 1)[1]})
        key = node.key if node else None
    if key is None:
        raise IndexIncompatibleError(f"resolved symbol is missing from the graph: {target.id}")
    return key


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
    callers of its methods (``Via(CALLS, method)``). An external target pulls in its
    callers over ``CALLS_EXTERN`` (``Via(CALLS, external)``, no confidence); the walk then
    continues over reverse ``CALLS``. Each item's ``min_confidence`` is that of the chosen
    shortest path, not the best path overall.

    Args:
        db: Open graph database.
        target: The resolved class, function, method or external function.
        target_key: Its stored id (``full_ref`` for an external).
        depth: Maximum distance.
        min_confidence: ``CALLS`` edges below this are not traversed.
        repo_root: Absolute repository root.

    Returns:
        The affected symbols and every edge traversed from them; an edge endpoint may
        not be an item (non-tree edges, or the target's class methods).

    Raises:
        IndexIncompatibleError: A stored row does not have the expected shape.

    Example:
        From ``decode_token`` at depth 2 the walk reaches ``handle``, ``run`` and
        ``nightly`` at distance 1 and ``tick`` (which calls ``nightly``) at distance 2.
    """
    walker = _Walker(target_key, target)
    frontier = [target_key]
    for distance in range(1, depth + 1):
        kinds = {k: walker.symbols[k].kind for k in frontier}
        functions = [k for k in frontier if kinds[k] in (SymbolKind.FUNCTION, SymbolKind.METHOD)]
        classes = [k for k in frontier if kinds[k] is SymbolKind.CLASS]
        externals = [k for k in frontier if kinds[k] is SymbolKind.EXTERNAL]
        if externals:
            for ext in CALLERS_OF_EXTERNALS.run(db, repo_root, {"ids": externals}):
                _offer_external_caller(walker, ext, distance, target_key)
        minc = _threshold(min_confidence)
        if functions:
            for call in CALLERS_OF_FUNCTIONS.run(db, repo_root, {"ids": functions, "minc": minc}):
                _offer_caller(walker, call, distance, call.callee.key)
        if classes:
            params = {"ids": classes, "minc": minc}
            for method_call in CALLERS_OF_METHODS.run(db, repo_root, params):
                _offer_caller(walker, method_call.call, distance, method_call.class_key)
            for pair in SUBCLASSES_OF.run(db, repo_root, {"ids": classes}):
                child, parent = pair.source, pair.target
                via = Via(kind=ViaKind.INHERITS, symbol=parent.symbol)
                walker.offer(child.key, child.symbol, distance, via, parent.key, None)
                walker.edge(
                    child.key, _structural_edge(child.symbol, parent.symbol, EdgeType.INHERITS)
                )
        frontier = walker.close_level()
        if not frontier:
            break
    return walker.result()


def _offer_caller(walker: _Walker, call: CallRow, distance: int, parent_key: str) -> None:
    via = Via(kind=ViaKind.CALLS, symbol=call.callee.symbol)
    walker.offer(call.caller.key, call.caller.symbol, distance, via, parent_key, call.confidence)
    walker.edge(call.caller.key, call.edge)


def _offer_external_caller(
    walker: _Walker, ext: ExternalCallRow, distance: int, external_key: str
) -> None:
    external = walker.symbols[external_key]
    via = Via(kind=ViaKind.CALLS, symbol=external)
    walker.offer(ext.caller.key, ext.caller.symbol, distance, via, external_key, None)
    edge = EdgeRef(
        source_id=ext.caller.symbol.id,
        target_id=external.id,
        type=EdgeType.CALLS_EXTERN,
        confidence=None,
        call_type=None,
        line=ext.line,
    )
    walker.edge(ext.caller.key, edge)


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
        ``CALLS`` and ``INHERITS`` between the definitions involved). Endpoints of the
        ``CALLS`` and ``INHERITS`` edges are functions and classes, never items here.

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
        for pair in IMPORTERS_OF_FILES.run(db, repo_root, {"paths": frontier}):
            importer, imported = pair.source, pair.target
            walker.symbols.setdefault(importer.key, importer.symbol)
            via = Via(kind=ViaKind.IMPORTS, symbol=imported.symbol)
            pending.append((importer.key, via, imported.key, None))
            walker.edge(
                importer.key,
                _structural_edge(importer.symbol, imported.symbol, EdgeType.IMPORTS),
            )
        params = {"paths": frontier, "minc": _threshold(min_confidence)}
        for call in CALLERS_IN_FILES.run(db, repo_root, params):
            via = Via(kind=ViaKind.CALLS, symbol=call.callee.symbol)
            pending.append((call.caller.path, via, call.callee.path, call.confidence))
            walker.edge(call.caller.path, call.edge)
        for pair in SUBCLASSES_IN_FILES.run(db, repo_root, {"paths": frontier}):
            child, parent = pair.source, pair.target
            via = Via(kind=ViaKind.INHERITS, symbol=parent.symbol)
            pending.append((child.path, via, parent.path, None))
            walker.edge(
                child.path, _structural_edge(child.symbol, parent.symbol, EdgeType.INHERITS)
            )
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
    for node in FILES_AT_PATHS.run(db, repo_root, {"paths": missing}):
        walker.symbols[node.key] = node.symbol
    absent = [p for p in missing if p not in walker.symbols]
    if absent:
        raise IndexIncompatibleError(f"definitions reference unindexed files: {absent}")
