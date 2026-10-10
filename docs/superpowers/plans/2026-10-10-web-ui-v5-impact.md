# Web UI v5 (Overview · Graph · Impact) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the v5 UI (warm theme, left rail, Overview, Graph, Impact) with Impact backed by a real `GET /api/impact`.

**Architecture:** A thin slice of the v1 query layer (`compass_core/query/`: typed models, `resolve`, `find_symbols`, `impact`, `overview`) is exposed through three FastAPI routes. The web app gets generated TypeScript types from `/openapi.json`, a re-themed shell with a left rail, and three views. The existing 3D canvas is kept.

**Tech Stack:** Python 3.11, FastAPI, LadybugDB (`real_ladybug`), pytest, mypy, ruff; Next.js 15, React 19, Tailwind 4, shadcn/ui, lucide-react, `openapi-typescript`.

**Spec:** [`specs/2026-10-10-web-ui-v5-impact-design.md`](../specs/2026-10-10-web-ui-v5-impact-design.md). Contracts: [`specs/2026-09-28-v1-query-layer-design.md`](../specs/2026-09-28-v1-query-layer-design.md) §4.2, §5, §6, §8. Parent plan (full v1): [`plans/2026-09-28-v1-query-layer.md`](2026-09-28-v1-query-layer.md).

## Global Constraints

- Google-style docstrings (`Args:`, `Returns:`, `Raises:`, `Attributes:`, `Example:`) on every public function and model (`CLAUDE.md`).
- Models are plain frozen dataclasses: `@dataclass(frozen=True, slots=True, kw_only=True)`, `tuple` fields, no Pydantic/DB/I/O imports (spec §5.1 rules 4, 7).
- No `Any`, bare `dict`/`list`, or free-form status strings in any public signature of `query/`; `Any` is allowed only in `graph/db.py` and `query/rows.py` (spec §5.1 rule 1, 6).
- All source line numbers are **1-indexed**; a stored line `0` becomes `None`.
- New tests live under `packages/core/tests/...` (never inline or ad hoc).
- Every task ends green: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `cd packages/core && uv run mypy`; web tasks also `pnpm exec tsc --noEmit` and `pnpm build` in `apps/web`.
- Web: shadcn/ui components, `lucide-react` icons only, `cursor-pointer` on every clickable element, existing theme tokens only (no ad-hoc hex), no file over 500 lines, no generic file names, don't repeat the parent directory in a file name.
- Never commit to `qa` or `main`. Commit only on the branch the user names, and only when told.
- `/api/repo/overview` and `/api/repo/graph` stay in place.

## Review Focus

The inputs most likely to bite someone using this, and the task whose tests pin each one:

1. A target that exists but has no callers/importers → empty `groups`, not an error (Task 7).
2. A bare name shared by two symbols → `AmbiguousReference` with candidates, rendered as a picker in the UI (Tasks 5, 7, 12).
3. `depth` = 0, 11 or a non-integer → 422 `ErrorResponse`, not a 500 (Task 9).
4. A cycle in the call or import graph (a → b → a) → terminates, each node appears once at its shortest distance (Task 7).
5. The index file is missing or locked by `compass ingest` → 503 `ErrorResponse` the UI shows as a message, not a blank page (Tasks 3, 9, 12).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `packages/core/src/compass_core/phases/pipeline.py` | Modify | Build into a temp DB, atomic swap, write metadata via `index.metadata` |
| `packages/core/src/compass_core/index/locate.py` | Create | `IndexLocation`, `find_index`, `require_index` |
| `packages/core/src/compass_core/index/metadata.py` | Create | `IndexMetadata` + atomic `load_metadata`/`save_metadata` |
| `packages/core/src/compass_core/graph/db.py` | Modify | `read_only` flag, query timeout, lock error mapping |
| `packages/core/src/compass_core/errors.py` | Modify | `ErrorCode` + `QueryError` hierarchy |
| `packages/core/src/compass_core/query/types.py` | Create | `StrEnum`s and `NewType` ids |
| `packages/core/src/compass_core/query/models.py` | Create | `SymbolRef`, `EdgeRef`, `Via`, `ResultItem`, `Caveat`, `IndexStatus` |
| `packages/core/src/compass_core/query/params.py` | Create | `SearchParams`, `ImpactParams`, bound constants |
| `packages/core/src/compass_core/query/results.py` | Create | `SearchResult`, `ImpactResult`, `OverviewResult`, `AmbiguousReference`, `SymbolNotFound`, `Lookup` |
| `packages/core/src/compass_core/query/errors.py` | Create | `ErrorResponse`, `ERROR_MAPPINGS` |
| `packages/core/src/compass_core/query/serialize.py` | Create | Cached `TypeAdapter`s, `to_json` |
| `packages/core/src/compass_core/query/rows.py` | Create | The only DB-row → model conversion |
| `packages/core/src/compass_core/query/references.py` | Create | `resolve` (spec §4.1) |
| `packages/core/src/compass_core/query/search.py` | Create | `find_symbols` |
| `packages/core/src/compass_core/query/impact.py` | Create | `impact` |
| `packages/core/src/compass_core/query/overview.py` | Create | `overview` |
| `packages/core/src/compass_core/server/routers/query.py` | Create | `/api/search`, `/api/impact`, `/api/overview` |
| `packages/core/src/compass_core/server/main.py` | Modify | Mount router, register exception handlers |
| `packages/core/tests/fixtures/sample_repo/` | Create | Known Python repo for query tests |
| `packages/core/tests/query/`, `tests/index/` | Create | Tests per module |
| `apps/web/src/lib/api-types.ts` | Create (generated) | Types from `/openapi.json` |
| `apps/web/src/lib/api.ts` | Modify | Typed client functions |
| `apps/web/src/styles/globals.css` | Modify | v5 tokens mapped onto shadcn variables |
| `apps/web/src/app/layout.tsx` | Modify | Geist + JetBrains Mono fonts |
| `apps/web/src/components/shell/NavRail.tsx` | Create | Left rail |
| `apps/web/src/components/shell/useWorkspaceView.ts` | Create | `?view=&focus=` URL state |
| `apps/web/src/components/project/WorkspaceTabs.tsx` | Rewrite (rename to `workspace/Workspace.tsx`) | Rail + active view |
| `apps/web/src/components/overview/*` | Create | Stat tiles, insight cards |
| `apps/web/src/components/impact/*` | Create | Target picker, header, group list, states |
| `apps/web/src/components/project/graph/*` | Modify | Restyle, accept `focus` |

---

## Backend

### Task 1: Clean rebuild on every ingest

