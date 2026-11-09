"""Impact analysis: what may break if a file or symbol changes.

Semantics follow the query-layer design (section 4.2). A symbol target walks reverse
``CALLS`` (a class also pulls in subclasses and callers of its methods); a file target
walks importers, files of callers and files of subclasses. The walks live in
``impact_walk``; this module resolves the reference, orders, groups and truncates the
items, and adds the ``UNRESOLVED_CALLS`` and ``STALE_INDEX`` caveats.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import groupby

from compass_core.contract.models import Caveat, EdgeRef, ResultItem, SymbolRef
from compass_core.contract.params import ImpactParams
from compass_core.contract.results import ImpactGroup, ImpactResult, Lookup
from compass_core.contract.types import CaveatCode, RepoPath
from compass_core.graph.db import GraphDB, Row
from compass_core.index.locate import IndexLocation
from compass_core.query.cypher import Query
from compass_core.query.impact_walk import Walk, walk_files, walk_key, walk_symbols
from compass_core.query.references import ResolvedReference, resolve
from compass_core.query.rows import text_list_value, text_value
from compass_core.query.status import index_status
from compass_core.shared_types import SymbolKind


@dataclass(frozen=True, slots=True, kw_only=True)
class RawCaller:
    """A function with raw call sites, and the names its resolved edges reach.

    Attributes:
        key: Id of the function.
        path: Its file path.
        raw_calls: Its raw call strings, in source order.
        reached: Names of the functions and externals it has a ``CALLS`` or
            ``CALLS_EXTERN`` edge to.

    Example:
        ``def run(): parse(x); getattr(o, n)()`` with only ``parse`` resolved gives
        ``RawCaller(key="app/cli.py::run", path="app/cli.py",
        raw_calls=("parse", "getattr(o, n)"), reached=frozenset({"parse"}))``.
    """

    key: str
    path: str
    raw_calls: tuple[str, ...]
    reached: frozenset[str]


RAW_CALLERS: Query[RawCaller] = Query(
    """
    MATCH (f:Function) WHERE size(f.raw_calls) > 0
    OPTIONAL MATCH (f)-[:CALLS]->(g:Function) WITH f, collect(g.name) AS internal
    OPTIONAL MATCH (f)-[:CALLS_EXTERN]->(x:ExternalFunction)
    RETURN f.id, f.file_path, f.raw_calls, internal, collect(x.name)
    """,
    lambda row: RawCaller(
        key=text_value(row[0], "id"),
        path=text_value(row[1], "file_path"),
        raw_calls=text_list_value(row[2], "raw_calls"),
        reached=frozenset(text_list_value(row[3], "name") + text_list_value(row[4], "name")),
    ),
)
"""Every function with raw calls, with the names its resolved edges reach."""


def _name(row: Row) -> str:
    return text_value(row[0], "name")


_METHOD_NAMES: Query[str] = Query(
    "MATCH (c:Class)-[:CONTAINS]->(m:Function) WHERE c.id IN $ids RETURN m.name", _name
)
_FILE_DEFINITION_NAMES: Query[str] = Query(
    """
    MATCH (f:Function) WHERE f.file_path = $path RETURN f.name
    UNION MATCH (c:Class) WHERE c.file_path = $path RETURN c.name
    """,
    _name,
)
"""Names of every definition in a file: functions, methods and classes."""


def bare_call_name(raw_call: str) -> str:
    """The called name of a raw call string: last dotted segment, arguments removed.

    Args:
        raw_call: A ``Function.raw_calls`` entry.

    Returns:
        The bare name, or ``""`` when nothing is left.

    Example:
        ``bare_call_name("User().save")`` returns ``"save"``;
        ``bare_call_name("getattr(obj, name)")`` returns ``"getattr"``.
    """
    depth = 0
    kept: list[str] = []
    for char in raw_call:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        elif depth == 0:
            kept.append(char)
    return "".join(kept).rsplit(".", 1)[-1].strip()


def _watched_names(db: GraphDB, target: SymbolRef, target_key: str, walk: Walk) -> set[str]:
    """Bare names whose unresolved calls may hide callers: the target, every affected
    symbol and the methods of the target and affected classes."""
    names = {target.name} | {r.item.symbol.name for r in walk.reached}
    classes = [r.key for r in walk.reached if r.item.symbol.kind is SymbolKind.CLASS]
    if target.kind is SymbolKind.CLASS:
        classes.append(target_key)
    if classes:
        names |= set(_METHOD_NAMES.run(db, {"ids": sorted(classes)}))
    return names


def _file_watched_names(db: GraphDB, path: str) -> set[str]:
    """Bare names whose unresolved calls may hide dependents of the file at ``path``:
    every function, method and class defined in it."""
    return set(_FILE_DEFINITION_NAMES.run(db, {"path": path}))


def _unresolved_callers(
    db: GraphDB, names: set[str], *, skip_id: str | None = None, skip_file: str | None = None
) -> set[str]:
    """Functions with a raw call to one of ``names`` that resolved to no edge to a
    function (or external) of that name.

    Only such calls can hide further callers of the target; a dependent's other
    unresolved calls (builtins, methods on locals) cannot, so they are not counted.

    Args:
        db: Open graph database.
        names: Watched bare names.
        skip_id: Id of a function not to count (the symbol target itself).
        skip_file: Path whose functions are not counted (the file target).

    Returns:
        The ids of the flagged functions.
    """
    found: set[str] = set()
    for caller in RAW_CALLERS.run(db):
        if caller.key == skip_id or caller.path == skip_file:
            continue
        called = {bare_call_name(c) for c in caller.raw_calls}
        if (called & names) - caller.reached:
            found.add(caller.key)
    return found


def _unresolved_caveat(functions: set[str]) -> tuple[Caveat, ...]:
    count = len(functions)
    if not count:
        return ()
    noun = "function contains" if count == 1 else "functions contain"
    message = f"{count} {noun} calls that could not be resolved; there may be more callers"
    return (Caveat(code=CaveatCode.UNRESOLVED_CALLS, message=message, count=count),)


def _stale_caveat(stale: int) -> tuple[Caveat, ...]:
    if not stale:
        return ()
    noun = "file has" if stale == 1 else "files have"
    message = f"{stale} indexed {noun} changed since the last ingest; run `compass ingest`"
    return (Caveat(code=CaveatCode.STALE_INDEX, message=message, count=stale),)


def _file_of(item: ResultItem) -> RepoPath:
    path = item.symbol.file_path
    assert path is not None, "impact walks only reach files and definitions"
    return path


def _groups(items: Sequence[ResultItem]) -> tuple[ImpactGroup, ...]:
    """Group already-sorted items by ``(distance, file_path)``."""
    return tuple(
        ImpactGroup(distance=distance, file_path=path, items=tuple(members))
        for (distance, path), members in groupby(items, key=lambda i: (i.distance, _file_of(i)))
    )


def _edges(walk: Walk, kept: Iterable[ResultItem]) -> tuple[EdgeRef, ...]:
    """Edges owned by the kept items, deduplicated and in a stable order."""
    ids = {i.symbol.id for i in kept}
    unique = {owned.edge for owned in walk.edges if owned.owner in ids}
    return tuple(sorted(unique, key=lambda e: (e.type, e.source_id, e.target_id, e.line or 0)))


def _walk(db: GraphDB, target: SymbolRef, params: ImpactParams) -> tuple[Walk, set[str]]:
    """Run the walk for ``target`` and collect the functions behind its caveat."""
    key = walk_key(target)
    depth, min_confidence = params.depth, params.min_confidence
    if target.kind is SymbolKind.FILE:
        walk = walk_files(db, target, depth=depth, min_confidence=min_confidence)
        return walk, _unresolved_callers(db, _file_watched_names(db, key), skip_file=key)
    walk = walk_symbols(db, target, depth=depth, min_confidence=min_confidence)
    return walk, _unresolved_callers(db, _watched_names(db, target, key, walk), skip_id=key)


def impact(
    db: GraphDB, location: IndexLocation, ref: str, params: ImpactParams
) -> Lookup[ImpactResult]:
    """List what may be affected by changing a file or symbol.

    Args:
        db: Open, read-only graph database.
        location: Index location, used for ``repo_root`` and the ``IndexStatus``.
        ref: File path or symbol reference (section 4.1 rules; files allowed).
        params: Depth, minimum ``CALLS`` confidence and item limit.

    Returns:
        An ``ImpactResult``, or the ``AmbiguousReference`` / ``SymbolNotFound`` from
        resolution. Groups are ordered by distance then file path, items by name.
        ``total`` counts items before the limit; ``affected_file_count`` counts the
        distinct files of all items. A symbol target lists affected functions, methods
        and classes; a file target lists one ``FILE`` item per affected file. An
        external target (``ext::json.dumps``) lists its ``CALLS_EXTERN`` callers at
        distance 1 (``min_confidence`` ``None``) and walks reverse ``CALLS`` from there.
        Each item's ``min_confidence`` is that of the chosen shortest path (see
        ``impact_walk`` for tie-breaks), not the best path overall. ``edges`` are the
        edges traversed from the returned items; their endpoints may not be items
        (non-tree edges, and function/class-level edges behind a file dependency).

    Raises:
        IndexIncompatibleError: A stored row or the index metadata is unreadable.

    Note:
        ``UNRESOLVED_CALLS`` counts functions that have a raw call to a watched bare
        name with no resolved edge to a function or external of that name. For a
        symbol target the watched names are the target, every affected symbol and
        the methods of the target and affected classes (the target itself is not
        counted); for a file target they are the names of every function, method and
        class defined in the file (its own functions are not counted). A dependent's
        other unresolved calls (builtins, methods on locals) are not counted.
        ``min_confidence`` is compared with a ``1e-6`` tolerance because stored
        confidences are float32. Overrides (``Via(OVERRIDES)``) are not walked.

    Example:
        ``impact(db, loc, "app/auth.py::decode_token", ImpactParams(depth=2))`` returns
        ``handle``, ``run`` and ``nightly`` at distance 1 (``via`` calls
        ``decode_token``, ``min_confidence`` 1.0) and ``tick`` at distance 2.
    """
    status = index_status(location, db)  # first: rejects an incompatible index
    repo_root = location.repo_root.resolve()
    resolved = resolve(db, ref, repo_root=repo_root, allow_file=True)
    if not isinstance(resolved, ResolvedReference):
        return resolved
    target = resolved.symbol
    walk, unresolved = _walk(db, target, params)
    items = sorted(
        (r.item for r in walk.reached),
        key=lambda i: (i.distance, _file_of(i), i.symbol.name, i.symbol.id),
    )
    kept = items[: params.limit]
    return ImpactResult(
        index=status,
        caveats=_unresolved_caveat(unresolved) + _stale_caveat(status.stale_file_count),
        target=target,
        matched_by=resolved.rule,
        depth=params.depth,
        groups=_groups(kept),
        affected_file_count=len({_file_of(i) for i in items}),
        edges=_edges(walk, kept),
        total=len(items),
        truncated=len(items) > params.limit,
    )
