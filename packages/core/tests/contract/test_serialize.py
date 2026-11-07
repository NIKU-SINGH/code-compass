import json
from datetime import UTC, datetime
from pathlib import Path

from compass_core.contract.errors import ErrorResponse
from compass_core.contract.models import Caveat, IndexStatus, SymbolRef
from compass_core.contract.results import (
    ImpactGroup,
    ImpactResult,
    SearchHit,
    SearchResult,
    SymbolNotFound,
)
from compass_core.contract.serialize import to_json
from compass_core.contract.types import (
    CaveatCode,
    MatchRule,
    QualifiedName,
    RepoPath,
    SearchMatch,
    SymbolId,
)
from compass_core.errors import ErrorCode
from compass_core.shared_types import SymbolKind


def _sym() -> SymbolRef:
    return SymbolRef(
        id=SymbolId("a.py::f"),
        kind=SymbolKind.FUNCTION,
        name="f",
        qualified_name=QualifiedName("a.f"),
        file_path=RepoPath("a.py"),
        line_start=1,
        line_end=2,
        signature="def f()",
    )


def _index() -> IndexStatus:
    return IndexStatus(
        repo_root=Path("/repo"),
        indexed_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        indexed_commit=None,
        schema_version=1,
        stale_file_count=0,
        new_file_count=None,
    )


def test_not_found_serializes_enum_as_string():
    out = to_json(SymbolNotFound(reference="x", suggestions=()))
    assert '"outcome":"not_found"' in out.replace(" ", "")


def test_search_result_roundtrip_shapes():
    res = SearchResult(
        index=_index(),
        caveats=(Caveat(code=CaveatCode.TRUNCATED, message="m", count=3),),
        query="f",
        kind=None,
        hits=(SearchHit(symbol=_sym(), match=SearchMatch.EXACT, fan_in=2),),
        total=1,
        truncated=False,
    )
    data = json.loads(to_json(res))
    assert data["operation"] == "FIND"
    assert data["outcome"] == "ok"
    assert data["index"]["repo_root"] == "/repo"
    assert data["index"]["indexed_at"].startswith("2026-01-02T03:04:05")
    assert data["caveats"][0]["code"] == "TRUNCATED"
    assert data["hits"][0]["symbol"]["kind"] == "function"


def test_impact_result_serializes():
    res = ImpactResult(
        index=_index(),
        caveats=(),
        target=_sym(),
        matched_by=MatchRule.EXACT_ID,
        depth=3,
        groups=(ImpactGroup(distance=1, file_path=RepoPath("a.py"), items=()),),
        affected_file_count=1,
        edges=(),
        total=0,
        truncated=False,
    )
    data = json.loads(to_json(res))
    assert data["groups"][0]["file_path"] == "a.py"


def test_error_response_serializes():
    out = json.loads(to_json(ErrorResponse(code=ErrorCode.INTERNAL, message="m", details=())))
    assert out == {"code": "INTERNAL", "message": "m", "details": []}


def _item():
    from compass_core.contract.models import ResultItem, Via
    from compass_core.contract.types import ViaKind

    return ResultItem(
        symbol=_sym(),
        distance=1,
        via=Via(kind=ViaKind.CALLS, symbol=_sym()),
        min_confidence=0.5,
    )


def test_populated_impact_result():
    from compass_core.contract.models import EdgeRef
    from compass_core.shared_types import CallType, EdgeType

    res = ImpactResult(
        index=_index(),
        caveats=(),
        target=_sym(),
        matched_by=MatchRule.EXACT_ID,
        depth=3,
        groups=(ImpactGroup(distance=1, file_path=RepoPath("a.py"), items=(_item(),)),),
        affected_file_count=1,
        edges=(
            EdgeRef(
                source_id=SymbolId("a"),
                target_id=SymbolId("b"),
                type=EdgeType.CALLS,
                confidence=0.5,
                call_type=CallType.MRO,
                line=4,
            ),
        ),
        total=1,
        truncated=False,
    )
    data = json.loads(to_json(res))
    assert data["outcome"] == "ok"
    assert data["operation"] == "IMPACT"
    assert data["matched_by"] == "EXACT_ID"
    item = data["groups"][0]["items"][0]
    assert item["via"]["kind"] == "CALLS"
    assert item["min_confidence"] == 0.5
    assert data["edges"][0]["type"] == "CALLS"
    assert data["edges"][0]["call_type"] == "MRO"
    assert data["index"]["repo_root"] == "/repo"
    assert data["index"]["indexed_at"].startswith("2026-01-02T03:04:05")


def test_overview_result():
    from compass_core.contract.results import (
        CallResolution,
        IndexCounts,
        LibraryUsage,
        OverviewResult,
        RankedSymbol,
    )
    from compass_core.shared_types import EdgeType

    res = OverviewResult(
        index=_index(),
        caveats=(),
        counts=IndexCounts(files=1, classes=2, functions=3, edges_by_type={EdgeType.CALLS: 55}),
        call_resolution=CallResolution(total=10, resolved=8),
        entry_points=(),
        most_imported_files=(),
        most_called_functions=(),
        riskiest_to_change=(RankedSymbol(symbol=_sym(), count=14),),
        top_external_libraries=(LibraryUsage(library="pydantic", call_count=2),),
    )
    data = json.loads(to_json(res))
    assert data["operation"] == "OVERVIEW"
    assert data["counts"]["edges_by_type"] == {"CALLS": 55}
    assert data["call_resolution"] == {"total": 10, "resolved": 8}
    assert data["riskiest_to_change"][0]["count"] == 14


def test_ambiguous_reference():
    from compass_core.contract.results import AmbiguousReference

    data = json.loads(to_json(AmbiguousReference(reference="f", candidates=(_sym(), _sym()))))
    assert data["outcome"] == "ambiguous"
    assert len(data["candidates"]) == 2


def test_adapters_build_for_every_public_type():
    from pydantic import TypeAdapter

    from compass_core.contract import results

    for tp in (
        results.SearchResult,
        results.ImpactResult,
        results.OverviewResult,
        results.AmbiguousReference,
        results.SymbolNotFound,
        ErrorResponse,
    ):
        TypeAdapter(tp)