Re-ingesting doubles every edge (verified on this repo's index: 2,774 IMPORTS rows for 252 distinct pairs; 668 CALLS rows for 55), and deleted code is never removed. Impact counts would be wrong without this.

**Files:**
- Modify: `packages/core/src/compass_core/phases/pipeline.py:62-70`
- Test: `packages/core/tests/phases/test_pipeline.py`

**Interfaces:**
- Produces: `Pipeline.run` writes to `<db_path>.building` and swaps with `os.replace`; the final DB is always a clean rebuild.

- [ ] **Step 1: Write the failing tests** (append to `tests/phases/test_pipeline.py`)

```python
from compass_core.graph.db import GraphDB, as_row


def _edge_count(db_path: Path) -> int:
    with GraphDB(db_path) as db:
        return int(as_row(db.execute("MATCH ()-[r]->() RETURN count(*)"))[0])


def _function_names(db_path: Path) -> set[str]:
    with GraphDB(db_path) as db:
        return {r[0] for r in db.execute("MATCH (f:Function) RETURN f.name").get_all()}


def test_reingest_does_not_duplicate_edges(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def run():\n    helper()\n")
    (repo / "b.py").write_text("def helper():\n    pass\n")
    db_path = tmp_path / "graph.ladybug"

    Pipeline().run(repo, db_path)
    first = _edge_count(db_path)
    Pipeline().run(repo, db_path)

    assert _edge_count(db_path) == first


def test_reingest_removes_deleted_functions(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def keep():\n    pass\n\ndef gone():\n    pass\n")
    db_path = tmp_path / "graph.ladybug"
    Pipeline().run(repo, db_path)

    (repo / "a.py").write_text("def keep():\n    pass\n")
    Pipeline().run(repo, db_path)

    assert _function_names(db_path) == {"keep"}


def test_failed_ingest_leaves_old_db_untouched(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def keep():\n    pass\n")
    db_path = tmp_path / "graph.ladybug"
    Pipeline().run(repo, db_path)
    before = _edge_count(db_path)

    def boom(*_args, **_kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr("compass_core.phases.pipeline.PersistencePhase.run", boom)
    try:
        Pipeline().run(repo, db_path)
    except RuntimeError:
        pass

    assert _edge_count(db_path) == before
    assert not db_path.with_name(db_path.name + ".building").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/core/tests/phases/test_pipeline.py -v`
Expected: `test_reingest_does_not_duplicate_edges` and `test_reingest_removes_deleted_functions` FAIL; the failure test may FAIL on the leftover `.building` file.

- [ ] **Step 3: Implement** — in `pipeline.py`, replace the persistence block:

```python
import os
import shutil

...
        db_path.parent.mkdir(parents=True, exist_ok=True)
        building = db_path.with_name(db_path.name + ".building")
        _remove_db(building)
        try:
            with GraphDB(building) as db:
                create_schema(db)
                ctx = PersistencePhase().run(ctx, db)
            os.replace(building, db_path)
        except BaseException:
            _remove_db(building)
            raise
        if on_phase_complete is not None:
            on_phase_complete("persistence", ctx)
```

and add:

```python
def _remove_db(path: Path) -> None:
    """Delete a LadybugDB file or directory plus its write-ahead log, if present.

    Args:
        path: The database path; sibling files named ``<path>.wal`` are removed too.
    """
    for candidate in (path, path.with_name(path.name + ".wal")):
        if candidate.is_dir():
            shutil.rmtree(candidate)
        elif candidate.exists():
            candidate.unlink()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest packages/core/tests/phases/test_pipeline.py -v`
Expected: PASS. If `os.replace` leaves a stale `<db_path>.wal`, extend `_remove_db(db_path)` to run before the swap and re-run.

- [ ] **Step 5: Gates** — run the global-constraints gate commands; fix anything flagged.

---

### Task 2: Index location and metadata

`IndexStatus` is part of every result header (spec §5.3, §5.5), so the engine needs the index location and typed metadata.

**Files:**
- Create: `packages/core/src/compass_core/index/__init__.py`, `locate.py`, `metadata.py`
- Modify: `packages/core/src/compass_core/phases/pipeline.py` (`_save_metadata`), `packages/core/src/compass_core/settings.py` (none; `LADYBUG_DB_PATH` stays the override)
- Test: `packages/core/tests/index/test_locate.py`, `test_metadata.py`

**Interfaces:**
- Produces:
  - `IndexLocation(repo_root: Path, db_path: Path, metadata_path: Path)` (frozen dataclass)
  - `find_index(start: Path) -> IndexLocation | None`
  - `require_index(start: Path, override: Path | None = None) -> IndexLocation` raising `IndexNotFoundError`
  - `IndexMetadata(indexed_commit: str | None, indexed_at: datetime, schema_version: int, grammar_versions: Mapping[Language, str])`
  - `load_metadata(path: Path) -> IndexMetadata`, `save_metadata(path: Path, meta: IndexMetadata) -> None`

- [ ] **Step 1: Write failing tests**

```python
# tests/index/test_locate.py
from pathlib import Path

import pytest

from compass_core.errors import IndexNotFoundError
from compass_core.index.locate import find_index, require_index


def _make_index(root: Path) -> Path:
    db = root / ".compass" / "graph.ladybug"
    db.parent.mkdir(parents=True)
    db.write_text("")
    return db


def test_found_in_cwd(tmp_path: Path):
    db = _make_index(tmp_path)
    loc = find_index(tmp_path)
    assert loc is not None and loc.db_path == db and loc.repo_root == tmp_path


def test_found_in_parent(tmp_path: Path):
    _make_index(tmp_path)
    child = tmp_path / "pkg" / "sub"
    child.mkdir(parents=True)
    loc = find_index(child)
    assert loc is not None and loc.repo_root == tmp_path


def test_not_found_returns_none(tmp_path: Path):
    assert find_index(tmp_path) is None


def test_require_index_raises_when_missing(tmp_path: Path):
    with pytest.raises(IndexNotFoundError) as exc:
        require_index(tmp_path)
    assert exc.value.searched_from == tmp_path


def test_override_takes_precedence(tmp_path: Path):
    other = tmp_path / "other"
    other.mkdir()
    db = _make_index(other)
    loc = require_index(tmp_path, override=db)
    assert loc.db_path == db
```

```python
# tests/index/test_metadata.py
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from compass_core.errors import IndexIncompatibleError
from compass_core.index.metadata import IndexMetadata, load_metadata, save_metadata
from compass_core.query.types import Language


def test_round_trip(tmp_path: Path):
    meta = IndexMetadata(
        indexed_commit="abc",
        indexed_at=datetime(2026, 10, 10, tzinfo=UTC),
        schema_version=1,
        grammar_versions={Language.PYTHON: "0.25.0"},
    )
    path = tmp_path / "metadata.json"
    save_metadata(path, meta)
    assert load_metadata(path) == meta


def test_pre_v1_metadata_loads_with_defaults(tmp_path: Path):
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps({"indexed_commit": "x", "indexed_at": 1788431823,
                                "grammar_versions": {"python": "0.25.0"}}))
    meta = load_metadata(path)
    assert meta.schema_version == 1 and meta.indexed_at.tzinfo is not None


@pytest.mark.parametrize("raw", ["{not json", json.dumps({"schema_version": 99}),
                                 json.dumps({"indexed_at": 1, "grammar_versions": {"cobol": "1"}})])
def test_bad_metadata_raises_incompatible(tmp_path: Path, raw: str):
    path = tmp_path / "metadata.json"
    path.write_text(raw)
    with pytest.raises(IndexIncompatibleError):
        load_metadata(path)
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest packages/core/tests/index -v` → FAIL (modules missing).

- [ ] **Step 3: Implement.** First add to `errors.py` (full hierarchy is Task 3; here add only what these tests import):

```python
class IndexNotFoundError(CompassError):
    """No ``.compass/graph.ladybug`` was found walking up from ``searched_from``."""

    def __init__(self, *, searched_from: Path) -> None:
        super().__init__(f"No Compass index found from {searched_from}. Run `compass ingest`.")
        self.searched_from = searched_from


class IndexIncompatibleError(CompassError):
    """The index or its metadata is unreadable or from an unsupported version."""
```

(Add `from pathlib import Path` to `errors.py`.) Then `locate.py`:

```python
"""Locate the on-disk Compass index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from compass_core.errors import IndexNotFoundError

_INDEX_DIR = ".compass"
_DB_NAME = "graph.ladybug"
_META_NAME = "metadata.json"


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexLocation:
    """Where an index lives on disk.

    Attributes:
        repo_root: Directory that contains ``.compass/``.
        db_path: Path to ``graph.ladybug``.
        metadata_path: Path to ``metadata.json``.

    Example:
        ``find_index(Path("/repo/pkg"))`` with ``/repo/.compass/graph.ladybug`` present
        returns ``IndexLocation(repo_root=Path("/repo"), ...)``.
    """

    repo_root: Path
    db_path: Path
    metadata_path: Path


def _location(repo_root: Path) -> IndexLocation:
    base = repo_root / _INDEX_DIR
    return IndexLocation(
        repo_root=repo_root, db_path=base / _DB_NAME, metadata_path=base / _META_NAME
    )


def find_index(start: Path) -> IndexLocation | None:
    """Walk up from ``start`` to the first directory holding ``.compass/graph.ladybug``.

    Args:
        start: Directory to begin searching from.

    Returns:
        The location, or ``None`` if none exists up to the filesystem root.
    """
    for candidate in (start, *start.parents):
        if (candidate / _INDEX_DIR / _DB_NAME).exists():
            return _location(candidate)
    return None


def require_index(start: Path, override: Path | None = None) -> IndexLocation:
    """Like ``find_index`` but an explicit ``override`` db path wins, and a miss raises.

    Args:
        start: Directory to begin searching from.
        override: Explicit path to a ``graph.ladybug`` file.

    Returns:
        The index location.

    Raises:
        IndexNotFoundError: If nothing is found.
    """
    if override is not None:
        return IndexLocation(
            repo_root=override.parent.parent,
            db_path=override,
            metadata_path=override.parent / _META_NAME,
        )
    location = find_index(start)
    if location is None:
        raise IndexNotFoundError(searched_from=start)
    return location
```

and `metadata.py` — `IndexMetadata` frozen dataclass (fields per Interfaces), `save_metadata` writes `metadata.json.tmp` then `os.replace`, storing `indexed_at` as epoch seconds and `grammar_versions` as `{lang.value: v}`; `load_metadata` parses JSON, defaults `schema_version` to 1 for pre-v1 files, converts epoch → `datetime.fromtimestamp(x, UTC)`, and converts `JSONDecodeError`, `KeyError`, `ValueError`, an unknown `Language` value or `schema_version > 1` into `IndexIncompatibleError(...) from exc`. Create `query/types.py` with `Language` first if Task 4 hasn't run (do Task 4 Step 3's `types.py` now; it has no dependencies). Update `pipeline._save_metadata` to build an `IndexMetadata` (`indexed_commit=None` when `_get_git_commit` returns `"unknown"`) and call `save_metadata`.

