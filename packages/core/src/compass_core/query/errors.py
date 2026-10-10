"""Typed error envelope and the per-code mapping used by every adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from compass_core.errors import (
    ErrorCode,
    IndexBusyError,
    IndexNotFoundError,
    InvalidArgumentError,
    QueryError,
    QueryTimeoutError,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorMapping:
    """How one error code surfaces in each adapter.

    Attributes:
        exit_code: CLI process exit code.
        http_status: HTTP status code.
        mcp_is_error: Whether MCP reports a tool error (else a structured result).

    Example:
        ``ErrorMapping(exit_code=2, http_status=422, mcp_is_error=True)``
    """

    exit_code: int
    http_status: int
    mcp_is_error: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorDetail:
    """One key/value fact attached to an error.

    Attributes:
        key: Detail name, e.g. ``"argument"``.
        value: Detail value rendered as text.

    Example:
        ``ErrorDetail(key="retry_after_s", value="5")``
    """

    key: str
    value: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorResponse:
    """The single envelope adapters render for any failure.

    Attributes:
        code: Machine-readable failure code.
        message: One sentence plus the fix.
        details: Typed context for the failure.

    Example:
        ``InvalidArgumentError(argument="depth", reason="too big")`` becomes
        ``ErrorResponse(code=INVALID_ARGUMENT, message="Invalid depth: too big",
        details=(ErrorDetail(key="argument", value="depth"),
        ErrorDetail(key="reason", value="too big")))``
    """

    code: ErrorCode
    message: str
    details: tuple[ErrorDetail, ...]


ERROR_MAPPINGS: Mapping[ErrorCode, ErrorMapping] = {
    ErrorCode.INVALID_ARGUMENT: ErrorMapping(exit_code=2, http_status=422, mcp_is_error=True),
    ErrorCode.NOT_FOUND: ErrorMapping(exit_code=3, http_status=404, mcp_is_error=False),
    ErrorCode.AMBIGUOUS: ErrorMapping(exit_code=4, http_status=409, mcp_is_error=False),
    ErrorCode.INDEX_NOT_FOUND: ErrorMapping(exit_code=5, http_status=503, mcp_is_error=True),
    ErrorCode.INDEX_BUSY: ErrorMapping(exit_code=6, http_status=503, mcp_is_error=True),
    ErrorCode.INDEX_INCOMPATIBLE: ErrorMapping(exit_code=7, http_status=503, mcp_is_error=True),
    ErrorCode.QUERY_TIMEOUT: ErrorMapping(exit_code=8, http_status=504, mcp_is_error=True),
    ErrorCode.INTERNAL: ErrorMapping(exit_code=1, http_status=500, mcp_is_error=True),
}


def _details(exc: QueryError) -> tuple[ErrorDetail, ...]:
    if isinstance(exc, InvalidArgumentError):
        return (
            ErrorDetail(key="argument", value=exc.argument),
            ErrorDetail(key="reason", value=exc.reason),
        )
    if isinstance(exc, IndexNotFoundError):
        return (ErrorDetail(key="searched_from", value=str(exc.searched_from)),)
    if isinstance(exc, IndexBusyError):
        return (ErrorDetail(key="retry_after_s", value=str(exc.retry_after_s)),)
    if isinstance(exc, QueryTimeoutError):
        return (ErrorDetail(key="timeout_ms", value=str(exc.timeout_ms)),)
    return ()


def to_error_response(exc: QueryError) -> ErrorResponse:
    """Build the error envelope for a query-layer exception.

    Args:
        exc: The exception raised by the query layer.

    Returns:
        An ``ErrorResponse`` carrying the exception's code, message and typed details.

    Example:
        ``to_error_response(IndexBusyError(retry_after_s=5))`` returns an
        ``INDEX_BUSY`` response with ``ErrorDetail(key="retry_after_s", value="5")``.
    """
    return ErrorResponse(code=exc.code, message=str(exc), details=_details(exc))
