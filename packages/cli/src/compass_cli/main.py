import subprocess
import sys
import time
from pathlib import Path

import typer

from compass_cli import display
from compass_cli.progress import RichProgressReporter
from compass_core.logger import setup as setup_logging
from compass_core.settings import settings

app = typer.Typer(
    help="Code Compass CLI",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Code Compass — Navigate your codebase with ease."""
    if ctx.invoked_subcommand is None:
        display.banner()
        display.help_commands()


@app.command()
def index(
    path: str = typer.Argument(..., help="Path to the repository to index"),
    db: str = typer.Option(None, "--db", help="Path to LadybugDB database (default: <repo>/.compass/graph.ladybug)"),
    workers: int = typer.Option(None, "--workers", help="Number of parallel parse workers"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Index a repository for code intelligence."""
    from compass_core.graph.db import GraphDB
    from compass_core.graph.schema import create_schema
    from compass_core.graph.writer import write
    from compass_core.indexer.engine import parse_files, save_metadata
    from compass_core.parser.file_walker import walk_python_files
    from compass_core.resolver.resolver import resolve

    setup_logging(level="DEBUG" if verbose else "WARNING", show_path=verbose)

    repo_path = Path(path).resolve()
    db_path = Path(db).resolve() if db else repo_path / ".compass" / "graph.ladybug"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()

    display.index_header(repo_path)

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
            len(pf.functions) + sum(len(c.methods) for c in pf.classes)
            for pf in parsed
        )
        skipped = len(skipped_files)

        display.step("Files parsed", f"{len(parsed)}" + (f"  ({skipped} skipped)" if skipped else ""))
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

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    display.summary(
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

    display.next_steps()


@app.command()
def serve(
    host: str = typer.Option(settings.API_HOST, help="Host for the API server"),
    port: int = typer.Option(settings.API_PORT, help="Port for the API server"),
    no_frontend: bool = typer.Option(False, "--no-frontend", help="Skip starting the frontend"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Start the API server and frontend dev server."""
    setup_logging(level="DEBUG" if verbose else "WARNING", show_path=verbose)

    web_dir = Path(__file__).parents[4] / "apps" / "web"
    procs: list[subprocess.Popen] = []

    try:
        display.console.print(f"[bold green]Starting API server[/bold green] on http://{host}:{port}")
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "compass_core.server.main:app",
                 "--host", host, "--port", str(port), "--reload"],
            )
        )

        if not no_frontend and web_dir.exists():
            display.console.print(f"[bold green]Starting frontend[/bold green] on {settings.FRONTEND_URL}")
            procs.append(subprocess.Popen(["pnpm", "dev"], cwd=web_dir))

        display.console.print("[dim]Press Ctrl+C to stop.[/dim]")

        for proc in procs:
            proc.wait()

    except KeyboardInterrupt:
        display.console.print("\n[yellow]Shutting down...[/yellow]")
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait()


if __name__ == "__main__":
    app()
