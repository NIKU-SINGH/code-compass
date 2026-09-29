# v1 Query Layer — Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Each task ends green:
> `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `cd packages/core && uv run mypy`,
> and for web tasks `pnpm exec tsc --noEmit` + `pnpm build` in `apps/web`. From Task 0 on, mypy runs
> strict on `core`, `cli` and `mcp`.
>
> **Typing is part of "done"** (spec §5.1). A task isn't complete if it adds `Any`, a bare `dict`/`list`,
> `dict[str, Any]`, an untyped parameter or return, a free-form status/kind string, or a `# type: ignore`
> without a linked reason. Every public function and model has a Google-style docstring (`Args:`,
> `Returns:`, `Raises:`, `Attributes:`, `Example:`) per `CLAUDE.md`.

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
| `pyproject.toml`, `packages/{cli,mcp}/pyproject.toml` | Modify | mypy strict for cli + mcp; ruff `ANN`, `TC` |
| `packages/core/src/compass_core/errors.py` | Modify | `QueryError` hierarchy with `ErrorCode` (spec §5.6) |
| `packages/core/src/compass_core/ir/models.py`, `ir/graph.py` | Modify | `ResolutionType` enum replaces `call_type: str` |
| `packages/core/src/compass_core/query/types.py` | Create | `StrEnum`s + `NewType` ids (spec §5.2) |
| `packages/core/src/compass_core/query/models.py` | Create | Building-block dataclasses (spec §5.3) |
| `packages/core/src/compass_core/query/params.py` | Create | Per-operation parameter objects + bounds (spec §5.4) |
| `packages/core/src/compass_core/query/results.py` | Create | Per-operation result dataclasses + `Lookup` (spec §5.5) |
| `packages/core/src/compass_core/query/rows.py` | Create | The only DB-row → model conversion; raises `IndexIncompatibleError` |
| `packages/core/src/compass_core/query/errors.py` | Create | `ErrorResponse` + `to_error_response` + code → exit/HTTP table |
| `packages/core/src/compass_core/query/serialize.py` | Create | Cached `TypeAdapter`s, `to_json` |
| `packages/core/src/compass_core/query/references.py` | Create | Symbol-reference resolution (spec §4.1) |
| `packages/core/src/compass_core/query/search.py` | Create | `find_symbols` |
| `packages/core/src/compass_core/query/connections.py` | Create | `describe`, `callers`, `callees` |
| `packages/core/src/compass_core/query/impact.py` | Create | Symbol + file impact |
| `packages/core/src/compass_core/query/paths.py` | Create | `call_path` |
| `packages/core/src/compass_core/query/structure.py` | Create | `outline`, `hierarchy`, `external_usage` |
| `packages/core/src/compass_core/query/overview.py` | Create | `status`, `overview`, `graph_map`, `neighborhood`, `read_source` |
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
| `apps/web/lib/api-types.ts` | Create (generated) | TS types from `/openapi.json` via `openapi-typescript` |

---

## Milestone 0 — Foundations

### Task 0: Type-checking gates

- [ ] Root `pyproject.toml`: add `ANN` and `TC` to ruff `select`. Add `[tool.mypy] strict = true` to `packages/cli` and `packages/mcp` (plus the `pydantic.mypy` plugin).
- [ ] Fix whatever the new gates flag in existing cli/mcp code, and extend CI to run mypy in all three packages.
- [ ] `ir/models.py`: `ResolutionType(StrEnum)` (`DIRECT_IMPORT`, `MODULE_ATTR`, `RE_EXPORT`, `MRO`, `WILDCARD`, `DYNAMIC`, `EXTERNAL`, `CIRCULAR`, `UNRESOLVED`). `CallResult.call_type` and `CallEdge.call_type` become `ResolutionType`, and `CONFIDENCE` becomes `Mapping[ResolutionType, float]`. The graph still stores `.value`, so the schema is unchanged.
- [ ] Tests: the existing resolution tests pass unchanged apart from the enum comparisons.

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
- [ ] `IndexLocation` frozen dataclass: `repo_root: Path`, `db_path: Path`, `metadata_path: Path`.
- [ ] `require_index(start: Path, override: Path | None) -> IndexLocation`, which raises `IndexNotFoundError(searched_from=start)`. Adapters call this instead of checking for `None` themselves.
- [ ] Settings: `LADYBUG_DB_PATH` stays as an explicit override. The default comes from `find_index(Path.cwd())`.
- [ ] Tests: found in cwd, found in parent, not found, and an explicit override takes precedence.

