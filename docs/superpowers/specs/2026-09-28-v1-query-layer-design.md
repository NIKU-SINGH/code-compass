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
| Typing | Every input, result and error is a named, immutable, mypy-strict type (§5). No `dict`/`Any`/free-form strings at a boundary; the web UI's types are generated from the API schema. |
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
**ambiguity** listing the candidates, never a guess. The result is an `AmbiguousReference` value
(§5.5): the CLI exits with code `4`, and the MCP tool returns the candidates as structured content
so the agent can retry with a more specific reference. The matched rule is reported as
`MatchRule` on the result.

### 4.2 Impact semantics

- **Symbol target:** walk backwards over `CALLS` (callers of callers …) up to `depth`
  (default 3). For a class, also include subclasses (reverse `INHERITS`) and callers of its methods.
- **File target:** the union of:
  - files that import it (reverse `IMPORTS`);
  - files containing callers of any symbol defined in it;
  - files with subclasses of its classes,

  expanded the same way up to `depth`.
- Each affected item is a `ResultItem` (§5.3) carrying: hop `distance`, the typed `Via` that pulled
  it in (`Via(kind=ViaKind.CALLS, symbol=write)`, rendered as `calls write`; also `IMPORTS`,
  `INHERITS`, `OVERRIDES`), and `min_confidence` along the path.
- Results are grouped into `ImpactGroup`s by distance, then by file.
- The result always includes a `Caveat(code=CaveatCode.UNRESOLVED_CALLS, …)` when calls in the affected area couldn't be resolved. The data for this is in
  `Function.raw_calls`, which holds calls that got no edge. So "no callers" is never shown as certain.

## 5. Output contract

Everything `query/` takes or returns is a named type. The CLI, MCP server, API and web UI all
use these same types, so an answer has one shape wherever it is shown.

### 5.1 Typing rules

1. **No untyped values at a boundary.** No `Any`, bare `dict`/`list`, `dict[str, Any]` or
   free-form status strings in any public signature of `query/`, `index/`, the CLI, the MCP server
   or the API routers. Every parameter and return value is one of the types below.
2. **Closed vocabularies are `StrEnum`s** (kinds, edge types, call types, error codes, …). They
   serialize as their string value, so the JSON looks the same as plain strings would, but mypy
   rejects a typo.
3. **Identifiers are `NewType`s over `str`** (`SymbolId`, `RepoPath`, `QualifiedName`), so mypy
   won't accept a file path where a symbol id is expected.
4. **Models are immutable.** `@dataclass(frozen=True, slots=True, kw_only=True)`, with
   `tuple[...]` fields instead of `list[...]`. A `Mapping` is allowed only when its keys are an enum
   (`Mapping[Language, str]`).
5. **Invariants are checked on construction.** `__post_init__` checks ranges (confidence in
   `[0, 1]`, 1-indexed lines ≥ 1, distance ≥ 0) and field combinations (only `CALLS` edges carry
   `confidence`). A violation raises `ValueError`, because it is a bug in `query/` and never
   caused by user input.
6. **One place turns untyped DB rows into models.** LadybugDB returns `Sequence[Any]` rows. Only
   `query/rows.py` reads them. It checks each value's type and enum membership and raises
   `IndexIncompatibleError` (§5.6) on a mismatch. No other module indexes a row. `Any` is
   allowed only in `graph/db.py` and `query/rows.py`.
7. **Models stay plain.** They are stdlib dataclasses with no Pydantic, DB or I/O imports (per
   `CLAUDE.md`). Serialization lives in adapters (§5.7).
8. **Checked in CI:** `mypy --strict` runs on `compass_core`, `compass_cli` and `compass_mcp`
   (today it runs on core only), and ruff enables `ANN` (annotations) and `TC` (type-checking
   imports). The web UI's types are generated from the API's OpenAPI schema and never written by hand.

### 5.2 Vocabularies — `query/types.py`

