# Web UI v5 — Overview · Graph · Impact

Date: 2026-10-10
Status: Draft for review
Source design: Claude Design project "Code Compass v5" (`Code Compass v5.dc.html`)
Parent spec: `2026-09-28-v1-query-layer-design.md` (§4.2 Impact semantics, §5 contract, §8 HTTP API, §9 Web UI)
Parent plan: `plans/2026-09-28-v1-query-layer.md`

## 1. Goal

Make the web UI look like the v5 design: a warm dark/light theme, a left navigation rail, and
three views — **Overview**, **Graph**, **Impact**. The Impact view is backed by a real
`GET /api/impact` endpoint.

## 2. Decisions

| Topic | Decision |
|---|---|
| Visual scope | Full: theme, fonts, left rail and redesigned Overview cards |
| Impact data | Real endpoint; contract and semantics exactly as parent spec §4.2, §5 and §8 |
| Sequencing | Thin vertical slice of the parent plan: only the tasks these 3 views need (§4) |
| Graph canvas | Keep the existing 3D canvas (`GraphCanvas3D`); restyle only |
| Existing endpoints | `/api/repo/overview` and `/api/repo/graph` stay until the UI no longer uses them |
| Theme mode | Dark and light palettes; mode follows the OS `prefers-color-scheme`. No toggle in this slice |

## 3. Out of scope

⌘K search, the Path view, the CLI, the MCP server, static bundling, the 2D orbit canvas, Impact
"Split" and "Graph" display modes, and call-resolution improvements. These Overview cards are
dropped:

- **Longest call chains** — needs `call_path` (parent Task 11).
- **Change hotspots** — needs git history ingestion.
- **Possibly dead code** — dead-code detection is out of scope in the parent spec (§2).

Known gaps that stay as they are in this slice (both handled by parent Tasks 15, 16 and 18):

- `/api/repo/graph` returns no `CALLS` edges, so the Graph legend keeps showing Calls: 0.
- `DetailsPanel` calls `/api/repo/file`, which does not exist, so the source preview stays broken.

## 4. Backend slice (`packages/core`)

The slice is a subset of the parent plan. Each item is implemented as that task describes,
limited to what is listed here.

| Parent task | Included in this slice |
|---|---|
| 1 — Clean rebuild on ingest | All. Required: the current index holds every edge ~11× (2,774 IMPORTS rows for 252 distinct pairs; 668 CALLS rows for 55), which would inflate Impact counts |
| 2 — Locate the index | `IndexLocation`, `find_index`, `require_index` (every result header carries an `IndexStatus`) |
| 3 — Metadata + freshness | `IndexMetadata`, `load_metadata`/`save_metadata`, and the stale-file count used by `IndexStatus`; not the `IngestReport` summary |
| 4 — Read-only DB access | All (`read_only`, timeout, `ErrorCode`, `QueryError` hierarchy) |
| 5 — Types, models, params, results, errors | Only what `impact`, `find_symbols` and `overview` need: `SymbolRef`, `EdgeRef`, `Via`, `ResultItem`, `Caveat`, `SearchParams`, `ImpactParams`, `SearchResult`, `SearchHit`, `ImpactResult`, `ImpactGroup`, `OverviewResult`, `RankedSymbol`, `LibraryUsage`, `AmbiguousReference`, `SymbolNotFound`, `Lookup`, `ErrorResponse`, `ERROR_MAPPINGS`, `serialize.to_json` |
| 6 — Test fixture | All |
| 7 — Row mapping and symbol references | All (`rows.py`, `resolve`) |
| 8 — `find_symbols` | All (backs the Impact target picker) |
| 10 — `impact` | All |
| 12 — `overview` | `overview()` only, plus the `riskiest_to_change` field below |
| 15 — Query endpoints | `GET /api/search`, `GET /api/impact`, `GET /api/overview` and the shared exception handlers |
| 17 — Static bundling | Only the generated TypeScript types (`openapi-typescript`, `pnpm gen:api`, `lib/api-types.ts`) |

