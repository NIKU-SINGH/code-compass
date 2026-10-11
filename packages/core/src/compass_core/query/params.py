"""Parameter objects for query operations.

Bounds are module constants so the CLI, MCP server and API can all read them.
``__post_init__`` also enforces them and raises ``InvalidArgumentError``.
"""

from __future__ import annotations

from dataclasses import dataclass

from compass_core.errors import InvalidArgumentError
from compass_core.query.types import SymbolKind

MAX_DEPTH = 10
"""Largest allowed traversal depth."""

MAX_LIMIT = 500
"""Largest allowed result limit."""

MAX_TEXT_LENGTH = 512
"""Longest allowed search query or symbol reference, in characters."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_limit(limit: int) -> None:
    if not _is_int(limit) or not 1 <= limit <= MAX_LIMIT:
        raise InvalidArgumentError(argument="limit", reason=f"must be between 1 and {MAX_LIMIT}")


def _check_depth(depth: int) -> None:
    if not _is_int(depth) or not 1 <= depth <= MAX_DEPTH:
        raise InvalidArgumentError(argument="depth", reason=f"must be between 1 and {MAX_DEPTH}")


def _check_confidence(min_confidence: float) -> None:
    if (
        isinstance(min_confidence, bool)
        or not isinstance(min_confidence, (int, float))
        or not 0.0 <= min_confidence <= 1.0
    ):
        raise InvalidArgumentError(argument="min_confidence", reason="must be between 0 and 1")


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchParams:
    """Parameters for symbol search.

    Attributes:
        query: Non-empty search text.
        kind: Restrict hits to one symbol kind; ``None`` for all.
        limit: Maximum hits, ``1..MAX_LIMIT``.

    Example:
        ``SearchParams(query="write", kind=SymbolKind.FUNCTION, limit=20)``
    """

    query: str
    kind: SymbolKind | None = None
    limit: int = 50

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise InvalidArgumentError(argument="query", reason="must not be empty")
        _check_limit(self.limit)


@dataclass(frozen=True, slots=True, kw_only=True)
class ImpactParams:
    """Parameters for impact analysis.

    Attributes:
        depth: Maximum hops to traverse, ``1..MAX_DEPTH``.
        min_confidence: Ignore CALLS edges below this confidence, ``0..1``.
        limit: Maximum affected symbols returned, ``1..MAX_LIMIT``.

    Example:
        ``ImpactParams(depth=3, min_confidence=0.5, limit=100)``
    """

    depth: int = 3
    min_confidence: float = 0.0
    limit: int = 50

    def __post_init__(self) -> None:
        _check_depth(self.depth)
        _check_confidence(self.min_confidence)
        _check_limit(self.limit)