```python
SymbolId = NewType("SymbolId", str)            # "py::compass_core.graph.writer::write"
RepoPath = NewType("RepoPath", str)            # repo-relative POSIX path: "packages/core/src/compass_core/graph/writer.py"
QualifiedName = NewType("QualifiedName", str)  # "compass_core.graph.writer.write"

class Language(StrEnum):    PYTHON = "python"
class SymbolKind(StrEnum):  FILE, CLASS, FUNCTION, METHOD, EXTERNAL            # values are lowercase
class EdgeType(StrEnum):    CONTAINS, IMPORTS, INHERITS, CALLS, CALLS_EXTERN
class CallType(StrEnum):    DIRECT_IMPORT, MODULE_ATTR, RE_EXPORT, MRO         # only the call types that write a CALLS edge
class ViaKind(StrEnum):     CALLS, CALLED_BY, IMPORTS, IMPORTED_BY, INHERITS, INHERITED_BY, OVERRIDES, CONTAINED_IN
class MatchRule(StrEnum):   EXACT_ID, FILE_PATH, QUALIFIED_NAME, PATH_AND_NAME, CLASS_MEMBER, BARE_NAME   # §4.1, in order
class SearchMatch(StrEnum): EXACT, QUALIFIED_SUFFIX, PREFIX, SUBSTRING
class Operation(StrEnum):   FIND, DESCRIBE, CALLERS, CALLEES, IMPACT, CALL_PATH, OUTLINE, HIERARCHY,
                            EXTERNAL_USAGE, STATUS, OVERVIEW, SOURCE, GRAPH_MAP, NEIGHBORHOOD
class Outcome(StrEnum):     OK, AMBIGUOUS, NOT_FOUND                           # JSON discriminator, §5.5
class CaveatCode(StrEnum):  STALE_INDEX, UNRESOLVED_CALLS, DEGRADED_FILES, TRUNCATED, DEPTH_LIMIT_REACHED
class ErrorCode(StrEnum):   INVALID_ARGUMENT, NOT_FOUND, AMBIGUOUS, INDEX_NOT_FOUND, INDEX_BUSY,
                            INDEX_INCOMPATIBLE, QUERY_TIMEOUT, INTERNAL
```

`CallType` has the four values that produce an edge. `UNRESOLVED`, `WILDCARD`, `DYNAMIC`,
`CIRCULAR` and `EXTERNAL` never reach the graph as `CALLS`, so a stored value outside the enum is
an `IndexIncompatibleError`. Phase 3 (`ir.CallResult.call_type`, `ir.CallEdge.call_type`)
changes from `str` to a full `ResolutionType` enum in `ir/`, and `CallType` is the subset that
produces an edge. That way the writer and the reader share one vocabulary.

**Ids for nodes without a definition id:** a file is `SymbolId("file::<repo path>")` and an
external function is `SymbolId("ext::<full_ref>")`. Every node in an answer therefore has a
`SymbolId`.

### 5.3 Building blocks — `query/models.py`

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolRef:
    id: SymbolId
    kind: SymbolKind
    name: str
    qualified_name: QualifiedName
    file_path: RepoPath | None       # None only for EXTERNAL
    line_start: int | None           # 1-indexed; None for FILE and EXTERNAL
    line_end: int | None             # 1-indexed, inclusive
    signature: str | None            # FUNCTION / METHOD only
    source: str | None = None        # set only when the caller asked for source

@dataclass(frozen=True, slots=True, kw_only=True)
class EdgeRef:
    source_id: SymbolId
    target_id: SymbolId
    type: EdgeType
    confidence: float | None         # set iff type is CALLS, in [0, 1]
    call_type: CallType | None       # set iff type is CALLS
    line: int | None                 # 1-indexed call site for CALLS / CALLS_EXTERN; stored 0 → None

@dataclass(frozen=True, slots=True, kw_only=True)
class Via:                           # why an item is in the answer; the renderer turns it into "calls write"
    kind: ViaKind
    symbol: SymbolRef

