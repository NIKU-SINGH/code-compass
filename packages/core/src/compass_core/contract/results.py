"""Result types returned by query operations.

Every successful result inherits ``ResultHeader`` so adapters read ``index`` and
``caveats`` flat. ``operation`` plus ``outcome`` form a discriminated union.
Reference outcomes (ambiguous / not found) are values, not exceptions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeAlias, TypeVar

from compass_core.contract.models import Caveat, EdgeRef, IndexStatus, ResultItem, SymbolRef
from compass_core.contract.types import (
    MatchRule,
    Operation,
    Outcome,
    RepoPath,
    SearchMatch,
    SymbolId,
)
from compass_core.shared_types import EdgeType, SymbolKind


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultHeader:
    """Fields common to every successful result.

    Attributes:
        outcome: Always ``Outcome.OK`` for a successful result.
        index: Status of the index that produced the answer.
        caveats: Reasons the answer may be incomplete.

    Example:
        Subclasses are built as ``SearchResult(index=status, caveats=(), ...)``.
    """

    outcome: Literal[Outcome.OK] = Outcome.OK
    index: IndexStatus
    caveats: tuple[Caveat, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchHit:
    """One search match.

    Attributes:
        symbol: The matching symbol.
        match: How it matched the query.
        fan_in: Number of incoming edges, used for ranking.

    Example:
        ``SearchHit(symbol=<f>, match=SearchMatch.EXACT, fan_in=2)``
    """

    symbol: SymbolRef
    match: SearchMatch
    fan_in: int


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchResult(ResultHeader):
    """Result of a symbol search.

    Attributes:
        operation: Always ``Operation.FIND``.
        query: The search text.
        kind: Kind filter that was applied, if any.
        hits: Matching symbols, best first.
        total: Number of matches before truncation.
        truncated: Whether ``hits`` was cut at the limit.

    Example:
        ``find "write"`` yields ``SearchResult(query="write", hits=(...), total=3,
        truncated=False, ...)``.
    """

    operation: Literal[Operation.FIND] = Operation.FIND
    query: str
    kind: SymbolKind | None
    hits: tuple[SearchHit, ...]
    total: int
    truncated: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ImpactGroup:
    """Affected symbols at one distance within one file.

    Attributes:
        distance: Hops from the target.
        file_path: Repo-relative path of the file holding the items.
        items: Affected symbols in that file at that distance.

    Example:
        ``ImpactGroup(distance=1, file_path=RepoPath("a.py"), items=(<item>,))``
    """

    distance: int
    file_path: RepoPath
    items: tuple[ResultItem, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ImpactResult(ResultHeader):
    """Result of an impact analysis.

    Attributes:
        operation: Always ``Operation.IMPACT``.
        target: The analysed file or symbol.
        matched_by: Resolution rule that matched the reference.
        depth: Depth that was traversed.
        groups: Affected symbols grouped by distance and file.
        affected_file_count: Number of distinct affected files.
        edges: Edges connecting the affected symbols.
        total: Number of affected symbols before truncation.
        truncated: Whether the output was cut at the limit.

    Example:
        ``impact write`` yields ``ImpactResult(target=<write>, depth=3,
        groups=(ImpactGroup(...),), affected_file_count=6, total=14, ...)``.
    """

    operation: Literal[Operation.IMPACT] = Operation.IMPACT
    target: SymbolRef
    matched_by: MatchRule
    depth: int
    groups: tuple[ImpactGroup, ...]
    affected_file_count: int
    edges: tuple[EdgeRef, ...]
    total: int
    truncated: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class RankedSymbol:
    """A symbol with a count used for ranking.

    Attributes:
        symbol: The symbol.
        count: Ranking count (callers, importers, or affected symbols).

    Example:
        ``RankedSymbol(symbol=<write>, count=14)``
    """

    symbol: SymbolRef
    count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class LibraryUsage:
    """How heavily an external library is called.

    Attributes:
        library: Library name, e.g. ``"pydantic"``.
        call_count: Number of call sites into the library.

    Example:
        ``LibraryUsage(library="pydantic", call_count=12)``
    """

    library: str
    call_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexCounts:
    """Node and edge totals of the index.

    Attributes:
        files: Number of file nodes.
        classes: Number of class nodes.
        functions: Number of function and method nodes.
        edges_by_type: Edge count per edge type.

    Example:
        ``IndexCounts(files=10, classes=2, functions=40,
        edges_by_type={EdgeType.CALLS: 55})``
    """

    files: int
    classes: int
    functions: int
    edges_by_type: Mapping[EdgeType, int]


@dataclass(frozen=True, slots=True, kw_only=True)
class CallResolution:
    """How many call sites in the index were tied to a definition.

    Attributes:
        total: Call sites recorded in function and method bodies.
        resolved: Call sites whose called name matches a function the caller has a
            ``CALLS`` or ``CALLS_EXTERN`` edge to.

    Example:
        ``CallResolution(total=193, resolved=171)`` means 22 calls are unresolved.
    """

    total: int
    resolved: int


@dataclass(frozen=True, slots=True, kw_only=True)
class OverviewResult(ResultHeader):
    """Repository overview.

    Attributes:
        operation: Always ``Operation.OVERVIEW``.
        counts: Node and edge totals.
        call_resolution: Share of call sites the indexer resolved.
        entry_points: Symbols that are entry points.
        most_imported_files: Files ranked by number of importers.
        most_called_functions: Functions ranked by number of callers.
        riskiest_to_change: Symbols ranked by number of affected symbols.
        top_external_libraries: External libraries ranked by call count.

    Example:
        ``OverviewResult(counts=IndexCounts(...), entry_points=(), ...,
        riskiest_to_change=(RankedSymbol(symbol=<write>, count=14),), ...)``
    """

    operation: Literal[Operation.OVERVIEW] = Operation.OVERVIEW
    counts: IndexCounts
    call_resolution: CallResolution
    entry_points: tuple[SymbolRef, ...]
    most_imported_files: tuple[RankedSymbol, ...]
    most_called_functions: tuple[RankedSymbol, ...]
    riskiest_to_change: tuple[RankedSymbol, ...]
    top_external_libraries: tuple[LibraryUsage, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class NodeDetail(ResultHeader):
    """Everything known about one node, for a details panel.

    Only the relationships that apply to the node's kind are filled; the rest are empty.

    Attributes:
        operation: Always ``Operation.DESCRIBE``.
        symbol: The node; ``symbol.source`` holds its source text for classes and functions.
        docstring: Extracted docstring, or ``None`` when there is none.
        bases: Classes this class inherits from, within the repository.
        subclasses: Classes that inherit from this class.
        members: Methods of a class, or the classes and functions a file defines.
        callees: Functions this function calls.
        callers: Functions that call this function.
        imports: Files this file imports.
        imported_by: Files that import this file.
        truncated: Whether any relationship was cut at the per-relationship limit.

    Example:
        ``describe(db, loc, "app/auth.py::Policy")`` yields ``NodeDetail(symbol=<Policy>,
        docstring="Declarative mapping...", bases=(), subclasses=(), members=(<Policy.allows>,),
        ...)``.
    """

    operation: Literal[Operation.DESCRIBE] = Operation.DESCRIBE
    symbol: SymbolRef
    docstring: str | None
    bases: tuple[SymbolRef, ...]
    subclasses: tuple[SymbolRef, ...]
    members: tuple[SymbolRef, ...]
    callees: tuple[SymbolRef, ...]
    callers: tuple[SymbolRef, ...]
    imports: tuple[SymbolRef, ...]
    imported_by: tuple[SymbolRef, ...]
    truncated: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class AmbiguousReference:
    """A reference that matched several symbols.

    Attributes:
        outcome: Always ``Outcome.AMBIGUOUS``.
        reference: What the user typed.
        candidates: At least two matches, ordered by rule then fan-in.

    Example:
        ``AmbiguousReference(reference="run", candidates=(<a.run>, <b.run>))``
    """

    outcome: Literal[Outcome.AMBIGUOUS] = Outcome.AMBIGUOUS
    reference: str
    candidates: tuple[SymbolRef, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolNotFound:
    """A reference that matched nothing.

    Attributes:
        outcome: Always ``Outcome.NOT_FOUND``.
        reference: What the user typed.
        suggestions: Up to five case-insensitive substring matches.

    Example:
        ``SymbolNotFound(reference="wrte", suggestions=(<write>,))``
    """

    outcome: Literal[Outcome.NOT_FOUND] = Outcome.NOT_FOUND
    reference: str
    suggestions: tuple[SymbolRef, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class MapNode:
    """One file, class, function or method in the map.

    Attributes:
        id: What ``MapEdge.source`` and ``MapEdge.target`` refer to: the public id of a
            class or function, the path of a file.
        label: Short display name.
        kind: Kind of node; never ``EXTERNAL``.
        file_path: Repo-relative path.
        public_id: Public id, accepted wherever a query takes a reference.

    Example:
        ``def f(): ...`` in ``a.py`` becomes ``MapNode(id="a.py::f", label="f",
        kind=SymbolKind.FUNCTION, file_path="a.py", public_id=SymbolId("a.py::f"))``.
    """

    id: str
    label: str
    kind: SymbolKind
    file_path: str
    public_id: SymbolId


@dataclass(frozen=True, slots=True, kw_only=True)
class MapEdge:
    """One relationship between two ``MapNode`` values.

    Attributes:
        source: ``MapNode.id`` the edge leaves.
        target: ``MapNode.id`` the edge enters.
        type: Kind of edge; never ``CALLS_EXTERN``, whose targets are not in the map.

    Example:
        ``a.py`` importing ``b.py`` becomes ``MapEdge(source="a.py", target="b.py",
        type=EdgeType.IMPORTS)``.
    """

    source: str
    target: str
    type: EdgeType


@dataclass(frozen=True, slots=True, kw_only=True)
class GraphMap:
    """Every indexed node and the deduplicated edges between them.

    Attributes:
        nodes: Files, then classes, then functions and methods.
        edges: Distinct ``(source, target, type)`` edges, grouped by type.

    Example:
        A repo with one file holding one function has two nodes and one ``CONTAINS``
        edge.
    """

    nodes: tuple[MapNode, ...]
    edges: tuple[MapEdge, ...]


R = TypeVar("R")
Lookup: TypeAlias = R | AmbiguousReference | SymbolNotFound
