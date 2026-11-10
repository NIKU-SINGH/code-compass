"""The `compass serve` command."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
import webbrowser
from enum import StrEnum
from pathlib import Path

import typer

from compass_cli import display
from compass_cli.errors import handle_errors
from compass_core.logger import setup as setup_logging
from compass_server.settings import server_settings
from compass_server.web_bundle import has_bundled_ui


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


class UiMode(StrEnum):
    """Where ``compass serve`` gets the web UI from.

    Attributes:
        BUNDLED: The static UI built into ``compass_server``, served on the API's own port
            (an installed package).
        DEV: The Next.js dev server from a source checkout, with hot reload.
        NONE: No UI; only the API.
    """

    BUNDLED = "bundled"
    DEV = "dev"
    NONE = "none"


WEB_DIR = Path(__file__).parents[5] / "apps" / "web"
"""The web app in a source checkout; absent in an installed package."""


def ui_mode(*, no_frontend: bool, dev: bool) -> UiMode:
    """Pick the UI to serve: the dev server when asked or unbundled, else the bundle.

    Args:
        no_frontend: Serve only the API.
        dev: Prefer the Next.js dev server even when a bundled UI exists.

    Returns:
        The mode.

    Example:
        In an installed package, ``ui_mode(no_frontend=False, dev=False)`` is
        ``UiMode.BUNDLED``.
    """
    if no_frontend:
        return UiMode.NONE
    if WEB_DIR.exists() and (dev or not has_bundled_ui()):
        return UiMode.DEV
    return UiMode.BUNDLED if has_bundled_ui() else UiMode.NONE


@handle_errors
def serve(
    host: str = typer.Option(server_settings.API_HOST, help="Host for the API server"),
    port: int = typer.Option(server_settings.API_PORT, help="Port for the API server"),
    no_frontend: bool = typer.Option(False, "--no-frontend", help="Serve only the API"),
    dev: bool = typer.Option(
        False, "--dev", help="Run the web UI's dev server from a source checkout"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Start the API server and the web UI, then open the UI in a browser."""
    setup_logging(level="DEBUG" if verbose else "WARNING", show_path=verbose)

    mode = ui_mode(no_frontend=no_frontend, dev=dev)
    api_url = f"http://{host}:{port}"
    procs: list[subprocess.Popen[bytes]] = []

    try:
        display.console.print(f"[bold green]Starting API server[/bold green] on {api_url}")
        command = [sys.executable, "-m", "uvicorn", "compass_server.main:app"]
        command += ["--host", host, "--port", str(port)]
        if mode is UiMode.DEV:
            command.append("--reload")
        procs.append(subprocess.Popen(command))

        if mode is UiMode.BUNDLED:
            display.console.print(f"[bold green]Web UI[/bold green] on {api_url}")
            if _wait_for_server(f"{api_url}/health"):
                webbrowser.open(api_url)
        elif mode is UiMode.DEV:
            frontend_url = server_settings.FRONTEND_URL
            display.console.print(f"[bold green]Starting frontend[/bold green] on {frontend_url}")
            procs.append(subprocess.Popen(["pnpm", "dev"], cwd=WEB_DIR))
            # Poll until the dev server is ready, then open the browser.
            if _wait_for_server(
                f"http://{server_settings.FRONTEND_HOST}:{server_settings.FRONTEND_PORT}"
            ):
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
