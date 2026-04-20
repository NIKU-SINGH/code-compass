"""/api/repo endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from compass_core.graph.db import GraphDB
from compass_core.settings import settings

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


_MAX_ENTRY_POINTS = 5

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count(db: GraphDB, query: str) -> int:
    result = db.execute(query)
    return int(result.get_next()[0]) if result.has_next() else 0


def _edge_count(db: GraphDB) -> int:
    result = db.execute("MATCH ()-[r]->() RETURN count(*)")
    return int(result.get_next()[0]) if result.has_next() else 0


def _entry_points(db: GraphDB) -> list[EntryPoint]:
    result = db.execute(
        f"""
        MATCH (f:File)
        WHERE NOT EXISTS {{ MATCH (:File)-[:IMPORTS]->(f) }}
        RETURN f.path, f.module_name
        LIMIT {_MAX_ENTRY_POINTS}
        """
    )
    rows = result.get_all()
    return [EntryPoint(path=row[0], module_name=row[1]) for row in rows]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/repo")
async def repo_info():
    return {"message": "not implemented"}


@router.get("/repo/overview", response_model=OverviewResponse)
async def repo_overview() -> OverviewResponse:
    try:
        with GraphDB() as db:
            file_count = _count(db, "MATCH (n:File) RETURN count(*)")
            class_count = _count(db, "MATCH (n:Class) RETURN count(*)")
            function_count = _count(db, "MATCH (n:Function) RETURN count(*)")
            edge_count = _edge_count(db)
            entry_points = _entry_points(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return OverviewResponse(
        project_id=settings.REPO_ROOT.name,
        file_count=file_count,
        class_count=class_count,
        function_count=function_count,
        edge_count=edge_count,
        entry_points=entry_points,
    )
