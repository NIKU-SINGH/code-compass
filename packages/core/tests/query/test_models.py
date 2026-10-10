import pytest

from compass_core.query.models import EdgeRef, ResultItem, SymbolRef, Via
from compass_core.query.types import (
    CallType,
    EdgeType,
    QualifiedName,
    RepoPath,
    SymbolId,
    SymbolKind,
    ViaKind,
)


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
