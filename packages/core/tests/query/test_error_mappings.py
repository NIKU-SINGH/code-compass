from compass_core.errors import (
    ErrorCode,
    IndexBusyError,
    InvalidArgumentError,
    QueryTimeoutError,
)
from compass_core.query.errors import ERROR_MAPPINGS, ErrorDetail, to_error_response


def test_mappings_cover_every_error_code():
    assert set(ERROR_MAPPINGS) == set(ErrorCode)


def test_mapping_values():
    m = ERROR_MAPPINGS[ErrorCode.INDEX_BUSY]
    assert (m.exit_code, m.http_status, m.mcp_is_error) == (6, 503, True)
    m = ERROR_MAPPINGS[ErrorCode.NOT_FOUND]
    assert (m.exit_code, m.http_status, m.mcp_is_error) == (3, 404, False)


def test_invalid_argument_response():
    resp = to_error_response(InvalidArgumentError(argument="depth", reason="too big"))
    assert resp.code is ErrorCode.INVALID_ARGUMENT
    assert ErrorDetail(key="argument", value="depth") in resp.details


def test_busy_and_timeout_details():
    assert (
        ErrorDetail(key="retry_after_s", value="5")
        in to_error_response(IndexBusyError(retry_after_s=5)).details
    )
    assert (
        ErrorDetail(key="timeout_ms", value="100")
        in to_error_response(QueryTimeoutError(timeout_ms=100)).details
    )
