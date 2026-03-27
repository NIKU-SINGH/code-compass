import subprocess
import sys
from pathlib import Path

import typer
from compass_core.settings import settings
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

app = typer.Typer(help="Code Compass CLI")
console = Console()


def print_banner():
    """Prints a beautiful branding banner."""
    banner_text = r"""
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
    clean_lines = [line.rstrip() for line in banner_text.strip("\n").split("\n")]
    clean_banner = "\n".join(clean_lines)

    console.print(
        Align.center(
            Panel(
                Text(clean_banner, style="bold color(214)", no_wrap=True, justify="left"),
                subtitle="[bold color(214)]Next-Gen Code Intelligence[/bold color(214)]",
                border_style="color(214)",
                padding=(1, 2),
                expand=False,
            )
        )
    )
    console.print()
    console.print(Align.center("[bold color(214)]🧭 Navigate your codebase with ease 🧭[/bold color(214)]"))


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Code Compass - Navigate your codebase with ease."""
    if ctx.invoked_subcommand is None:
        print_banner()
        console.print("\n[bold yellow]Usage:[/bold yellow] compass [COMMAND]")
        console.print("[dim]Use --help to see available commands.[/dim]")
    else:
        print_banner()


@app.command()
def index(path: str = typer.Argument(..., help="Path to the repository to index")):
    """Index a repository for code intelligence."""
    console.print(f"[bold blue]Indexing repository at:[/bold blue] {path}")
    # TODO: Connect to compass-core for indexing
    console.print("[green]Indexing complete (mocked).[/green]")


@app.command()
def serve(
    host: str = typer.Option(settings.API_HOST, help="Host for the API server"),
    port: int = typer.Option(settings.API_PORT, help="Port for the API server"),
    no_frontend: bool = typer.Option(False, "--no-frontend", help="Skip starting the frontend"),
):
    """Start the API server and frontend dev server."""
    web_dir = Path(__file__).parents[4] / "apps" / "web"

    procs: list[subprocess.Popen] = []

    try:
        console.print(f"[bold green]Starting API server[/bold green] on http://{host}:{port}")
        procs.append(
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "compass_core.server.main:app",
                 "--host", host, "--port", str(port), "--reload"],
            )
        )

        if not no_frontend and web_dir.exists():
            console.print(f"[bold green]Starting frontend[/bold green] on {settings.FRONTEND_URL}")
            procs.append(
                subprocess.Popen(["pnpm", "dev"], cwd=web_dir)
            )

        console.print("[dim]Press Ctrl+C to stop.[/dim]")

        for proc in procs:
            proc.wait()

    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait()


if __name__ == "__main__":
    app()
