"""Tests for compass_cli.display."""

from rich.console import Console

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


def _terminal(monkeypatch, width: int) -> Console:
    terminal = Console(force_terminal=True, width=width, record=True, color_system=None)
    monkeypatch.setattr(display, "console", terminal)
    return terminal


def test_logo_shows_in_a_wide_terminal_with_its_subtitle(monkeypatch):
    terminal = _terminal(monkeypatch, display.LOGO_MIN_WIDTH)

    assert display.logo(subtitle="compass-code 9.9.9") is True
    text = terminal.export_text()
    assert "██████╗" in text and "compass-code 9.9.9" in text


def test_logo_is_skipped_in_a_narrow_terminal(monkeypatch):
    terminal = _terminal(monkeypatch, display.LOGO_MIN_WIDTH - 1)

    assert display.logo() is False
    assert terminal.export_text() == ""


def test_welcome_is_the_logo_then_the_commands_and_help_has_no_logo(monkeypatch):
    terminal = _terminal(monkeypatch, 100)

    display.welcome()
    welcome = terminal.export_text()
    assert welcome.index("██████╗") < welcome.index("Commands:")

    display.help_commands()
    assert "██████╗" not in terminal.export_text()
