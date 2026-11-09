"""/api/repo endpoints: wire models over the engine's overview and graph map."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from compass_core.graph.db import GraphDB
from compass_core.query.graph_map import graph_map
from compass_core.query.overview import entry_points, index_counts
from compass_core.settings import settings
from compass_server.routers.query import get_index

logger = logging.getLogger(__name__)

router = APIRouter(tags=["repo"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class EntryPoint(BaseModel):
    path: str
    module_name: str


class OverviewResponse(BaseModel):
    project_id: str
    file_count: int
    class_count: int
    function_count: int
    edge_count: int
    entry_points: list[EntryPoint]


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    file_path: str
    public_id: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_index() -> GraphDB:
    """Open the index the query routes use (``get_index``), read-only.

    Located from ``LADYBUG_DB_PATH`` or by walking up from the cwd, so the routes
    work when the server is started from a subdirectory of the indexed repo.

    Raises:
        IndexNotFoundError: No index can be located (the routes answer 503).
    """
    return GraphDB(get_index().db_path, read_only=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/repo/overview", response_model=OverviewResponse)
async def repo_overview() -> OverviewResponse:
    try:
        with _open_index() as db:
            counts = index_counts(db)
            entries = entry_points(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return OverviewResponse(
        project_id=settings.REPO_ROOT.name,
        file_count=counts.files,
        class_count=counts.classes,
        function_count=counts.functions,
        edge_count=sum(counts.edges_by_type.values()),
        entry_points=[
            EntryPoint(path=str(entry.file_path), module_name=entry.qualified_name)
            for entry in entries
        ],
    )


@router.get("/repo/graph", response_model=GraphResponse)
async def repo_graph() -> GraphResponse:
    try:
        with _open_index() as db:
            result = graph_map(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return GraphResponse(
        nodes=[
            GraphNode(
                id=node.id,
                label=node.label,
                type=node.kind.value.title(),
                file_path=node.file_path,
                public_id=node.public_id,
            )
            for node in result.nodes
        ],
        edges=[
            GraphEdge(id=f"e{i}", source=edge.source, target=edge.target, type=edge.type.value)
            for i, edge in enumerate(result.edges)
        ],
    )
