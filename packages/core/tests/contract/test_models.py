import pytest

from compass_core.contract.models import EdgeRef, ResultItem, SymbolRef, Via
from compass_core.contract.types import QualifiedName, RepoPath, SymbolId, ViaKind
from compass_core.shared_types import CallType, EdgeType, SymbolKind


def _sym(**kw):
    base = dict(
        id=SymbolId("a.py::f"),
        kind=SymbolKind.FUNCTION,
        name="f",
        qualified_name=QualifiedName("a.f"),
        file_path=RepoPath("a.py"),
        line_start=1,
        line_end=2,
        signature="def f()",
    )
    return SymbolRef(**{**base, **kw})


def test_line_must_be_one_indexed():
    with pytest.raises(ValueError):
        _sym(line_start=0)


def test_line_end_not_before_start():
    with pytest.raises(ValueError):
        _sym(line_start=5, line_end=4)


def test_confidence_range():
    with pytest.raises(ValueError):
        EdgeRef(
            source_id=SymbolId("a"),
            target_id=SymbolId("b"),
            type=EdgeType.CALLS,
            confidence=1.5,
            call_type=CallType.DIRECT_IMPORT,
            line=3,
        )


def test_only_calls_edges_carry_confidence():
    with pytest.raises(ValueError):
        EdgeRef(
            source_id=SymbolId("a"),
            target_id=SymbolId("b"),
            type=EdgeType.IMPORTS,
            confidence=1.0,
            call_type=None,
            line=None,
        )


def test_calls_edge_requires_confidence_and_call_type():
    with pytest.raises(ValueError):
        EdgeRef(
            source_id=SymbolId("a"),
            target_id=SymbolId("b"),
            type=EdgeType.CALLS,
            confidence=None,
            call_type=None,
            line=None,
        )


def test_distance_zero_has_no_via():
    with pytest.raises(ValueError):
        ResultItem(
            symbol=_sym(),
            distance=0,
            via=Via(kind=ViaKind.CALLS, symbol=_sym()),
            min_confidence=None,
        )


def test_positive_distance_requires_via():
    with pytest.raises(ValueError):
        ResultItem(symbol=_sym(), distance=1, via=None, min_confidence=None)


def test_negative_distance_rejected():
    with pytest.raises(ValueError):
        ResultItem(symbol=_sym(), distance=-1, via=None, min_confidence=None)


def _edge(**kw):
    base = dict(
        source_id=SymbolId("a"),
        target_id=SymbolId("b"),
        type=EdgeType.CALLS,
        confidence=1.0,
        call_type=CallType.DIRECT_IMPORT,
        line=3,
    )
    return EdgeRef(**{**base, **kw})


def _via():
    return Via(kind=ViaKind.CALLS, symbol=_sym())


def test_negative_distance_with_valid_via_rejected():
    with pytest.raises(ValueError, match="distance must be >= 0"):
        ResultItem(symbol=_sym(), distance=-1, via=_via(), min_confidence=None)


def test_edge_line_must_be_one_indexed():
    with pytest.raises(ValueError, match="line must be"):
        _edge(line=0)


@pytest.mark.parametrize("conf", [1.5, -0.1])
def test_result_item_min_confidence_range(conf):
    with pytest.raises(ValueError, match="min_confidence"):
        ResultItem(symbol=_sym(), distance=1, via=_via(), min_confidence=conf)


def test_line_end_one_indexed_without_start():
    with pytest.raises(ValueError, match="line_end must be >= 1"):
        _sym(line_start=None, line_end=0)


def test_call_type_without_calls_edge_rejected():
    with pytest.raises(ValueError, match="call_type"):
        _edge(type=EdgeType.IMPORTS, confidence=None, call_type=CallType.MRO, line=None)


def test_calls_edge_confidence_without_call_type_rejected():
    with pytest.raises(ValueError, match="call_type"):
        _edge(call_type=None)


def test_calls_edge_call_type_without_confidence_rejected():
    with pytest.raises(ValueError, match="confidence"):
        _edge(confidence=None)


def test_negative_confidence_rejected():
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        _edge(confidence=-0.1)


def _status(**kw):
    from datetime import UTC, datetime
    from pathlib import Path

    from compass_core.contract.models import IndexStatus

    base = dict(
        repo_root=Path("/repo"),
        indexed_at=datetime(2026, 1, 1, tzinfo=UTC),
        indexed_commit=None,
        schema_version=1,
        stale_file_count=0,
        new_file_count=None,
    )
    return IndexStatus(**{**base, **kw})


def test_index_status_requires_aware_datetime():
    from datetime import datetime

    with pytest.raises(ValueError, match="timezone-aware"):
        _status(indexed_at=datetime(2026, 1, 1))


def test_index_status_requires_absolute_root():
    from pathlib import Path

    with pytest.raises(ValueError, match="absolute"):
        _status(repo_root=Path("rel/repo"))
