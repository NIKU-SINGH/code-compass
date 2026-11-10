"""The terminal views show the same facts as the compact text, laid out for people."""

from __future__ import annotations

from dataclasses import replace

from rich.console import Console, RenderableType

from compass_cli import result_views
from compass_core.contract.params import ImpactParams, SearchParams
from compass_core.contract.results import ImpactResult, NodeDetail
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation
from compass_core.query.detail import describe
from compass_core.query.impact import impact
from compass_core.query.overview import overview
from compass_core.query.search import find_symbols
from compass_core.query.status import index_status

WIDTH = 160


def _text(view: RenderableType) -> str:
    console = Console(width=WIDTH, record=True, color_system=None)
    console.print(view)
    return console.export_text()


def test_status_panel_says_fresh_or_stale(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    status = index_status(fixture_index, fixture_db)
    text = _text(result_views.status_view(status))
    assert "compass index" in text and "✓ up to date" in text
    stale = _text(result_views.status_view(replace(status, stale_file_count=2)))
    assert "⚠ 2 files changed since; run compass ingest" in stale


def test_overview_has_totals_and_ranked_tables(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    text = _text(result_views.overview_view(overview(fixture_db, fixture_index)))
    assert "compass overview" in text
    assert "Files" in text and "Calls resolved" in text
    assert "Riskiest to change" in text
    assert "decode_token" in text and "app/auth.py:3" in text


def test_search_rows_show_short_name_location_and_reason(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    result = find_symbols(fixture_db, fixture_index, SearchParams(query="save"))
    text = _text(result_views.search_view(result))
    assert 'search "save" · 2 hits' in text
    row = next(line for line in text.splitlines() if "Base.save" in line)
    assert "method" in row and "app/models.py:2" in row and "exact name · 1 caller" in row


def test_describe_panel_and_neighbours(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    detail = describe(fixture_db, fixture_index, "app/models.py::User.save")
    assert isinstance(detail, NodeDetail)
    text = _text(result_views.describe_view(detail))
    assert "method save" in text and "app/models.py:6-7" in text
    assert "Callees (1)" in text and "Base.save" in text
    assert "Source" not in text
    assert "Source" in _text(result_views.describe_view(detail, include_source=True))


def test_impact_lists_hops_and_keeps_caveats(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    result = impact(fixture_db, fixture_index, "decode_token", ImpactParams(depth=2))
    assert isinstance(result, ImpactResult)
    text = _text(result_views.impact_view(result))
    assert "impact of function decode_token" in text
    row = next(line for line in text.splitlines() if "handle" in line)
    assert "app/api.py:4" in row and "calls decode_token" in row
    assert "\n! " in text
