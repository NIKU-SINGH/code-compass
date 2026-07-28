# Project Page — Overview Tab + Graph Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `compass serve` opens the browser, land on a wiki-style Overview tab showing repo stats, entry points, and an architecture diagram; replace the Graph tab placeholder with a real Sigma.js + Graphology interactive knowledge graph with a filter panel.

**Architecture:** Two new FastAPI endpoints (`/api/repo/overview`, `/api/repo/graph`) read from LadybugDB and return JSON. The React frontend has three new/rewritten components: `OverviewTab` (static+fetched content), `FilterPanel` (controlled toggle state), and `GraphTab` (Sigma.js canvas wired to filter state). The filter panel controls Sigma node/edge visibility via graphology `hidden` attributes.

**Tech Stack:** Python/FastAPI (backend), React 19 + Next.js 15, Sigma.js v3, Graphology, graphology-layout-forceatlas2, graphology-layout, Tailwind v4.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `apps/web/package.json` | Modify | Add sigma + graphology deps |
| `apps/web/src/lib/api.ts` | Create | API base URL constant + typed fetch helper |
| `packages/core/src/compass_core/server/routers/repo.py` | Modify | `/api/repo/overview` and `/api/repo/graph` endpoints |
| `packages/core/tests/test_server.py` | Modify | Tests for both new endpoints |
| `apps/web/src/components/project/RightPanel.tsx` | Modify | Add Overview tab, change defaultValue to "overview" |
| `apps/web/src/components/project/OverviewTab.tsx` | Create | Stats + summary + entry points + arch diagram |
| `apps/web/src/components/project/FilterPanel.tsx` | Create | Node/edge/depth/layout/display toggles |
| `apps/web/src/components/project/GraphTab.tsx` | Rewrite | Sigma canvas + filter panel integration |

---

## Task 1: Install Sigma + Graphology packages

**Files:**
- Modify: `apps/web/package.json`

- [ ] **Step 1: Install packages**

```bash
cd apps/web && pnpm add sigma graphology graphology-layout-forceatlas2 graphology-layout
```

Expected output: packages added, no peer dependency errors.

- [ ] **Step 2: Verify TypeScript can see types**

```bash
cd apps/web && pnpm exec tsc --noEmit 2>&1 | head -20
```

Expected: no errors about missing sigma/graphology types (they ship their own).

- [ ] **Step 3: Commit**

```bash
git add apps/web/package.json apps/web/pnpm-lock.yaml
git commit -m "chore: add sigma, graphology, and layout packages"
```

---

## Task 2: Frontend API helper

**Files:**
- Create: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Create the file**

```typescript
// apps/web/src/lib/api.ts

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/lib/api.ts
git commit -m "feat: add typed API fetch helper"
```

---

## Task 3: Backend — `/api/repo/overview` endpoint

**Files:**
- Modify: `packages/core/src/compass_core/server/routers/repo.py`
- Modify: `packages/core/tests/test_server.py`

- [ ] **Step 1: Write the failing test**

Add to `packages/core/tests/test_server.py`:

```python
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_repo_overview_returns_shape():
    """Overview endpoint returns the expected JSON shape."""
    mock_db = MagicMock()

    def fake_execute(query, params=None):
        result = MagicMock()
        if "count(n)" in query or "count(r)" in query:
            result.has_next.return_value = True
            result.get_next.return_value = (10,)
        else:
            # entry points query
            result.get_all.return_value = [
                ("/repo/main.py", "main"),
                ("/repo/server.py", "server"),
            ]
        return result

    mock_db.execute.side_effect = fake_execute
    mock_db.__enter__ = lambda s: mock_db
    mock_db.__exit__ = MagicMock(return_value=False)

    with patch("compass_core.server.routers.repo.GraphDB", return_value=mock_db):
        response = client.get("/api/repo/overview")

    assert response.status_code == 200
    data = response.json()
    assert "file_count" in data
    assert "class_count" in data
    assert "function_count" in data
    assert "edge_count" in data
    assert "entry_points" in data
    assert isinstance(data["entry_points"], list)


def test_repo_overview_503_when_db_unavailable():
    """Overview endpoint returns 503 if DB cannot be opened."""
    with patch(
        "compass_core.server.routers.repo.GraphDB",
        side_effect=Exception("DB not found"),
    ):
        response = client.get("/api/repo/overview")

    assert response.status_code == 503
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/core && uv run pytest tests/test_server.py::test_repo_overview_returns_shape -v
```