- [ ] **Step 4: Run to verify pass** — `uv run pytest packages/core/tests/index packages/core/tests/phases/test_pipeline.py -v` → PASS.
- [ ] **Step 5: Gates.**

---

### Task 3: Read-only access and error hierarchy

**Files:**
- Modify: `packages/core/src/compass_core/graph/db.py:49-65`, `packages/core/src/compass_core/errors.py`, `packages/core/src/compass_core/settings.py`
- Test: `packages/core/tests/test_graph_db.py`, `packages/core/tests/test_errors.py`

**Interfaces:**
- Produces:
  - `GraphDB(db_path=None, *, read_only: bool = False, timeout_ms: int | None = None)`
  - `ErrorCode` (`StrEnum`: `INVALID_ARGUMENT, NOT_FOUND, AMBIGUOUS, INDEX_NOT_FOUND, INDEX_BUSY, INDEX_INCOMPATIBLE, QUERY_TIMEOUT, INTERNAL`)
  - `QueryError(CompassError)` with `ClassVar[ErrorCode] code`; subclasses `InvalidArgumentError(argument: str, reason: str)`, `IndexBusyError(retry_after_s: int)`, `QueryTimeoutError(timeout_ms: int)`, and `IndexNotFoundError` / `IndexIncompatibleError` re-parented onto `QueryError`.
  - `QUERY_TIMEOUT_MS: int = 10_000` setting.

- [ ] **Step 1: Write failing tests**

```python
# append to tests/test_graph_db.py
import pytest

from compass_core.errors import ErrorCode, IndexBusyError, QueryTimeoutError


def test_read_only_rejects_writes(tmp_path):
    path = tmp_path / "g.ladybug"
    with GraphDB(path) as db:
        db.execute("CREATE NODE TABLE T(id STRING, PRIMARY KEY(id))")
    with GraphDB(path, read_only=True) as db, pytest.raises(Exception):  # noqa: B017
        db.execute("CREATE (:T {id: 'x'})")


def test_second_writer_maps_to_index_busy(tmp_path):
    path = tmp_path / "g.ladybug"
    with GraphDB(path):
        with pytest.raises(IndexBusyError) as exc:
            GraphDB(path, read_only=True)
        assert exc.value.code is ErrorCode.INDEX_BUSY
        assert exc.value.retry_after_s >= 1
        assert exc.value.__cause__ is not None
```

```python
# append to tests/test_errors.py
from compass_core.errors import ErrorCode, InvalidArgumentError, QueryError


def test_every_query_error_declares_a_unique_code():
    codes = [cls.code for cls in QueryError.__subclasses__()]
    assert len(codes) == len(set(codes))


def test_invalid_argument_carries_context():
    err = InvalidArgumentError(argument="depth", reason="must be between 1 and 10")
    assert err.code is ErrorCode.INVALID_ARGUMENT and err.argument == "depth"
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest packages/core/tests/test_graph_db.py packages/core/tests/test_errors.py -v` → FAIL.

- [ ] **Step 3: Implement.** In `errors.py` add `ErrorCode` and `QueryError` (below) and re-parent `IndexNotFoundError`, `IndexIncompatibleError` (keep their constructors):

```python
from enum import StrEnum
from typing import ClassVar


class ErrorCode(StrEnum):
    """Machine-readable failure codes shared by the API, CLI and MCP adapters."""

    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    INDEX_NOT_FOUND = "INDEX_NOT_FOUND"
    INDEX_BUSY = "INDEX_BUSY"
    INDEX_INCOMPATIBLE = "INDEX_INCOMPATIBLE"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    INTERNAL = "INTERNAL"


class QueryError(CompassError):
    """Base class for failures raised by the query layer."""

    code: ClassVar[ErrorCode] = ErrorCode.INTERNAL


class InvalidArgumentError(QueryError):
    code: ClassVar[ErrorCode] = ErrorCode.INVALID_ARGUMENT

    def __init__(self, *, argument: str, reason: str) -> None:
        super().__init__(f"Invalid {argument}: {reason}")
        self.argument = argument
        self.reason = reason


class IndexBusyError(QueryError):
    code: ClassVar[ErrorCode] = ErrorCode.INDEX_BUSY

    def __init__(self, *, retry_after_s: int) -> None:
        super().__init__(f"The index is being rebuilt; retry in {retry_after_s}s.")
        self.retry_after_s = retry_after_s


class QueryTimeoutError(QueryError):
    code: ClassVar[ErrorCode] = ErrorCode.QUERY_TIMEOUT

    def __init__(self, *, timeout_ms: int) -> None:
        super().__init__(f"Query exceeded {timeout_ms} ms.")
        self.timeout_ms = timeout_ms
```

`IndexNotFoundError.code = ErrorCode.INDEX_NOT_FOUND`, `IndexIncompatibleError.code = ErrorCode.INDEX_INCOMPATIBLE`, both subclass `QueryError`. In `graph/db.py` change `__init__` to the new signature: pass `read_only=read_only` to `lb.Database`; wrap construction in `try/except RuntimeError as exc` and when `"Could not set lock on file" in str(exc)` raise `IndexBusyError(retry_after_s=2) from exc` (this file is the only place that matches driver text); after connecting call `self._conn.set_query_timeout(timeout_ms or settings.QUERY_TIMEOUT_MS)`; in `execute`, convert a driver timeout error (message contains `"interrupted"`) into `QueryTimeoutError(timeout_ms=...) from exc`. Add `QUERY_TIMEOUT_MS: int = Field(default=10_000, ...)` to `Settings`.

- [ ] **Step 4: Run to verify pass.** If the driver's lock/timeout message differs from the strings above, print the real message in a scratch run, match on that, and keep the test as the source of truth.
- [ ] **Step 5: Gates.**

---

### Task 4: Vocabularies, models, params, results, errors, serialization

**Files:**
- Create: `query/__init__.py`, `types.py`, `models.py`, `params.py`, `results.py`, `errors.py`, `serialize.py` (all under `packages/core/src/compass_core/query/`)
- Test: `packages/core/tests/query/test_models.py`, `test_params.py`, `test_serialize.py`, `test_error_mappings.py`

