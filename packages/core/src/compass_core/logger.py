"""Centralized logging configuration for Code Compass.

Call :func:`setup` once at process startup (e.g. from the CLI entry point).
All other modules should continue to use ``logging.getLogger(__name__)`` —
this module only configures the root handler.

Example::

    from compass_core.log import setup
    setup(level="INFO")
"""

from __future__ import annotations

import logging

from rich.logging import RichHandler


def setup(level: str = "WARNING", *, show_path: bool = False) -> None:
    """Configure the root logger with a Rich console handler.

    Args:
        level: Log level string (e.g. ``"DEBUG"``, ``"INFO"``, ``"WARNING"``).
            Defaults to ``"WARNING"`` so only important messages surface in the
            CLI by default.
        show_path: Whether Rich should append the source file/line to each
            log line.  Useful in debug mode, noisy otherwise.
    """
    handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_path=show_path,
        log_time_format="[%X]",
    )
    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
        force=True,
    )
