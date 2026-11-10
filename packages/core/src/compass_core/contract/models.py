"""Building-block models shared by every query result.

All models are plain frozen dataclasses with no I/O or database dependencies.
Invariants are checked on construction; a violation raises ``ValueError``
because it is a bug in the query layer, never caused by user input.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from compass_core.contract.types import CaveatCode, QualifiedName, RepoPath, SymbolId, ViaKind
from compass_core.shared_types import CallType, EdgeType, SymbolKind


@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolRef:
    """A reference to one graph node (file, class, function, method or external).

    Public ids are ``<repo-relative POSIX path>::<[Class.]name>`` for classes and
    functions, ``file::<repo-relative path>`` for files and ``ext::<full_ref>`` for
    externals.

    Attributes:
        id: Public symbol id.
        kind: Kind of node.
        name: Short name, e.g. ``"write"``.
        qualified_name: Dotted qualified name.
        file_path: Repo-relative POSIX path; ``None`` only for ``EXTERNAL``.
        line_start: 1-indexed first line; ``None`` for ``FILE`` and ``EXTERNAL``.
        line_end: 1-indexed last line, inclusive; ``None`` when ``line_start`` is.
        signature: Signature text; ``FUNCTION`` and ``METHOD`` only.
        source: Source text; set only when the caller asked for source.

    Example:
        ``def f(): ...`` on lines 1-2 of ``a.py`` becomes::

            SymbolRef(id=SymbolId("a.py::f"), kind=SymbolKind.FUNCTION, name="f",
                      qualified_name=QualifiedName("a.f"), file_path=RepoPath("a.py"),
                      line_start=1, line_end=2, signature="def f()")
    """

    id: SymbolId
    kind: SymbolKind
    name: str
    qualified_name: QualifiedName
    file_path: RepoPath | None
    line_start: int | None
    line_end: int | None
    signature: str | None
    source: str | None = None

    def __post_init__(self) -> None:
        if self.line_start is not None and self.line_start < 1:
            raise ValueError(f"line_start must be >= 1 (1-indexed), got {self.line_start}")
        if self.line_end is not None and self.line_end < 1:
            raise ValueError(f"line_end must be >= 1 (1-indexed), got {self.line_end}")
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            raise ValueError(f"line_end {self.line_end} is before line_start {self.line_start}")


@dataclass(frozen=True, slots=True, kw_only=True)
class EdgeRef:
    """A directed graph edge.

    Attributes:
        source_id: Id of the edge's source node.
        target_id: Id of the edge's target node.
        type: Edge type.
        confidence: Resolution confidence in ``[0, 1]``; set iff ``type`` is ``CALLS``.
        call_type: Resolution type; set iff ``type`` is ``CALLS``.
        line: 1-indexed call site for ``CALLS`` / ``CALLS_EXTERN``; ``None`` if unknown.

    Example:
        ``a`` calls ``b`` at line 3 through a direct import::

            EdgeRef(source_id=SymbolId("a"), target_id=SymbolId("b"), type=EdgeType.CALLS,
                    confidence=1.0, call_type=CallType.DIRECT_IMPORT, line=3)
    """

    source_id: SymbolId
    target_id: SymbolId
    type: EdgeType
    confidence: float | None
    call_type: CallType | None
    line: int | None

    def __post_init__(self) -> None:
        is_calls = self.type is EdgeType.CALLS
        if is_calls != (self.confidence is not None):
            raise ValueError("confidence must be set if and only if type is CALLS")
        if is_calls != (self.call_type is not None):
            raise ValueError("call_type must be set if and only if type is CALLS")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if self.line is not None and self.line < 1:
            raise ValueError(f"line must be >= 1 (1-indexed), got {self.line}")


@dataclass(frozen=True, slots=True, kw_only=True)
class Via:
    """Why an item is in an answer, e.g. "calls write".

    Attributes:
        kind: Relationship to ``symbol``.
        symbol: The node the relationship points at.

    Example:
        ``g`` is reached because it calls ``f``::

            Via(kind=ViaKind.CALLS, symbol=<SymbolRef for f>)
    """

    kind: ViaKind
    symbol: SymbolRef


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultItem:
    """One symbol in a traversal answer.

    Attributes:
        symbol: The symbol reached.
        distance: Hops from the target; 0 is the target itself.
        via: Why the item is present; ``None`` iff ``distance == 0``.
        min_confidence: Lowest ``CALLS`` confidence on the path; ``None`` when the
            path has no ``CALLS`` edge.

    Example:
        A direct caller of the target::

            ResultItem(symbol=<caller>, distance=1,
                       via=Via(kind=ViaKind.CALLS, symbol=<target>), min_confidence=1.0)
    """

    symbol: SymbolRef
    distance: int
    via: Via | None
    min_confidence: float | None

    def __post_init__(self) -> None:
        if self.distance < 0:
            raise ValueError(f"distance must be >= 0, got {self.distance}")
        if (self.distance == 0) != (self.via is None):
            raise ValueError("via must be None if and only if distance == 0")
        if self.min_confidence is not None and not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(f"min_confidence must be in [0, 1], got {self.min_confidence}")


@dataclass(frozen=True, slots=True, kw_only=True)
class Caveat:
    """A reason an answer may be incomplete.

    Attributes:
        code: Machine-readable caveat code.
        message: Rendered sentence for humans.
        count: The number in the message, for machine use.

    Example:
        ``Caveat(code=CaveatCode.UNRESOLVED_CALLS, message="4 unresolved calls in 3
        affected functions; there may be more callers", count=4)``
    """

    code: CaveatCode
    message: str
    count: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexStatus:
    """Freshness and identity of the index that produced an answer.

    Attributes:
        repo_root: Absolute path of the indexed repository.
        indexed_at: Timezone-aware UTC time of the last ingest.
        indexed_commit: Git commit at ingest; ``None`` when not a git checkout.
        schema_version: Graph schema version of the index.
        stale_file_count: Indexed files changed or deleted since ``indexed_at``.
        new_file_count: Unindexed files; computed by ``status`` only.

    Example:
        ``IndexStatus(repo_root=Path("/repo"), indexed_at=datetime(2026, 1, 2,
        tzinfo=UTC), indexed_commit=None, schema_version=2, stale_file_count=0,
        new_file_count=None)``
    """

    repo_root: Path
    indexed_at: datetime
    indexed_commit: str | None
    schema_version: int
    stale_file_count: int
    new_file_count: int | None

    def __post_init__(self) -> None:
        if self.indexed_at.tzinfo is None or self.indexed_at.utcoffset() is None:
            raise ValueError("indexed_at must be timezone-aware")
        if not self.repo_root.is_absolute():
            raise ValueError(f"repo_root must be absolute, got {self.repo_root}")