### Task 3: Metadata v1 + freshness

- [ ] `index/metadata.py`: `IndexMetadata`, `IndexCounts`, `IngestReportSummary` frozen dataclasses (spec §6), `load_metadata(path: Path) -> IndexMetadata` (parsed through a `TypeAdapter`) and `save_metadata(path: Path, meta: IndexMetadata) -> None` (temp file + `os.replace`).
- [ ] Move `_save_metadata` from `pipeline.py` to use it. Add counts and the `IngestReport` summary.
- [ ] `index/freshness.py`: `stale_files(meta: IndexMetadata, indexed: Iterable[RepoPath]) -> tuple[RepoPath, ...]` (mtime > `indexed_at` or missing).
- [ ] Tests: fresh index → 0; touch a file → 1; delete a file → 1; a pre-v1 `metadata.json` loads with defaults; malformed JSON, a future `schema_version` and an unknown language each raise `IndexIncompatibleError` (not `KeyError`/`JSONDecodeError`).

### Task 4: Read-only DB access

- [ ] `GraphDB(db_path, read_only=True)` passes through to `lb.Database(..., read_only=True)`.
- [ ] Wrap `conn.set_query_timeout(ms)` (default 10 s, `QUERY_TIMEOUT_MS` setting).
- [ ] `errors.py`: `ErrorCode` (`StrEnum`, defined here and re-exported from `query/types.py`) and the `QueryError` hierarchy from spec §5.6. Each subclass has a `ClassVar[ErrorCode]` and typed keyword context (`retry_after_s: int`, `timeout_ms: int`, …).
- [ ] `graph/db.py` is the only place that matches LadybugDB error text: "Could not set lock on file" becomes `IndexBusyError`, and a timeout becomes `QueryTimeoutError`, both with `raise … from exc`.
- [ ] Tests: read-only rejects writes; lock error maps to `IndexBusyError` with `retry_after_s`; timeout maps to `QueryTimeoutError`; the original exception is kept as `__cause__`.

---

## Milestone 1 — `query/` engine

All functions take a `GraphDB` (read-only) plus a typed `…Params` object and return the spec §5.5
result type or `Lookup[…]`, with the exact signatures listed there. No Cypher anywhere else, and no row
indexing outside `query/rows.py`.

### Task 5: Types, models, params, results, errors

- [ ] `query/types.py`: every `StrEnum` and `NewType` in spec §5.2.
- [ ] `query/models.py`: `SymbolRef`, `EdgeRef`, `Via`, `ResultItem`, `Caveat`, `IndexStatus`, all `frozen=True, slots=True, kw_only=True` with `tuple` fields. `__post_init__` checks the invariants from spec §5.1 rule 5.
- [ ] `query/params.py`: the bound constants and the `…Params` classes from spec §5.4. `__post_init__` raises `InvalidArgumentError(argument=…, reason=…)`.
- [ ] `query/results.py`: `ResultHeader`, the thirteen result classes (each with `operation: Literal[Operation.X]`), their nested types (`SearchHit`, `ImpactGroup`, `ClassOutline`, `ExternalUsageGroup`, `ExternalCall`, `RankedSymbol`, `LibraryUsage`), `AmbiguousReference`, `SymbolNotFound`, `ResolvedReference`, `Lookup`, and the `QueryResult` alias.
- [ ] `query/errors.py`: `ErrorResponse`, `to_error_response(...)`, and one `ERROR_MAPPINGS: Mapping[ErrorCode, ErrorMapping]` (`exit_code: int`, `http_status: int`, `mcp_is_error: bool`) that every adapter reads.
- [ ] `query/serialize.py`: cached `TypeAdapter`s, `to_json(...) -> str`. Replaces the old `to_dict()` idea, so JSON has no hand-written dict code.
- [ ] Google-style docstrings with `Attributes:` and a code → model `Example:` (per `CLAUDE.md`). Keep each file under 500 lines.
- [ ] Tests: each invariant rejects a bad value (confidence 1.5, line 0, `via` set at distance 0, `confidence` on an `IMPORTS` edge); each params bound raises `InvalidArgumentError` naming the argument; `to_json` round-trips each result through its `TypeAdapter`; `ERROR_MAPPINGS` covers every `ErrorCode` (checked by iterating the enum).

