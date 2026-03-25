import typer

app = typer.Typer(name="compass", help="Code Compass – codebase intelligence engine")


@app.command()
def index(repo_path: str = typer.Argument(..., help="Path to the repository to index")):
    """Index a repository into the code graph."""
    typer.echo(f"Indexing {repo_path} ...")


@app.command()
def ui(
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
):
    """Launch the Code Compass web UI."""
    import uvicorn

    uvicorn.run("compass_core.server.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    app()
