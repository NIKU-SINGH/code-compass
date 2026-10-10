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
