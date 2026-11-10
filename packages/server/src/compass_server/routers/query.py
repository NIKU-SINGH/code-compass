"""``/api`` routes: thin HTTP adapters over the read-only query layer.

Each route parses its parameters, calls one ``compass_core.query`` function and returns
its ``compass_core.contract`` result. Status codes for failures come from
``ERROR_MAPPINGS``, the table every adapter shares.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, Query, Response

from compass_core.contract.errors import ERROR_MAPPINGS, ErrorResponse
from compass_core.contract.models import IndexStatus
from compass_core.contract.params import (
    DEFAULT_IMPACT_DEPTH,
    DEFAULT_LIMIT,
    DEFAULT_MIN_CONFIDENCE,
    MAX_DEPTH,
    MAX_LIMIT,
    MAX_TEXT_LENGTH,
    ImpactParams,
    SearchParams,
)
from compass_core.contract.results import (
    AmbiguousReference,
    GraphMap,
    ImpactResult,
    Lookup,
    NodeDetail,
    OverviewResult,
    SearchResult,
    SymbolNotFound,
)
from compass_core.contract.serialize import to_json
from compass_core.errors import ErrorCode
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation, locate_index
from compass_core.query.detail import describe
from compass_core.query.graph_map import graph_map
from compass_core.query.impact import impact
from compass_core.query.overview import overview
from compass_core.query.search import find_symbols
from compass_core.query.status import index_status
from compass_core.shared_types import SymbolKind

router = APIRouter(tags=["query"])

R = TypeVar("R")

_AMBIGUOUS_STATUS = ERROR_MAPPINGS[ErrorCode.AMBIGUOUS].http_status
_NOT_FOUND_STATUS = ERROR_MAPPINGS[ErrorCode.NOT_FOUND].http_status
_ERRORS: dict[int | str, dict[str, Any]] = {
    ERROR_MAPPINGS[ErrorCode.INVALID_ARGUMENT].http_status: {
        "model": ErrorResponse,
        "description": "Invalid argument",
    },
    ERROR_MAPPINGS[ErrorCode.INDEX_NOT_FOUND].http_status: {
        "model": ErrorResponse,
        "description": "Index missing, busy or incompatible",
    },
    ERROR_MAPPINGS[ErrorCode.QUERY_TIMEOUT].http_status: {
        "model": ErrorResponse,
        "description": "Query timed out",
    },
}
_LOOKUP_ERRORS: dict[int | str, dict[str, Any]] = {
    _NOT_FOUND_STATUS: {"model": SymbolNotFound, "description": "Reference matched nothing"},
    _AMBIGUOUS_STATUS: {
        "model": AmbiguousReference,
        "description": "Reference matched several symbols",
    },
    **_ERRORS,
}


def get_index() -> IndexLocation:
    """FastAPI dependency for the index; the lookup rule lives in ``locate_index``.

    Returns:
        The index location.

    Raises:
        IndexNotFoundError: If no index can be found.
        IndexIncompatibleError: If the index must be rebuilt with ``compass ingest``.
    """
    return locate_index()


def get_db(location: Annotated[IndexLocation, Depends(get_index)]) -> Iterator[GraphDB]:
    """Yield a read-only database handle that is always closed afterwards.

    Args:
        location: The located index.

    Yields:
        A read-only ``GraphDB``.
    """
    with GraphDB(location.db_path, read_only=True) as db:
        yield db


def _lookup_response(result: Lookup[R]) -> R | Response:
    """Return a found result as is; an ambiguous or missing reference as its status code.

    Args:
        result: What a reference-taking operation returned.

    Returns:
        ``result`` itself, or a JSON response with the status ``ERROR_MAPPINGS`` gives
        ``AMBIGUOUS`` or ``NOT_FOUND`` and the outcome as its body.

    Example:
        ``_lookup_response(SymbolNotFound(reference="x", suggestions=()))`` is a 404 whose
        body is ``{"outcome":"not_found","reference":"x","suggestions":[]}``.
    """
    if isinstance(result, AmbiguousReference):
        status = _AMBIGUOUS_STATUS
    elif isinstance(result, SymbolNotFound):
        status = _NOT_FOUND_STATUS
    else:
        return result
    return Response(to_json(result), status_code=status, media_type="application/json")


Location = Annotated[IndexLocation, Depends(get_index)]
Db = Annotated[GraphDB, Depends(get_db)]
# Free text: 1..MAX_TEXT_LENGTH characters with at least one non-whitespace character;
# anything else is a 422 INVALID_ARGUMENT naming the parameter.
_TEXT = Query(min_length=1, max_length=MAX_TEXT_LENGTH, pattern=r"\S")


@router.get("/search", response_model=SearchResult, responses=_ERRORS)
def search(
    db: Db,
    location: Location,
    q: Annotated[str, _TEXT],
    kind: SymbolKind | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> SearchResult:
    """Search files, classes, functions and methods by name."""
    return find_symbols(db, location, SearchParams(query=q, kind=kind, limit=limit))


@router.get("/impact", response_model=ImpactResult, responses=_LOOKUP_ERRORS)
def impact_of(
    db: Db,
    location: Location,
    ref: Annotated[str, _TEXT],
    depth: Annotated[int, Query(ge=1, le=MAX_DEPTH)] = DEFAULT_IMPACT_DEPTH,
    min_confidence: Annotated[float, Query(ge=0, le=1)] = DEFAULT_MIN_CONFIDENCE,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> ImpactResult | Response:
    """List what may be affected by changing a file or symbol."""
    params = ImpactParams(depth=depth, min_confidence=min_confidence, limit=limit)
    return _lookup_response(impact(db, location, ref, params))


@router.get("/status", response_model=IndexStatus, responses=_ERRORS)
def status(db: Db, location: Location) -> IndexStatus:
    """Describe the index: which repository, when it was built and how many files changed since."""
    return index_status(location, db)


@router.get("/describe", response_model=NodeDetail, responses=_LOOKUP_ERRORS)
def describe_node(db: Db, location: Location, ref: Annotated[str, _TEXT]) -> NodeDetail | Response:
    """Describe one file, class, function or method: docstring, source and neighbours."""
    return _lookup_response(describe(db, location, ref))


@router.get("/overview", response_model=OverviewResult, responses=_ERRORS)
def repo_overview(db: Db, location: Location) -> OverviewResult:
    """Summarise the index: totals, entry points and ranked hot spots."""
    return overview(db, location)


@router.get("/graph/map", response_model=GraphMap, responses=_ERRORS)
def graph(db: Db) -> GraphMap:
    """Every file, class, function and method, and the edges between them, for drawing."""
    return graph_map(db)
