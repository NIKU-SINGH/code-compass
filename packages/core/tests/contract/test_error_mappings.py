import pytest

from compass_core.contract.errors import ERROR_MAPPINGS, ErrorDetail, to_error_response
from compass_core.errors import (
    ErrorCode,
    IndexBusyError,
    IndexIncompatibleError,
    IndexNotFoundError,
    InvalidArgumentError,
    QueryTimeoutError,
)


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


def test_full_mapping_table():
    expected = {
        ErrorCode.INVALID_ARGUMENT: (2, 422, True),
        ErrorCode.NOT_FOUND: (3, 404, False),
        ErrorCode.AMBIGUOUS: (4, 409, False),
        ErrorCode.INDEX_NOT_FOUND: (5, 503, True),
        ErrorCode.INDEX_BUSY: (6, 503, True),
        ErrorCode.INDEX_INCOMPATIBLE: (7, 503, True),
        ErrorCode.QUERY_TIMEOUT: (8, 504, True),
        ErrorCode.INTERNAL: (1, 500, True),
    }
    actual = {c: (m.exit_code, m.http_status, m.mcp_is_error) for c, m in ERROR_MAPPINGS.items()}
    assert actual == expected


def test_mappings_immutable():
    with pytest.raises(TypeError):
        ERROR_MAPPINGS[ErrorCode.INTERNAL] = ERROR_MAPPINGS[ErrorCode.NOT_FOUND]  # type: ignore[index]


def test_index_not_found_details():
    from pathlib import Path

    resp = to_error_response(IndexNotFoundError(searched_from=Path("/x")))
    assert resp.code is ErrorCode.INDEX_NOT_FOUND
    assert ErrorDetail(key="searched_from", value="/x") in resp.details


def test_index_incompatible_response():
    resp = to_error_response(IndexIncompatibleError("bad schema"))
    assert resp.code is ErrorCode.INDEX_INCOMPATIBLE
    assert resp.message == "bad schema"
    assert resp.details == ()
