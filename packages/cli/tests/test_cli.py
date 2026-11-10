"""Tests for compass_cli."""

import pytest
from typer.testing import CliRunner

from compass_cli.main import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_cli_without_command_shows_concise_help():
    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert "Navigate your codebase with ease" in result.output
    assert "Usage:" in result.output
    for command in (
        "ingest",
        "status",
        "search",
        "describe",
        "impact",
        "overview",
        "setup",
        "mcp",
        "serve",
    ):
        assert command in result.output
    assert "██████╗" not in result.output


def test_help_command_shows_the_same_list():
    result = runner.invoke(app, ["help"])

    assert result.exit_code == 0
    assert result.output == runner.invoke(app, []).output


def test_ingest_command_exists():
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0


def test_serve_command_exists():
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0


def test_ingest_command_wraps_oserror(tmp_path):
    # A path that's a file, not a directory: `db_path.parent.mkdir(parents=True)`
    # inside ingest() will try to create a ".compass" directory *under* this
    # file, which raises NotADirectoryError (an OSError subclass). Note: a
    # simply nonexistent path would NOT work here — mkdir(parents=True) would
    # silently create it as a side effect before any error could occur.
    blocked_path = tmp_path / "not-a-directory"
    blocked_path.write_text("not a repo")

    result = runner.invoke(app, ["ingest", str(blocked_path)])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_ingest_reports_skipped_edges(tmp_path):
    # app.py's call to the class constructor resolves, but CALLS edges only
    # connect functions, so the writer cannot store it: the summary must say
    # so instead of counting it as written.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "lib.py").write_text("class Widget:\n    pass\n\n\ndef helper():\n    pass\n")
    (repo / "app.py").write_text(
        "from lib import Widget, helper\n\n\n"
        "def build():\n    return Widget()\n\n\n"
        "def run():\n    helper()\n"
    )

    result = runner.invoke(app, ["ingest", str(repo), "--db", str(tmp_path / "g.ladybug")])

    assert result.exit_code == 0, result.output
    assert "1 edge skipped (callee is not a stored function, e.g. class constructor calls)" in (
        result.output
    )


@pytest.mark.parametrize(
    "command", ["status", "search", "describe", "impact", "overview", "setup", "mcp"]
)
def test_query_commands_exist(command: str) -> None:
    result = runner.invoke(app, [command, "--help"])
    assert result.exit_code == 0


def test_version_flag_names_the_package():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.output.startswith("compass-code ")