@dataclass(frozen=True, slots=True, kw_only=True)
class ResultItem:
    symbol: SymbolRef
    distance: int                    # hops from the target; 0 = the target itself
    via: Via | None                  # None iff distance == 0
    min_confidence: float | None     # lowest CALLS confidence on the path; None if the path has no CALLS edge

@dataclass(frozen=True, slots=True, kw_only=True)
class Caveat:
    code: CaveatCode
    message: str                     # rendered sentence, e.g. "4 unresolved calls in 3 affected functions; there may be more callers"
    count: int | None                # the number in the message, for machine use

@dataclass(frozen=True, slots=True, kw_only=True)
class IndexStatus:
    repo_root: Path                  # absolute
    indexed_at: datetime             # timezone-aware UTC
    indexed_commit: str | None       # None when the repo is not a git checkout
    schema_version: int
    stale_file_count: int            # indexed files changed or deleted since indexed_at
    new_file_count: int | None       # unindexed files; computed by `status` only (requires rediscovery)
```

Each model's docstring follows `CLAUDE.md`: Google style, every field under `Attributes:`, and an
`Example:` mapping a code snippet to the model it produces.

### 5.4 Parameters — `query/params.py`

Each operation takes one frozen parameter object. The bounds are module constants (`MAX_DEPTH = 10`,
`MAX_LIMIT = 500`, …), and the CLI (`typer.Option(min=, max=)`), MCP (`Annotated[int, Field(ge=, le=)]`)
and API (`Query(ge=, le=)`) all read them, so the three can't drift apart. `__post_init__` also
checks them and raises `InvalidArgumentError(argument="depth", …)`.

| Params | Fields (defaults) |
|---|---|
| `SearchParams` | `query: str` (non-empty), `kind: SymbolKind \| None = None`, `limit: int = 50` |
| `DescribeParams` | `include_source: bool = False` |
| `TraversalParams` | `depth: int = 1`, `min_confidence: float = 0.0`, `limit: int = 50`, `include_source: bool = False` |
| `ImpactParams` | `depth: int = 3`, `min_confidence: float = 0.0`, `limit: int = 50` |
| `CallPathParams` | `max_depth: int = 6` |
| `ExternalUsageParams` | `limit: int = 50` |
| `SourceParams` | `path: str` (checked against indexed `File` nodes), `start: int \| None = None`, `end: int \| None = None` (1-indexed, inclusive) |
| `NeighborhoodParams` | `depth: int = 1`, `edge_types: frozenset[EdgeType] = frozenset(EdgeType)`, `limit: int = 200` |

### 5.5 Results — `query/results.py`

Every result has the same header, then fields specific to its operation. `operation` is typed as
`Literal[Operation.X]`, and together with `outcome` it gives adapters and the web UI a discriminated union.

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ResultHeader:
    outcome: Literal[Outcome.OK] = Outcome.OK
    index: IndexStatus
    caveats: tuple[Caveat, ...]
```

