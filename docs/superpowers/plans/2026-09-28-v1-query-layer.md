# v1 Query Layer — Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Each task ends green:
> `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `cd packages/core && uv run mypy`,
> and for web tasks `pnpm exec tsc --noEmit` + `pnpm build` in `apps/web`.

**Goal:** Expose the Phase 1 knowledge graph to coding agents (CLI + MCP) and to people (web UI)
through one read-only query engine. Design and contracts:
[`specs/2026-09-28-v1-query-layer-design.md`](../specs/2026-09-28-v1-query-layer-design.md).

**Prerequisite:** [NIKU-SINGH/code-compass#32](https://github.com/NIKU-SINGH/code-compass/pull/32) merged.

**Out of scope:** incremental indexing, git ownership, dead-code detection, text/semantic search,
non-Python languages.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `packages/core/src/compass_core/phases/pipeline.py` | Modify | Build into temp DB, atomic swap, richer metadata |
| `packages/core/src/compass_core/index/locate.py` | Create | Find `.compass/` by walking up; resolve DB + metadata paths |
| `packages/core/src/compass_core/index/metadata.py` | Create | `IndexMetadata` dataclass, atomic read/write |
| `packages/core/src/compass_core/index/freshness.py` | Create | Stale-file detection |
| `packages/core/src/compass_core/graph/db.py` | Modify | `read_only` flag, query timeout, busy-lock error |
| `packages/core/src/compass_core/query/models.py` | Create | Result dataclasses (spec §5) |
| `packages/core/src/compass_core/query/references.py` | Create | Symbol-reference resolution (spec §4.1) |
| `packages/core/src/compass_core/query/search.py` | Create | `find_symbols` |
| `packages/core/src/compass_core/query/connections.py` | Create | `describe`, `callers`, `callees` |
| `packages/core/src/compass_core/query/impact.py` | Create | Symbol + file impact |
| `packages/core/src/compass_core/query/paths.py` | Create | `call_path` |
| `packages/core/src/compass_core/query/structure.py` | Create | `outline`, `hierarchy`, `external_usage` |
| `packages/core/src/compass_core/query/overview.py` | Create | `status`, `overview`, `graph_map`, `neighborhood` |
| `packages/core/tests/fixtures/sample_repo/` | Create | Small, known Python repo for golden tests |
| `packages/core/tests/query/` | Create | Tests per query module |
| `packages/cli/src/compass_cli/commands/query.py` | Create | `find/show/callers/callees/impact/path/outline/hierarchy/externals/status` |
| `packages/cli/src/compass_cli/render.py` | Create | Text + JSON renderers for `QueryResult` |
| `packages/cli/src/compass_cli/commands/mcp.py` | Create | `compass mcp` launcher |
| `packages/mcp/src/compass_mcp/server.py` | Rewrite | FastMCP tools over `query/` |
| `packages/core/src/compass_core/server/routers/query.py` | Create | Spec §8 endpoints |
| `packages/core/src/compass_core/server/routers/graph.py` | Create | `/api/graph/map`, `/api/graph/neighborhood` |
| `packages/core/src/compass_core/server/routers/repo.py` | Delete (last) | Superseded once the UI migrates |
| `packages/core/src/compass_core/server/main.py` | Modify | Mount routers + static UI |
| `apps/web/next.config.ts`, `Makefile`, `packages/cli/.../serve.py` | Modify | Static export, bundling, `--dev` |

---

## Milestone 0 — Foundations

### Task 1: Clean rebuild on every ingest (fixes duplicate edges)

Re-ingesting today doubles every edge (verified: 2 → 4 on a two-function repo), and deleted code
is never removed.

- [ ] Write a failing test in `tests/phases/test_pipeline.py`: ingest the fixture twice → node and edge counts are identical.
- [ ] Write a failing test: delete a function from the fixture and re-ingest → the function is gone from the graph.
- [ ] In `Pipeline.run`, write to `db_path.with_suffix(".ladybug.building")`, removing any leftover first.
- [ ] After a successful write, `os.replace(building, db_path)`. On failure, delete the temp file and leave the old DB untouched.
- [ ] Write a test: a read-only connection held open by another process during ingest does not make ingest fail.

### Task 2: Locate the index

- [ ] `index/locate.py`: `find_index(start: Path) -> IndexLocation | None` walks up to the first dir containing `.compass/graph.ladybug`.
- [ ] `IndexLocation` dataclass: `repo_root`, `db_path`, `metadata_path`.
- [ ] Settings: `LADYBUG_DB_PATH` stays as an explicit override. The default comes from `find_index(Path.cwd())`.
- [ ] Tests: found in cwd, found in parent, not found, and an explicit override takes precedence.

### Task 3: Metadata v1 + freshness

- [ ] `index/metadata.py`: `IndexMetadata` dataclass matching spec §6, with `load(path)` and `save(path)` (temp file + `os.replace`).
- [ ] Move `_save_metadata` from `pipeline.py` to use it. Add counts and the `IngestReport` summary.
- [ ] `index/freshness.py`: `stale_files(meta, indexed_paths) -> list[str]` (mtime > `indexed_at` or missing).
- [ ] Tests: fresh index → 0; touch a file → 1; delete a file → 1; a pre-v1 `metadata.json` loads with defaults.

### Task 4: Read-only DB access

- [ ] `GraphDB(db_path, read_only=True)` passes through to `lb.Database(..., read_only=True)`.
- [ ] Wrap `conn.set_query_timeout(ms)` (default 10 s, `QUERY_TIMEOUT_MS` setting).
- [ ] Translate "Could not set lock on file" into `IndexBusyError` (new, in `compass_core/errors.py`).
- [ ] Tests: read-only rejects writes; lock error maps to `IndexBusyError`.

---

## Milestone 1 — `query/` engine

All functions take a `GraphDB` (read-only) plus arguments and return spec §5 values. No Cypher
anywhere else.

### Task 5: Models

- [ ] `query/models.py`: `SymbolRef`, `EdgeRef`, `ResultItem`, `IndexStatus`, `QueryResult`, `AmbiguousReference`, `SymbolNotFound`.
- [ ] Google-style docstrings with `Attributes:` and a code → model example (per `CLAUDE.md`).
- [ ] `to_dict()` helper for JSON (stable key order).

### Task 6: Test fixture

- [ ] `tests/fixtures/sample_repo/`, about 8 files, designed to hit each case:
  - a direct call, a module-attribute call, a re-export via `__init__`, an inheritance chain (3 levels) with an overridden method;
  - a call that can't be resolved (`getattr(obj, name)()`), an external call (`json.dumps`);
  - two functions with the same bare name in different modules (ambiguity);
  - a file imported by 3 others (file impact).
- [ ] Session-scoped pytest fixture that ingests it once into a tmp dir and yields a read-only `GraphDB`.

### Task 7: Symbol references

- [ ] `resolve(db, ref, *, allow_file=False) -> SymbolRef | AmbiguousReference | SymbolNotFound`, using the order in spec §4.1.
- [ ] `SymbolNotFound.suggestions`: up to 5 case-insensitive substring matches.
- [ ] Tests: one per resolution rule, ambiguity on the duplicate bare name, not-found with suggestions.

### Task 8: `find_symbols`

- [ ] Ranking: exact name > qualified-name suffix > prefix > substring; ties broken by fan-in (incoming `CALLS`).
- [ ] Optional `kind` filter and `limit`.
- [ ] Tests: ranking order, kind filter, limit + `total`.

### Task 9: `describe`, `callers`, `callees`

- [ ] `describe`: the symbol + parent class/file + members (for classes) + 1-hop callers, callees and external callees, all as `edges`.
- [ ] `callers` / `callees`: variable-length `CALLS` up to `depth`, `min_confidence` filter, shortest distance per symbol, `via` naming the edge.
- [ ] `callees` includes `CALLS_EXTERN` targets as `kind="external"`.
- [ ] Caveat: count `raw_calls` that produced no edge in the traversed functions.
- [ ] Tests against the fixture, including depth 2 and the confidence filter.

### Task 10: `impact`

- [ ] Symbol target per spec §4.2 (reverse `CALLS`, plus subclasses and callers of methods for classes).
- [ ] File target per spec §4.2 (reverse `IMPORTS` ∪ files of callers ∪ files of subclasses), expanded to `depth`.
- [ ] Group items by distance, then file. Set `min_confidence` along the path.
- [ ] Tests: file imported by 3 → 3 files at distance 1; transitive depth 2; unresolved-call caveat present.

### Task 11: `call_path`

- [ ] Shortest `CALLS` path from A to B with `max_depth` (default 6), returning ordered items + edges.
- [ ] Tests: path exists; no path; exceeds depth → `truncated=True` with a caveat.

### Task 12: `outline`, `hierarchy`, `external_usage`, `status`, `overview`

- [ ] `outline(path)`: classes → methods, top-level functions, imports, imported-by.
- [ ] `hierarchy(class)`: ancestors and descendants via `INHERITS`.
- [ ] `external_usage(library_or_ref)`: `CALLS_EXTERN` grouped by caller file.
- [ ] `status()`: metadata + freshness. `overview()`: counts, index health, entry points, most-imported files, most-called functions, top external libraries.
- [ ] `graph_map()` (files + IMPORTS) and `neighborhood(ref, depth, edge_types)` for the UI.
- [ ] Tests for each.

---

## Milestone 2 — CLI

### Task 13: Commands and rendering

- [ ] `render.py`: `render_text(result)` and `render_json(result)` (spec §5.1), plus renderers for ambiguity / not-found.
- [ ] `commands/query.py`: `find`, `show`, `callers`, `callees`, `impact`, `path`, `outline`, `hierarchy`, `externals`, `status`.
- [ ] Shared options: `--json`, `--limit`, `--depth`, `--min-confidence`, `--source`, `--repo`.
- [ ] Exit codes `0/1/2/3/4` (spec §5.1). Errors go to stderr, results to stdout.
- [ ] Register in `main.py`, and update `display.help_commands()`.
- [ ] Tests with Typer's `CliRunner` against the fixture index: text snapshot per command, JSON parses, and exit codes.

---

## Milestone 3 — MCP

### Task 14: MCP server

- [ ] `compass_mcp/server.py`: `FastMCP("code-compass")` with the tools in spec §4. Each calls one `query` function and returns `to_dict()`.
- [ ] Tool descriptions say when to use each tool and name the reference formats accepted.
- [ ] Every result includes `ui_url` (built from `API_HOST`/`API_PORT`).
- [ ] `compass mcp` subcommand (lazy import of `compass_mcp`) runs stdio.
- [ ] Tests: in-process MCP client lists tools and calls `get_impact` on the fixture; ambiguity returns candidates, not an error.
- [ ] README: config snippets for Claude Code and Cursor, and a short "when to use Compass" block for an agent's `CLAUDE.md` / `AGENTS.md`.

---

## Milestone 4 — HTTP API

### Task 15: Query endpoints

- [ ] `routers/query.py` with the spec §8 endpoints. Pydantic response models mirror the dataclasses.
- [ ] Ambiguity → HTTP 409 with candidates, not found → 404 with suggestions, no index → 503, busy → 503 + `Retry-After`.
- [ ] `/api/source`: serve only paths present as `File` nodes, clamp line ranges (closes the missing `/api/repo/file` that `DetailsPanel.tsx` calls).
- [ ] Tests with `TestClient` against the fixture index, including a path-traversal attempt on `/api/source`.

### Task 16: Graph endpoints for the canvas

- [ ] `routers/graph.py`: `/api/graph/map`, `/api/graph/neighborhood`.
- [ ] Tests: the map contains only File nodes; neighborhood respects depth and edge types.

---

## Milestone 5 — Web UI (after the Claude Design pass)

### Task 17: Static bundling

- [ ] `next.config.ts`: `output: "export"`. Replace the `rewrites()` with a `NEXT_PUBLIC_API_BASE` used in `lib/api.ts` for dev.
- [ ] `Makefile build`: copy `apps/web/out/` (not `dist/`) into `compass_core/server/static/`. Include it in the core wheel via hatch `artifacts`.
- [ ] `server/main.py`: mount `StaticFiles(html=True)` at `/` after the API routers.
- [ ] `compass serve`: uvicorn only by default; `--dev` keeps the `pnpm dev` flow. Open the browser at the API URL.

### Task 18: Views

Implement the designed Overview, Explore, Impact and Path views, the ⌘K search and deep links
(`?view=&focus=`). Also implement the no-index, stale, busy, loading and empty states. Split each
view into feature components (≤ 500 lines each, shadcn/ui, lucide icons, `cursor-pointer` on
clickables, per `CLAUDE.md`).

- [ ] Move `useGraphData` to `/api/graph/map` + `/api/graph/neighborhood`.
- [ ] Move `DetailsPanel` to `/api/symbol` + `/api/source`.
- [ ] Delete `routers/repo.py` and its tests once nothing calls `/api/repo/*`.

---

## Milestone 6 — Evaluation and docs

### Task 19: Golden questions

- [ ] `tests/query/test_golden.py`: about 30 questions against the fixture (the spec §4 table × edge cases), each asserting the exact set of returned ids.
- [ ] Runs in CI, so a resolver change that degrades answers fails the build.

### Task 20: Docs

- [ ] README: install, `compass ingest`, the query commands with sample output, MCP setup, `compass serve`.
- [ ] Remove the stale `packages/core/uv.lock` (the workspace uses the root lockfile).

---

## Suggested PR slicing

| PR | Tasks | Delivers |
|---|---|---|
| 1 | 1–4 | Correct re-ingest, index discovery, metadata, read-only access |
| 2 | 5–12 | `query/` engine + fixture + tests |
| 3 | 13 | CLI commands (first usable release for agents) |
| 4 | 14 | MCP server |
| 5 | 15–16 | HTTP API |
| 6 | 17–18 | Designed UI + static bundling |
| 7 | 19–20 | Golden evaluation + docs |
