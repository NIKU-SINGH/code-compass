# Compact CLI Default Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the oversized no-argument CLI banner with concise command guidance.

**Architecture:** Keep Typer command registration and `--help` behavior unchanged. Change only the no-subcommand callback, reuse the existing `display.help_commands()` renderer, and remove banner-only display code after a CLI integration test proves the behavior change.

**Tech Stack:** Python 3.11+, Typer, Rich, pytest, uv, Hatchling

## Global Constraints

- `compass` without a subcommand must exit successfully.
- The default output must retain the product guidance, usage, `index`, and `serve` commands.
- The large `CODE COMPASS` ASCII artwork must not appear.
- Existing subcommands and Typer's `compass --help` output must remain unchanged.

---

### Task 1: Make no-argument output concise

**Files:**
- Modify: `packages/cli/tests/test_cli.py`
- Modify: `packages/cli/src/compass_cli/main.py`
- Modify: `packages/cli/src/compass_cli/display.py`

**Interfaces:**
- Consumes: Typer application `compass_cli.main.app` and `display.help_commands() -> None`.
- Produces: concise terminal output from `runner.invoke(app, [])` without banner artwork.

- [x] **Step 1: Write the failing integration test**

```python
def test_cli_without_command_shows_concise_help():
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Navigate your codebase with ease" in result.output
    assert "Usage:" in result.output
    assert "index" in result.output
    assert "serve" in result.output
    assert "██████╗" not in result.output
```

- [x] **Step 2: Run the test and verify the red state**

Run: `uv run pytest packages/cli/tests/test_cli.py::test_cli_without_command_shows_concise_help -q`

Expected: FAIL because the current default output contains `██████╗`.

- [x] **Step 3: Implement the minimal behavior change**

In `packages/cli/src/compass_cli/main.py`, change the no-subcommand callback to call only:

```python
display.help_commands()
```

In `packages/cli/src/compass_cli/display.py`, remove the now-unused `banner()` function and imports used only by that function. Preserve `help_commands()` and all index-output helpers.

- [x] **Step 4: Verify the green state and regressions**

Run: `uv run pytest packages/cli/tests -q`

Expected: all CLI tests pass.

Run: `uv run compass`

Expected: concise usage and commands with no ASCII artwork.

Run: `uv build --package compass-cli`

Expected: the CLI source distribution and wheel build successfully under `dist/`.

- [ ] **Step 5: Commit the implementation**

```bash
git add packages/cli/tests/test_cli.py packages/cli/src/compass_cli/main.py packages/cli/src/compass_cli/display.py
git commit -m "fix(cli): remove oversized default banner"
```