| Result (`operation`) | Specific fields |
|---|---|
| `SearchResult` (`FIND`) | `query: str`, `kind: SymbolKind \| None`, `hits: tuple[SearchHit, ...]`, `total: int`, `truncated: bool` — `SearchHit(symbol: SymbolRef, match: SearchMatch, fan_in: int)` |
| `DescribeResult` (`DESCRIBE`) | `symbol: SymbolRef`, `matched_by: MatchRule`, `parent: SymbolRef \| None`, `members: tuple[SymbolRef, ...]`, `callers`, `callees`, `external_callees: tuple[ResultItem, ...]`, `edges: tuple[EdgeRef, ...]` |
| `TraversalResult` (`CALLERS` \| `CALLEES`) | `target: SymbolRef`, `matched_by: MatchRule`, `depth: int`, `items: tuple[ResultItem, ...]`, `edges`, `total: int`, `truncated: bool` |
| `ImpactResult` (`IMPACT`) | `target: SymbolRef` (a `FILE` or a symbol), `matched_by`, `depth`, `groups: tuple[ImpactGroup, ...]`, `affected_file_count: int`, `edges`, `total`, `truncated` — `ImpactGroup(distance: int, file_path: RepoPath, items: tuple[ResultItem, ...])` |
| `CallPathResult` (`CALL_PATH`) | `source: SymbolRef`, `target: SymbolRef`, `hops: tuple[ResultItem, ...]` (ordered source → target; empty if no path), `found: bool`, `edges` |
| `OutlineResult` (`OUTLINE`) | `file: SymbolRef`, `classes: tuple[ClassOutline, ...]`, `functions: tuple[SymbolRef, ...]`, `imports: tuple[SymbolRef, ...]`, `imported_by: tuple[SymbolRef, ...]` — `ClassOutline(cls: SymbolRef, methods: tuple[SymbolRef, ...])` |
| `HierarchyResult` (`HIERARCHY`) | `root: SymbolRef`, `ancestors: tuple[ResultItem, ...]`, `descendants: tuple[ResultItem, ...]`, `edges` |
| `ExternalUsageResult` (`EXTERNAL_USAGE`) | `library: str`, `groups: tuple[ExternalUsageGroup, ...]`, `total`, `truncated` — `ExternalUsageGroup(file_path: RepoPath, calls: tuple[ExternalCall, ...])`, `ExternalCall(caller: SymbolRef, external: SymbolRef, line: int \| None)` |
| `StatusResult` (`STATUS`) | `metadata: IndexMetadata` (§6) |
| `OverviewResult` (`OVERVIEW`) | `counts: IndexCounts`, `report: IngestReportSummary`, `entry_points: tuple[SymbolRef, ...]`, `most_imported_files`, `most_called_functions: tuple[RankedSymbol, ...]`, `top_external_libraries: tuple[LibraryUsage, ...]` — `RankedSymbol(symbol: SymbolRef, count: int)`, `LibraryUsage(library: str, call_count: int)` |
| `SourceResult` (`SOURCE`) | `file_path: RepoPath`, `start_line: int`, `end_line: int` (1-indexed, inclusive, after clamping), `lines: tuple[str, ...]` |
| `GraphMapResult` (`GRAPH_MAP`) | `nodes: tuple[SymbolRef, ...]` (files only), `edges: tuple[EdgeRef, ...]` (`IMPORTS` only) |
| `NeighborhoodResult` (`NEIGHBORHOOD`) | `center: SymbolRef`, `depth`, `edge_types: frozenset[EdgeType]`, `nodes`, `edges`, `truncated` |

`QueryResult` is a type alias for the union of these thirteen, used where an adapter handles any of them
(the text renderer, for example).

**Reference outcomes are values, not exceptions.** This matches the rule in `errors.py` that
expected failures are typed results.

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class AmbiguousReference:
    outcome: Literal[Outcome.AMBIGUOUS] = Outcome.AMBIGUOUS
    reference: str                        # what the user typed
    candidates: tuple[SymbolRef, ...]     # ≥ 2, ordered by MatchRule then fan-in

@dataclass(frozen=True, slots=True, kw_only=True)
class SymbolNotFound:
    outcome: Literal[Outcome.NOT_FOUND] = Outcome.NOT_FOUND
    reference: str
    suggestions: tuple[SymbolRef, ...]    # ≤ 5 case-insensitive substring matches

