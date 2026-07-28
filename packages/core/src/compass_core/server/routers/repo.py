"""/api/repo endpoints."""

from __future__ import annotations

import ast
from pathlib import Path

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


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    file_path: str


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


def _graph_nodes(db: GraphDB) -> list[GraphNode]:
    nodes: list[GraphNode] = []

    for row in db.execute("MATCH (f:File) RETURN f.path, f.path, 'File', f.path").get_all():
        path = row[0]
        nodes.append(GraphNode(id=path, label=path.split("/")[-1], type="File", file_path=path))

    for row in db.execute("MATCH (c:Class) RETURN c.id, c.name, 'Class', c.file_path").get_all():
        nodes.append(GraphNode(id=row[0], label=row[1], type="Class", file_path=row[3]))

    for row in db.execute(
        "MATCH (fn:Function) RETURN fn.id, fn.name, fn.is_method, fn.file_path"
    ).get_all():
        node_type = "Method" if row[2] else "Function"
        nodes.append(GraphNode(id=row[0], label=row[1], type=node_type, file_path=row[3]))

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

    for row in db.execute("MATCH (a:File)-[:CONTAINS]->(b:Class) RETURN a.path, b.id").get_all():
        _add(row[0], row[1], "CONTAINS")

    for row in db.execute("MATCH (a:File)-[:CONTAINS]->(b:Function) RETURN a.path, b.id").get_all():
        _add(row[0], row[1], "CONTAINS")

    for row in db.execute("MATCH (a:Class)-[:CONTAINS]->(b:Function) RETURN a.id, b.id").get_all():
        _add(row[0], row[1], "CONTAINS")

    for row in db.execute("MATCH (a:File)-[:IMPORTS]->(b:File) RETURN a.path, b.path").get_all():
        _add(row[0], row[1], "IMPORTS")

    # DB IMPORTS is empty when module names weren't resolved at index time.
    # Fall back to parsing Python files directly with ast.
    if not any(e.type == "IMPORTS" for e in edges):
        file_paths = []
        for row in db.execute("MATCH (f:File) RETURN f.path, f.module_name").get_all():
            file_paths.append(row[0])
        for src, tgt in _ast_import_edges(file_paths):
            _add(src, tgt, "IMPORTS")

    for row in db.execute("MATCH (a:Class)-[:INHERITS]->(b:Class) RETURN a.id, b.id").get_all():
        _add(row[0], row[1], "INHERITS")

    return edges


def _ast_import_edges(file_paths: list[str]) -> list[tuple[str, str]]:
    """Derive file→file import edges by parsing Python source with ast.

    The DB module names use full repo-relative paths (packages.X.src.Y) rather
    than install names, so the resolver produces no IMPORTS edges. We work
    around this by building a lookup from every plausible suffix of each
    module name to its file path, then matching import statements against it.
    """
    # Build suffix-based lookup: "compass_core.graph.db" → path, "graph.db" → path, etc.
    path_set = set(file_paths)
    suffix_to_path: dict[str, str] = {}
    for fp in file_paths:
        p = Path(fp)
        # derive dotted name from path parts, try all trailing sub-sequences
        parts = list(p.with_suffix("").parts)
        for start in range(len(parts)):
            key = ".".join(parts[start:])
            suffix_to_path.setdefault(key, fp)
        # bare stem as well
        suffix_to_path.setdefault(p.stem, fp)

    results: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for src_path in file_paths:
        try:
            source = Path(src_path).read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=src_path)
        except (OSError, SyntaxError):
            continue

        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)

        for mod in imported:
            tgt_path = suffix_to_path.get(mod)
            if not tgt_path or tgt_path == src_path or tgt_path not in path_set:
                continue
            key = (src_path, tgt_path)
            if key not in seen:
                seen.add(key)
                results.append(key)

    return results


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


@router.get("/repo/graph", response_model=GraphResponse)
async def repo_graph() -> GraphResponse:
    try:
        with GraphDB() as db:
            nodes = _graph_nodes(db)
            edges = _graph_edges(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return GraphResponse(nodes=nodes, edges=edges)