Expected: FAIL — `404 Not Found` (endpoint doesn't exist yet).

- [ ] **Step 3: Implement the endpoint**

Replace `packages/core/src/compass_core/server/routers/repo.py` entirely:

```python
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count(db: GraphDB, query: str) -> int:
    result = db.execute(query)
    return int(result.get_next()[0]) if result.has_next() else 0


def _edge_count(db: GraphDB) -> int:
    total = 0
    for rel in ("CONTAINS", "IMPORTS", "INHERITS", "CALLS", "CALLS_EXTERN", "HAS_FIELD"):
        total += _count(db, f"MATCH ()-[:{rel}]->() RETURN count(*)")
    return total


def _entry_points(db: GraphDB) -> list[EntryPoint]:
    result = db.execute(
        """
        MATCH (f:File)
        WHERE NOT EXISTS { MATCH (:File)-[:IMPORTS]->(f) }
        RETURN f.path, f.module_name
        LIMIT 5
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
            file_count = _count(db, "MATCH (n:File) RETURN count(n)")
            class_count = _count(db, "MATCH (n:Class) RETURN count(n)")
            function_count = _count(db, "MATCH (n:Function) RETURN count(n)")
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
```

- [ ] **Step 4: Run tests**

```bash
cd packages/core && uv run pytest tests/test_server.py -v
```

Expected: all pass including `test_repo_overview_returns_shape` and `test_repo_overview_503_when_db_unavailable`.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/compass_core/server/routers/repo.py packages/core/tests/test_server.py
git commit -m "feat: add /api/repo/overview endpoint with stats and entry points"
```

---

## Task 4: Backend — `/api/repo/graph` endpoint

**Files:**
- Modify: `packages/core/src/compass_core/server/routers/repo.py`
- Modify: `packages/core/tests/test_server.py`

- [ ] **Step 1: Write the failing test**

Add to `packages/core/tests/test_server.py`:

```python
def test_repo_graph_returns_nodes_and_edges():
    """Graph endpoint returns nodes list and edges list."""
    mock_db = MagicMock()

    def fake_execute(query, params=None):
        result = MagicMock()
        if ":File)" in query:
            result.get_all.return_value = [("/repo/a.py", "a.py", "File", "/repo/a.py")]
        elif ":Class)" in query:
            result.get_all.return_value = []
        elif ":Function)" in query:
            result.get_all.return_value = []
        elif "CONTAINS" in query or "IMPORTS" in query or "INHERITS" in query:
            result.get_all.return_value = []
        else:
            result.get_all.return_value = []
        return result

    mock_db.execute.side_effect = fake_execute
    mock_db.__enter__ = lambda s: mock_db
    mock_db.__exit__ = MagicMock(return_value=False)

    with patch("compass_core.server.routers.repo.GraphDB", return_value=mock_db):
        response = client.get("/api/repo/graph")

    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)
    # The one file node we mocked
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "/repo/a.py"
    assert data["nodes"][0]["type"] == "File"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/core && uv run pytest tests/test_server.py::test_repo_graph_returns_nodes_and_edges -v
```

Expected: FAIL — 404.

- [ ] **Step 3: Implement the endpoint**

Add to `packages/core/src/compass_core/server/routers/repo.py` — append after the OverviewResponse model and before the routes section:

```python
class GraphNode(BaseModel):
    id: str
    label: str
    type: str      # "File" | "Class" | "Function" | "Method"
    file_path: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str      # "CONTAINS" | "IMPORTS" | "INHERITS"


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
```

Then add these helpers and route after `repo_overview`:

```python
def _graph_nodes(db: GraphDB) -> list[GraphNode]:
    nodes: list[GraphNode] = []

    # File nodes — id = path
    for row in db.execute("MATCH (f:File) RETURN f.path, f.path, 'File', f.path").get_all():
        path = row[0]
        nodes.append(GraphNode(id=path, label=path.split("/")[-1], type="File", file_path=path))

    # Class nodes — id = class id string
    for row in db.execute(
        "MATCH (c:Class) RETURN c.id, c.name, 'Class', c.file_path"
    ).get_all():
        nodes.append(GraphNode(id=row[0], label=row[1], type="Class", file_path=row[3]))

    # Function and Method nodes — id = function id string
    for row in db.execute(
        "MATCH (fn:Function) RETURN fn.id, fn.name, fn.is_method, fn.file_path"
    ).get_all():
        node_type = "Method" if row[2] else "Function"
        nodes.append(GraphNode(id=row[0], label=row[1], type=node_type, file_path=row[3]))

    return nodes


def _graph_edges(db: GraphDB) -> list[GraphEdge]:
    edges: list[GraphEdge] = []
    counter = 0

    def _add(source: str, target: str, edge_type: str) -> None:
        nonlocal counter
        edges.append(GraphEdge(id=f"e{counter}", source=source, target=target, type=edge_type))
        counter += 1

    # CONTAINS: File→Class
    for row in db.execute(
        "MATCH (a:File)-[:CONTAINS]->(b:Class) RETURN a.path, b.id"
    ).get_all():
        _add(row[0], row[1], "CONTAINS")

    # CONTAINS: File→Function
    for row in db.execute(
        "MATCH (a:File)-[:CONTAINS]->(b:Function) RETURN a.path, b.id"
    ).get_all():
        _add(row[0], row[1], "CONTAINS")

    # CONTAINS: Class→Function
    for row in db.execute(
        "MATCH (a:Class)-[:CONTAINS]->(b:Function) RETURN a.id, b.id"
    ).get_all():
        _add(row[0], row[1], "CONTAINS")

    # IMPORTS: File→File
    for row in db.execute(
        "MATCH (a:File)-[:IMPORTS]->(b:File) RETURN a.path, b.path"
    ).get_all():
        _add(row[0], row[1], "IMPORTS")

    # INHERITS: Class→Class
    for row in db.execute(
        "MATCH (a:Class)-[:INHERITS]->(b:Class) RETURN a.id, b.id"
    ).get_all():
        _add(row[0], row[1], "INHERITS")

    return edges