R = TypeVar("R")
Lookup: TypeAlias = R | AmbiguousReference | SymbolNotFound
```

**Operation signatures** (`db` is always a read-only `GraphDB`):

```python
def find_symbols(db: GraphDB, params: SearchParams) -> SearchResult
def describe(db: GraphDB, ref: str, params: DescribeParams) -> Lookup[DescribeResult]
def callers(db: GraphDB, ref: str, params: TraversalParams) -> Lookup[TraversalResult]
def callees(db: GraphDB, ref: str, params: TraversalParams) -> Lookup[TraversalResult]
def impact(db: GraphDB, ref: str, params: ImpactParams) -> Lookup[ImpactResult]
def call_path(db: GraphDB, source: str, target: str, params: CallPathParams) -> Lookup[CallPathResult]
def outline(db: GraphDB, path: str) -> Lookup[OutlineResult]
def hierarchy(db: GraphDB, ref: str) -> Lookup[HierarchyResult]
def external_usage(db: GraphDB, library_or_ref: str, params: ExternalUsageParams) -> Lookup[ExternalUsageResult]
def status(location: IndexLocation) -> StatusResult
def overview(db: GraphDB) -> OverviewResult
def read_source(db: GraphDB, location: IndexLocation, params: SourceParams) -> Lookup[SourceResult]
def graph_map(db: GraphDB) -> GraphMapResult
def neighborhood(db: GraphDB, ref: str, params: NeighborhoodParams) -> Lookup[NeighborhoodResult]
```

For `call_path`, an ambiguous or unknown **source or target** comes back as the matching outcome, with
`reference` saying which one it was. The resolver is
`resolve(db, ref: str, *, allow_file: bool) -> Lookup[ResolvedReference]`, where
`ResolvedReference(symbol: SymbolRef, rule: MatchRule)`.

Adapters handle a `Lookup` with an exhaustive `match` that ends in `assert_never`, so adding an
outcome is a type error until every adapter handles it.

### 5.6 Errors — `compass_core/errors.py`

Failures that come from the environment rather than from the question are exceptions under
`CompassError`. Each carries its `ErrorCode` and typed context. None of them is a bare
`RuntimeError` or a string match at the call site.

```python
class QueryError(CompassError):              code: ClassVar[ErrorCode]
class InvalidArgumentError(QueryError):      code = INVALID_ARGUMENT;   argument: str; reason: str
class IndexNotFoundError(QueryError):        code = INDEX_NOT_FOUND;    searched_from: Path
class IndexBusyError(QueryError):            code = INDEX_BUSY;         retry_after_s: int
class IndexIncompatibleError(QueryError):    code = INDEX_INCOMPATIBLE; found_schema_version: int | None; expected_schema_version: int
class QueryTimeoutError(QueryError):         code = QUERY_TIMEOUT;      timeout_ms: int
```

`graph/db.py` is the only place that inspects LadybugDB exception text. It turns "Could not set
lock on file" into `IndexBusyError` and a timeout into `QueryTimeoutError`, chaining the original
with `raise … from exc`. Every adapter renders failures through one typed envelope:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ErrorResponse:
    code: ErrorCode
    message: str                              # one sentence plus the fix, e.g. "No index found. Run `compass ingest`."
    argument: str | None = None               # INVALID_ARGUMENT
    candidates: tuple[SymbolRef, ...] = ()    # AMBIGUOUS
    suggestions: tuple[SymbolRef, ...] = ()   # NOT_FOUND
    retry_after_s: int | None = None          # INDEX_BUSY
```

It is built only by `query/errors.py::to_error_response(QueryError | AmbiguousReference | SymbolNotFound)`.
Each code has one mapping, used by every adapter:

| `ErrorCode` | Source | CLI exit | HTTP | MCP |
|---|---|---|---|---|
| — (ok) | result | `0` | 200 | structured result |
| `INTERNAL` | any other exception | `1` | 500 | tool error; details logged, not returned |
| `INVALID_ARGUMENT` | `InvalidArgumentError`, Typer usage error | `2` | 422 | tool error |
| `NOT_FOUND` | `SymbolNotFound` | `3` | 404 | structured result (agent retries with a suggestion) |
| `AMBIGUOUS` | `AmbiguousReference` | `4` | 409 | structured result (agent retries with a candidate) |
| `INDEX_NOT_FOUND` | `IndexNotFoundError` | `5` | 503 | tool error |
| `INDEX_BUSY` | `IndexBusyError` | `6` | 503 + `Retry-After` | tool error |
| `INDEX_INCOMPATIBLE` | `IndexIncompatibleError` | `7` | 503 | tool error |
| `QUERY_TIMEOUT` | `QueryTimeoutError` | `8` | 504 | tool error |