Contract change to parent spec §5.5: `OverviewResult` gains
`riskiest_to_change: tuple[RankedSymbol, ...]` — the functions and methods with the most
transitive dependents at the default impact depth (3), top 5. `RankedSymbol.count` is the number
of affected symbols. The parent spec is updated in the same change.

Impact semantics are the parent spec's §4.2, unchanged: symbol targets walk reverse `CALLS`
(classes also pull in subclasses and callers of their methods); file targets are the union of
reverse `IMPORTS`, files containing callers, and files with subclasses. Every result carries a
`Caveat(code=UNRESOLVED_CALLS)` when calls in the affected area were not resolved. All source
locations are 1-indexed line numbers.

Tests live under `packages/core/tests/` per the parent tasks.

## 5. Frontend (`apps/web`)

### 5.1 Theme
Port the v5 tokens into `styles/globals.css` and map them onto the existing shadcn CSS
variables, so current components restyle without rewrites. Fonts: Geist and JetBrains Mono.
Accent: amber. Add only the new tokens the design needs (entity kind colors, edge colors).

### 5.2 Shell
Replace the shadcn `Tabs` in `WorkspaceTabs.tsx` with a left rail (`shell/NavRail.tsx`) of three
lucide-icon items: Overview (`layout-dashboard`), Graph (`orbit`), Impact (`target`). View and
focus live in the URL: `?view=overview|graph|impact&focus=<id>`. `view=explore` is accepted as an
alias for `graph`, so links built from the parent spec's `ui_url` keep working.

### 5.3 Overview
Stat counts, entity and edge breakdowns, and three grouped card pairs with metric bars, all from
`/api/overview`:

| Card | `OverviewResult` field |
|---|---|
| Riskiest to change | `riskiest_to_change` |
| Most-imported files | `most_imported_files` |
| Most-called functions | `most_called_functions` |
| External libraries | `top_external_libraries` |

Each card has an empty state. Clicking a row opens it in Impact (riskiest) or Graph (the others).

### 5.4 Graph
Keep `GraphCanvas3D`, `useExpandableGraph` and `useGraphData`. Restyle `GraphLegend` and
`DetailsPanel` to the new tokens. Accept `focus` from the URL to select a node.

### 5.5 Impact
- Target picker backed by `/api/search` (functions, classes and files).
- Target header card: name, kind badge, location, affected symbol and file counts.
- Unresolved-calls banner when the result has an `UNRESOLVED_CALLS` caveat.
- Results grouped by distance; each row shows name, location, "via" and confidence.
  Clicking a row re-targets Impact on that symbol.
- Depth control (1 to the parent spec's `MAX_DEPTH`); "Show in graph" switches to Graph with the
  target focused.
- `lib/api.ts` returns only the generated types from `lib/api-types.ts`; no hand-written
  response interfaces.
- States: loading, empty (no affected symbols), ambiguous reference (pick a candidate), not found
  (show suggestions), and backend errors rendered from `ErrorResponse.code`.

### 5.6 Conventions
shadcn/ui components, `lucide-react` icons, `cursor-pointer` on clickable elements, theme tokens
only (no ad-hoc hex), stateless presentational components, no file over 500 lines, files named
for what is specific to them (e.g. `impact/ImpactGroupList.tsx`, `shell/NavRail.tsx`).

## 6. Risk — sparse call resolution

The current index of this repo resolves 55 distinct internal call pairs across 868 functions.
Symbol-level Impact results and the Most-called card will therefore be thin on real repos, and
many results will carry the unresolved-calls caveat. File-level Impact (IMPORTS, 252 distinct
pairs) is unaffected. Improving resolution is a separate change; the UI must make the caveat
visible rather than imply "nothing else is affected".

## 7. Open questions

1. Overriding methods: the parent spec (§10.2) says they count as affected, with
   `via: OVERRIDES`, if MRO edges make it cheap. This slice follows the parent.
2. Default `min_confidence`: `0`, as in the parent spec (§10.1).
