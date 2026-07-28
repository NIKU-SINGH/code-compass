# Project Page UI — Overview Tab + Graph Visualization

**Date:** 2026-04-10  
**Status:** Approved

---

## Summary

When a user runs `compass serve`, the browser opens to `/project/{projectId}` and lands on a new **Overview tab** — a wiki-style page showing repo stats, a generated summary, detected entry points, and an architecture sequence diagram. The existing **Graph tab** is replaced with a real interactive knowledge graph powered by **Sigma.js + Graphology**, with a thoughtful filter panel on the left.

---

## 1. Routing Change

`RightPanel` currently sets `defaultValue="graph"`. Change to `defaultValue="overview"` so `compass serve` lands on the Overview tab.

No routing infrastructure changes needed — the tab system is already in place.

---

## 2. Overview Tab

### 2.1 New component: `OverviewTab`

Replaces the placeholder in `RightPanel`. Fetches data from the API on mount.

**Sections (top to bottom):**

1. **Repo header** — repo name (from `projectId`), language tag, file path, "Indexed N ago"
2. **Stats strip** — 4 stat blocks in a bordered grid: Files / Functions / Classes / Edges
3. **Summary** — prose block. Static for now: `"Indexed {n} files across {n} modules across {n} packages."` LLM summary deferred to a later phase.
4. **Starting Points** — list of entry-point files (files with 0 incoming IMPORTS edges, max 5). Each row: `tag | monospace path | short description`
5. **Architecture diagram** — static SVG sequence diagram showing the call/data flow: CLI → compass-core → LadybugDB and React → FastAPI → LadybugDB. Shape is fixed; actors are always the same for a Compass-indexed repo.

### 2.2 New API endpoint: `GET /api/repo/overview`

Lives in `packages/core/src/compass_core/server/routers/repo.py`.

**Response shape:**
```json
{
  "project_id": "code-compass",
  "file_count": 42,
  "class_count": 23,
  "function_count": 187,
  "edge_count": 312,
  "entry_points": [
    { "path": "packages/cli/src/compass_cli/main.py", "tag": "entry", "description": "CLI commands" }
  ]
}
```

**Entry point detection:** Cypher query — files that appear in no IMPORTS edge as destination:
```cypher
MATCH (f:File)
WHERE NOT EXISTS { MATCH (:File)-[:IMPORTS]->(f) }
RETURN f.path, f.module_name
LIMIT 5
```

**Counts:** Simple `MATCH (n:File) RETURN count(n)` style queries for each node type.

### 2.3 Design tokens used

Follows existing design system exactly: `bg-background`, `text-foreground`, `text-muted-foreground`, `border-border`, `bg-muted`, `font-sans` (DM Sans), `font-mono` (SF Mono). No custom colours beyond what's in `globals.css`.

---

## 3. Graph Tab

### 3.1 Library

**sigma** + **graphology** + **@sigma/layout-forceatlas2**

Same stack as GitNexus. Sigma renders via WebGL — handles large graphs without performance issues. Graphology manages the graph data structure.

### 3.2 Layout

```
┌─────────────────────────────────────────────────┐
│  [Overview] [Graph*] [Query] [Analysis]  ← tabs  │
├──────────────┬──────────────────────────────────┤
│ Filter panel │  Sigma canvas (flex: 1)           │
│   210px      │                                   │
│              │   [search bar — top center]       │
│              │                                   │
│              │   [zoom/fit toolbar — bottom left]│
└──────────────┴──────────────────────────────────┘
```

No right-side detail panel — clicked node info shows as a floating tooltip/popover anchored to the node.

### 3.3 New API endpoint: `GET /api/repo/graph`

Returns the full node+edge list for Sigma to render.

**Response shape:**
```json
{
  "nodes": [
    { "id": "path/to/file.py", "label": "file.py", "type": "File", "file_path": "path/to/file.py" },
    { "id": "path::ClassName", "label": "ClassName", "type": "Class", "file_path": "path/to/file.py" }
  ],
  "edges": [
    { "id": "e1", "source": "path/to/a.py", "target": "path/to/b.py", "type": "IMPORTS" }
  ]
}
```

Default query returns: all File, Class, Function, Method nodes + CONTAINS, IMPORTS, INHERITS edges. CALLS and CALLS_EXTERN excluded by default (too dense). Field and ExternalFunction excluded by default.

**Cypher queries (one per node type, merged into response):**
```cypher
MATCH (f:File) RETURN f.path AS id, f.path AS file_path, 'File' AS type
MATCH (c:Class) RETURN c.id AS id, c.file_path AS file_path, 'Class' AS type
MATCH (fn:Function) RETURN fn.id AS id, fn.file_path AS file_path,
  CASE WHEN fn.is_method THEN 'Method' ELSE 'Function' END AS type
```

### 3.4 Filter panel

Single panel, no sub-tabs. Sections:

**Nodes** — toggle per type. Defaults:

| Type | Default | Color |
|---|---|---|
| File | ON | `oklch(0.588 0.217 264)` (primary) |
| Class | ON | `#f59e0b` |
| Function | ON | `#10b981` |
| Method | ON | `#06b6d4` |
| External Dep | OFF | `#94a3b8` |
| Field | OFF | `#a78bfa` |

**Relationships** — toggle per edge type. Defaults:

| Edge | Default | Color |
|---|---|---|
| Contains | ON | `#10b981` |
| Imports | ON | primary purple |
| Inherits | ON | `#f97316` |
| Calls | OFF | dashed white (too dense) |
| Ext. Calls | OFF | dashed slate |

**Focus Depth** — All / 1 / 2 / 3 hops. Only activates after node click; "All" is default.

**Layout** — Force (default) / Tree / Radial. Switches Sigma layout algorithm.

**Display** — "Node labels" toggle. ON by default; useful to turn off on large repos.

### 3.5 Node colours in Sigma

Set via `graphology` node attributes, rendered by Sigma's `NodeCircleProgram`. Size: File=12, Class=9, Function=6, Method=6.

### 3.6 Interactions

- **Click node** → show floating popover (name, type, path, edge counts). Activates focus depth filtering.
- **Click canvas background** → deselect, restore full graph.
- **Search bar** → filters visible nodes by label substring, highlights matches.
- **Drag** to pan, **scroll** to zoom.
- **Toolbar** buttons: zoom in, zoom out, fit-to-screen, reset layout.

---

## 4. File changes

| File | Change |
|---|---|
| `apps/web/src/components/project/RightPanel.tsx` | Add Overview tab, change `defaultValue` to `"overview"`, pass `projectId` to GraphTab |
| `apps/web/src/components/project/OverviewTab.tsx` | New component |
| `apps/web/src/components/project/GraphTab.tsx` | Rewrite with Sigma canvas + FilterPanel |
| `apps/web/src/components/project/FilterPanel.tsx` | New component |
| `packages/core/src/compass_core/server/routers/repo.py` | Add `/overview` and `/graph` endpoints |
| `apps/web/package.json` | Add `sigma`, `graphology`, `@sigma/layout-forceatlas2` |

---

## 5. Out of scope

- LLM-generated summary (deferred)
- CALLS / CALLS_EXTERN in default graph query (deferred — too dense without a good UX)
- Field nodes in graph (deferred)
- Graph persistence / layout save (deferred)
- Incremental graph updates (deferred)