### Task 6: Test fixture

- [ ] `tests/fixtures/sample_repo/`, about 8 files, designed to hit each case:
  - a direct call, a module-attribute call, a re-export via `__init__`, an inheritance chain (3 levels) with an overridden method;
  - a call that can't be resolved (`getattr(obj, name)()`), an external call (`json.dumps`);
  - two functions with the same bare name in different modules (ambiguity);
  - a file imported by 3 others (file impact).
- [ ] Session-scoped pytest fixture that ingests it once into a tmp dir and yields a read-only `GraphDB`.

### Task 7: Row mapping and symbol references

- [ ] `query/rows.py`: `symbol_from_row(row: Sequence[Any], kind: SymbolKind) -> SymbolRef`, `edge_from_row(...) -> EdgeRef`, and so on. Each value is checked with `isinstance` or enum construction; a mismatch raises `IndexIncompatibleError`. A stored line `0` becomes `None`. File ids are `file::<path>` and external ids are `ext::<full_ref>`.
- [ ] `resolve(db: GraphDB, ref: str, *, allow_file: bool = False) -> Lookup[ResolvedReference]`, using the order in spec §4.1 and recording the `MatchRule`.
- [ ] `SymbolNotFound.suggestions`: up to 5 case-insensitive substring matches, as `SymbolRef`s.
- [ ] Tests: one per resolution rule (asserting `rule`), ambiguity on the duplicate bare name, not-found with suggestions; `rows.py` raises `IndexIncompatibleError` on a wrong-typed column and on an unknown `call_type`.

### Task 8: `find_symbols`

- [ ] Ranking: exact name > qualified-name suffix > prefix > substring; ties broken by fan-in (incoming `CALLS`).
- [ ] `find_symbols(db: GraphDB, params: SearchParams) -> SearchResult`. Each hit records its `SearchMatch`.
- [ ] Tests: ranking order, kind filter, limit + `total`.

### Task 9: `describe`, `callers`, `callees`

- [ ] `describe`: the symbol + parent class/file + members (for classes) + 1-hop callers, callees and external callees, all as `edges`.
- [ ] `callers` / `callees` → `Lookup[TraversalResult]`: variable-length `CALLS` up to `depth`, `min_confidence` filter, shortest distance per symbol, `via` as `Via(kind=ViaKind.CALLS | CALLED_BY, symbol=…)`.
- [ ] `callees` includes `CALLS_EXTERN` targets as `SymbolKind.EXTERNAL`.
- [ ] `Caveat(code=CaveatCode.UNRESOLVED_CALLS, count=n)`: count `raw_calls` that produced no edge in the traversed functions.
- [ ] Tests against the fixture, including depth 2 and the confidence filter.

### Task 10: `impact`

