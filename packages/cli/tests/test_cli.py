"""Tests for compass_cli."""

from typer.testing import CliRunner

from compass_cli.main import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_index_command_exists():
    result = runner.invoke(app, ["index", "--help"])
    assert result.exit_code == 0
