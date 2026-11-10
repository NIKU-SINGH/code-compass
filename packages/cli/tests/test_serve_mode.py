"""``compass serve`` picks the bundled UI when installed and the dev server in a checkout."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from compass_cli.commands import serve
from compass_cli.commands.serve import UiMode, ui_mode

Layout = Callable[..., None]
"""``layout(checkout=..., bundled=...)``: fake a source checkout and/or a bundled UI."""


@pytest.fixture
def layout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Layout:
    def configure(*, checkout: bool, bundled: bool) -> None:
        web_dir = tmp_path / "apps" / "web"
        if checkout:
            web_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(serve, "WEB_DIR", web_dir)
        monkeypatch.setattr(serve, "has_bundled_ui", lambda: bundled)

    return configure


def test_installed_package_serves_the_bundle(layout: Layout) -> None:
    layout(checkout=False, bundled=True)
    assert ui_mode(no_frontend=False, dev=False) is UiMode.BUNDLED


def test_checkout_without_bundle_runs_the_dev_server(layout: Layout) -> None:
    layout(checkout=True, bundled=False)
    assert ui_mode(no_frontend=False, dev=False) is UiMode.DEV


def test_dev_flag_prefers_the_dev_server_over_a_bundle(layout: Layout) -> None:
    layout(checkout=True, bundled=True)
    assert ui_mode(no_frontend=False, dev=False) is UiMode.BUNDLED
    assert ui_mode(no_frontend=False, dev=True) is UiMode.DEV


def test_no_ui_available_or_wanted_serves_only_the_api(layout: Layout) -> None:
    layout(checkout=False, bundled=False)
    assert ui_mode(no_frontend=False, dev=False) is UiMode.NONE
    layout(checkout=True, bundled=True)
    assert ui_mode(no_frontend=True, dev=False) is UiMode.NONE