- [ ] Symbol target per spec §4.2 (reverse `CALLS`, plus subclasses and callers of methods for classes).
- [ ] File target per spec §4.2 (reverse `IMPORTS` ∪ files of callers ∪ files of subclasses), expanded to `depth`.
- [ ] `impact(...) -> Lookup[ImpactResult]`: group into `ImpactGroup`s by distance, then file. Set `min_confidence` along the path. `via` uses `ViaKind.CALLS / IMPORTS / INHERITS / OVERRIDES`.
- [ ] Tests: file imported by 3 → 3 files at distance 1; transitive depth 2; unresolved-call caveat present.

### Task 11: `call_path`

- [ ] Shortest `CALLS` path from A to B with `max_depth` (default 6), returning ordered items + edges.
- [ ] Tests: path exists; no path → `found=False`, empty `hops`; exceeds depth → `Caveat(code=DEPTH_LIMIT_REACHED)`; ambiguous source vs. ambiguous target both come back as `AmbiguousReference` with the right `reference`.

### Task 12: `outline`, `hierarchy`, `external_usage`, `status`, `overview`

- [ ] `outline(path)`: classes → methods, top-level functions, imports, imported-by.
- [ ] `hierarchy(class)`: ancestors and descendants via `INHERITS`.
- [ ] `external_usage(library_or_ref)`: `CALLS_EXTERN` grouped by caller file.
- [ ] `status()`: metadata + freshness. `overview()`: counts, index health, entry points, most-imported files, most-called functions, top external libraries.
- [ ] `graph_map()` (files + IMPORTS), `neighborhood(db, ref, NeighborhoodParams)` and `read_source(db, location, SourceParams) -> Lookup[SourceResult]` for the UI.
- [ ] Each function returns its spec §5.5 result type. Tests for each, including one `mypy`-checked `match … case _: assert_never(...)` test module that proves the `Lookup` unions are exhaustive.

---

## Milestone 2 — CLI

### Task 13: Commands and rendering

- [ ] `render.py`: `render_text(result: QueryResult) -> str` (exhaustive `match` + `assert_never`, builds text from `Via`/`Caveat`), `render_json(...)` via `serialize.to_json`, and `render_error(err: ErrorResponse, *, as_json: bool) -> str`.
- [ ] `commands/query.py`: `find`, `show`, `callers`, `callees`, `impact`, `path`, `outline`, `hierarchy`, `externals`, `status`.
- [ ] Shared options: `--json`, `--limit`, `--depth`, `--min-confidence`, `--source`, `--repo`, all annotated (`Annotated[int, typer.Option(min=1, max=MAX_DEPTH)]`), with `--kind` as `SymbolKind` so Typer lists the choices. Options turn into `…Params` objects.
- [ ] One `run_query` wrapper maps outcomes and `QueryError`s through `ERROR_MAPPINGS` to exit codes `0–8` (spec §5.6). The `ErrorResponse` goes to stderr and results go to stdout. Unexpected exceptions exit `1` with a one-line message (full traceback only with `--debug`).
- [ ] Register in `main.py`, and update `display.help_commands()`.
- [ ] Tests with Typer's `CliRunner` against the fixture index: text snapshot per command; `--json` output validates against the result's `TypeAdapter`; one exit-code test per `ErrorCode` (including no index → 5 and a bad `--depth` → 2).

---

## Milestone 3 — MCP

### Task 14: MCP server

- [ ] `compass_mcp/server.py`: `FastMCP("code-compass")` with the tools in spec §4. Each tool has annotated, bounded parameters (enums for `kind` / `edge_types`) and a return annotation of `ToolResult[<Result> | AmbiguousReference | SymbolNotFound]`, so FastMCP publishes `inputSchema` + `outputSchema` and returns `structuredContent`. No tool returns a `dict` or a preformatted string.
- [ ] `QueryError`s become tool errors whose text is the `ErrorResponse` JSON (spec §5.6).
- [ ] Tool descriptions say when to use each tool and name the reference formats accepted.
- [ ] `ToolResult.ui_url` is built from `API_HOST`/`API_PORT`.
- [ ] `compass mcp` subcommand (lazy import of `compass_mcp`) runs stdio.
- [ ] Tests: in-process MCP client lists tools, and every tool has an `outputSchema` and enum-constrained inputs; `get_impact` on the fixture returns `structuredContent` that validates against `ImpactResult`; ambiguity returns candidates (not `isError`); no index returns `isError` with code `INDEX_NOT_FOUND`.
- [ ] README: config snippets for Claude Code and Cursor, and a short "when to use Compass" block for an agent's `CLAUDE.md` / `AGENTS.md`.

