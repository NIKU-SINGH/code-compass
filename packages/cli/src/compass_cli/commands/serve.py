"""The `compass serve` command."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

import typer

from compass_cli import display
from compass_cli.errors import handle_errors
from compass_core.logger import setup as setup_logging
from compass_core.settings import settings


def _wait_for_server(url: str, timeout: int = 30) -> bool:
    """Poll url until it responds or timeout (seconds) is reached."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


@handle_errors
def serve(
    host: str = typer.Option(settings.API_HOST, help="Host for the API server"),
    port: int = typer.Option(settings.API_PORT, help="Port for the API server"),
    no_frontend: bool = typer.Option(False, "--no-frontend", help="Skip starting the frontend"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Start the API server and frontend dev server."""
    setup_logging(level="DEBUG" if verbose else "WARNING", show_path=verbose)

    web_dir = Path(__file__).parents[5] / "apps" / "web"
    procs: list[subprocess.Popen] = []

    frontend_url = settings.FRONTEND_URL

    try:
        display.console.print(
            f"[bold green]Starting API server[/bold green] on http://{host}:{port}"
        )
        procs.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "compass_core.server.main:app",
                    "--host",
                    host,
                    "--port",
                    str(port),
                    "--reload",
                ],
            )
        )

        if not no_frontend and web_dir.exists():
            display.console.print(f"[bold green]Starting frontend[/bold green] on {frontend_url}")
            procs.append(subprocess.Popen(["pnpm", "dev"], cwd=web_dir))
            # Poll until the dev server is ready, then open the browser.
            if _wait_for_server(f"http://{settings.FRONTEND_HOST}:{settings.FRONTEND_PORT}"):
                webbrowser.open(frontend_url)

        display.console.print("[dim]Press Ctrl+C to stop.[/dim]")

        for proc in procs:
            proc.wait()

    except KeyboardInterrupt:
        display.console.print("\n[yellow]Shutting down...[/yellow]")
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait()
