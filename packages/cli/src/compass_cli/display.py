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

from compass_cli.types import IngestSummary

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


def step(label: str, value: str) -> None:
    """Print a single key-value step line with consistent alignment.

    Used for reporting discrete metrics or metadata during a phase.

    Args:
        label: The descriptive name of the step or metric.
        value: The string value to display alongside the label.
    """
    console.print(f"  [dim]{label:<28}[/dim][bold]{value}[/bold]")


def phase_done(message: str) -> None:
    """Print a green check-mark completion line for the current phase.

    Args:
        message: The completion message to display (e.g., "Files parsed successfully").
    """
    console.print(f"\n  [green]✓[/green] {message}\n")


def summary(summary: IngestSummary) -> None:
    """Print the final summary in a gold-bordered panel.

    Args:
        summary: Aggregate results of the ingest run to display.
    """
    table = Table.grid(padding=(0, 4))
    table.add_column(style="dim", min_width=18)
    table.add_column(style="bold", min_width=14)
    table.add_column(style="dim", min_width=18)
    table.add_column(style="bold")

    table.add_row("Files indexed", str(summary.file_count), "Nodes", f"{summary.node_count:,}")
    table.add_row("Classes", str(summary.class_count), "Edges", f"{summary.edge_count:,}")
    table.add_row("Functions", str(summary.function_count), "DB size", _fmt_size(summary.db_size))
    table.add_row("Skipped", str(summary.skipped), "", "")
    table.add_row("Elapsed", f"{summary.elapsed:.1f}s", "", "")

    db_line = Text(no_wrap=True, overflow="fold")
    db_line.append("Database   ", style="dim")
    db_line.append(str(summary.db_path), style="bold")

    content = Group(table, Text(""), db_line)

    console.print(
        Panel(
            content,
            title=f"[bold {_GOLD}]compass ingest complete[/bold {_GOLD}]",
            border_style=_GOLD,
            padding=(1, 2),
            expand=True,
        )
    )
    console.print()


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


def _fmt_size(size_bytes: int) -> str:
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