**Interfaces:**
- Produces: every type in spec §5.2–§5.5 *used by this slice* — `SymbolId, RepoPath, QualifiedName, Language, SymbolKind, EdgeType, CallType, ViaKind, MatchRule, SearchMatch, Operation, Outcome, CaveatCode`; `SymbolRef, EdgeRef, Via, ResultItem, Caveat, IndexStatus`; `SearchParams, ImpactParams, MAX_DEPTH=10, MAX_LIMIT=500`; `SearchHit, SearchResult, ImpactGroup, ImpactResult, RankedSymbol, LibraryUsage, OverviewResult, ResultHeader, AmbiguousReference, SymbolNotFound, Lookup`; `ErrorResponse(code, message, details)`, `ERROR_MAPPINGS: Mapping[ErrorCode, ErrorMapping(exit_code, http_status, mcp_is_error)]`; `to_json(obj) -> str`.
- Contract change (spec §4): `OverviewResult.riskiest_to_change: tuple[RankedSymbol, ...]`; `RankedSymbol.count` is the number of affected symbols.

- [ ] **Step 1: Write failing tests**

```python
# tests/query/test_models.py
import pytest

from compass_core.query.models import EdgeRef, ResultItem, SymbolRef
from compass_core.query.types import CallType, EdgeType, QualifiedName, RepoPath, SymbolId, SymbolKind, ViaKind


def _sym(**kw):
    base = dict(id=SymbolId("a.py::f"), kind=SymbolKind.FUNCTION, name="f",
                qualified_name=QualifiedName("a.f"), file_path=RepoPath("a.py"),
                line_start=1, line_end=2, signature="def f()")
    return SymbolRef(**{**base, **kw})


def test_line_must_be_one_indexed():
    with pytest.raises(ValueError):
        _sym(line_start=0)


def test_confidence_range():
    with pytest.raises(ValueError):
        EdgeRef(source_id=SymbolId("a"), target_id=SymbolId("b"), type=EdgeType.CALLS,
                confidence=1.5, call_type=CallType.DIRECT_IMPORT, line=3)


def test_only_calls_edges_carry_confidence():
    with pytest.raises(ValueError):
        EdgeRef(source_id=SymbolId("a"), target_id=SymbolId("b"), type=EdgeType.IMPORTS,
                confidence=1.0, call_type=None, line=None)


def test_distance_zero_has_no_via():
    from compass_core.query.models import Via
    with pytest.raises(ValueError):
        ResultItem(symbol=_sym(), distance=0, via=Via(kind=ViaKind.CALLS, symbol=_sym()),
                   min_confidence=None)
```

```python
# tests/query/test_params.py
import pytest

from compass_core.errors import InvalidArgumentError
from compass_core.query.params import MAX_DEPTH, ImpactParams, SearchParams


@pytest.mark.parametrize("depth", [0, MAX_DEPTH + 1, -1])
def test_depth_out_of_bounds(depth):
    with pytest.raises(InvalidArgumentError) as exc:
        ImpactParams(depth=depth)
    assert exc.value.argument == "depth"


def test_empty_search_query_rejected():
    with pytest.raises(InvalidArgumentError):
        SearchParams(query="  ")
```

```python
# tests/query/test_error_mappings.py
from compass_core.errors import ErrorCode
from compass_core.query.errors import ERROR_MAPPINGS


def test_mappings_cover_every_error_code():
    assert set(ERROR_MAPPINGS) == set(ErrorCode)
```

```python
# tests/query/test_serialize.py
from compass_core.query.results import SymbolNotFound
from compass_core.query.serialize import to_json


def test_not_found_serializes_enum_as_string():
    out = to_json(SymbolNotFound(reference="x", suggestions=()))
    assert '"outcome":"not_found"' in out.replace(" ", "")
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest packages/core/tests/query -v` → FAIL (imports).
- [ ] **Step 3: Implement** each file exactly per spec §5.2–§5.5, with these specifics:
  - `Outcome` values are lowercase (`"ok"`, `"ambiguous"`, `"not_found"`); `SymbolKind` values lowercase; `ErrorCode` values are their names.
  - `SymbolRef.__post_init__`: `line_start`/`line_end` must be `None` or ≥ 1; `line_end >= line_start` when both set.
  - `EdgeRef.__post_init__`: `confidence`/`call_type` set **iff** `type is EdgeType.CALLS`; `confidence` in `[0, 1]`.
  - `ResultItem.__post_init__`: `distance >= 0`; `via is None` iff `distance == 0`.
  - `ImpactParams` / `SearchParams`: `__post_init__` raises `InvalidArgumentError(argument="depth"|"limit"|"min_confidence"|"query", reason=...)`; bounds `1 ≤ depth ≤ MAX_DEPTH`, `1 ≤ limit ≤ MAX_LIMIT`, `0 ≤ min_confidence ≤ 1`.
  - `ERROR_MAPPINGS` (exit/http/mcp): INVALID_ARGUMENT 2/422/True, NOT_FOUND 3/404/False, AMBIGUOUS 4/409/False, INDEX_NOT_FOUND 5/503/True, INDEX_BUSY 6/503/True, INDEX_INCOMPATIBLE 7/503/True, QUERY_TIMEOUT 8/504/True, INTERNAL 1/500/True.
  - `serialize.py`: `_adapter(type)` cached with `functools.cache`; `to_json(obj)` uses `TypeAdapter(type(obj)).dump_json(obj).decode()`; `StrEnum`s serialize as their value, `tuple` as arrays, `frozenset` as arrays.
  - Docstrings per Global Constraints; each file under 500 lines.
- [ ] **Step 4: Run to verify pass.** If Pydantic rejects a `slots=True, kw_only=True` dataclass in `TypeAdapter`, keep the dataclasses plain and verify with the failing test before changing anything else.
- [ ] **Step 5: Gates (mypy strict on `query/`).**

---

### Task 5: Fixture repo, row mapping, reference resolution

**Files:**
- Create: `tests/fixtures/sample_repo/` (files below), `tests/query/conftest.py`, `query/rows.py`, `query/references.py`
- Test: `tests/query/test_rows.py`, `tests/query/test_references.py`

**Interfaces:**
- Consumes: `GraphDB`, types/models from Task 4.
- Produces:
  - `symbol_from_row(row: Sequence[Any], kind: SymbolKind, repo_root: Path) -> SymbolRef`
  - `ResolvedReference(symbol: SymbolRef, rule: MatchRule)`
  - `resolve(db: GraphDB, ref: str, *, repo_root: Path, allow_file: bool = False) -> Lookup[ResolvedReference]`
  - pytest fixtures `fixture_index` (session: `IndexLocation`) and `fixture_db` (read-only `GraphDB`)

Fixture files (create exactly):

```python
# sample_repo/app/__init__.py
from app.auth import decode_token  # re-export
```
```python
# sample_repo/app/auth.py
import json

def decode_token(raw):
    return parse(raw)

def parse(raw):
    return json.dumps(raw)

def lookup(obj, name):
    return getattr(obj, name)()   # unresolvable
```
```python
# sample_repo/app/models.py
class Base:
    def save(self):
        return 1

class User(Base):
    def save(self):          # overrides Base.save
        return super().save()

class Admin(User):
    pass
```
```python
# sample_repo/app/api.py
from app.auth import decode_token
from app.models import User

def handle(req):
    decode_token(req)
    return User().save()
```
```python
# sample_repo/app/cli.py
from app.auth import decode_token

def run():
    return decode_token("x")
```
```python
# sample_repo/app/jobs.py
from app.auth import decode_token

def nightly():
    return decode_token("y")

def run():                   # same bare name as cli.run → ambiguity
    return nightly()
```
```python
# sample_repo/app/util.py
def helper():
    return 1                 # imported by nobody → no importers
```

`app/auth.py` is imported by `api.py`, `cli.py`, `jobs.py` (3 files) and re-exported by `__init__.py`.

