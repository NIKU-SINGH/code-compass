"""The ``compass mcp`` command: serve the code graph to coding agents over MCP (stdio)."""

from __future__ import annotations

from pathlib import Path

import typer

from compass_mcp.server import build_server

REPO = typer.Option(
    None,
    "--repo",
    file_okay=False,
    help="Repository to serve; default: the one containing the working directory.",
)


def mcp(repo: Path | None = REPO) -> None:
    """Run the MCP server on stdin/stdout for Claude Code, Codex and other MCP clients.

    Nothing else is printed: stdout carries the protocol. Register it with
    `compass setup --mcp`, or point a client at the command `compass mcp`.
    """
    build_server(repo).run("stdio")
