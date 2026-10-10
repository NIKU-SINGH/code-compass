"""Exception handlers that render every failure as an ``ErrorResponse``."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from compass_core.errors import ErrorCode, IndexBusyError, QueryError
from compass_core.query.errors import (
    ERROR_MAPPINGS,
    ErrorDetail,
    ErrorResponse,
    to_error_response,
)
from compass_core.query.serialize import to_json

logger = logging.getLogger(__name__)


def _respond(body: ErrorResponse, status: int, headers: dict[str, str] | None = None) -> Response:
    return Response(
        to_json(body), status_code=status, headers=headers, media_type="application/json"
    )


def _loc(loc: tuple[int | str, ...]) -> tuple[int | str, ...]:
    return loc[1:] if loc and loc[0] == "query" else loc


async def _query_error(_request: Request, exc: Exception) -> Response:
    assert isinstance(exc, QueryError)
    headers = {"Retry-After": str(exc.retry_after_s)} if isinstance(exc, IndexBusyError) else None
    return _respond(to_error_response(exc), ERROR_MAPPINGS[exc.code].http_status, headers)


async def _validation_error(_request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    details = tuple(
        ErrorDetail(
            key=".".join(str(part) for part in _loc(err["loc"])),
            value=str(err["msg"]),
        )
        for err in exc.errors()
    )
    body = ErrorResponse(
        code=ErrorCode.INVALID_ARGUMENT,
        message="Invalid request: " + "; ".join(f"{d.key}: {d.value}" for d in details),
        details=details,
    )
    return _respond(body, ERROR_MAPPINGS[ErrorCode.INVALID_ARGUMENT].http_status)


async def _catch_unexpected(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Turn any unexpected exception into a 500 ``ErrorResponse``.

    Runs as middleware (not an exception handler) so CORS, registered after it,
    stays outermost and decorates the 500.
    """
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error in request")
    body = ErrorResponse(code=ErrorCode.INTERNAL, message="Internal error", details=())
    return _respond(body, ERROR_MAPPINGS[ErrorCode.INTERNAL].http_status)


def register_error_handlers(app: FastAPI) -> None:
    """Install the ``QueryError``, validation and catch-all handling on ``app``.

    Call this BEFORE adding ``CORSMiddleware`` so CORS wraps the catch-all 500.

    Args:
        app: The FastAPI application.
    """
    app.add_exception_handler(QueryError, _query_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_middleware(BaseHTTPMiddleware, dispatch=_catch_unexpected)
