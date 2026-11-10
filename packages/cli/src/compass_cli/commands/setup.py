"""The ``compass setup`` command: tell coding agents in a repository about Code Compass.

It keeps one managed block, between ``<!-- compass:begin -->`` and ``<!-- compass:end -->``,
in ``AGENTS.md`` (read by Codex, Cursor and others) and ``CLAUDE.md`` (read by Claude
Code), creating the files when missing and never touching text outside the markers.
``CLAUDE.md`` is left alone when it already imports ``@AGENTS.md``. With ``--mcp`` it also
registers the MCP server in the project's ``.mcp.json``. Running it again refreshes the
block and changes nothing else.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

import typer

from compass_core.index.locate import find_index
from compass_mcp.guide import AGENT_GUIDE
from compass_mcp.server import SERVER_NAME

BEGIN = "<!-- compass:begin -->"
END = "<!-- compass:end -->"
AGENTS_FILE = "AGENTS.md"
CLAUDE_FILE = "CLAUDE.md"
CLAUDE_IMPORTS_AGENTS = "@AGENTS.md"
MCP_FILE = ".mcp.json"
MCP_ENTRY: dict[str, object] = {"command": "compass", "args": ["mcp"]}
CODEX_HINT = f"""\
For Codex, add this to ~/.codex/config.toml:
  [mcp_servers.{SERVER_NAME}]
  command = "compass"
  args = ["mcp"]"""


class Change(StrEnum):
    """What ``setup`` did to one file.

    Attributes:
        CREATED: The file did not exist and was written.
        UPDATED: The file existed and its managed part was added or replaced.
        UNCHANGED: The file already had exactly this content.
        SKIPPED: The file was deliberately left alone.
    """

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"


def managed_block() -> str:
    """The agent guide between the markers, ending with a newline.

    Returns:
        The block ``setup`` keeps in agent instruction files.

    Example:
        ``managed_block().splitlines()[0]`` is ``"<!-- compass:begin -->"``.
    """
    return f"{BEGIN}\n{AGENT_GUIDE}{END}\n"


def upsert_block(text: str, block: str) -> str:
    """Replace the managed block in ``text``, or append it; other text is kept as is.

    Args:
        text: Current file content (may be empty).
        block: The new managed block, markers included.

    Returns:
        The new content.

    Example:
        ``upsert_block("# Rules\\n", block)`` returns ``"# Rules\\n\\n" + block``; calling it
        again on that result with a newer block replaces only the block.
    """
    start = text.find(BEGIN)
    end = text.find(END, start)
    if start != -1 and end != -1:
        tail = text[end + len(END) :].removeprefix("\n")
        return text[:start] + block + tail
    if not text.strip():
        return block
    return text.rstrip("\n") + "\n\n" + block


def write_guide(path: Path, block: str) -> Change:
    """Put the managed block into one agent instruction file.

    Args:
        path: ``AGENTS.md`` or ``CLAUDE.md``.
        block: The managed block.

    Returns:
        What happened to the file.
    """
    existed = path.exists()
    current = path.read_text(encoding="utf-8") if existed else ""
    if path.name == CLAUDE_FILE and CLAUDE_IMPORTS_AGENTS in current.replace(block, ""):
        return Change.SKIPPED
    updated = upsert_block(current, block)
    if updated == current:
        return Change.UNCHANGED
    path.write_text(updated, encoding="utf-8")
    return Change.UPDATED if existed else Change.CREATED


def register_mcp(path: Path) -> Change:
    """Add or refresh the Code Compass entry in a project's ``.mcp.json``.

    Other servers and keys are kept. A file that is not a JSON object is not touched.

    Args:
        path: The ``.mcp.json`` file.

    Returns:
        What happened to the file.

    Raises:
        ValueError: The existing file is not a JSON object with an ``mcpServers`` object.
    """
    existed = path.exists()
    data = json.loads(path.read_text(encoding="utf-8")) if existed else {}
    servers = data.setdefault("mcpServers", {}) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        raise ValueError(f"{path} is not a JSON object with an 'mcpServers' object")
    if servers.get(SERVER_NAME) == MCP_ENTRY:
        return Change.UNCHANGED
    servers[SERVER_NAME] = MCP_ENTRY
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return Change.UPDATED if existed else Change.CREATED


REPO = typer.Option(
    Path("."), "--repo", file_okay=False, help="Repository to set up; default: here."
)


def setup(
    repo: Path = REPO,
    mcp: bool = typer.Option(False, "--mcp", help=f"Also register the server in {MCP_FILE}."),
    print_only: bool = typer.Option(
        False, "--print", help="Print the agent guide and write nothing."
    ),
) -> None:
    """Tell coding agents in this repository to use Code Compass.

    Writes a managed section to AGENTS.md and CLAUDE.md (and, with --mcp, the MCP server
    to .mcp.json). Safe to run again; text outside the section is never changed.
    """
    block = managed_block()
    if print_only:
        typer.echo(block, nl=False)
        return
    root = repo.resolve()
    for name in (AGENTS_FILE, CLAUDE_FILE):
        change = write_guide(root / name, block)
        note = f" (it imports {CLAUDE_IMPORTS_AGENTS})" if change is Change.SKIPPED else ""
        typer.echo(f"{name}: {change.value}{note}")
    if mcp:
        try:
            change = register_mcp(root / MCP_FILE)
        except (ValueError, json.JSONDecodeError) as exc:
            typer.echo(f"{MCP_FILE}: not changed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"{MCP_FILE}: {change.value} ({SERVER_NAME} runs `compass mcp`)")
        typer.echo(CODEX_HINT)
    if find_index(root) is None:
        typer.echo("No index yet: run `compass ingest` here before asking questions.")
