"""Rich-based display rendering for the Code Compass CLI.

All terminal output formatting lives here — main.py handles argument
parsing and phase orchestration, this module handles how things look.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

_GOLD = "color(214)"

console = Console()


# ---------------------------------------------------------------------------
# Banner & help
# ---------------------------------------------------------------------------


def banner() -> None:
    """Print the Code Compass ASCII logo (left-aligned).

    The banner includes a stylized "CODE COMPASS" title and a sub-title
    rendered within a gold-bordered panel.
    """
    logo = r"""
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
    """
    clean = "\n".join(line.rstrip() for line in logo.strip("\n").split("\n"))
    console.print(
        Panel(
            Text(clean, style=f"bold {_GOLD}", no_wrap=True, justify="left"),
            subtitle=f"[bold {_GOLD}]Next-Gen Code Intelligence[/bold {_GOLD}]",
            border_style=_GOLD,
            padding=(1, 2),
            expand=False,
        )
    )
    console.print()
    console.print(f"[bold {_GOLD}]Navigate your codebase with ease[/bold {_GOLD}]")
    console.print()


def help_commands() -> None:
    """Print the available CLI commands.

    Summarizes the base usage and primary subcommands (`index`, `serve`)
    with brief descriptions and formatting.
    """
    console.print("[bold]Usage:[/bold]  compass [OPTIONS] COMMAND [ARGS]...\n")
    console.print("[bold]Commands:[/bold]")
    console.print(f"  [bold {_GOLD}]index[/bold {_GOLD}]   Index a repository for code intelligence")
    console.print(f"  [bold {_GOLD}]serve[/bold {_GOLD}]   Start the API server and frontend dev server")
    console.print()
    console.print("[dim]Run [bold]compass COMMAND --help[/bold] for command-specific options.[/dim]")


# ---------------------------------------------------------------------------
# Index command display helpers
# ---------------------------------------------------------------------------


def index_header(repo_path: Path) -> None:
    """Print the opening line for an index run.

    Args:
        repo_path: The filesystem path to the repository being indexed.
    """
    console.print(f"\n[dim]Indexing[/dim] [bold]{repo_path}[/bold]\n")


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


def summary(
    *,
    file_count: int,
    class_count: int,
    function_count: int,
    elapsed: float,
    node_count: int,
    edge_count: int,
    db_path: Path,
    db_size: int,
    skipped: int,
) -> None:
    """Print the final summary in a gold-bordered panel.

    Args:
        file_count: Total number of files successfully indexed.
        class_count: Total number of classes discovered.
        function_count: Total number of functions/methods discovered.
        elapsed: Time taken for the entire index run in seconds.
        node_count: Total count of nodes inserted into the graph.
        edge_count: Total count of edges (calls/imports) resolved.
        db_path: Path to the generated SQLite database.
        db_size: Size of the database in bytes.
        skipped: Number of files tasks skipped due to errors or filters.
    """
    table = Table.grid(padding=(0, 4))
    table.add_column(style="dim", min_width=18)
    table.add_column(style="bold", min_width=14)
    table.add_column(style="dim", min_width=18)
    table.add_column(style="bold")

    table.add_row("Files indexed", str(file_count), "Nodes", f"{node_count:,}")
    table.add_row("Classes", str(class_count), "Edges", f"{edge_count:,}")
    table.add_row("Functions", str(function_count), "DB size", _fmt_size(db_size))
    table.add_row("Skipped", str(skipped), "", "")
    table.add_row("Elapsed", f"{elapsed:.1f}s", "", "")

    db_line = Text(no_wrap=True, overflow="fold")
    db_line.append("Database   ", style="dim")
    db_line.append(str(db_path), style="bold")

    content = Group(table, Text(""), db_line)

    console.print(
        Panel(
            content,
            title=f"[bold {_GOLD}]compass index complete[/bold {_GOLD}]",
            border_style=_GOLD,
            padding=(1, 2),
            expand=True,
        )
    )
    console.print()


def next_steps() -> None:
    """Print suggested next actions after a successful index.

    Includes the command to start the web UI.
    """
    console.print(f"[bold]What's next:[/bold]")
    console.print(
        f"  [bold {_GOLD}]compass serve[/bold {_GOLD}]            "
        f"Start the web UI and explore your codebase"
    )
    console.print(
        f"  [bold {_GOLD}]compass serve --help[/bold {_GOLD}]     "
        f"See all server options"
    )
    console.print()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


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
