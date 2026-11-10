"""Shared CLI error-boundary decorator."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TypeVar

import typer

from compass_cli import display

F = TypeVar("F", bound=Callable[..., None])


def handle_errors(func: F) -> F:
    """Catch expected OS-level failures, print a clean message, and exit(1).

    Anything not an OSError still propagates with a full traceback.
    """

    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> None:
        try:
            func(*args, **kwargs)
        except OSError as exc:
            display.error(str(exc))
            raise typer.Exit(code=1) from exc

    return wrapper  # type: ignore[return-value]  # functools.wraps keeps the signature; mypy cannot prove wrapper is F