- [ ] **Step 1: Write failing tests**

```python
# tests/query/test_references.py
from compass_core.query.references import resolve
from compass_core.query.results import AmbiguousReference, SymbolNotFound
from compass_core.query.types import MatchRule


def test_exact_id(fixture_db, fixture_index):
    out = resolve(fixture_db, "app/auth.py::decode_token", repo_root=fixture_index.repo_root)
    assert out.rule is MatchRule.EXACT_ID and out.symbol.name == "decode_token"


def test_file_path_requires_allow_file(fixture_db, fixture_index):
    out = resolve(fixture_db, "app/auth.py", repo_root=fixture_index.repo_root, allow_file=True)
    assert out.rule is MatchRule.FILE_PATH
    miss = resolve(fixture_db, "app/auth.py", repo_root=fixture_index.repo_root)
    assert isinstance(miss, SymbolNotFound)


def test_bare_name_ambiguity_lists_both(fixture_db, fixture_index):
    out = resolve(fixture_db, "run", repo_root=fixture_index.repo_root)
    assert isinstance(out, AmbiguousReference)
    assert {c.file_path for c in out.candidates} == {"app/cli.py", "app/jobs.py"}


def test_class_member(fixture_db, fixture_index):
    out = resolve(fixture_db, "User.save", repo_root=fixture_index.repo_root)
    assert out.rule is MatchRule.CLASS_MEMBER


def test_not_found_has_suggestions(fixture_db, fixture_index):
    out = resolve(fixture_db, "decode", repo_root=fixture_index.repo_root)
    # bare-name rule needs an exact name; "decode" is a substring only
    assert isinstance(out, SymbolNotFound)
    assert any(s.name == "decode_token" for s in out.suggestions)
```

```python
# tests/query/test_rows.py
import pytest

from compass_core.errors import IndexIncompatibleError
from compass_core.query.rows import symbol_from_row
from compass_core.query.types import SymbolKind


def test_wrong_typed_column_raises_incompatible(tmp_path):
    with pytest.raises(IndexIncompatibleError):
        symbol_from_row(["id", 123, "f.py", 1, 2, "def f()"], SymbolKind.FUNCTION, tmp_path)


def test_stored_zero_line_becomes_none(tmp_path):
    sym = symbol_from_row(["f.py::f", "f", "f.py", 0, 0, "def f()"], SymbolKind.FUNCTION, tmp_path)
    assert sym.line_start is None
```

```python
# tests/query/conftest.py
from pathlib import Path
import shutil

import pytest

import compass_core.languages.python  # noqa: F401
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation, require_index
from compass_core.phases.pipeline import Pipeline

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_repo"


@pytest.fixture(scope="session")
def fixture_index(tmp_path_factory) -> IndexLocation:
    repo = tmp_path_factory.mktemp("sample_repo")
    shutil.copytree(FIXTURE, repo, dirs_exist_ok=True)
    Pipeline().run(repo, repo / ".compass" / "graph.ladybug")
    return require_index(repo)


@pytest.fixture
def fixture_db(fixture_index):
    with GraphDB(fixture_index.db_path, read_only=True) as db:
        yield db
```

- [ ] **Step 2: Run to verify failure** — FAIL (modules missing).
- [ ] **Step 3: Implement.**
  - `rows.py`: `symbol_from_row` takes columns `[id, name, file_path, line_start, line_end, signature]`; each value checked with `isinstance`, a mismatch raises `IndexIncompatibleError("unexpected column type …")`; absolute `file_path` is made repo-relative POSIX with `Path(file_path).relative_to(repo_root)` (fall back to the stored string if it is already relative); `0` lines → `None`; file ids `file::<path>`, external ids `ext::<full_ref>`; `qualified_name` for Function/Class is built from the file's dotted module (`File.module_name`) plus the id's `[Class.]name` tail. **Before writing this, run one scratch query against the fixture index to see the real stored `File.path` form (absolute or relative) and `module_name`, and write the repo-relative conversion to match it.**
  - `references.py`: apply spec §4.1's order (exact id → file path (only if `allow_file`) → qualified name → path+name → `Class.member` → bare name). Bare-name with ≥ 2 hits returns `AmbiguousReference` ordered by `MatchRule` then fan-in (count of incoming `CALLS`); no hit returns `SymbolNotFound` with ≤ 5 case-insensitive substring suggestions (`WHERE lower(f.name) CONTAINS lower($q)`).
  - Cypher is always parameterized (`$q`, `$id`); never f-string user input.
- [ ] **Step 4: Run to verify pass.** Read spec §4.1 once more if a rule's order is in doubt, and keep the test as the arbiter.
- [ ] **Step 5: Gates.**

---

### Task 6: `find_symbols`

**Files:** Create `query/search.py`; Test `tests/query/test_search.py`

**Interfaces:**
- Consumes: `GraphDB`, `SearchParams`, `rows.symbol_from_row`, `Task 2` metadata (for `IndexStatus`).
- Produces: `find_symbols(db: GraphDB, location: IndexLocation, params: SearchParams) -> SearchResult`, and a shared `index_status(location: IndexLocation, db: GraphDB) -> IndexStatus` in `query/status.py`.

- [ ] **Step 1: Write failing tests**

```python
def test_exact_name_ranks_first(fixture_db, fixture_index):
    res = find_symbols(fixture_db, fixture_index, SearchParams(query="parse"))
    assert res.hits[0].symbol.name == "parse" and res.hits[0].match is SearchMatch.EXACT


def test_kind_filter(fixture_db, fixture_index):
    res = find_symbols(fixture_db, fixture_index, SearchParams(query="a", kind=SymbolKind.CLASS))
    assert {h.symbol.kind for h in res.hits} == {SymbolKind.CLASS}


def test_limit_and_total(fixture_db, fixture_index):
    res = find_symbols(fixture_db, fixture_index, SearchParams(query="a", limit=1))
    assert len(res.hits) == 1 and res.total > 1 and res.truncated


def test_files_are_searchable(fixture_db, fixture_index):
    res = find_symbols(fixture_db, fixture_index, SearchParams(query="auth.py"))
    assert any(h.symbol.kind is SymbolKind.FILE for h in res.hits)
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.** Query Files (match on `path`), Classes and Functions (match on `name`) with `lower(x) CONTAINS lower($q)`; classify each hit as `EXACT` / `QUALIFIED_SUFFIX` / `PREFIX` / `SUBSTRING`; sort by match rank then `fan_in` (incoming `CALLS` count for functions, incoming `IMPORTS` for files) then name; slice to `limit`; `total` is the pre-slice count; `truncated = total > limit`. `index_status` builds `IndexStatus` from `load_metadata` and counts stale files (`mtime > indexed_at` or missing) using `File.path`s.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Gates.**

---

### Task 7: `impact`

**Files:** Create `query/impact.py`; Test `tests/query/test_impact.py`

**Interfaces:**
- Consumes: `resolve`, `ImpactParams`, `index_status`, `symbol_from_row`.
- Produces: `impact(db: GraphDB, location: IndexLocation, ref: str, params: ImpactParams) -> Lookup[ImpactResult]`.

Approach: breadth-first search in Python, one parameterized single-hop query per level (`WHERE b.id IN $ids`). This gives exact shortest distance, trivially handles cycles, and tracks the path's minimum `CALLS` confidence. Variable-length Cypher is avoided because its distance semantics are harder to pin in tests.

- [ ] **Step 1: Write failing tests**

```python
def test_file_target_lists_three_importers_at_distance_one(fixture_db, fixture_index):
    res = impact(fixture_db, fixture_index, "app/auth.py", ImpactParams(depth=1))
    files = {g.file_path for g in res.groups if g.distance == 1}
    assert {"app/api.py", "app/cli.py", "app/jobs.py"} <= files


