import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Static
from textual.containers import Vertical

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
                Text(clean_banner, style="bold bright_cyan", no_wrap=True, justify="left"),
                subtitle="[bold bright_magenta]Next-Gen Code Intelligence[/bold bright_magenta]",
                border_style="bright_magenta",
                padding=(1, 2),
                expand=False,
            )
        )
    )
    console.print()
    console.print(
        Align.center("[bold white]🧭 Navigate your codebase with ease 🧭[/bold white]")
    )

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Code Compass - Navigate your codebase with ease."""
    if ctx.invoked_subcommand is None:
        print_banner()
        console.print("\n[bold yellow]Usage:[/bold yellow] compass [COMMAND]")
        console.print("[dim]Use --help to see available commands.[/dim]")
    else:
        # For subcommands, we might want a shorter version or just the logo
        if ctx.invoked_subcommand != "ui": # Don't print banner before TUI starts
             print_banner()

class CodeCompassTUI(App):
    """An interactive Terminal UI for Code Compass (Similar to Claude Code)."""
    
    # Textual allows you to write actual CSS for the terminal!
    CSS = """
    #banner {
        height: auto;
        content-align: center middle;
        background: transparent;
        color: cyan;
        text-style: bold;
        padding: 0 2;
        border: solid magenta;
        margin: 1 2;
    }
    Input {
        dock: bottom;
        margin: 1 2;
    }
    RichLog {
        padding: 1 2;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        """Draw the UI."""
        yield Header(show_clock=True)
        banner_text = r"""
  🧭 CODE COMPASS 🧭
  Navigate your codebase with intelligence
        """
        yield Static(banner_text, id="banner")
        with Vertical():
            yield Log(id="chat_history") # Where the AI responses go
            yield Input(placeholder="Ask Code Compass (e.g., 'Trace the auth flow')...", id="prompt")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when the user hits Enter."""
        log = self.query_one(Log)
        input_widget = self.query_one(Input)
        
        # 1. Print user message
        log.write_line(f"[bold blue]You:[/bold blue] {event.value}")
        
        # 2. Clear the input box
        input_widget.value = ""
        
        # 3. TODO: Send this to your core.llm.router and KuzuDB!
        # For now, we mock the response:
        log.write_line(f"[bold green]Compass:[/bold green] Tracing '{event.value}' in KuzuDB...\n")

def run_tui():
    """Start the interactive TUI."""
    tui = CodeCompassTUI()
    tui.run()

@app.command()
def index(path: str = typer.Argument(..., help="Path to the repository to index")):
    """Index a repository for code intelligence."""
    console.print(f"[bold blue]Indexing repository at:[/bold blue] {path}")
    # TODO: Connect to compass-core for indexing
    console.print("[green]Indexing complete (mocked).[/green]")

@app.command()
def ui():
    """Launch the interactive Code Compass UI."""
    # We clear the screen for TUI
    console.clear()
    run_tui()

if __name__ == "__main__":
    app()