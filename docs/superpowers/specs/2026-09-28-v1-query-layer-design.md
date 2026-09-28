# v1 Query Layer — CLI, MCP and Visual UI over one engine

**Date:** 2026-09-28
**Status:** Draft — for review
**Depends on:** [NIKU-SINGH/code-compass#32](https://github.com/NIKU-SINGH/code-compass/pull/32) (removes the LLM layer, chat and placeholder UI)

---

## 1. Summary

Phase 1 turns a Python repository into a knowledge graph (`compass ingest`). v1 makes that
graph useful in two ways:

1. **For coding agents** (Claude Code, Cursor, …): a CLI (`compass callers …`, `compass impact …`)
   and an MCP server exposing the same operations as tools.
2. **For people**: a local web UI (`compass serve`) that visualizes the graph and the same
   answers (impact, paths, connections).

Compass never calls an LLM. The agent is the LLM; Compass is a deterministic tool it calls.

## 2. Decisions

| Topic | Decision |
|---|---|
| Consumers | Agents via CLI + MCP, people via the web UI. All three in v1. |
| LLM inside Compass | None. |
| Languages | Python only. The IR stays language-agnostic. |
| Storage | One graph per repo root in `<repo>/.compass/` (`graph.ladybug` + `metadata.json`). No SQLite, no global registry. |
| Project discovery | Walk up from the working directory to the nearest `.compass/`, as git does with `.git/`. `--repo PATH` overrides. |
| Freshness | Full re-ingest only. Every query reports if files changed since the last ingest. Incremental indexing is deferred. |
| Search | Name-based search (exact → qualified → prefix → substring) in Cypher. No text or semantic search in v1. |
| Out of scope | Incremental indexing, git ownership/blame, dead-code detection, text/semantic search, other languages. |

## 3. Architecture

```
compass_core/
  phases/ + graph/writer.py  ──writes──►  <repo>/.compass/graph.ladybug   (built to a temp file, then atomically swapped in)
                                          <repo>/.compass/metadata.json
  query/                     ◄──reads───  read-only, short-lived connections
     ▲             ▲                 ▲
  compass CLI   compass mcp       compass serve (FastAPI /api/* + static UI)
  (text/--json)  (MCP stdio tools)  (JSON for the web UI)
```

**Rule:** all graph logic lives in `compass_core/query/`. The CLI, MCP server and API routers
are thin adapters. They parse input, call one `query` function and render its result. They never
contain Cypher. This way the same question gets the same answer everywhere.

### 3.1 Why build into a temp file and swap (verified against LadybugDB 0.15.3)

- **Re-ingest duplicates data today.** Nodes are written with `MERGE` but edges with `CREATE`, and the DB is never cleared.
  Ingesting a two-function repo twice takes the edge count from 2 to 4. Deleted functions also
  stay in the graph forever.
- **Locks are exclusive between processes.** A process holding the DB read-write blocks read-only opens from other
  processes, and a read-only holder blocks a writer. Several read-only readers can coexist.
- **Opening a read-only connection and running a query takes about 50 ms.** So a connection per request is cheap.
- The DB is a single file.

**Therefore:**
- Ingest writes a fresh DB to `.compass/graph.ladybug.building` and then calls
  `os.replace()` to move it onto `graph.ladybug`. That makes every ingest a clean rebuild, and
  readers never block the writer.
- Readers (CLI, MCP, API) open `read_only=True` per operation and close right away. They
  never hold the DB between calls.
- `metadata.json` is written the same way (temp file + `os.replace`), after the graph swap.

### 3.2 Why no full-text search extension

LadybugDB's `fts` and `algo` extensions are downloaded from `extension.ladybugdb.com` at
runtime. A local CLI must work offline, so v1 does name search in plain Cypher (`=`,
`STARTS WITH`, `CONTAINS` on lowercased names). That is fast enough for repos of tens of
thousands of symbols. Traversals (callers, impact, path) are plain variable-length Cypher
matches, capped by depth.

## 4. What users and agents can ask

| # | Question | Operation | CLI | MCP tool |
|---|---|---|---|---|
| 1 | "Where is `write` implemented?" | `find_symbols` | `compass find write` | `find_symbol` |
| 2 | "What is `GraphDB.execute` and how is it connected?" | `describe` | `compass show GraphDB.execute` | `describe_symbol` |
| 3 | "Who calls X?" (n hops) | `callers` | `compass callers X --depth 2` | `get_callers` |
| 4 | "What does X call?" (n hops, incl. external libs) | `callees` | `compass callees X` | `get_callees` |
| 5 | "If I change this **function/class**, what's affected?" | `impact` | `compass impact X` | `get_impact` |
| 6 | "If I change this **file**, which files are affected?" | `impact` (file target) | `compass impact path/to/file.py` | `get_impact` |
| 7 | "How does A reach B?" | `call_path` | `compass path A B` | `find_call_path` |
| 8 | "What's in this file? What does it import / who imports it?" | `outline` | `compass outline file.py` | `get_file_outline` |
| 9 | "Class hierarchy of X?" | `hierarchy` | `compass hierarchy X` | `get_class_hierarchy` |
| 10 | "Who uses `jwt`?" | `external_usage` | `compass externals jwt` | `find_external_usage` |
| 11 | "What is this repo? Is the index fresh?" | `status` / `overview` | `compass status` | `get_index_status` |

### 4.1 Symbol references

Definition ids look like `py::compass_core.graph.db::GraphDB.execute`. Nobody types that, so every
operation takes a **symbol reference** resolved in this order:

1. Exact id (`py::pkg.mod::Name`)
2. File path (`src/pkg/mod.py`, repo-relative), for operations that accept a file
3. Fully qualified dotted name (`compass_core.graph.db.GraphDB.execute`)
4. `path.py::Name` or `path.py::Class.method`
5. `Class.method`
6. Bare name (`execute`)

If a reference matches exactly one symbol, it is used. If it matches several, the result is an
**ambiguity** listing the candidates, never a guess. The CLI exits with code 2 and the MCP tool
returns the candidates so the agent can retry with a more specific reference.

### 4.2 Impact semantics

- **Symbol target:** walk backwards over `CALLS` (callers of callers …) up to `depth`
  (default 3). For a class, also include subclasses (reverse `INHERITS`) and callers of its methods.
- **File target:** the union of:
  - files that import it (reverse `IMPORTS`);
  - files containing callers of any symbol defined in it;
  - files with subclasses of its classes,

  expanded the same way up to `depth`.
- Each affected item carries: hop `distance`, the `via` edge that pulled it in (e.g. `calls write`,
  `imports`, `inherits Phase`), and `min_confidence` along the path.
- Results are grouped by distance, then by file.
- The result always includes a caveat when calls in the affected area couldn't be resolved. The data for this is in
  `Function.raw_calls`, which holds calls that got no edge. So "no callers" is never shown as certain.

## 5. Output contract

Plain dataclasses in `compass_core/query/models.py`, following the Google-style docstring rules
in `CLAUDE.md`:

```python
@dataclass(frozen=True, slots=True)
class SymbolRef:          # a node in an answer
    id: str               # "py::compass_core.graph.writer::write"
    kind: str             # "file" | "class" | "function" | "method" | "external"
    name: str             # "write"
    qualified_name: str   # "compass_core.graph.writer.write"
    file_path: str | None # repo-relative, "packages/core/src/compass_core/graph/writer.py"
    line_start: int | None  # 1-indexed
    line_end: int | None    # 1-indexed
    signature: str | None

@dataclass(frozen=True, slots=True)
class EdgeRef:
    source_id: str
    target_id: str
    type: str             # CONTAINS | IMPORTS | INHERITS | CALLS | CALLS_EXTERN
    confidence: float | None
    call_type: str | None # DIRECT_IMPORT | MODULE_ATTR | RE_EXPORT | MRO | …
    line: int | None      # 1-indexed call site

@dataclass(frozen=True, slots=True)
class ResultItem:
    symbol: SymbolRef
    distance: int         # hops from the target (0 = the target itself)
    via: str | None       # human-readable reason, e.g. "calls write"
    min_confidence: float | None

@dataclass(slots=True)
class QueryResult:
    operation: str        # "impact"
    target: SymbolRef | None
    items: list[ResultItem]
    edges: list[EdgeRef]  # subgraph for the UI
    total: int            # before truncation
    truncated: bool
    caveats: list[str]    # "4 unresolved calls in 3 affected functions; there may be more callers"
    index: IndexStatus    # indexed_at, indexed_commit, stale_file_count
```

An ambiguous reference returns `AmbiguousReference(candidates: list[SymbolRef])`, and an unknown one returns
`SymbolNotFound(reference, suggestions)`. Both are values, not exceptions, so every adapter can
render them.

### 5.1 Rendering

**CLI text (default)** is compact and grep-friendly, with one line per item and paths formatted as `file:line`:

```
impact of compass_core.graph.writer.write  (function, packages/core/src/compass_core/graph/writer.py:74)
14 symbols in 6 files · depth 3 · index 12 min old

distance 1
  packages/core/src/compass_core/phases/persistence.py:22   PersistencePhase.run   calls write   1.00
distance 2
  packages/core/src/compass_core/phases/pipeline.py:38      Pipeline.run           calls run     1.00
…
! 2 unresolved calls in affected functions; there may be more callers
```

**`--json`** prints `QueryResult` serialized with `dataclasses.asdict`. MCP returns the same JSON.
The API returns the same shape through Pydantic response models generated from the dataclasses.

**Defaults:** `--limit 50` (report `total`), `--depth` 1 for callers/callees, 3 for impact, and 6 for
path. `--min-confidence 0` means everything is shown, with confidence labelled. `--source` includes
the source bodies; by default they are left out to save agent context.

**CLI exit codes:** `0` ok · `1` not found · `2` ambiguous · `3` no index found · `4` DB busy/locked.

## 6. Index metadata and freshness

`.compass/metadata.json` already exists (`indexed_commit`, `indexed_at`, `grammar_versions`). v1
extends it with:

```json
{
  "schema_version": 1,
  "compass_version": "0.1.0",
  "repo_root": "/abs/path/to/repo",
  "indexed_commit": "c51b442…",
  "indexed_at": 1759049940,
  "grammar_versions": {"python": "0.25.0"},
  "counts": {"files": 71, "classes": 58, "functions": 412, "edges": 1804},
  "report": {"resolved_ratio": {"python": 0.83}, "dangling_imports": 0, "degraded_files": 0}
}
```

**Staleness check** (runs on every query, and is cheap): `stat()` each indexed file and count those
whose mtime is later than `indexed_at` or which no longer exist. `compass status` additionally
rediscovers the repo to count new, unindexed files. A stale index never blocks a query; it only
adds a caveat and fills `index.stale_file_count`.

## 7. MCP server

- Built with the official `mcp` Python SDK (`FastMCP`), stdio transport, in `packages/mcp`.
- Launched as `compass mcp` (a CLI subcommand, so users configure one binary):

  ```json
  { "mcpServers": { "code-compass": { "command": "compass", "args": ["mcp"] } } }
  ```
- One tool per row in §4. Each tool description says **when** to use it (e.g. "Use before changing a
  function to see what else might break"). Tool inputs are symbol references (§4.1), never raw ids.
- Tools are read-only. v1 has no ingest tool; the agent runs `compass ingest` in its shell when the
  index is stale, and every result tells it so through `caveats`.
- Each result includes `ui_url` (for example `http://127.0.0.1:8000/?view=impact&focus=<id>`) so an agent can
  hand the user a visual. The URL only works while `compass serve` is running.

## 8. HTTP API (for the web UI)

All endpoints are thin wrappers over `query/`. Symbol references go in query parameters.

| Endpoint | Operation |
|---|---|
| `GET /api/status` | index metadata + staleness |
| `GET /api/overview` | counts, index health, entry points, most-imported files, most-called functions, top external libraries |
| `GET /api/search?q=&kind=&limit=` | `find_symbols` |
| `GET /api/symbol?ref=` | `describe` |
| `GET /api/callers?ref=&depth=&min_confidence=` / `GET /api/callees?…` | callers / callees |
| `GET /api/impact?ref=&depth=` | impact (symbol or file) |
| `GET /api/path?from=&to=&max_depth=` | call path |
| `GET /api/outline?path=` | file outline + imports / imported-by |
| `GET /api/hierarchy?ref=` | class hierarchy |
| `GET /api/source?path=&start=&end=` | source lines. Only files present in the index are served (no path traversal). |
| `GET /api/graph/map` | file-level map: File nodes + aggregated IMPORTS edges (replaces the whole-graph dump) |
| `GET /api/graph/neighborhood?ref=&depth=&edge_types=` | subgraph around a node, for expand-on-click |

`/api/repo/overview` and `/api/repo/graph` stay until the UI moves to the new endpoints, and are
then removed.

**Serving:** the Next.js app is built as a static export and bundled into
`compass_core/server/static/`. `compass serve` then runs only uvicorn (FastAPI serves `/api/*` plus the
static UI), so users need no Node. `compass serve --dev` keeps today's `pnpm dev` flow for UI work.

## 9. Web UI

Built from the Claude Design brief (Overview · Explore · Impact · Path, ⌘K search, deep links
via `?view=&focus=`, empty/stale/busy states). The existing 3D canvas (`GraphCanvas3D`,
`useExpandableGraph`) is kept and fed from `/api/graph/map` + `/api/graph/neighborhood` instead
of the whole-graph dump.

## 10. Open questions

1. **Default `--min-confidence`:** `0` (show everything, labelled) or `0.5`? The draft uses `0`.
2. **Class impact:** should overriding methods in subclasses count as affected by a change to the
   base method? The draft says yes, with `via: "overrides"`, if the MRO edges make it cheap.
3. **MCP tool count:** 11 tools, or merge `get_callers` / `get_callees` into
   `get_connections(direction=…)` to keep the agent's tool list short?
