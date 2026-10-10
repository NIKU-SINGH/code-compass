"""Exception handlers that render every failure as an ``ErrorResponse``."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

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


async def _query_error(_request: Request, exc: Exception) -> Response:
    assert isinstance(exc, QueryError)
    headers = {"Retry-After": str(exc.retry_after_s)} if isinstance(exc, IndexBusyError) else None
    return _respond(to_error_response(exc), ERROR_MAPPINGS[exc.code].http_status, headers)


async def _validation_error(_request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    details = tuple(
        ErrorDetail(
            key=".".join(str(part) for part in err["loc"] if part != "query"),
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


async def _unexpected_error(_request: Request, exc: Exception) -> Response:
    logger.exception("Unhandled error in request", exc_info=exc)
    body = ErrorResponse(code=ErrorCode.INTERNAL, message="Internal error", details=())
    return _respond(body, ERROR_MAPPINGS[ErrorCode.INTERNAL].http_status)


def register_error_handlers(app: FastAPI) -> None:
    """Install the ``QueryError``, validation and catch-all handlers on ``app``.

    Args:
        app: The FastAPI application.
    """
    app.add_exception_handler(QueryError, _query_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unexpected_error)
