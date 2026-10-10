"""/api/repo endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from compass_core.graph.db import GraphDB, as_row, as_rows
from compass_core.query.rows import public_definition_id, public_file_id
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


_MAX_ENTRY_POINTS = 5

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count(db: GraphDB, query: str) -> int:
    result = db.execute(query)
    return int(as_row(result)[0]) if result.has_next() else 0


def _edge_count(db: GraphDB) -> int:
    result = db.execute("MATCH ()-[r]->() RETURN count(*)")
    return int(as_row(result)[0]) if result.has_next() else 0


def _entry_points(db: GraphDB) -> list[EntryPoint]:
    result = db.execute(
        f"""
        MATCH (f:File)
        WHERE NOT EXISTS {{ MATCH (:File)-[:IMPORTS]->(f) }}
        RETURN f.path, f.module_name
        LIMIT {_MAX_ENTRY_POINTS}
        """
    )
    rows = as_rows(result)
    return [EntryPoint(path=row[0], module_name=row[1]) for row in rows]


def _graph_nodes(db: GraphDB) -> list[GraphNode]:
    repo_root = Path(settings.REPO_ROOT).resolve()
    nodes: list[GraphNode] = []

    for row in as_rows(db.execute("MATCH (f:File) RETURN f.path, f.path, 'File', f.path")):
        path = row[0]
        nodes.append(
            GraphNode(
                id=path,
                label=path.split("/")[-1],
                type="File",
                file_path=path,
                public_id=public_file_id(path, repo_root),
            )
        )

    for row in as_rows(db.execute("MATCH (c:Class) RETURN c.id, c.name, 'Class', c.file_path")):
        nodes.append(
            GraphNode(
                id=row[0],
                label=row[1],
                type="Class",
                file_path=row[3],
                public_id=public_definition_id(row[0], row[3], repo_root),
            )
        )

    for row in as_rows(
        db.execute("MATCH (fn:Function) RETURN fn.id, fn.name, fn.is_method, fn.file_path")
    ):
        node_type = "Method" if row[2] else "Function"
        nodes.append(
            GraphNode(
                id=row[0],
                label=row[1],
                type=node_type,
                file_path=row[3],
                public_id=public_definition_id(row[0], row[3], repo_root),
            )
        )

    return nodes


def _graph_edges(db: GraphDB) -> list[GraphEdge]:
    seen: set[tuple[str, str, str]] = set()
    edges: list[GraphEdge] = []
    counter = 0

    def _add(source: str, target: str, edge_type: str) -> None:
        nonlocal counter
        key = (source, target, edge_type)
        if key in seen:
            return
        seen.add(key)
        edges.append(GraphEdge(id=f"e{counter}", source=source, target=target, type=edge_type))
        counter += 1

    for row in as_rows(db.execute("MATCH (a:File)-[:CONTAINS]->(b:Class) RETURN a.path, b.id")):
        _add(row[0], row[1], "CONTAINS")

    for row in as_rows(db.execute("MATCH (a:File)-[:CONTAINS]->(b:Function) RETURN a.path, b.id")):
        _add(row[0], row[1], "CONTAINS")

    for row in as_rows(db.execute("MATCH (a:Class)-[:CONTAINS]->(b:Function) RETURN a.id, b.id")):
        _add(row[0], row[1], "CONTAINS")

    for row in as_rows(db.execute("MATCH (a:File)-[:IMPORTS]->(b:File) RETURN a.path, b.path")):
        _add(row[0], row[1], "IMPORTS")

    for row in as_rows(db.execute("MATCH (a:Class)-[:INHERITS]->(b:Class) RETURN a.id, b.id")):
        _add(row[0], row[1], "INHERITS")

    return edges


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


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


@router.get("/repo/graph", response_model=GraphResponse)
async def repo_graph() -> GraphResponse:
    try:
        with GraphDB() as db:
            nodes = _graph_nodes(db)
            edges = _graph_edges(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return GraphResponse(nodes=nodes, edges=edges)
