import pytest

from compass_core.errors import InvalidArgumentError
from compass_core.query.params import MAX_DEPTH, MAX_LIMIT, ImpactParams, SearchParams


@pytest.mark.parametrize("depth", [0, MAX_DEPTH + 1, -1])
def test_depth_out_of_bounds(depth):
    with pytest.raises(InvalidArgumentError) as exc:
        ImpactParams(depth=depth)
    assert exc.value.argument == "depth"


@pytest.mark.parametrize("limit", [0, MAX_LIMIT + 1])
def test_limit_out_of_bounds(limit):
    with pytest.raises(InvalidArgumentError) as exc:
        SearchParams(query="x", limit=limit)
    assert exc.value.argument == "limit"


@pytest.mark.parametrize("conf", [-0.1, 1.1])
def test_min_confidence_out_of_bounds(conf):
    with pytest.raises(InvalidArgumentError) as exc:
        ImpactParams(min_confidence=conf)
    assert exc.value.argument == "min_confidence"


def test_empty_search_query_rejected():
    with pytest.raises(InvalidArgumentError) as exc:
        SearchParams(query="  ")
    assert exc.value.argument == "query"


def test_defaults_valid():
    assert ImpactParams().depth == 3
    assert SearchParams(query="x").limit == 50


@pytest.mark.parametrize("limit", [0, MAX_LIMIT + 1])
def test_impact_limit_out_of_bounds(limit):
    with pytest.raises(InvalidArgumentError) as exc:
        ImpactParams(limit=limit)
    assert exc.value.argument == "limit"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"depth": 1},
        {"depth": MAX_DEPTH},
        {"limit": 1},
        {"limit": MAX_LIMIT},
        {"min_confidence": 0.0},
        {"min_confidence": 1.0},
    ],
)
def test_boundaries_accepted(kwargs):
    ImpactParams(**kwargs)


def test_search_boundaries_accepted():
    SearchParams(query="x", limit=1)
    SearchParams(query="x", limit=MAX_LIMIT)


def test_nan_min_confidence_rejected():
    with pytest.raises(InvalidArgumentError) as exc:
        ImpactParams(min_confidence=float("nan"))
    assert exc.value.argument == "min_confidence"


@pytest.mark.parametrize(
    ("kwargs", "arg"),
    [
        ({"depth": True}, "depth"),
        ({"limit": True}, "limit"),
        ({"min_confidence": True}, "min_confidence"),
    ],
)
def test_bool_rejected(kwargs, arg):
    with pytest.raises(InvalidArgumentError) as exc:
        ImpactParams(**kwargs)
    assert exc.value.argument == arg


def test_search_bool_limit_rejected():
    with pytest.raises(InvalidArgumentError) as exc:
        SearchParams(query="x", limit=True)
    assert exc.value.argument == "limit"


def test_non_str_query_rejected():
    with pytest.raises(InvalidArgumentError) as exc:
        SearchParams(query=None)  # type: ignore[arg-type]
    assert exc.value.argument == "query"
