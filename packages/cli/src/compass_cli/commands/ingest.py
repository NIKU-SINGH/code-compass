"""The `compass ingest` command."""

from __future__ import annotations

import time
from pathlib import Path

import typer

from compass_cli import display
from compass_cli.errors import handle_errors
from compass_cli.progress import RichProgressReporter
from compass_cli.types import IngestSummary
from compass_core.graph.db import GraphDB
from compass_core.graph.schema import create_schema
from compass_core.graph.writer import write
from compass_core.ingest.engine import parse_files, save_metadata
from compass_core.logger import setup as setup_logging
from compass_core.parser.file_walker import walk_python_files
from compass_core.resolver.resolver import resolve


def _run_ingest(
    repo_path: Path,
    db_path: Path,
    *,
    workers: int | None,
    verbose: bool,
) -> IngestSummary:
    """Run the ingest pipeline and return its summary."""
    start = time.monotonic()

    display.ingest_header(repo_path)

    files = list(walk_python_files(repo_path))

    with RichProgressReporter(console=display.console) as reporter:
        # ------------------------------------------------------------------
        # Phase 1 — Ingestion
        # ------------------------------------------------------------------
        display.phase_header(1, 2, "Ingestion")
        display.step("Discovered", f"{len(files)} Python files")

        parsed, skipped_files = parse_files(
            files, repo_path, max_workers=workers or None, reporter=reporter
        )
        graph = resolve(parsed, reporter=reporter)

        class_count = sum(len(pf.classes) for pf in parsed)
        function_count = sum(
            len(pf.functions) + sum(len(c.methods) for c in pf.classes) for pf in parsed
        )
        skipped = len(skipped_files)

        display.step(
            "Files parsed", f"{len(parsed)}" + (f"  ({skipped} skipped)" if skipped else "")
        )
        if verbose and skipped_files:
            for f in skipped_files:
                display.console.print(f"  [dim red]  skipped: {f}[/dim red]")
        display.step("Classes", f"{class_count}")
        display.step("Functions", f"{function_count}")
        display.step("Import edges", f"{len(graph.import_edges):,}")
        display.step("Inheritance edges", f"{len(graph.inherit_edges):,}")
        display.step("Call edges", f"{len(graph.call_edges):,}")
        display.step("External calls", f"{len(graph.external_call_edges):,}")
        display.phase_done("Ingestion complete")

        # ------------------------------------------------------------------
        # Phase 2 — Persistence
        # ------------------------------------------------------------------
        display.phase_header(2, 2, "Persistence")

        with GraphDB(db_path) as gdb:
            create_schema(gdb)
            write_result = write(gdb, graph, reporter=reporter)

        try:
            display_db = db_path.relative_to(repo_path)
        except ValueError:
            display_db = db_path
        display.step("Database", str(display_db))
        display.phase_done("Done")

    # Metadata
    save_metadata(repo_path)

    elapsed = time.monotonic() - start

    # DB size — single file or directory
    if db_path.is_file():
        db_size = db_path.stat().st_size
    elif db_path.is_dir():
        db_size = sum(f.stat().st_size for f in db_path.rglob("*") if f.is_file())
    else:
        db_size = 0

    return IngestSummary(
        file_count=len(parsed),
        class_count=class_count,
        function_count=function_count,
        elapsed=elapsed,
        node_count=write_result.node_count,
        edge_count=write_result.edge_count,
        db_path=display_db,
        db_size=db_size,
        skipped=skipped,
    )


@handle_errors
def ingest(
    path: str = typer.Argument(..., help="Path to the repository to ingest"),
    db: str | None = typer.Option(
        None, "--db", help="Path to LadybugDB database (default: <repo>/.compass/graph.ladybug)"
    ),
    workers: int | None = typer.Option(None, "--workers", help="Number of parallel parse workers"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Ingest a repository for code intelligence."""
    setup_logging(level="DEBUG" if verbose else "WARNING", show_path=verbose)

    repo_path = Path(path).resolve()
    db_path = Path(db).resolve() if db else repo_path / ".compass" / "graph.ladybug"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    summary = _run_ingest(repo_path, db_path, workers=workers, verbose=verbose)

    display.summary(summary)
    display.next_steps()
