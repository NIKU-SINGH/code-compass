"""Tests for compass_cli."""

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
    assert "ingest" in result.output
    assert "serve" in result.output
    assert "██████╗" not in result.output


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
