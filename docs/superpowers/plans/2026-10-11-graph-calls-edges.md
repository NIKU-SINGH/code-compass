# Graph Tab: Show Function Call Edges — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or superpowers:subagent-driven-development) to implement this plan task-by-task, and superpowers:test-driven-development for Task 1. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the user turns on the Functions filter in the Graph tab, arrows appear between functions that call each other.

**Root cause (verified 2026-10-11):** `_graph_edges` in `packages/core/src/compass_core/server/routers/repo.py` (lines 158–187) only queries `CONTAINS`, `IMPORTS` and `INHERITS`. It never queries `CALLS`, so `/api/repo/graph` returns no call edges even though the index has them:

| Layer | State |
|---|---|
| Index (`.compass/graph.ladybug`) | 193 `CALLS` edges (183 function → function, 10 involving a method) |
| `GET /api/repo/graph` (live server) | 747 `CONTAINS`, 284 `IMPORTS`, 17 `INHERITS`, **0 `CALLS`** |
| Frontend | Already handles `CALLS`: type in `useGraphData.ts`, toggle (on by default) in `useExpandableGraph.ts`, colour/label/legend in `graphStyle.ts` and `GraphLegend.tsx` |

**Architecture:** This is a backend-only change. Add one query to `_graph_edges` that emits `CALLS` edges between `Function` nodes. Methods are stored as `Function` nodes with `is_method = true`, so the same query covers method calls. Node ids already match: `_graph_nodes` uses `fn.id` as the node id, and `CALLS` connects `Function` nodes by `id`.

**Tech Stack:** Python 3.11, FastAPI, LadybugDB, pytest, ruff, mypy.

## Global Constraints

- **Do not change the frontend.** It already supports `CALLS`. `GraphEdge.type` is a plain `str`, so no regeneration of `apps/web/src/lib/api-types.ts` is needed.
- **Do not change the schema** (`graph/schema.py`) or the writer (`graph/writer.py`).
- New tests go under `packages/core/tests/server/`, never inline or ad hoc.
- Use Google-style docstrings on any new public function (`CLAUDE.md`).
- Don't commit unless the user asks. Never commit to `qa` or `main`. Ask the user for the branch name first.
- The task ends green: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `cd packages/core && uv run mypy`.

## Out of Scope

Don't do these. They are possible follow-ups.

- **`CALLS_EXTERN` edges.** Their targets are `ExternalFunction` nodes, which `_graph_nodes` doesn't emit. The UI's `ExternalDep` node filter is unused for the same reason. Fixing it needs a new node type in the response.
- **Sending call `confidence` / `line` on `GraphEdge`.** This would only matter for a future "hide low-confidence calls" filter.
- **Calls to classes** (constructor calls). The writer deliberately doesn't store these (see `_write_call_edge` in `graph/writer.py`).

---

## Task 1: Emit `CALLS` edges from `/api/repo/graph`

**Files:**
- Modify: `packages/core/src/compass_core/server/routers/repo.py` (`_graph_edges`, lines 158–187)
- Create: `packages/core/tests/server/test_repo_graph_calls.py`

### Fixture facts

The session fixture `fixture_index` (`packages/core/tests/conftest.py`) indexes `tests/fixtures/sample_repo`. That index has exactly these five `CALLS` edges (stored ids):

| source | target | note |
|---|---|---|
| `py::app.api::handle` | `py::app.auth::decode_token` | function → function |
| `py::app.cli::run` | `py::app.auth::decode_token` | function → function |
| `py::app.jobs::nightly` | `py::app.auth::decode_token` | function → function |
| `py::app.scheduler::tick` | `py::app.jobs::nightly` | function → function |
| `py::app.models::User.save` | `py::app.models::Base.save` | method → method (confidence 0.8) |

### Steps

- [ ] **Step 1: Write the failing test.** Create `packages/core/tests/server/test_repo_graph_calls.py`. Follow the pattern in `test_repo_graph_public_ids.py`: monkeypatch `settings.LADYBUG_DB_PATH` to `fixture_index.db_path`, then call `/api/repo/graph` with `TestClient(app)`. Write these tests:
  1. `test_graph_includes_call_edges`: the set of `(source, target)` pairs for edges with `type == "CALLS"` equals the five pairs in the table above.
  2. `test_call_edges_connect_emitted_nodes`: every `CALLS` edge's `source` and `target` is the `id` of a node in the same response. This guards against edges the UI would silently drop.
  3. `test_method_call_edge_present`: `("py::app.models::User.save", "py::app.models::Base.save")` is a `CALLS` edge, and both endpoints have node `type == "Method"`. This shows the method case works.
  4. `test_edge_ids_unique`: all edge `id`s in the response are unique.

  Give the module a one-line docstring like the sibling test files.

- [ ] **Step 2: Run it and confirm it fails.**
  ```bash
  cd packages/core && uv run pytest tests/server/test_repo_graph_calls.py -v
  ```
  Expected: tests 1–3 fail, because there are no `CALLS` edges. Test 4 passes.

- [ ] **Step 3: Implement.** In `_graph_edges`, after the `INHERITS` block and before `return edges`, add:
  ```python
  for row in as_rows(db.execute("MATCH (a:Function)-[:CALLS]->(b:Function) RETURN a.id, b.id")):
      _add(row[0], row[1], "CALLS")
  ```
  Keep the existing `_add` helper. It already de-duplicates on `(source, target, type)`, which matters because one function can call another from several lines.

- [ ] **Step 4: Run the new tests. They should pass.**
  ```bash
  cd packages/core && uv run pytest tests/server/test_repo_graph_calls.py -v
  ```

- [ ] **Step 5: Run the full checks.**
  ```bash
  uv run pytest
  uv run ruff check .
  uv run ruff format --check .
  cd packages/core && uv run mypy
  ```
  All must pass. If an existing test asserts an exact edge count or exact set of edge types from `/api/repo/graph`, update it to include `CALLS`. Don't weaken it.

## Task 2: Manual check in the UI

- [ ] **Step 1:** Restart the API server so it picks up the change. Confirm the live payload now contains call edges:
  ```bash
  curl -s http://localhost:8000/api/repo/graph | python3 -c "import json,sys,collections;d=json.load(sys.stdin);print(collections.Counter(e['type'] for e in d['edges']))"
  ```
  Expected for this repo's index: `CALLS: 193` alongside the existing counts.
- [ ] **Step 2:** In the web app Graph tab, turn on **Functions** (with Files off). Arrows labelled "Calls" should connect functions. Turn on **Methods** too to see the 10 method-involved calls.
- [ ] **Step 3:** Report the result. Note in the report that most of the 595 functions will still have no arrows (only ~171 take part in an internal call). That's expected, not a bug.

## Review Focus

1. **Edge endpoints must match node ids.** `_graph_nodes` skips definitions whose stored id is malformed (`IndexIncompatibleError`). A `CALLS` edge to a skipped node would point at nothing. The UI drops such edges, so this is harmless today, and Task 1 test 2 pins the normal case.
2. **Duplicates.** Multiple call sites between the same pair must produce one edge, via `_add`'s `seen` set.
