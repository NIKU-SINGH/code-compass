"""The `compass ingest` command."""

from __future__ import annotations

import time
from pathlib import Path

import typer

import compass_core.languages.python  # noqa: F401 — registers the Python plugin
from compass_cli import display
from compass_cli.errors import handle_errors
from compass_cli.progress import RichProgressReporter
from compass_cli.types import IngestSummary
from compass_core.ir.graph import ResolvedGraph
from compass_core.ir.models import DefinitionKind
from compass_core.logger import setup as setup_logging
from compass_core.phases.base import IngestContext
from compass_core.phases.pipeline import Pipeline


def _count_definitions(resolved_graph: ResolvedGraph) -> tuple[int, int]:
    """Return (class_count, function_count) across all files in the graph."""
    class_count = 0
    function_count = 0
    for pf in resolved_graph.files:
        for d in pf.definitions:
            if d.kind is DefinitionKind.CLASS:
                class_count += 1
            elif d.kind in (DefinitionKind.FUNCTION, DefinitionKind.METHOD):
                function_count += 1
    return class_count, function_count


def _db_size(db_path: Path) -> int:
    """Total bytes on disk for the database — a single file or a directory."""
    if db_path.is_file():
        return db_path.stat().st_size
    if db_path.is_dir():
        return sum(f.stat().st_size for f in db_path.rglob("*") if f.is_file())
    return 0


def _relative_db_path(db_path: Path, repo_path: Path) -> Path:
    """Express db_path relative to repo_path for display, falling back to the absolute path."""
    try:
        return db_path.relative_to(repo_path)
    except ValueError:
        return db_path


def _display_ingest_stats(
    ctx: IngestContext, display_db: Path, class_count: int, function_count: int
) -> None:
    """Print the post-ingest summary lines (file/def/edge counts, db path)."""
    assert ctx.manifest is not None
    assert ctx.resolved_graph is not None

    display.step("Files indexed", f"{len(ctx.manifest.files)}")
    display.step("Classes", f"{class_count}")
    display.step("Functions", f"{function_count}")
    display.step("Import edges", f"{len(ctx.resolved_graph.import_edges):,}")
    display.step("Inheritance edges", f"{len(ctx.resolved_graph.inherit_edges):,}")
    display.step("Call edges", f"{len(ctx.resolved_graph.call_edges):,}")
    display.step("External calls", f"{len(ctx.resolved_graph.external_call_edges):,}")
    display.step("Database", str(display_db))
    display.phase_done("Done")


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

    with RichProgressReporter(console=display.console) as reporter:
        ctx = Pipeline(max_workers=workers).run(repo_path, db_path, reporter=reporter)

    assert ctx.manifest is not None
    assert ctx.resolved_graph is not None
    assert ctx.report is not None
    assert ctx.write_result is not None

    display_db = _relative_db_path(db_path, repo_path)
    class_count, function_count = _count_definitions(ctx.resolved_graph)
    _display_ingest_stats(ctx, display_db, class_count, function_count)

    return IngestSummary(
        file_count=len(ctx.manifest.files),
        class_count=class_count,
        function_count=function_count,
        elapsed=time.monotonic() - start,
        node_count=ctx.write_result.node_count,
        edge_count=ctx.write_result.edge_count,
        db_path=display_db,
        db_size=_db_size(db_path),
        skipped=ctx.report.degraded_file_count,
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
