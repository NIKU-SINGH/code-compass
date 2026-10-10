"""``/api`` query routes: search, impact and overview over the read-only index."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response

from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation, require_index
from compass_core.query.errors import ErrorResponse
from compass_core.query.impact import impact
from compass_core.query.overview import overview
from compass_core.query.params import MAX_DEPTH, MAX_LIMIT, ImpactParams, SearchParams
from compass_core.query.results import (
    AmbiguousReference,
    ImpactResult,
    OverviewResult,
    SearchResult,
    SymbolNotFound,
)
from compass_core.query.search import find_symbols
from compass_core.query.serialize import to_json
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

    Returns:
        The index location.

    Raises:
        IndexNotFoundError: If no index can be found.
    """
    configured = Path(settings.LADYBUG_DB_PATH)
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


@router.get("/search", response_model=SearchResult, responses=_ERRORS)
def search(
    db: Db,
    location: Location,
    q: Annotated[str, Query(min_length=1)],
    kind: SymbolKind | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
) -> SearchResult:
    """Search files, classes, functions and methods by name."""
    return find_symbols(db, location, SearchParams(query=q, kind=kind, limit=limit))


@router.get("/impact", response_model=ImpactResult, responses=_LOOKUP_ERRORS)
def impact_of(
    db: Db,
    location: Location,
    ref: Annotated[str, Query(min_length=1)],
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


@router.get("/overview", response_model=OverviewResult, responses=_ERRORS)
def repo_overview(db: Db, location: Location) -> OverviewResult:
    """Summarise the index: totals, entry points and ranked hot spots."""
    return overview(db, location)
