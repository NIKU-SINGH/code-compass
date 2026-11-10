import typer

from compass_cli import display
from compass_cli.commands.ingest import ingest
from compass_cli.commands.query import describe, impact, overview, search, status
from compass_cli.commands.serve import serve

app = typer.Typer(
    help="Code Compass CLI",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
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


if __name__ == "__main__":
    app()
