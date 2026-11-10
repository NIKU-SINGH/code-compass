from importlib.metadata import version

import typer

from compass_cli import display
from compass_cli.commands.ingest import ingest
from compass_cli.commands.mcp import mcp
from compass_cli.commands.query import describe, impact, overview, search, status
from compass_cli.commands.serve import serve
from compass_cli.commands.setup import setup

app = typer.Typer(
    help="Code Compass CLI",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


DISTRIBUTION = "compass-code"
"""The PyPI package that installs the ``compass`` command."""


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"{DISTRIBUTION} {version(DISTRIBUTION)}")
        raise typer.Exit()


VERSION = typer.Option(
    False, "--version", "-V", callback=_print_version, is_eager=True, help="Print the version."
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, show_version: bool = VERSION) -> None:
    """Code Compass — Navigate your codebase with ease."""
    if ctx.invoked_subcommand is None:
        display.help_commands()


app.command(name="ingest")(ingest)
app.command(name="status")(status)
app.command(name="search")(search)
app.command(name="describe")(describe)
app.command(name="impact")(impact)
app.command(name="overview")(overview)
app.command(name="serve")(serve)
app.command(name="mcp")(mcp)
app.command(name="setup")(setup)
app.command(name="help")(display.help_commands)


if __name__ == "__main__":
    app()