def test_symbol_target_walks_reverse_calls(fixture_db, fixture_index):
    res = impact(fixture_db, fixture_index, "app/auth.py::parse", ImpactParams(depth=3))
    by_dist = {(g.distance, i.symbol.name) for g in res.groups for i in g.items}
    assert (1, "decode_token") in by_dist
    assert {(2, "handle"), (2, "run"), (2, "nightly")} <= by_dist   # callers of decode_token


def test_depth_limits_the_walk(fixture_db, fixture_index):
    res = impact(fixture_db, fixture_index, "app/auth.py::parse", ImpactParams(depth=1))
    assert max(g.distance for g in res.groups) == 1


def test_target_without_dependents_is_empty_not_error(fixture_db, fixture_index):
    res = impact(fixture_db, fixture_index, "app/util.py", ImpactParams())
    assert res.groups == () and res.total == 0


def test_cycle_terminates_and_lists_each_node_once(tmp_path):
    repo = tmp_path / "cycle"
    repo.mkdir()
    (repo / "a.py").write_text("from b import b\n\ndef a():\n    return b()\n")
    (repo / "b.py").write_text("from a import a\n\ndef b():\n    return a()\n")
    Pipeline().run(repo, repo / ".compass" / "graph.ladybug")
    location = require_index(repo)

    with GraphDB(location.db_path, read_only=True) as db:
        res = impact(db, location, "a.py::a", ImpactParams(depth=5))

    names = [i.symbol.name for g in res.groups for i in g.items]
    assert names == ["b"]                       # b once, at distance 1; the target never lists itself
    assert res.groups[0].distance == 1


def test_unresolved_calls_caveat_present(fixture_db, fixture_index):
    res = impact(fixture_db, fixture_index, "app/auth.py::lookup", ImpactParams())
    assert any(c.code is CaveatCode.UNRESOLVED_CALLS for c in res.caveats)
```

```python
def test_ambiguous_ref_returns_candidates(fixture_db, fixture_index):
    assert isinstance(impact(fixture_db, fixture_index, "run", ImpactParams()), AmbiguousReference)


def test_truncation_flag(fixture_db, fixture_index):
    res = impact(fixture_db, fixture_index, "app/auth.py", ImpactParams(limit=1))
    assert res.truncated and sum(len(g.items) for g in res.groups) == 1
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.**
  1. `resolve(..., allow_file=True)`; pass `AmbiguousReference`/`SymbolNotFound` straight through.
  2. Symbol target: frontier = `{target.id}`; for each distance `1..depth`, query reverse `CALLS` (`MATCH (a:Function)-[r:CALLS]->(b:Function) WHERE b.id IN $ids AND r.confidence >= $minc RETURN a.id, b.id, r.confidence`); skip ids already seen; record `Via(kind=CALLS, symbol=<the callee it was reached through>)` and `min_confidence = min(path_min, r.confidence)`. For a class target also seed the frontier with its methods and add subclasses (`MATCH (c:Class)-[:INHERITS]->(p:Class) WHERE p.id IN $ids`) with `Via(INHERITS)`.
  3. File target: seed with the file's definitions; per level add (a) importers (`MATCH (a:File)-[:IMPORTS]->(b:File) WHERE b.path IN $paths`, `Via(IMPORTS)`), (b) files containing callers of any symbol defined in the frontier files (`Via(CALLS)`), (c) files with subclasses (`Via(INHERITS)`).
  4. Group items by `(distance, file_path)` into `ImpactGroup`s, sorted by distance then path; `total` = item count before truncation; apply `limit` over items in that order and set `truncated`.
  5. Caveat: count `raw_calls` entries in affected functions that produced no `CALLS` edge (`Function.raw_calls` minus resolved callee names); if > 0, add `Caveat(UNRESOLVED_CALLS, message, count)`. Add `STALE_INDEX` when `index_status.stale_file_count > 0`.
  6. `affected_file_count` = distinct group `file_path`s.
  Keep the module under 500 lines; split `_expand_symbols` / `_expand_files` helpers into `query/_impact_walk.py` if it grows.
- [ ] **Step 4: Run to verify pass.** If `IN $ids` does not accept a list parameter in LadybugDB, verify in a scratch query and fall back to `UNWIND $ids AS id MATCH …`.
- [ ] **Step 5: Gates.**

---

### Task 8: `overview` with riskiest-to-change

**Files:** Create `query/overview.py`; Test `tests/query/test_overview.py`

**Interfaces:**
- Produces: `overview(db: GraphDB, location: IndexLocation) -> OverviewResult` with `counts: IndexCounts(files, classes, functions, edges_by_type: Mapping[EdgeType, int])`, `entry_points`, `most_imported_files: tuple[RankedSymbol, ...]`, `most_called_functions`, `top_external_libraries: tuple[LibraryUsage, ...]`, `riskiest_to_change: tuple[RankedSymbol, ...]` (top 5 functions/methods by number of affected symbols at depth 3).

- [ ] **Step 1: Write failing tests**

```python
def test_counts(fixture_db, fixture_index):
    res = overview(fixture_db, fixture_index)
    assert res.counts.files >= 7 and res.counts.classes == 3
    assert res.counts.edges_by_type[EdgeType.IMPORTS] > 0


def test_most_imported_file_is_auth(fixture_db, fixture_index):
    res = overview(fixture_db, fixture_index)
    assert res.most_imported_files[0].symbol.file_path == "app/auth.py"
    assert res.most_imported_files[0].count == 3


def test_riskiest_is_parse_or_decode_token(fixture_db, fixture_index):
    res = overview(fixture_db, fixture_index)
    assert res.riskiest_to_change[0].symbol.name in {"parse", "decode_token"}
    assert res.riskiest_to_change[0].count >= 3


def test_external_libraries(fixture_db, fixture_index):
    libs = {l.library: l.call_count for l in overview(fixture_db, fixture_index).top_external_libraries}
    assert libs.get("json") == 1


def test_empty_index_has_empty_lists(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    (repo / "x.py").write_text("x = 1\n")
    Pipeline().run(repo, repo / ".compass" / "graph.ladybug")
    location = require_index(repo)

    with GraphDB(location.db_path, read_only=True) as db:
        res = overview(db, location)

    assert res.counts.functions == 0 and res.counts.classes == 0
    assert res.most_imported_files == () and res.most_called_functions == ()
    assert res.top_external_libraries == () and res.riskiest_to_change == ()
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.** Counts via `count(*)` queries per label/rel; most-imported by incoming `IMPORTS` count; most-called by incoming `CALLS` distinct callers; libraries by `CALLS_EXTERN` count grouped by `ExternalFunction.library`; riskiest: compute `impact`-style affected counts with the Task 7 walker for the top 30 functions by fan-in (cap at 30 to bound cost), sort descending, take 5. Document the cap in the docstring.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Gates.**

---

### Task 9: HTTP routes and error handling

**Files:**
- Create: `server/routers/query.py`
- Modify: `server/main.py`, `server/routers/repo.py` (no change; stays)
- Test: `packages/core/tests/server/test_query_routes.py`

**Interfaces:**
- Produces: `GET /api/search?q=&kind=&limit=` → `SearchResult`; `GET /api/impact?ref=&depth=&min_confidence=&limit=` → `ImpactResult`; `GET /api/overview` → `OverviewResult`. Ambiguity → 409 `AmbiguousReference` body; not found → 404 `SymbolNotFound` body; other failures → `ErrorResponse` with the status from `ERROR_MAPPINGS`.
- The routes open the index through a FastAPI dependency `get_db()` that calls `require_index(Path.cwd(), override=Path(settings.LADYBUG_DB_PATH) if env set)` and yields a read-only `GraphDB`, so tests override it.

- [ ] **Step 1: Write failing tests**

```python
@pytest.fixture
def client(fixture_index):
    app.dependency_overrides[get_index] = lambda: fixture_index
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_impact_ok(client):
    r = client.get("/api/impact", params={"ref": "app/auth.py", "depth": 1})
    assert r.status_code == 200 and r.json()["operation"] == "impact"
    assert r.json()["affected_file_count"] >= 3


