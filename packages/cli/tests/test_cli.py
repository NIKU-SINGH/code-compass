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
    assert "index" in result.output
    assert "serve" in result.output
    assert "██████╗" not in result.output


def test_index_command_exists():
    result = runner.invoke(app, ["index", "--help"])
    assert result.exit_code == 0