Exit code `2` stays reserved for usage errors, because Click/Typer already exits with `2` on bad
arguments, and `1` stays reserved for crashes. The error envelope goes to stderr (text, or JSON
with `--json`), and results go to stdout.

### 5.7 Serialization and rendering

**Serialization.** `compass_core/query/serialize.py` holds one cached `pydantic.TypeAdapter` per
result type, built from the dataclasses themselves. There are no hand-written mirror models, so
nothing can drift. It gives:
- `to_json(value: QueryResult | AmbiguousReference | SymbolNotFound | ErrorResponse) -> str` for `--json`;
- `json_schema(tp: type) -> JsonSchema` (a `TypeAlias` for the JSON-schema mapping) for tests and docs.

The API declares the dataclasses directly as `response_model`s (FastAPI supports stdlib
dataclasses). The MCP tools declare them as return annotations, so FastMCP publishes an
`outputSchema` and returns `structuredContent`. Enums serialize as values, `datetime` as ISO-8601
UTC, `Path` as a string, and `frozenset` as a sorted list.

**CLI text (default)** is compact and grep-friendly, with one line per item and paths formatted as
`file:line`. `render_text` matches on the result type (exhaustive, `assert_never`) and builds
`via` strings from `Via`:

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

**Web UI.** `apps/web/lib/api-types.ts` is generated from `/openapi.json` with `openapi-typescript`
(`pnpm gen:api`). CI regenerates it and fails on a diff. `lib/api.ts` returns those types,
and views narrow on `outcome` / `operation`.

**Defaults:** see §5.4. `--min-confidence 0` means everything is shown, with confidence labelled.
`--source` sets `include_source`; by default source bodies are left out to save agent context.

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

In memory the file is typed as follows (`index/metadata.py`). The JSON is only its serialized form:

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class IndexCounts:
    files: int; classes: int; functions: int; edges: int

@dataclass(frozen=True, slots=True, kw_only=True)
class IngestReportSummary:
    resolved_ratio: Mapping[Language, float]   # each in [0, 1]
    dangling_imports: int
    degraded_files: int

@dataclass(frozen=True, slots=True, kw_only=True)
class IndexMetadata:
    schema_version: int
    compass_version: str
    repo_root: Path                            # absolute
    indexed_commit: str | None
    indexed_at: datetime                       # UTC; stored as epoch seconds
    grammar_versions: Mapping[Language, str]
    counts: IndexCounts
    report: IngestReportSummary

@dataclass(frozen=True, slots=True, kw_only=True)
class IndexLocation:
    repo_root: Path; db_path: Path; metadata_path: Path