@pytest.mark.parametrize("depth", ["0", "11", "abc"])
def test_bad_depth_is_422_error_response(client, depth):
    r = client.get("/api/impact", params={"ref": "app/auth.py", "depth": depth})
    assert r.status_code == 422 and r.json()["code"] == "INVALID_ARGUMENT"


def test_ambiguous_ref_is_409_with_candidates(client):
    r = client.get("/api/impact", params={"ref": "run"})
    assert r.status_code == 409 and len(r.json()["candidates"]) == 2


def test_unknown_ref_is_404_with_suggestions(client):
    r = client.get("/api/impact", params={"ref": "decode"})
    assert r.status_code == 404 and r.json()["suggestions"]


def test_missing_index_is_503(tmp_path):
    def no_index():
        raise IndexNotFoundError(searched_from=tmp_path)
    app.dependency_overrides[get_index] = no_index
    r = TestClient(app).get("/api/overview")
    app.dependency_overrides.clear()
    assert r.status_code == 503 and r.json()["code"] == "INDEX_NOT_FOUND"


def test_search_and_overview(client):
    assert client.get("/api/search", params={"q": "parse"}).json()["hits"]
    assert client.get("/api/overview").json()["riskiest_to_change"]


def test_openapi_names_a_schema_for_every_new_route(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/search", "/api/impact", "/api/overview"):
        assert "200" in paths[p]["get"]["responses"]
```

- [ ] **Step 2: Run to verify failure.**
- [ ] **Step 3: Implement.**
  - Parameters: `depth: Annotated[int, Query(ge=1, le=MAX_DEPTH)] = 3`, `min_confidence: Annotated[float, Query(ge=0, le=1)] = 0.0`, `limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50`, `kind: SymbolKind | None`.
  - Routes build the `…Params` object and call the query function; `AmbiguousReference` / `SymbolNotFound` results are returned via `JSONResponse(status_code=409|404, content=<to_json>)` (routes contain no `try`/`except`).
  - In `main.py` register once: a `QueryError` handler that maps `exc.code` through `ERROR_MAPPINGS` to `ErrorResponse` (adding `Retry-After` for `INDEX_BUSY`), and a `RequestValidationError` handler that reshapes FastAPI's 422 into `ErrorResponse(code=INVALID_ARGUMENT, ...)`.
  - `response_model=` is the result dataclass; `responses={409: {"model": AmbiguousReference}, 404: {"model": SymbolNotFound}, 422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}`.
  - Allow `?` CORS unchanged.
- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Gates.** Then commit point 1 (backend): ask the user for the branch before committing.

---

## Frontend

> The web app has no unit-test runner today. Each web task is verified with `pnpm exec tsc --noEmit`, `pnpm build`, and the manual check listed in the task, run against `compass serve` on a real index. Adding a runner is out of scope.

### Task 10: Generated API types and typed client

**Files:**
- Modify: `apps/web/package.json`, `apps/web/src/lib/api.ts`, `Makefile` (or root script)
- Create: `apps/web/src/lib/api-types.ts` (generated), `packages/core/scripts/dump_openapi.py`

**Interfaces:**
- Produces: `searchSymbols(q: string, kind?: SymbolKind, signal?: AbortSignal): Promise<SearchResult>`, `getImpact(ref: string, opts: {depth: number; signal?: AbortSignal}): Promise<ImpactOutcome>` where `type ImpactOutcome = {status: "ok"; data: ImpactResult} | {status: "ambiguous"; data: AmbiguousReference} | {status: "not_found"; data: SymbolNotFound}`, `getOverview(signal?): Promise<OverviewResult>`, and `class ApiError extends Error { code: ErrorCode; status: number }`. Types are re-exported from `api-types.ts` (`components["schemas"]["ImpactResult"]` aliased).

- [ ] **Step 1:** `dump_openapi.py` imports `compass_core.server.main.app` and prints `json.dumps(app.openapi())` to the path in `argv[1]`. Add `"gen:api": "openapi-typescript ../../.build/openapi.json -o src/lib/api-types.ts"` to `apps/web/package.json` and `openapi-typescript` to devDependencies; add `make openapi gen-api` targets that run the dump then the generator.
- [ ] **Step 2:** `pnpm add -D openapi-typescript` in `apps/web`; run the two commands; confirm `api-types.ts` contains `ImpactResult` and `ErrorResponse`.
- [ ] **Step 3:** In `api.ts` keep `apiFetch` and add the three functions plus `ApiError`. `getImpact` treats 200 as `ok`, 409 as `ambiguous`, 404 as `not_found`, and throws `ApiError` (parsed from the `ErrorResponse` body) for any other non-2xx status. No hand-written response interfaces and no `any`.
- [ ] **Step 4: Verify** — `pnpm exec tsc --noEmit` passes.
- [ ] **Step 5:** `pnpm build` passes.

---

### Task 11: Theme tokens, fonts and the left rail

**Files:**
- Modify: `apps/web/src/styles/globals.css`, `apps/web/src/app/layout.tsx`, `apps/web/src/app/page.tsx`
- Create: `apps/web/src/components/shell/NavRail.tsx`, `apps/web/src/components/shell/useWorkspaceView.ts`, `apps/web/src/components/workspace/Workspace.tsx`
- Delete: `apps/web/src/components/project/WorkspaceTabs.tsx` (replaced by `Workspace.tsx`)

**Interfaces:**
- Produces: `type WorkspaceView = "overview" | "graph" | "impact"`; `useWorkspaceView(): { view: WorkspaceView; focus: string | null; setView(view: WorkspaceView, focus?: string | null): void }` backed by `?view=&focus=` (`view=explore` accepted as `graph`); `<NavRail items={...} active={view} onSelect={setView} />` with `items: ReadonlyArray<{ id: WorkspaceView; label: string; icon: LucideIcon }>`.

- [ ] **Step 1: Theme.** In `globals.css`, replace the `:root` and dark values with the v5 tokens, mapped onto the existing shadcn variables so components restyle without edits:

| shadcn variable | v5 token (dark / light) |
|---|---|
| `--background` | `#1a1817` / `#f3f2f2` |
| `--card`, `--popover` | `#201e1d` / `#f8f7f6` |
| `--muted` | `#282625` / `#eae9e9` |
| `--border` | `color-mix(in srgb, #f3f2f2 10%, transparent)` / `color-mix(in srgb, #201f1d 14%, transparent)` |
| `--foreground` | `#f3f2f2` / `#201f1d` |
| `--muted-foreground` | `#9b9797` / `#6f6b6b` |
| `--primary` | `#e1ad66` / `#b68235` |
| `--primary-foreground` | `#3a270d` / `#fff3e4` |
| `--accent` | `color-mix(in srgb, #e1ad66 13%, transparent)` / `color-mix(in srgb, #b68235 13%, transparent)` |

Add only these new variables (and expose them in `@theme`): `--kind-file`, `--kind-class`, `--kind-function`, `--kind-method`, `--kind-external`, `--edge-imports`, `--edge-calls`, `--edge-inherits`, `--edge-contains`, with the oklch values from the design file's `--k-*` / `--e-*` tokens (dark and light sets). Dark/light follow `prefers-color-scheme`: switch the `@custom-variant dark` rule to `@media (prefers-color-scheme: dark)` and remove the dependence on a `.dark` class.
- [ ] **Step 2: Fonts.** In `layout.tsx` load Geist and JetBrains Mono with `next/font/google`, exposing `--font-sans` and `--font-mono` on `<body>`; reference them in `@theme`.
- [ ] **Step 3: Rail.** `NavRail.tsx`: a 56 px-wide column using shadcn `Tooltip` + `Button` (`variant="ghost"`, `size="icon"`), `cursor-pointer`, the active item with `bg-accent text-primary`, icons `LayoutDashboard`, `Orbit`, `Target` from `lucide-react`; props are data only (no routing inside). `useWorkspaceView.ts` reads/writes `useSearchParams` + `useRouter().replace` (shallow), validating `view` against the three values and defaulting to `overview`.
- [ ] **Step 4: Workspace.** `Workspace.tsx` renders `<NavRail>` beside the active view (placeholders `<OverviewView/>`, `<GraphView/>`, `<ImpactView/>` imported from their feature folders as they land; until Tasks 12–14, render the existing `OverviewTab` / `GraphTab` and a short "Impact" stub). Update `page.tsx` to render `Workspace` inside `Suspense` (required for `useSearchParams`).
- [ ] **Step 5: Verify** — `tsc`, `pnpm build`; manually: run `uv run compass serve`, open the app, confirm the amber/warm theme in both OS appearances, rail switching updates the URL, and `?view=explore` opens Graph.

---

### Task 12: Impact view

**Files (all new, under `apps/web/src/components/impact/`):**
- `ImpactView.tsx` — data fetching and state; composes the pieces below
- `TargetPicker.tsx` — search box with results list (uses `searchSymbols`, debounced 200 ms, `AbortController`)
- `ImpactTargetCard.tsx` — header: kind icon/badge, name, location, affected counts
- `ImpactGroupList.tsx` — groups by distance; rows via `ImpactRow.tsx`
- `ImpactRow.tsx` — name, `file:line`, "via" text, confidence
- `DepthControl.tsx` — 1..10 stepper (shadcn `Button` + `lucide` `Minus`/`Plus`)
- `ImpactStates.tsx` — `AmbiguousChooser`, `NotFoundHint`, `CaveatBanner`, `ErrorNotice`, `EmptyImpact`
- `viaText.ts` — `viaText(via: Via): string` ("calls write", "imports", "subclass of", …)

**Interfaces:**
- Consumes: `getImpact`, `searchSymbols`, `ImpactOutcome`, `useWorkspaceView` (focus = target ref; `setView("graph", id)` for "Show in graph").
- Presentational components take data and callbacks only; `ImpactView` is the one stateful container (target, depth, request state).

- [ ] **Step 1:** Implement `viaText.ts` with an exhaustive `switch` over `ViaKind` ending in a `never` check, and `ImpactGroupList` rendering one section per `distance` ("Direct (1 hop)", "2 hops", …) with a count badge, rows as buttons (`cursor-pointer`) that call `onRetarget(symbol.id)`.
- [ ] **Step 2:** `ImpactView` state machine: `idle` (no target: show the picker and a hint) → `loading` (shadcn `Skeleton`) → `ok | ambiguous | not_found | error`. Changing target or depth aborts the in-flight request. `focus` from the URL seeds the target; retarget calls `setView("impact", id)`.
- [ ] **Step 3:** States: `ok` with zero groups → `EmptyImpact` ("Nothing depends on this"); a result with an `UNRESOLVED_CALLS` caveat → `CaveatBanner` above the list with the caveat message; `ambiguous` → `AmbiguousChooser` listing candidates (click re-requests with the candidate id); `not_found` → `NotFoundHint` with clickable suggestions; `ApiError` with `INDEX_NOT_FOUND`/`INDEX_BUSY`/`INDEX_INCOMPATIBLE` → `ErrorNotice` with a message per code ("Run `compass ingest`", "Index is rebuilding, retry", "Re-ingest needed").
- [ ] **Step 4:** "Show in graph" button (`lucide` `Orbit`) → `setView("graph", target.id)`.
- [ ] **Step 5: Verify** — `tsc`, `pnpm build`; manually against a real index: search `decode_token`, see grouped results; pick an ambiguous bare name (`run`), see the chooser; enter a nonsense name, see suggestions; stop the backend, see the unavailable notice; use a file path target and see file-level groups. Every file < 500 lines.

---

### Task 13: Overview view

**Files (new, under `apps/web/src/components/overview/`):** `OverviewView.tsx` (fetch + state), `StatTile.tsx`, `BreakdownBar.tsx` (entity/edge breakdowns), `InsightCard.tsx` (title, icon, description, rows), `InsightRow.tsx` (icon, name, location, metric, bar), `InsightGroup.tsx`.

**Interfaces:**
- Consumes: `getOverview`, `OverviewResult`; `useWorkspaceView` for row clicks (riskiest → `setView("impact", id)`; others → `setView("graph", id)`).
- `InsightCard` props: `{ title: string; description: string; icon: LucideIcon; badge?: string; rows: ReadonlyArray<InsightRowData>; emptyText: string }`, `InsightRowData = { id: string; name: string; location: string; metric: string; barPercent: number; kind: SymbolKind }`.

- [ ] **Step 1:** Map `OverviewResult` → card data in `overviewCards.ts` (pure functions, one per card: riskiest, most-imported, most-called, external libraries). `barPercent` = value / max of that card.
- [ ] **Step 2:** Build the components with shadcn `Card`, `Badge`, `Skeleton`; metric bars use `bg-primary` / kind tokens; group the four cards as "Impact" (riskiest, most-imported) and "Usage" (most-called, libraries) matching the design.
- [ ] **Step 3:** Empty states per card ("No resolved calls yet" for most-called; "No external calls found" for libraries) and an `ErrorNotice` reused from `impact/ImpactStates.tsx` — move it to `components/ui/` as `InlineError.tsx` and import from there in both views (shared/reusable lives in `ui/`).
- [ ] **Step 4: Verify** — `tsc`, `pnpm build`; manually: counts match `compass` data (200 files / 868 functions on this repo), clicking a riskiest row lands on Impact with that target.

---

### Task 14: Graph restyle and focus

**Files:**
- Modify: `apps/web/src/components/project/graph/GraphLegend.tsx`, `DetailsPanel.tsx`, `graphStyle.ts`, `apps/web/src/components/project/GraphTab.tsx` (rename to `graph/GraphView.tsx`)

**Interfaces:**
- Consumes: `useWorkspaceView().focus`.
- Produces: `GraphView` selects and centers the node whose `id` equals `focus`, if present.

- [ ] **Step 1:** Replace hard-coded colors in `graphStyle.ts` with the new `--kind-*` / `--edge-*` tokens (read once via `getComputedStyle(document.documentElement)`, re-read on `prefers-color-scheme` change).
- [ ] **Step 2:** Restyle `GraphLegend` (rows with kind color dots, counts, "Show labels" switch) and `DetailsPanel` using card/muted tokens and `font-mono` for paths; add a "Show impact" button (`Target` icon) → `setView("impact", node.id)`. The panel's source preview calls `/api/repo/file`, which doesn't exist; show "Source preview unavailable" instead of the failing fetch until the `/api/source` endpoint lands (out of scope here).
- [ ] **Step 3:** On mount and when `focus` changes, call the canvas's select/center (extend `GraphCanvas3D` with an optional `focusId` prop that selects and camera-centers that node; no other behavior change).
- [ ] **Step 4: Verify** — `tsc`, `pnpm build`; manually: Graph renders with the new palette in both appearances; "Show in graph" from Impact centers the node; "Show impact" returns to Impact.

---

### Task 15: End-to-end verification

- [ ] **Step 1:** `uv run compass ingest` on this repo, `uv run compass serve`, and (in `apps/web`) `pnpm dev`; click through Overview → riskiest row → Impact → Show in graph → Show impact.
- [ ] **Step 2:** Re-ingest while the UI is open and confirm Impact still loads (or shows the "rebuilding" notice), and that the second ingest does not change the edge counts (`MATCH ()-[r]->() RETURN count(*)`).
- [ ] **Step 3:** Full gates: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `cd packages/core && uv run mypy`, `cd apps/web && pnpm exec tsc --noEmit && pnpm build`.
- [ ] **Step 4:** `wc -l` every new/changed web file; confirm none exceeds 500 lines.
- [ ] **Step 5:** Report results faithfully, including anything not verified (for example, light-mode visuals if only dark was checked).
