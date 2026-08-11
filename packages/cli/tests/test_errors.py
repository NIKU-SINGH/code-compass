"""Tests for compass_cli.errors."""

import pytest
import typer

from compass_cli.errors import handle_errors


def test_handle_errors_catches_oserror_and_exits(capsys):
    @handle_errors
    def raises_os_error() -> None:
        raise OSError("bad path")

    with pytest.raises(typer.Exit) as exc_info:
        raises_os_error()

    assert exc_info.value.exit_code == 1
    captured = capsys.readouterr()
    assert "bad path" in captured.out


def test_handle_errors_lets_other_exceptions_propagate():
    @handle_errors
    def raises_value_error() -> None:
        raise ValueError("not an os error")

    with pytest.raises(ValueError, match="not an os error"):
        raises_value_error()


def test_handle_errors_returns_value_on_success():
    @handle_errors
    def returns_none() -> None:
        return None

    assert returns_none() is None