```

`load_metadata(path: Path) -> IndexMetadata` parses and checks the file with a `TypeAdapter`.
A pre-v1 file (no `schema_version`) loads with zeroed counts and report. Malformed JSON, a newer
`schema_version` or an unknown language raises `IndexIncompatibleError`, never `KeyError` or
`json.JSONDecodeError`. `save_metadata(path: Path, meta: IndexMetadata) -> None` writes through a
temp file + `os.replace`.

**Staleness check** (runs on every query, and is cheap):
`stale_files(meta: IndexMetadata, indexed: Iterable[RepoPath]) -> tuple[RepoPath, ...]` stats each
indexed file and returns those whose mtime is later than `indexed_at` or which no longer exist.
`compass status` also rediscovers the repo and fills `IndexStatus.new_file_count`. A stale index
never blocks a query; it only fills `index.stale_file_count` and adds a
`Caveat(code=CaveatCode.STALE_INDEX, …)`.

## 7. MCP server

- Built with the official `mcp` Python SDK (`FastMCP`), stdio transport, in `packages/mcp`.
- Launched as `compass mcp` (a CLI subcommand, so users configure one binary):

  ```json
  { "mcpServers": { "code-compass": { "command": "compass", "args": ["mcp"] } } }
  ```
- One tool per row in §4. Each tool description says **when** to use it (e.g. "Use before changing a
  function to see what else might break"). Tool inputs are symbol references (§4.1), never raw ids.
- **Typed tool signatures.** Every tool has annotated parameters, with bounds from `query/params.py`
  (`depth: Annotated[int, Field(ge=1, le=MAX_DEPTH)] = 3`, `kind: SymbolKind | None`). FastMCP
  therefore publishes an exact `inputSchema`, and enum values show up as allowed choices. Every tool's
  return annotation is its result union (e.g. `ImpactResult | AmbiguousReference | SymbolNotFound`),
  so FastMCP publishes an `outputSchema` and returns `structuredContent`. No tool returns a
  `dict` or a preformatted string.
- **Errors** follow §5.6. Ambiguous and not-found are normal structured results. `QueryError`s become
  tool errors (`isError: true`) whose text is the `ErrorResponse` JSON, so the agent sees the
  code and the fix (e.g. "run `compass ingest`").
- Tools are read-only. v1 has no ingest tool; the agent runs `compass ingest` in its shell when the
  index is stale, and every result tells it so through `caveats`.
- Each tool result is wrapped in `ToolResult[R](result: R, ui_url: str | None)`, where `ui_url` is for example `http://127.0.0.1:8000/?view=impact&focus=<id>`, so an agent can
  hand the user a visual. `ui_url` is an MCP concern and stays out of the core result types. The URL only works while `compass serve` is running.

## 8. HTTP API (for the web UI)

All endpoints are thin wrappers over `query/`. Symbol references go in query parameters.
Parameters are typed and bounded (`depth: Annotated[int, Query(ge=1, le=MAX_DEPTH)]`,
`kind: SymbolKind | None`, `edge_types: list[EdgeType]`), so FastAPI rejects bad input with a 422
before `query/` runs, and each route turns them into the matching `…Params` object. Every route declares
`response_model` as its result dataclass, and `responses=` lists the `ErrorResponse` status codes
from §5.6. The OpenAPI schema therefore describes every success and error body, and the web UI's
types are generated from it. One exception handler per `QueryError` subclass, plus handlers
for `AmbiguousReference`/`SymbolNotFound`, turns failures into `ErrorResponse`; routes contain no
`try`/`except`.

| Endpoint | Operation → `response_model` |
|---|---|
| `GET /api/status` | `status` → `StatusResult` |
| `GET /api/overview` | `overview` → `OverviewResult` |
| `GET /api/search?q=&kind=&limit=` | `find_symbols` → `SearchResult` |
| `GET /api/symbol?ref=&include_source=` | `describe` → `DescribeResult` |
| `GET /api/callers?ref=&depth=&min_confidence=&limit=` / `GET /api/callees?…` | `callers` / `callees` → `TraversalResult` |
| `GET /api/impact?ref=&depth=&min_confidence=&limit=` | `impact` (symbol or file) → `ImpactResult` |
| `GET /api/path?from=&to=&max_depth=` | `call_path` → `CallPathResult` |
| `GET /api/outline?path=` | `outline` → `OutlineResult` |
| `GET /api/hierarchy?ref=` | `hierarchy` → `HierarchyResult` |
| `GET /api/externals?q=&limit=` | `external_usage` → `ExternalUsageResult` |
| `GET /api/source?path=&start=&end=` | `read_source` → `SourceResult`. Only files present in the index are served (no path traversal); the line range is clamped. |
| `GET /api/graph/map` | `graph_map` → `GraphMapResult`: File nodes + IMPORTS edges (replaces the whole-graph dump) |
| `GET /api/graph/neighborhood?ref=&depth=&edge_types=&limit=` | `neighborhood` → `NeighborhoodResult`, for expand-on-click |

Error bodies on every endpoint are `ErrorResponse` with the status codes in §5.6.

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
