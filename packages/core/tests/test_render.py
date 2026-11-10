"""``render`` turns every result into compact text with ``file:line`` first."""

from __future__ import annotations

from dataclasses import replace

from compass_core.contract.errors import ErrorResponse
from compass_core.contract.params import ImpactParams, SearchParams
from compass_core.contract.results import (
    AmbiguousReference,
    ImpactResult,
    NodeDetail,
    SymbolNotFound,
)
from compass_core.errors import ErrorCode
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation
from compass_core.query.detail import describe
from compass_core.query.impact import impact
from compass_core.query.overview import overview
from compass_core.query.search import find_symbols
from compass_core.query.status import index_status
from compass_core.render import (
    local_name,
    location,
    render_ambiguous,
    render_describe,
    render_error,
    render_impact,
    render_not_found,
    render_overview,
    render_search,
    render_status,
)


def test_status_header_says_whether_the_index_is_fresh(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    status = index_status(fixture_index, fixture_db)
    assert render_status(status).endswith("up to date")
    stale = render_status(replace(status, stale_file_count=2, indexed_commit="abcdef1234"))
    assert stale.startswith("index: abcdef1 · built ")
    assert stale.endswith("2 files changed since; run `compass ingest`")


def test_search_lists_hits_with_location_and_reason(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    text = render_search(find_symbols(fixture_db, fixture_index, SearchParams(query="save")))
    lines = text.splitlines()
    assert lines[1] == 'search "save" · 2 hits'
    assert lines[2] == "app/models.py:2  method  app.models.Base.save  exact name · 1 caller"
    assert lines[3] == "app/models.py:6  method  app.models.User.save  exact name · 0 callers"


def test_search_says_how_many_more_hits_the_limit_hid(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    result = find_symbols(fixture_db, fixture_index, SearchParams(query="a", limit=1))
    assert result.total > 1
    assert f"… {result.total - 1} more; raise the limit" in render_search(result)


def test_describe_shows_location_id_and_neighbours(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    detail = describe(fixture_db, fixture_index, "app/models.py::User.save")
    assert isinstance(detail, NodeDetail)
    text = render_describe(detail)
    assert "method app.models.User.save  app/models.py:6-7" in text
    assert "id: app/models.py::User.save" in text
    assert "callees (1):\n  app/models.py:2  method  app.models.Base.save" in text
    assert "source:" not in text
    assert "source:" in render_describe(detail, include_source=True)


def test_impact_groups_items_by_distance_with_via_and_caveats(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    result = impact(fixture_db, fixture_index, "decode_token", ImpactParams(depth=2))
    assert isinstance(result, ImpactResult)
    text = render_impact(result)
    assert "impact of function app.auth.decode_token (app/auth.py:3) · depth 2" in text
    assert "distance 1\n  app/api.py:4  function  app.api.handle  calls decode_token  1.00" in text
    assert "distance 2\n  app/scheduler.py:4  function  app.scheduler.tick  calls nightly" in text
    assert "\n! " in text  # the unresolved-calls caveat is never dropped


def test_overview_summarises_totals_and_hot_spots(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    text = render_overview(overview(fixture_db, fixture_index))
    assert "8 files · 3 classes · 11 functions" in text
    assert "calls resolved: " in text
    assert "riskiest to change:\n  app/auth.py:3  function  app.auth.decode_token" in text


def test_ambiguous_and_not_found_say_what_to_pass_instead(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    ambiguous = describe(fixture_db, fixture_index, "save")
    assert isinstance(ambiguous, AmbiguousReference)
    assert render_ambiguous(ambiguous).splitlines() == [
        '"save" matches 2 symbols; pass one of these ids or a qualified name:',
        "  app/models.py::Base.save  method  app/models.py:2",
        "  app/models.py::User.save  method  app/models.py:6",
    ]
    missing = describe(fixture_db, fixture_index, "decode_tokn")
    assert isinstance(missing, SymbolNotFound)
    assert render_not_found(missing).startswith('no symbol matches "decode_tokn"')
    empty = SymbolNotFound(reference="zzz", suggestions=())
    assert render_not_found(empty) == 'no symbol matches "zzz"; try `compass search`'


def test_error_shows_code_and_fix() -> None:
    error = ErrorResponse(
        code=ErrorCode.INDEX_NOT_FOUND, message="Run `compass ingest`.", details=()
    )
    assert render_error(error) == "error [INDEX_NOT_FOUND]: Run `compass ingest`."


def test_location_of_each_kind(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    hits = find_symbols(fixture_db, fixture_index, SearchParams(query="auth")).hits
    file_hit = next(h for h in hits if h.symbol.kind == "file")
    assert location(file_hit.symbol) == "app/auth.py"


def test_local_name_is_the_name_within_the_file(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    detail = describe(fixture_db, fixture_index, "app/models.py::User.save")
    assert isinstance(detail, NodeDetail)
    assert local_name(detail.symbol) == "User.save"
    hits = find_symbols(fixture_db, fixture_index, SearchParams(query="auth")).hits
    file_hit = next(h for h in hits if h.symbol.kind == "file")
    assert local_name(file_hit.symbol) == "app/auth.py"
