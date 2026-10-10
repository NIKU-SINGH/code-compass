import json
from datetime import UTC, datetime
from pathlib import Path

from compass_core.errors import ErrorCode
from compass_core.query.errors import ErrorResponse
from compass_core.query.models import Caveat, IndexStatus, SymbolRef
from compass_core.query.results import (
    ImpactGroup,
    ImpactResult,
    SearchHit,
    SearchResult,
    SymbolNotFound,
)
from compass_core.query.serialize import to_json
from compass_core.query.types import (
    CaveatCode,
    MatchRule,
    QualifiedName,
    RepoPath,
    SearchMatch,
    SymbolId,
    SymbolKind,
)


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
