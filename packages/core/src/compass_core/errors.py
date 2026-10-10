"""Exception hierarchy for compass_core.

Reserved for genuinely unexpected/unrecoverable failures (DB connection
lost, malformed grammar binary, config missing) that propagate up to
phases/pipeline.py and are caught once at the top level. Expected failures
(an unresolved call site, a degraded parse) are modeled as typed result
objects elsewhere, never raised as one of these.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import ClassVar


class CompassError(Exception):
    """Base exception for compass_core. Carries enough context to debug without re-running."""

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        language: str | None = None,
        phase_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.file_path = file_path
        self.language = language
        self.phase_name = phase_name


class DiscoveryError(CompassError):
    """Phase 0 failure — repo walk or manifest construction failed unrecoverably."""


class ParseError(CompassError):
    """Phase 1 failure. Only raised for unrecoverable extractor setup failures
    (e.g. grammar binary missing) — per-file parse failures are captured as a
    `degraded` flag on ParsedFile, not raised."""


class UnsupportedLanguageError(ParseError):
    """Raised by languages/registry.py when no extractor is registered for a file's language."""


class ResolutionError(CompassError):
    """Phase 3 failure — unrecoverable failure building the symbol table or resolving edges."""


class ValidationError(CompassError):
    """Phase 4 failure — the ingest run failed a regression gate check."""


class PersistenceError(CompassError):
    """Phase 5 failure — DB connection lost or write failed unrecoverably mid-batch."""


class ErrorCode(StrEnum):
    """Machine-readable failure codes shared by the API, CLI and MCP adapters."""

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    INDEX_NOT_FOUND = "INDEX_NOT_FOUND"
    INDEX_BUSY = "INDEX_BUSY"
    INDEX_INCOMPATIBLE = "INDEX_INCOMPATIBLE"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    INTERNAL = "INTERNAL"


class QueryError(CompassError):
    """Base class for failures raised by the query layer.

    Attributes:
        code: Machine-readable failure code; every direct subclass declares a
            distinct value.
    """

    code: ClassVar[ErrorCode] = ErrorCode.INTERNAL


class InvalidArgumentError(QueryError):
    """A caller-supplied argument was missing, malformed or out of range.

    Attributes:
        argument: Name of the offending argument.
        reason: Human-readable explanation of why it was rejected.

    Example:
        >>> InvalidArgumentError(argument="depth", reason="must be between 1 and 10")
    """

    code: ClassVar[ErrorCode] = ErrorCode.INVALID_ARGUMENT

    def __init__(self, *, argument: str, reason: str) -> None:
        super().__init__(f"Invalid {argument}: {reason}")
        self.argument = argument
        self.reason = reason


class IndexNotFoundError(QueryError):
    """No ``.compass/graph.ladybug`` was found walking up from ``searched_from``.

    Attributes:
        searched_from: Directory the upward search started from.
    """

    code: ClassVar[ErrorCode] = ErrorCode.INDEX_NOT_FOUND

    def __init__(self, *, searched_from: Path) -> None:
        super().__init__(f"No Compass index found from {searched_from}. Run `compass ingest`.")
        self.searched_from = searched_from


class IndexBusyError(QueryError):
    """The index is locked by another process (typically an ingest rebuild).

    Attributes:
        retry_after_s: Suggested number of seconds to wait before retrying.
    """

    code: ClassVar[ErrorCode] = ErrorCode.INDEX_BUSY

    def __init__(self, *, retry_after_s: int) -> None:
        super().__init__(f"The index is being rebuilt; retry in {retry_after_s}s.")
        self.retry_after_s = retry_after_s


class IndexIncompatibleError(QueryError):
    """The index or its metadata is unreadable or from an unsupported version."""

    code: ClassVar[ErrorCode] = ErrorCode.INDEX_INCOMPATIBLE


class QueryTimeoutError(QueryError):
    """A query ran longer than the configured timeout and was interrupted.

    Attributes:
        timeout_ms: The timeout, in milliseconds, that was exceeded.
    """

    code: ClassVar[ErrorCode] = ErrorCode.QUERY_TIMEOUT

    def __init__(self, *, timeout_ms: int) -> None:
        super().__init__(f"Query exceeded {timeout_ms} ms.")
        self.timeout_ms = timeout_ms
