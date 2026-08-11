"""Tests for compass_cli.display."""

from compass_cli import display


def test_error_prints_message(capsys):
    display.error("something broke")

    captured = capsys.readouterr()
    assert "something broke" in captured.out
    assert "Error" in captured.out
