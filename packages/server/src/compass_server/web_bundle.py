"""The web UI bundled into this package as static files, when it was built in.

``make web-static`` exports the Next.js app into ``compass_server/static``; the release
build always does, so an installed ``compass serve`` serves the UI from the API's own
port. A source checkout without that step has no bundle and runs the dev server instead.
"""

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"
"""Where ``make web-static`` puts the exported web app."""

_ENTRY = "index.html"


def has_bundled_ui() -> bool:
    """Whether the static web UI was built into this package.

    Returns:
        ``True`` when ``STATIC_DIR`` holds an exported app.

    Example:
        After ``make web-static``, ``has_bundled_ui()`` is ``True``.
    """
    return (STATIC_DIR / _ENTRY).is_file()
