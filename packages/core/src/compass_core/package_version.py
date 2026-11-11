"""The installed version of Code Compass, read once for the CLI and the HTTP server.

Code Compass is published as one package, ``compass-code``, so that is the name to ask
the installed metadata about. A development environment synced before the package got
that name has no such metadata; the version is then unknown rather than a crash.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

DISTRIBUTION = "compass-code"
"""The PyPI package that installs Code Compass."""

UNKNOWN = "unknown"
"""What ``installed_version`` returns when ``compass-code`` is not installed."""


def installed_version() -> str:
    """The installed version of ``compass-code``.

    Returns:
        The version, e.g. ``"0.1.1"``, or ``UNKNOWN`` when the package metadata is
        missing (a workspace that needs ``uv sync --all-packages``).

    Example:
        After ``uv tool install compass-code==0.1.1``, ``installed_version()`` returns
        ``"0.1.1"``.
    """
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return UNKNOWN