@router.get("/repo/graph", response_model=GraphResponse)
async def repo_graph() -> GraphResponse:
    try:
        with GraphDB() as db:
            nodes = _graph_nodes(db)
            edges = _graph_edges(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return GraphResponse(nodes=nodes, edges=edges)
```

- [ ] **Step 4: Run all server tests**

```bash
cd packages/core && uv run pytest tests/test_server.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/compass_core/server/routers/repo.py packages/core/tests/test_server.py
git commit -m "feat: add /api/repo/graph endpoint returning nodes and edges"
```

---

## Task 5: RightPanel — add Overview tab, change default

**Files:**
- Modify: `apps/web/src/components/project/RightPanel.tsx`

- [ ] **Step 1: Update RightPanel**

Replace `apps/web/src/components/project/RightPanel.tsx` entirely:

```tsx
"use client";

import { Network, Terminal, BarChart2, LayoutDashboard } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { GraphTab } from "./GraphTab";
import { QueryTab } from "./QueryTab";
import { AnalysisTab } from "./AnalysisTab";
import { OverviewTab } from "./OverviewTab";

export function RightPanel({ projectId }: { projectId: string }) {
  return (
    <Tabs defaultValue="overview" className="flex-1 flex flex-col overflow-hidden">
      <TabsList>
        <TabsTrigger value="overview" className="flex items-center gap-1.5">
          <LayoutDashboard className="size-3.5" />
          Overview
        </TabsTrigger>
        <TabsTrigger value="graph" className="flex items-center gap-1.5">
          <Network className="size-3.5" />
          Graph
        </TabsTrigger>
        <TabsTrigger value="query" className="flex items-center gap-1.5">
          <Terminal className="size-3.5" />
          Query
        </TabsTrigger>
        <TabsTrigger value="analysis" className="flex items-center gap-1.5">
          <BarChart2 className="size-3.5" />
          Analysis
        </TabsTrigger>
      </TabsList>

      <TabsContent value="overview">
        <OverviewTab projectId={projectId} />
      </TabsContent>
      <TabsContent value="graph">
        <GraphTab projectId={projectId} />
      </TabsContent>
      <TabsContent value="query">
        <QueryTab />
      </TabsContent>
      <TabsContent value="analysis">
        <AnalysisTab />
      </TabsContent>
    </Tabs>
  );
}
```

- [ ] **Step 2: Create OverviewTab stub so it compiles**

Create `apps/web/src/components/project/OverviewTab.tsx`:

```tsx
"use client";

export function OverviewTab({ projectId: _projectId }: { projectId: string }) {
  return (
    <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
      Loading overview…
    </div>
  );
}
```

- [ ] **Step 3: Update GraphTab signature so it accepts projectId**

Edit `apps/web/src/components/project/GraphTab.tsx` — change the component signature only (keep placeholder body for now):

```tsx
import { Network } from "lucide-react";

export function GraphTab({ projectId: _projectId }: { projectId: string }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 text-muted-foreground">
      <div className="size-12 rounded-xl bg-muted flex items-center justify-center">
        <Network className="size-6" />
      </div>
      <div className="text-center">
        <p className="text-sm font-medium text-foreground">Graph View</p>
        <p className="text-xs mt-1">Code graph visualization will appear here</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd apps/web && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/project/RightPanel.tsx apps/web/src/components/project/OverviewTab.tsx apps/web/src/components/project/GraphTab.tsx
git commit -m "feat: add Overview tab to RightPanel, set as default"
```

---

## Task 6: OverviewTab — full content

**Files:**
- Modify: `apps/web/src/components/project/OverviewTab.tsx`

- [ ] **Step 1: Write the full OverviewTab**

Replace `apps/web/src/components/project/OverviewTab.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

interface EntryPoint {
  path: string;
  module_name: string;
}

interface OverviewData {
  project_id: string;
  file_count: number;
  class_count: number;
  function_count: number;
  edge_count: number;
  entry_points: EntryPoint[];
}

function tagForModule(moduleName: string): string {
  if (moduleName.includes("main")) return "entry";
  if (moduleName.includes("server") || moduleName.includes("api")) return "server";
  if (moduleName.includes("settings") || moduleName.includes("config")) return "config";
  return "core";
}

export function OverviewTab({ projectId }: { projectId: string }) {
  const [data, setData] = useState<OverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<OverviewData>("/api/repo/overview")
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [projectId]);

  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center px-6">
        <p className="text-sm font-medium text-foreground">No index found</p>
        <p className="text-xs text-muted-foreground">
          Run{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
            compass index ./repo
          </code>{" "}
          first to index this repository.
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Loading…
      </div>
    );
  }

  const totalModules = data.file_count;

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-8 py-7 max-w-3xl">

        {/* Repo header */}
        <div className="mb-5">
          <h1 className="text-xl font-bold tracking-tight">{data.project_id}</h1>
          <p className="text-xs text-muted-foreground mt-1">Python · {data.file_count} files</p>
        </div>

        <div className="h-px bg-border mb-6" />

        {/* Stats strip */}
        <div className="grid grid-cols-4 border border-border rounded-lg overflow-hidden mb-8">
          {[
            { label: "Files", value: data.file_count },
            { label: "Functions", value: data.function_count },
            { label: "Classes", value: data.class_count },
            { label: "Edges", value: data.edge_count },
          ].map((s, i) => (
            <div
              key={s.label}
              className={`px-4 py-3.5 ${i < 3 ? "border-r border-border" : ""}`}
            >
              <div className="text-lg font-bold">{s.value.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground mt-0.5">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Summary */}
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
            Summary
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">
            <span className="text-foreground font-medium">{data.project_id}</span> is a Python
            codebase with {data.file_count} files across {totalModules} modules,{" "}
            {data.class_count} classes, and {data.function_count} functions connected by{" "}
            {data.edge_count.toLocaleString()} edges in the knowledge graph.
          </p>
        </div>

        {/* Starting Points */}
        {data.entry_points.length > 0 && (
          <div className="mb-8">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Starting Points
            </p>
            <div className="border border-border rounded-lg overflow-hidden">
              {data.entry_points.map((ep) => {
                const tag = tagForModule(ep.module_name);
                return (
                  <div
                    key={ep.path}
                    className="flex items-baseline gap-3 px-4 py-2.5 border-b border-border last:border-b-0 bg-card"
                  >
                    <span className="text-[10px] font-medium text-muted-foreground bg-muted border border-border rounded px-1.5 py-px flex-shrink-0">
                      {tag}
                    </span>
                    <span className="font-mono text-xs text-foreground truncate">
                      {ep.path}
                    </span>
                    <span className="text-xs text-muted-foreground ml-auto flex-shrink-0">
                      {ep.module_name}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Architecture diagram */}
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-3">
            Architecture
          </p>
          <div className="border border-border rounded-lg bg-card p-5">
            <ArchDiagram />
          </div>
        </div>

      </div>
    </div>
  );
}

function ArchDiagram() {
  return (
    <svg
      viewBox="0 0 620 290"
      width="100%"
      xmlns="http://www.w3.org/2000/svg"
      style={{ fontFamily: "inherit" }}
    >
      <defs>
        <marker id="arr-fwd" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,1.5 L5,3 L0,4.5" fill="none" stroke="currentColor" strokeWidth="1.2" opacity="0.35" />
        </marker>
        <marker id="arr-bwd" markerWidth="6" markerHeight="6" refX="1" refY="3" orient="auto">
          <path d="M6,1.5 L1,3 L6,4.5" fill="none" stroke="currentColor" strokeWidth="1.2" opacity="0.35" />
        </marker>
      </defs>

      {/* Actor boxes */}
      {[
        { x: 10,  label: "compass-cli" },
        { x: 160, label: "compass-core" },
        { x: 310, label: "FastAPI" },
        { x: 460, label: "React frontend" },
      ].map(({ x, label }) => (
        <g key={label}>
          <rect x={x} y={10} width={110} height={34} rx="5"
            fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.10)" strokeWidth="1" />
          <text x={x + 55} y={31} textAnchor="middle" fontSize="11" fill="rgba(255,255,255,0.7)" fontWeight="500">
            {label}
          </text>
        </g>
      ))}

      {/* LadybugDB */}
      <rect x="235" y={255} width="110" height="34" rx="5"
        fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.10)" strokeWidth="1" />
      <text x="290" y={276} textAnchor="middle" fontSize="11" fill="rgba(255,255,255,0.7)" fontWeight="500">
        LadybugDB
      </text>

      {/* Lifelines */}
      {[65, 215, 365, 515].map((x) => (
        <line key={x} x1={x} y1={44} x2={x} y2={255}
          stroke="rgba(255,255,255,0.07)" strokeWidth="1" strokeDasharray="5,4" />
      ))}
      <line x1="290" y1={44} x2="290" y2={255}
        stroke="rgba(255,255,255,0.07)" strokeWidth="1" strokeDasharray="5,4" />
      {/* LadybugDB header lifeline */}
      <rect x="235" y={10} width="110" height="34" rx="5"
        fill="rgba(255,255,255,0.03)" stroke="rgba(255,255,255,0.10)" strokeWidth="1" />
      <text x="290" y={31} textAnchor="middle" fontSize="11" fill="rgba(255,255,255,0.7)" fontWeight="500">
        LadybugDB
      </text>

      {/* Step 1: CLI → core */}
      <circle cx="52" cy="80" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="52" y="84" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">1</text>
      <line x1="65" y1="80" x2="210" y2="80" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-fwd)" />
      <text x="137" y="74" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">compass index ./repo</text>

      {/* Step 2: core → DB */}
      <circle cx="202" cy="112" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="202" y="116" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">2</text>
      <line x1="215" y1="112" x2="278" y2="112" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-fwd)" />
      <text x="246" y="106" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">write graph</text>

      {/* Step 3: CLI → FastAPI */}
      <circle cx="52" cy="148" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="52" y="152" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">3</text>
      <line x1="65" y1="148" x2="360" y2="148" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-fwd)" />
      <text x="212" y="142" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">compass serve</text>

      {/* Step 4: React → FastAPI */}
      <circle cx="503" cy="180" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="503" y="184" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">4</text>
      <line x1="505" y1="180" x2="380" y2="180" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-bwd)" />
      <text x="442" y="174" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">GET /api/repo/graph</text>

      {/* Step 5: FastAPI → DB */}
      <circle cx="352" cy="214" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="352" y="218" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">5</text>
      <line x1="357" y1="214" x2="303" y2="214" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-bwd)" />
      <text x="330" y="208" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">Cypher</text>

      {/* Step 6: DB → FastAPI */}
      <circle cx="278" cy="236" r="8" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <text x="278" y="240" textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.4)">6</text>
      <line x1="283" y1="236" x2="357" y2="236" stroke="rgba(255,255,255,0.3)" strokeWidth="1" markerEnd="url(#arr-fwd)" />
      <text x="320" y="230" textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.4)">graph data</text>
    </svg>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd apps/web && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/project/OverviewTab.tsx apps/web/src/lib/api.ts
git commit -m "feat: implement OverviewTab with stats, summary, entry points, and arch diagram"
```

---

## Task 7: FilterPanel component

**Files:**
- Create: `apps/web/src/components/project/FilterPanel.tsx`

- [ ] **Step 1: Create FilterPanel**

Create `apps/web/src/components/project/FilterPanel.tsx`:

```tsx
"use client";

export type NodeType = "File" | "Class" | "Function" | "Method" | "ExternalDep" | "Field";
export type EdgeType = "CONTAINS" | "IMPORTS" | "INHERITS" | "CALLS" | "CALLS_EXTERN";
export type LayoutType = "force" | "tree" | "radial";

export interface FilterState {
  nodes: Record<NodeType, boolean>;
  edges: Record<EdgeType, boolean>;
  focusDepth: number | null;   // null = All
  layout: LayoutType;
  showLabels: boolean;
}

export const DEFAULT_FILTER_STATE: FilterState = {
  nodes: {
    File: true,
    Class: true,
    Function: true,
    Method: true,
    ExternalDep: false,
    Field: false,
  },
  edges: {
    CONTAINS: true,
    IMPORTS: true,
    INHERITS: true,
    CALLS: false,
    CALLS_EXTERN: false,
  },
  focusDepth: null,
  layout: "force",
  showLabels: true,
};

const NODE_CONFIG: Array<{ type: NodeType; label: string; color: string }> = [
  { type: "File",        label: "File",         color: "oklch(0.588 0.217 264)" },
  { type: "Class",       label: "Class",        color: "#f59e0b" },
  { type: "Function",    label: "Function",     color: "#10b981" },
  { type: "Method",      label: "Method",       color: "#06b6d4" },
  { type: "ExternalDep", label: "External Dep", color: "#94a3b8" },
  { type: "Field",       label: "Field",        color: "#a78bfa" },
];

const EDGE_CONFIG: Array<{ type: EdgeType; label: string; color: string; dashed?: boolean }> = [
  { type: "CONTAINS",    label: "Contains",  color: "#10b981" },
  { type: "IMPORTS",     label: "Imports",   color: "oklch(0.588 0.217 264)" },
  { type: "INHERITS",    label: "Inherits",  color: "#f97316" },
  { type: "CALLS",       label: "Calls",     color: "rgba(255,255,255,0.25)", dashed: true },
  { type: "CALLS_EXTERN",label: "Ext. Calls",color: "#94a3b8",               dashed: true },
];

interface Props {
  state: FilterState;
  onChange: (state: FilterState) => void;
}

export function FilterPanel({ state, onChange }: Props) {
  function toggleNode(type: NodeType) {
    onChange({ ...state, nodes: { ...state.nodes, [type]: !state.nodes[type] } });
  }

  function toggleEdge(type: EdgeType) {
    onChange({ ...state, edges: { ...state.edges, [type]: !state.edges[type] } });
  }

  function setDepth(depth: number | null) {
    onChange({ ...state, focusDepth: depth });
  }

  function setLayout(layout: LayoutType) {
    onChange({ ...state, layout });
  }

  function toggleLabels() {
    onChange({ ...state, showLabels: !state.showLabels });
  }

  return (
    <div className="w-[210px] border-r border-border bg-card flex flex-col flex-shrink-0 overflow-y-auto text-sm">

      {/* Header */}
      <div className="px-4 py-3 border-b border-border">
        <p className="text-xs font-semibold text-foreground">Graph Filters</p>
        <p className="text-xs text-muted-foreground mt-0.5">Customise what&apos;s visible</p>
      </div>

      {/* Nodes */}
      <Section title="Nodes">
        {NODE_CONFIG.map(({ type, label, color }) => (
          <ToggleRow
            key={type}
            label={label}
            on={state.nodes[type]}
            onToggle={() => toggleNode(type)}
            indicator={<span className="size-2 rounded-full flex-shrink-0" style={{ background: color }} />}
          />
        ))}
      </Section>

      {/* Relationships */}
      <Section title="Relationships">
        {EDGE_CONFIG.map(({ type, label, color, dashed }) => (
          <ToggleRow
            key={type}
            label={label}
            on={state.edges[type]}
            onToggle={() => toggleEdge(type)}
            indicator={
              <span
                className="w-5 flex-shrink-0"
                style={{
                  height: dashed ? 0 : 2,
                  borderTop: dashed ? `2px dashed ${color}` : "none",
                  background: dashed ? "none" : color,
                  borderRadius: 2,
                  marginTop: dashed ? 1 : 0,
                }}
              />
            }
          />
        ))}
      </Section>

      {/* Focus Depth */}
      <Section title="Focus Depth" sub="Hops from selected node">
        <div className="flex flex-wrap gap-1.5">
          {([null, 1, 2, 3] as Array<number | null>).map((d) => (
            <button
              key={String(d)}
              onClick={() => setDepth(d)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
                state.focusDepth === d
                  ? "bg-primary border-primary text-primary-foreground"
                  : "bg-muted border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {d === null ? "All" : `${d}`}
            </button>
          ))}
        </div>
      </Section>

      {/* Layout */}
      <Section title="Layout">
        <div className="flex gap-1">
          {(["force", "tree", "radial"] as LayoutType[]).map((l) => (
            <button
              key={l}
              onClick={() => setLayout(l)}
              className={`flex-1 py-1.5 rounded-md text-xs font-medium border capitalize transition-colors ${
                state.layout === l
                  ? "border-primary text-foreground bg-muted"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {l}
            </button>
          ))}
        </div>
      </Section>

      {/* Display */}
      <Section title="Display">
        <div className="flex items-center justify-between">
          <span className={`text-xs ${state.showLabels ? "text-foreground" : "text-muted-foreground"}`}>
            Node labels
          </span>
          <Toggle on={state.showLabels} onToggle={toggleLabels} />
        </div>
      </Section>

    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function Section({
  title,
  sub,
  children,
}: {
  title: string;
  sub?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="px-4 py-3.5 border-b border-border flex flex-col gap-2">
      <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
        {title}
      </p>
      {sub && <p className="text-[10px] text-muted-foreground/60 -mt-1">{sub}</p>}
      {children}
    </div>
  );
}

function ToggleRow({
  label,
  on,
  onToggle,
  indicator,
}: {
  label: string;
  on: boolean;
  onToggle: () => void;
  indicator: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 py-[3px]">
      {indicator}
      <span className={`flex-1 text-xs ${on ? "text-foreground" : "text-muted-foreground/50"}`}>
        {label}
      </span>
      <Toggle on={on} onToggle={onToggle} />
    </div>
  );
}

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      className={`w-7 h-3.5 rounded-full relative transition-colors flex-shrink-0 ${
        on ? "bg-primary" : "bg-muted-foreground/20"
      }`}
    >
      <span
        className={`absolute top-[2px] size-[10px] rounded-full bg-white transition-[left] ${
          on ? "left-[14px]" : "left-[2px]"
        }`}
      />
    </button>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd apps/web && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/project/FilterPanel.tsx
git commit -m "feat: add FilterPanel component with node/edge/layout/depth toggles"
```

---

## Task 8: GraphTab — Sigma canvas + data loading

**Files:**
- Modify: `apps/web/src/components/project/GraphTab.tsx`

- [ ] **Step 1: Rewrite GraphTab with Sigma**

Replace `apps/web/src/components/project/GraphTab.tsx` entirely:

```tsx
"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import Graph from "graphology";
import Sigma from "sigma";
import forceAtlas2 from "graphology-layout-forceatlas2";
import { circular } from "graphology-layout";
import { apiFetch } from "@/lib/api";
import {
  FilterPanel,
  FilterState,
  DEFAULT_FILTER_STATE,
  NodeType,
  EdgeType,
} from "./FilterPanel";

// ── Colour + size maps ───────────────────────────────────────────────────────

const NODE_COLOR: Record<NodeType, string> = {
  File:        "oklch(0.588 0.217 264)",
  Class:       "#f59e0b",
  Function:    "#10b981",
  Method:      "#06b6d4",
  ExternalDep: "#94a3b8",
  Field:       "#a78bfa",
};

const NODE_SIZE: Record<NodeType, number> = {
  File:        12,
  Class:       9,
  Function:    6,
  Method:      6,
  ExternalDep: 5,
  Field:       5,
};

const EDGE_COLOR: Record<EdgeType, string> = {
  CONTAINS:    "#10b981",
  IMPORTS:     "oklch(0.588 0.217 264)",
  INHERITS:    "#f97316",
  CALLS:       "rgba(255,255,255,0.15)",
  CALLS_EXTERN:"#94a3b8",
};

// ── Types matching API ────────────────────────────────────────────────────────

interface ApiNode { id: string; label: string; type: string; file_path: string; }
interface ApiEdge { id: string; source: string; target: string; type: string; }
interface GraphData { nodes: ApiNode[]; edges: ApiEdge[]; }

// ── Component ────────────────────────────────────────────────────────────────

export function GraphTab({ projectId }: { projectId: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef     = useRef<Sigma | null>(null);
  const graphRef     = useRef<Graph | null>(null);
  const [filter, setFilter]   = useState<FilterState>(DEFAULT_FILTER_STATE);
  const [search, setSearch]   = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  // ── Load graph data once ────────────────────────────────────────────────

  useEffect(() => {
    if (!containerRef.current) return;

    let sigma: Sigma | null = null;

    apiFetch<GraphData>("/api/repo/graph")
      .then((data) => {
        const graph = new Graph({ multi: false, type: "directed" });

        data.nodes.forEach((n) => {
          const nodeType = n.type as NodeType;
          graph.addNode(n.id, {
            label:     n.label,
            nodeType,
            filePath:  n.file_path,
            color:     NODE_COLOR[nodeType] ?? "#6b7280",
            size:      NODE_SIZE[nodeType]  ?? 6,
            x:         Math.random(),
            y:         Math.random(),
          });
        });

        data.edges.forEach((e) => {
          try {
            graph.addEdgeWithKey(e.id, e.source, e.target, {
              edgeType: e.type as EdgeType,
              color:    EDGE_COLOR[e.type as EdgeType] ?? "rgba(255,255,255,0.15)",
              size:     1,
            });
          } catch {
            // skip duplicate or missing-node edges
          }
        });

        // Run ForceAtlas2 layout
        circular.assign(graph);
        forceAtlas2.assign(graph, { iterations: 100, settings: { gravity: 1 } });

        graphRef.current = graph;

        sigma = new Sigma(graph, containerRef.current!, {
          renderEdgeLabels: false,
          defaultEdgeColor: "rgba(255,255,255,0.15)",
          defaultNodeColor: "#6b7280",
        });

        sigmaRef.current = sigma;
        setLoading(false);
      })
      .catch((e: Error) => {
        setError(e.message);
        setLoading(false);
      });

    return () => {
      sigma?.kill();
    };
  }, [projectId]);

  // ── Apply filter state to graph ─────────────────────────────────────────

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    graph.forEachNode((node, attrs) => {
      const type = attrs.nodeType as NodeType;
      const hidden = !filter.nodes[type];
      graph.setNodeAttribute(node, "hidden", hidden);
    });

    graph.forEachEdge((edge, attrs) => {
      const type = attrs.edgeType as EdgeType;
      const srcHidden = graph.getNodeAttribute(graph.source(edge), "hidden");
      const tgtHidden = graph.getNodeAttribute(graph.target(edge), "hidden");
      const hidden = !filter.edges[type] || srcHidden || tgtHidden;
      graph.setEdgeAttribute(edge, "hidden", hidden);
    });

    sigmaRef.current?.refresh();
  }, [filter]);

  // ── Apply label visibility ───────────────────────────────────────────────

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.forEachNode((node, attrs) => {
      graph.setNodeAttribute(node, "label", filter.showLabels ? attrs.label : "");
    });
    sigmaRef.current?.refresh();
  }, [filter.showLabels]);

  // ── Search filter ────────────────────────────────────────────────────────

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || search === "") {
      graph?.forEachNode((node, attrs) => {
        const type = attrs.nodeType as NodeType;
        graph.setNodeAttribute(node, "hidden", !filter.nodes[type]);
      });
      sigmaRef.current?.refresh();
      return;
    }

    const term = search.toLowerCase();
    graph.forEachNode((node, attrs) => {
      const matches = (attrs.label as string).toLowerCase().includes(term);
      graph.setNodeAttribute(node, "hidden", !matches);
    });
    sigmaRef.current?.refresh();
  }, [search, filter.nodes]);

  // ── Layout switching ─────────────────────────────────────────────────────

  const applyLayout = useCallback((layout: FilterState["layout"]) => {
    const graph = graphRef.current;
    if (!graph) return;
    if (layout === "force") {
      forceAtlas2.assign(graph, { iterations: 100, settings: { gravity: 1 } });
    } else {
      circular.assign(graph);
    }
    sigmaRef.current?.refresh();
  }, []);

  useEffect(() => {
    applyLayout(filter.layout);
  }, [filter.layout, applyLayout]);

  // ── Toolbar handlers ─────────────────────────────────────────────────────

  function zoomIn()  { sigmaRef.current?.getCamera().animatedZoom({ duration: 200 }); }
  function zoomOut() { sigmaRef.current?.getCamera().animatedUnzoom({ duration: 200 }); }
  function fitGraph() {
    sigmaRef.current?.getCamera().animatedReset({ duration: 300 });
  }
  function resetLayout() { applyLayout(filter.layout); }

  return (
    <div className="flex-1 flex overflow-hidden">
      <FilterPanel state={filter} onChange={setFilter} />

      <div className="flex-1 relative overflow-hidden">
        {/* Search */}
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search nodes…"
            className="bg-card border border-border rounded-lg px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground outline-none focus:border-ring w-56"
          />
        </div>

        {/* Sigma container */}
        <div ref={containerRef} className="w-full h-full" />

        {/* Loading / error overlay */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
            Loading graph…
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center px-6">
            <p className="text-sm font-medium text-foreground">No graph data</p>
            <p className="text-xs text-muted-foreground">
              Run{" "}
              <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
                compass index ./repo
              </code>{" "}
              first.
            </p>
          </div>
        )}

        {/* Toolbar */}
        <div className="absolute bottom-4 left-4 flex gap-1.5 z-10">
          {[
            { label: "+", action: zoomIn,      title: "Zoom in" },
            { label: "−", action: zoomOut,     title: "Zoom out" },
            { label: "⊡", action: fitGraph,    title: "Fit to screen" },
            { label: "↺", action: resetLayout, title: "Reset layout" },
          ].map(({ label, action, title }) => (
            <button
              key={label}
              onClick={action}
              title={title}
              className="size-8 bg-card border border-border rounded-lg text-muted-foreground hover:text-foreground text-sm font-semibold transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd apps/web && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/project/GraphTab.tsx
git commit -m "feat: implement GraphTab with Sigma.js, filter panel, search, and toolbar"
```

---

## Task 9: GraphTab — node click popover

**Files:**
- Modify: `apps/web/src/components/project/GraphTab.tsx`

- [ ] **Step 1: Add popover state and click handler to GraphTab**

Inside the `GraphTab` component, add after the `sigmaRef` and `graphRef` declarations:

```tsx
const [popover, setPopover] = useState<{
  nodeId: string;
  label: string;
  nodeType: string;
  filePath: string;
  x: number;
  y: number;
} | null>(null);
```

In the `useEffect` that initialises Sigma (after `sigmaRef.current = sigma`), add:

```tsx
sigma.on("clickNode", ({ node, event }) => {
  const attrs = graph.getNodeAttributes(node);
  const rect = containerRef.current!.getBoundingClientRect();
  const vp = sigma.graphToViewport({ x: attrs.x as number, y: attrs.y as number });
  setPopover({
    nodeId:   node,
    label:    attrs.label as string,
    nodeType: attrs.nodeType as string,
    filePath: attrs.filePath as string,
    x: rect.left + vp.x,
    y: rect.top  + vp.y,
  });
});

sigma.on("clickStage", () => setPopover(null));
```

- [ ] **Step 2: Render the popover**

In the JSX, just before the closing `</div>` of the flex container, add:

```tsx
{popover && (
  <div
    className="fixed z-20 bg-card border border-border rounded-lg shadow-lg p-3 text-xs pointer-events-none"
    style={{ left: popover.x + 12, top: popover.y - 8 }}
  >
    <p className="font-semibold text-foreground mb-1">{popover.label}</p>
    <p className="text-muted-foreground">{popover.nodeType}</p>
    <p className="font-mono text-[10px] text-muted-foreground mt-1 max-w-[200px] truncate">
      {popover.filePath}
    </p>
  </div>
)}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd apps/web && pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components/project/GraphTab.tsx
git commit -m "feat: add node click popover to GraphTab"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `compass serve` lands on Overview tab | Task 5 (defaultValue="overview") |
| Stats strip (Files/Functions/Classes/Edges) | Task 6 |
| Summary prose | Task 6 |
| Starting points — entry files with tags | Task 6 |
| Architecture SVG sequence diagram | Task 6 |
| `/api/repo/overview` endpoint | Task 3 |
| `/api/repo/graph` endpoint | Task 4 |
| Sigma + Graphology graph rendering | Task 8 |
| Node colours per type | Task 8 |
| FilterPanel — node toggles | Task 7 |
| FilterPanel — edge toggles | Task 7 |
| FilterPanel — focus depth | Task 7 |
| FilterPanel — layout switcher | Task 7, 8 |
| FilterPanel — labels toggle | Task 7, 8 |
| Click node → popover | Task 9 |
| Search bar | Task 8 |
| Zoom/fit/reset toolbar | Task 8 |
| Error state (DB not indexed) | Tasks 6, 8 |

All requirements covered. No gaps found.

**Type consistency check:**
- `NodeType` defined in `FilterPanel.tsx`, imported in `GraphTab.tsx` ✓
- `EdgeType` defined in `FilterPanel.tsx`, imported in `GraphTab.tsx` ✓
- `FilterState` and `DEFAULT_FILTER_STATE` defined once, imported where needed ✓
- `ApiNode`, `ApiEdge`, `GraphData` defined locally in `GraphTab.tsx` ✓
- `apiFetch` defined in `lib/api.ts`, imported in both `OverviewTab.tsx` and `GraphTab.tsx` ✓
- `OverviewData`, `EntryPoint` defined locally in `OverviewTab.tsx` ✓

**Placeholder scan:** No TBD/TODO/placeholder language found in implementation steps. All code blocks are complete.
