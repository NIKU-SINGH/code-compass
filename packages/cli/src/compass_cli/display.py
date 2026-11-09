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

_GOLD = "color(214)"

console = Console()


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


def help_commands() -> None:
    """Print the available CLI commands.

    Summarizes the base usage and primary subcommands (`ingest`, `serve`)
    with brief descriptions and formatting.
    """
    console.print(f"[bold {_GOLD}]Code Compass[/bold {_GOLD}] — Navigate your codebase with ease\n")
    console.print("[bold]Usage:[/bold]  compass [OPTIONS] COMMAND [ARGS]...\n")
    console.print("[bold]Commands:[/bold]")
    console.print(
        f"  [bold {_GOLD}]ingest[/bold {_GOLD}]  Ingest a repository for code intelligence"
    )
    console.print(
        f"  [bold {_GOLD}]serve[/bold {_GOLD}]   Start the API server and frontend dev server"
    )
    console.print()
    console.print(
        "[dim]Run [bold]compass COMMAND --help[/bold] for command-specific options.[/dim]"
    )


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
            f"[bold {_GOLD}]Phase {num} of {total}[/bold {_GOLD}]"
            f"[dim]  ·  [/dim]"
            f"[bold]{title}[/bold]",
            style=_GOLD,
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
            title=f"[bold {_GOLD}]compass ingest complete[/bold {_GOLD}]",
            border_style=_GOLD,
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


def next_steps() -> None:
    """Print suggested next actions after a successful ingest.

    Includes the command to start the web UI.
    """
    console.print("[bold]What's next:[/bold]")
    console.print(
        f"  [bold {_GOLD}]compass serve[/bold {_GOLD}]            "
        f"Start the web UI and explore your codebase"
    )
    console.print(f"  [bold {_GOLD}]compass serve --help[/bold {_GOLD}]     See all server options")
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
