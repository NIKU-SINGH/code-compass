"""Tests for compass_cli.display."""

from compass_cli import display


def test_error_prints_message(capsys):
    display.error("something broke")

    captured = capsys.readouterr()
    assert "something broke" in captured.out
    assert "Error" in captured.out


def test_next_steps_suggest_query_commands_and_help(capsys):
    display.next_steps()
    out = capsys.readouterr().out
    for command in ("compass overview", "compass search", "compass setup", "compass help"):
        assert command in out
    assert "--help" not in out
