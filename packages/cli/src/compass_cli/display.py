"""Rich-based display rendering for the Code Compass CLI.

All terminal output formatting lives here — commands/ handles argument
parsing and phase orchestration, this module handles how things look.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from compass_cli.progress import fmt_duration
from compass_cli.types import IngestSummary
from compass_core.shared_types import Language

GOLD = "color(214)"
"""Accent colour of every Code Compass panel, rule and command name."""

console = Console()


# ---------------------------------------------------------------------------
# Logo and help
# ---------------------------------------------------------------------------


LOGO = r"""
  ██████╗ ██████╗ ██████╗ ███████╗
 ██╔════╝██╔═══██╗██╔══██╗██╔════╝
 ██║     ██║   ██║██║  ██║█████╗
 ██║     ██║   ██║██║  ██║██╔══╝
 ╚██████╗╚██████╔╝██████╔╝███████╗
  ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝

  ██████╗ ██████╗ ███╗   ███╗██████╗  █████╗ ███████╗███████╗
 ██╔════╝██╔═══██╗████╗ ████║██╔══██╗██╔══██╗██╔════╝██╔════╝
 ██║     ██║   ██║██╔████╔██║██████╔╝███████║███████╗███████╗
 ██║     ██║   ██║██║╚██╔╝██║██╔═══╝ ██╔══██║╚════██║╚════██║
 ╚██████╗╚██████╔╝██║ ╚═╝ ██║██║     ██║  ██║███████║███████║
  ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝
