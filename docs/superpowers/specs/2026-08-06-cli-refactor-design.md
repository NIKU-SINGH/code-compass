# CLI Refactor: commands/ directory, typed objects, ingest rename

## Problem

`packages/cli/src/compass_cli/main.py` mixes Typer app wiring, argument
parsing, and full command orchestration logic for both `index` and `serve`
in one file. Command output data (9 loose kwargs passed into
`display.summary()`) has no shared type. The primary command is named
`index`, which reads as "look something up" rather than "ingest a repo into
the graph" — `ingest` is a clearer name for what the command does.

## Goals

1. One file per command under a new `commands/` directory.
2. Replace loose kwargs for command results with typed dataclasses.
3. Rename the `index` command to `ingest` (full rename, no alias).
4. Rename `compass_core.indexer` → `compass_core.ingest` for naming
   consistency across packages (single importer: the CLI).

## Non-goals

- No behavior change to indexing/graph logic itself.
- No new CLI commands or options.
- No mypy/type-checking enforcement setup (typed dataclasses only).

## File layout

```
packages/cli/src/compass_cli/
  __init__.py
  main.py            # Typer app wiring + no-args help callback only
  types.py           # NEW — IngestSummary dataclass
  display.py         # shared console + all rendering functions
  progress.py         # RichProgressReporter (unchanged)
  commands/
    __init__.py
    ingest.py         # `ingest` command: parsing + orchestration
    serve.py          # `serve` command: parsing + orchestration + _wait_for_server

packages/core/src/compass_core/
  ingest/              # renamed from indexer/
    __init__.py
    engine.py          # unchanged contents (parse_files, save_metadata)
```

`main.py` responsibilities shrink to: construct the `Typer` app, register
`ingest` and `serve` from `commands/`, and keep the `invoke_without_command`
callback that prints `display.help_commands()`.

`display.py` keeps both generic primitives (`console`, `step`,
`phase_header`, `phase_done`, `help_commands`) and per-command composite
renderers (e.g. the ingest summary panel, `next_steps`). It is the shared
module home per the "commands/ + shared modules at root" layout decision.

## Typed objects

`compass_cli/types.py` adds:

```python
@dataclass(frozen=True)
class IngestSummary:
    file_count: int
    class_count: int
    function_count: int
    elapsed: float
    node_count: int
    edge_count: int
    db_path: Path
    db_size: int
    skipped: int
```

`commands/ingest.py` builds one `IngestSummary` after the pipeline
completes and passes it to `display.summary(summary: IngestSummary)`,
replacing the current 9 separate keyword arguments.

## Rename: `index` → `ingest`

Full rename, no backward-compatible alias. Touches:

- `compass_cli/commands/ingest.py` (new home of the command function,
  named `ingest`)
- `compass_cli/display.py`: `index_header` → `ingest_header`; panel title
  `"compass index complete"` → `"compass ingest complete"`; help text in
  `help_commands()`
- `compass_cli/tests/test_cli.py`: `test_index_command_exists` →
  `test_ingest_command_exists`, invokes `["ingest", "--help"]`
- `README.md`: `compass index` → `compass ingest`
- `docs/superpowers/plans/2026-08-03-compact-cli-banner.md` and
  `docs/superpowers/plans/2026-04-13-project-page-overview-graph.md`:
  update references to `compass index` (historical plan docs — update for
  accuracy, not functional)

## Rename: `compass_core.indexer` → `compass_core.ingest`

`packages/core/src/compass_core/indexer/` becomes
`packages/core/src/compass_core/ingest/`. `engine.py` keeps its filename
and contents unchanged. The only importer
(`compass_cli/commands/ingest.py`, formerly `main.py`) updates its import
from `compass_core.indexer.engine` to `compass_core.ingest.engine`.

## Testing impact

Existing tests in `packages/cli/tests/test_cli.py` continue to exercise
the CLI through `typer.testing.CliRunner` against the same `app` object
exported from `main.py` — no test behavior changes beyond the renamed
command and renamed test function. No new test files required by this
refactor (it's structural, not new functionality).