---

## Milestone 4 — HTTP API

### Task 15: Query endpoints

- [ ] `routers/query.py` with the spec §8 endpoints. Parameters use `Annotated[..., Query(ge=, le=)]` with the `query/params.py` bounds. `response_model` is the result dataclass itself (no mirror Pydantic models), and `responses=` declares `ErrorResponse` for each error status.
- [ ] Exception handlers registered once in `server/main.py`, driven by `ERROR_MAPPINGS`: ambiguity → 409 with candidates, not found → 404 with suggestions, invalid → 422, no index / incompatible → 503, busy → 503 + `Retry-After`, timeout → 504. Routes have no `try`/`except`. FastAPI's own 422 validation body is also reshaped into `ErrorResponse`.
- [ ] `/api/source`: serve only paths present as `File` nodes, clamp line ranges (closes the missing `/api/repo/file` that `DetailsPanel.tsx` calls).
- [ ] Tests with `TestClient` against the fixture index: each endpoint's body validates against its result `TypeAdapter`; each error status returns a valid `ErrorResponse`; a path-traversal attempt on `/api/source` → 404 `NOT_FOUND`; `/openapi.json` names a response schema for every route.

### Task 16: Graph endpoints for the canvas

- [ ] `routers/graph.py`: `/api/graph/map`, `/api/graph/neighborhood`.
- [ ] Tests: the map contains only File nodes; neighborhood respects depth and edge types.

---

## Milestone 5 — Web UI (after the Claude Design pass)

### Task 17: Static bundling

- [ ] `apps/web`: add `openapi-typescript` and a `pnpm gen:api` script that writes `lib/api-types.ts` from the API's `/openapi.json` (dumped by a `make openapi` target, no running server needed). CI regenerates it and fails on a diff. `lib/api.ts` returns only these generated types; no hand-written response interfaces, and no `any`.
- [ ] `next.config.ts`: `output: "export"`. Replace the `rewrites()` with a `NEXT_PUBLIC_API_BASE` used in `lib/api.ts` for dev.
- [ ] `Makefile build`: copy `apps/web/out/` (not `dist/`) into `compass_core/server/static/`. Include it in the core wheel via hatch `artifacts`.
- [ ] `server/main.py`: mount `StaticFiles(html=True)` at `/` after the API routers.
- [ ] `compass serve`: uvicorn only by default; `--dev` keeps the `pnpm dev` flow. Open the browser at the API URL.

### Task 18: Views

Implement the designed Overview, Explore, Impact and Path views, the ⌘K search and deep links
(`?view=&focus=`). Also implement the no-index, stale, busy, loading and empty states. Split each
view into feature components (≤ 500 lines each, shadcn/ui, lucide icons, `cursor-pointer` on
clickables, per `CLAUDE.md`).

- [ ] Views narrow API responses on `outcome` / `operation` (exhaustive `switch` with a `never` check), and render `ErrorResponse` codes as the no-index / stale / busy states.
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
| 1 | 0–4 | Type gates, correct re-ingest, index discovery, typed metadata + errors, read-only access |
| 2 | 5–12 | `query/` engine + fixture + tests |
| 3 | 13 | CLI commands (first usable release for agents) |
| 4 | 14 | MCP server |
| 5 | 15–16 | HTTP API |
| 6 | 17–18 | Designed UI + static bundling |
| 7 | 19–20 | Golden evaluation + docs |
