"""``/api`` query routes: search, impact and overview over the read-only index."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response

from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation, require_index
from compass_core.query.detail import describe
from compass_core.query.errors import ErrorResponse
from compass_core.query.impact import impact
from compass_core.query.models import IndexStatus
from compass_core.query.overview import overview
from compass_core.query.params import (
    MAX_DEPTH,
    MAX_LIMIT,
    MAX_TEXT_LENGTH,
    ImpactParams,
    SearchParams,
)
from compass_core.query.results import (
    AmbiguousReference,
    ImpactResult,
    NodeDetail,
    OverviewResult,
    SearchResult,
    SymbolNotFound,
)
from compass_core.query.search import find_symbols
from compass_core.query.serialize import to_json
from compass_core.query.status import index_status
from compass_core.query.types import SymbolKind
from compass_core.settings import settings

router = APIRouter(tags=["query"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Invalid argument"},
    503: {"model": ErrorResponse, "description": "Index missing, busy or incompatible"},
    504: {"model": ErrorResponse, "description": "Query timed out"},
}
_LOOKUP_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": SymbolNotFound, "description": "Reference matched nothing"},
    409: {"model": AmbiguousReference, "description": "Reference matched several symbols"},
    **_ERRORS,
}


def get_index() -> IndexLocation:
    """Locate the index: ``LADYBUG_DB_PATH`` if it exists, else walk up from the cwd.

    The configured path is resolved so ``repo_root`` is absolute regardless of the
    cwd. A configured path that does not exist falls back to the cwd search.

    Returns:
        The index location.

    Raises:
        IndexNotFoundError: If no index can be found.
    """
    configured = Path(settings.LADYBUG_DB_PATH).resolve()
    if configured.exists():
        return require_index(Path.cwd(), override=configured)
    return require_index(Path.cwd())


def get_db(location: Annotated[IndexLocation, Depends(get_index)]) -> Iterator[GraphDB]:
    """Yield a read-only database handle that is always closed afterwards.

    Args:
        location: The located index.

    Yields:
        A read-only ``GraphDB``.
    """
    with GraphDB(location.db_path, read_only=True) as db:
        yield db


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
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
) -> SearchResult:
    """Search files, classes, functions and methods by name."""
    return find_symbols(db, location, SearchParams(query=q, kind=kind, limit=limit))


@router.get("/impact", response_model=ImpactResult, responses=_LOOKUP_ERRORS)
def impact_of(
    db: Db,
    location: Location,
    ref: Annotated[str, _TEXT],
    depth: Annotated[int, Query(ge=1, le=MAX_DEPTH)] = 3,
    min_confidence: Annotated[float, Query(ge=0, le=1)] = 0.0,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
) -> ImpactResult | Response:
    """List what may be affected by changing a file or symbol."""
    params = ImpactParams(depth=depth, min_confidence=min_confidence, limit=limit)
    result = impact(db, location, ref, params)
    if isinstance(result, AmbiguousReference):
        return Response(to_json(result), status_code=409, media_type="application/json")
    if isinstance(result, SymbolNotFound):
        return Response(to_json(result), status_code=404, media_type="application/json")
    return result


@router.get("/status", response_model=IndexStatus, responses=_ERRORS)
def status(db: Db, location: Location) -> IndexStatus:
    """Describe the index: which repository, when it was built and how many files changed since."""
    return index_status(location, db)


@router.get("/describe", response_model=NodeDetail, responses=_LOOKUP_ERRORS)
def describe_node(db: Db, location: Location, ref: Annotated[str, _TEXT]) -> NodeDetail | Response:
    """Describe one file, class, function or method: docstring, source and neighbours."""
    result = describe(db, location, ref)
    if isinstance(result, AmbiguousReference):
        return Response(to_json(result), status_code=409, media_type="application/json")
    if isinstance(result, SymbolNotFound):
        return Response(to_json(result), status_code=404, media_type="application/json")
    return result


@router.get("/overview", response_model=OverviewResult, responses=_ERRORS)
def repo_overview(db: Db, location: Location) -> OverviewResult:
    """Summarise the index: totals, entry points and ranked hot spots."""
    return overview(db, location)