""".strip("\n")
"""The block-letter logo shown by bare ``compass`` and ``compass --version``."""

LOGO_MIN_WIDTH = 70
"""Narrowest terminal (in columns) the logo panel fits without wrapping."""

TAGLINE = "Local-first code knowledge graph"
"""Shown under the logo."""


def logo(subtitle: str = TAGLINE) -> bool:
    """Print the logo in a gold panel, only in a terminal wide enough for it.

    Piped output (scripts, coding agents) and narrow terminals get nothing, so the
    logo never breaks a parser or wraps into noise.

    Args:
        subtitle: Text on the panel's bottom edge.

    Returns:
        Whether the logo was printed.

    Example:
        ``compass`` in an 80-column terminal prints the panel; ``compass | cat`` does not.
    """
    if not console.is_terminal or console.width < LOGO_MIN_WIDTH:
        return False
    console.print(
        Panel(
            Text(LOGO, style=f"bold {GOLD}", no_wrap=True),
            subtitle=f"[bold {GOLD}]{subtitle}[/bold {GOLD}]",
            border_style=GOLD,
            padding=(1, 2),
            expand=False,
        )
    )
    console.print()
    return True


_COMMANDS: tuple[tuple[str, str], ...] = (
    ("ingest", "Index a repository (run again after code changes)"),
    ("status", "Show which index is used and whether it is up to date"),
    ("search", "Find files, classes, functions and methods by name"),
    ("describe", "Show one symbol: location, docstring, callers, callees"),
    ("impact", "List what may break if a symbol or file changes"),
    ("overview", "Summarise the repository: entry points and hot spots"),
    ("setup", "Tell coding agents in this repo to use Code Compass"),
    ("mcp", "Serve the code graph to coding agents over MCP"),
    ("serve", "Start the API server and the web UI"),
    ("help", "Show this list"),
)
"""Commands listed by ``compass`` with no arguments, in the order a user needs them."""


def help_commands() -> None:
    """Print the available CLI commands with one line each."""
    width = max(len(name) for name, _ in _COMMANDS)
    console.print(f"[bold {GOLD}]Code Compass[/bold {GOLD}] — Navigate your codebase with ease\n")
    console.print("[bold]Usage:[/bold]  compass [OPTIONS] COMMAND [ARGS]...\n")
    console.print("[bold]Commands:[/bold]")
    for name, summary in _COMMANDS:
        console.print(f"  [bold {GOLD}]{name:<{width}}[/bold {GOLD}]  {summary}")
    console.print()
    console.print("[dim]Run [bold]compass COMMAND --help[/bold] for a command's options.[/dim]")


def welcome() -> None:
    """What bare ``compass`` prints: the logo (in a wide terminal), then the commands."""
    logo()
    help_commands()


# ---------------------------------------------------------------------------
# Ingest command display helpers
# ---------------------------------------------------------------------------


def ingest_header(repo_path: Path) -> None:
    """Print the opening line for an ingest run.

    Args:
        repo_path: The filesystem path to the repository being ingested.
    """
    console.print(f"\n[dim]Ingesting[/dim] [bold]{repo_path}[/bold]\n")


def phase_header(num: int, total: int, title: str) -> None:
    """Print a centered phase separator rule.

    Example output: `Phase 1 of 2 · Ingestion` (centered with a gold rule).

    Args:
        num: The 1-indexed phase number currently starting.
        total: The total number of phases in the run.
        title: A descriptive name for the current phase.
    """
    console.print(
        Rule(
            f"[bold {GOLD}]Phase {num} of {total}[/bold {GOLD}]"
            f"[dim]  ·  [/dim]"
            f"[bold]{title}[/bold]",
            style=GOLD,
            align="center",
        )
    )
    console.print()


def _language_grid(language_counts: dict[Language, int]) -> Table:
    """Lay out a "Languages" label followed by a language -> file-count
    breakdown, three columns wide."""
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="dim", min_width=13)
    for _ in range(3):
        grid.add_column(style="bold")
        grid.add_column(style="dim", min_width=6)

    items = sorted(language_counts.items(), key=lambda kv: kv[1], reverse=True)
    for i in range(0, len(items), 3):
        row: list[str] = ["Languages" if i == 0 else ""]
        for lang, count in items[i : i + 3]:
            row += [lang, f"{count:,}"]
        row += [""] * (7 - len(row))
        grid.add_row(*row)
    return grid


def summary(summary: IngestSummary) -> None:
    """Print the final summary in a gold-bordered panel.

    Args:
        summary: Aggregate results of the ingest run to display.
    """
    left = Table.grid(padding=(0, 3))
    left.add_column(style="dim", min_width=13)
    left.add_column(style="bold")
    left.add_row("Files indexed", f"{summary.file_count:,}")
    left.add_row("Classes", f"{summary.class_count:,}")
    left.add_row("Functions", f"{summary.function_count:,}")
    left.add_row("Skipped", str(summary.skipped))
    left.add_row("Elapsed", fmt_duration(summary.elapsed))

    right = Table.grid(padding=(0, 3))
    right.add_column(style="dim", min_width=9)
    right.add_column(style="bold")
    right.add_row("Nodes", f"{summary.node_count:,}")
    right.add_row("Edges", f"{summary.edge_count:,}")
    if summary.dropped_edges:
        right.add_row("Skipped", f"{summary.dropped_edges:,} edges")
    right.add_row("Resolved", f"{summary.resolved_pct:.0%}")
    right.add_row("Orphans", f"{summary.orphan_count:,}")
    right.add_row("DB size", fmt_size(summary.db_size))

    columns = Table.grid(padding=(0, 6))
    columns.add_column()
    columns.add_column()
    columns.add_row(left, right)

    db_line = Text(no_wrap=True, overflow="fold")
    db_line.append("Database   ", style="dim")
    db_line.append(str(summary.db_path), style="bold")

    parts: list[Table | Text] = [columns, Text("")]
    if summary.language_counts:
        parts.append(_language_grid(summary.language_counts))
        parts.append(Text(""))
    parts.append(db_line)

    console.print(
        Panel(
            Group(*parts),
            title=f"[bold {GOLD}]compass ingest complete[/bold {GOLD}]",
            border_style=GOLD,
            padding=(1, 2),
            expand=True,
        )
    )
    if summary.dropped_edges:
        console.print(f"  [dim]{skipped_edges_note(summary.dropped_edges)}[/dim]", soft_wrap=True)
    console.print()


def skipped_edges_note(count: int) -> str:
    """Explain why some resolved edges are missing from the database.

    Args:
        count: Number of edges the writer could not store.

    Returns:
        A one-line explanation, e.g. ``"3 edges skipped (callee is not a stored
        function, e.g. class constructor calls)"``.
    """
    noun = "edge" if count == 1 else "edges"
    return (
        f"{count:,} {noun} skipped (callee is not a stored function, e.g. class constructor calls)"
    )


NEXT_STEPS: tuple[tuple[str, str], ...] = (
    ("compass overview", "See entry points and hot spots"),
    ("compass search NAME", "Find where something is defined"),
    ("compass setup", "Let coding agents (Claude Code, Codex) use this index"),
    ("compass serve", "Explore the graph in the web UI"),
    ("compass help", "See every command"),
)
"""Commands suggested after an ingest, most useful first."""


def next_steps() -> None:
    """Print the commands worth running after a successful ingest."""
    width = max(len(command) for command, _ in NEXT_STEPS)
    console.print("[bold]What's next:[/bold]")
    for command, summary in NEXT_STEPS:
        console.print(f"  [bold {GOLD}]{command:<{width}}[/bold {GOLD}]  {summary}")
    console.print()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def error(message: str) -> None:
    """Print a formatted error message.

    Args:
        message: The error text to display.
    """
    console.print(f"[bold red]Error:[/bold red] {message}")


def fmt_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable string.

    Args:
        size_bytes: The number of bytes to format.

    Returns:
        A formatted string (e.g., "1.5 KB", "300 B").
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
