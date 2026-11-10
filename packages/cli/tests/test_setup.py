"""``compass setup`` keeps one managed block per file and never touches anything else."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from compass_cli.commands.setup import BEGIN, END, managed_block, upsert_block
from compass_cli.main import app
from compass_core.index.locate import IndexLocation
from compass_mcp.guide import AGENT_GUIDE

runner = CliRunner()


def _setup(repo: Path, *flags: str) -> tuple[int, str]:
    result = runner.invoke(app, ["setup", "--repo", str(repo), *flags])
    return result.exit_code, result.stdout + result.stderr


def test_creates_both_files_with_the_block(tmp_path: Path) -> None:
    code, out = _setup(tmp_path)
    assert code == 0 and "AGENTS.md: created" in out and "CLAUDE.md: created" in out
    assert (tmp_path / "AGENTS.md").read_text() == managed_block()
    assert "run `compass ingest`" in out  # no index yet
    assert not (tmp_path / ".mcp.json").exists()


def test_keeps_text_outside_the_markers_and_is_idempotent(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# House rules\n\nBe kind.\n")
    _setup(tmp_path)
    first = agents.read_text()
    assert first.startswith("# House rules\n\nBe kind.\n\n" + BEGIN)
    code, out = _setup(tmp_path)
    assert code == 0 and "AGENTS.md: unchanged" in out
    assert agents.read_text() == first


def test_replaces_an_outdated_block_in_place() -> None:
    old = f"intro\n{BEGIN}\nold guide\n{END}\noutro\n"
    new = upsert_block(old, managed_block())
    assert new == f"intro\n{managed_block()}outro\n"
    assert "old guide" not in new and AGENT_GUIDE in new


def test_skips_claude_md_that_imports_agents_md(tmp_path: Path) -> None:
    claude = tmp_path / "CLAUDE.md"
    claude.write_text("@AGENTS.md\n\nClaude-only notes.\n")
    code, out = _setup(tmp_path)
    assert code == 0 and "CLAUDE.md: skipped (it imports @AGENTS.md)" in out
    assert claude.read_text() == "@AGENTS.md\n\nClaude-only notes.\n"


def test_mcp_registers_the_server_and_keeps_other_servers(tmp_path: Path) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "extra": 1}))
    code, out = _setup(tmp_path, "--mcp")
    assert code == 0 and ".mcp.json: updated" in out and "~/.codex/config.toml" in out
    data = json.loads(config.read_text())
    assert data["mcpServers"]["other"] == {"command": "x"} and data["extra"] == 1
    assert data["mcpServers"]["code-compass"] == {"command": "compass", "args": ["mcp"]}
    assert ".mcp.json: unchanged" in _setup(tmp_path, "--mcp")[1]


def test_malformed_mcp_json_is_left_alone(tmp_path: Path) -> None:
    config = tmp_path / ".mcp.json"
    config.write_text("{not json")
    code, out = _setup(tmp_path, "--mcp")
    assert code == 1 and ".mcp.json: not changed" in out
    assert config.read_text() == "{not json"


def test_print_writes_nothing(tmp_path: Path) -> None:
    code, out = _setup(tmp_path, "--print")
    assert code == 0 and out == managed_block()
    assert list(tmp_path.iterdir()) == []


def test_no_ingest_hint_when_the_repo_is_indexed(
    fixture_index: IndexLocation, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(fixture_index.repo_root, repo)
    code, out = _setup(repo)
    assert code == 0 and "AGENTS.md: created" in out
    assert "compass ingest" not in out
