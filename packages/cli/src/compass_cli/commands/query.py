"""Query commands: ``status``, ``search``, ``describe``, ``impact`` and ``overview``.

Each command finds the index, opens it read-only, calls one ``compass_core.query``
function and prints its result: in a terminal, Rich tables and panels
(``compass_cli.result_views``); when piped, as for a script or a coding agent, the compact
one-line-per-item text of ``compass_core.render``; and the contract JSON with
``--format json``. Queries never write; without an index they exit with a message saying
to run ``compass ingest``.

Answers go to stdout. An ambiguous or unknown reference is an answer too (the candidates
or suggestions), printed to stdout with its own exit code; failures go to stderr. Exit
codes come from ``ERROR_MAPPINGS``: 0 ok, 2 invalid argument, 3 not found, 4 ambiguous,
5 no index, 6 index busy, 7 index must be rebuilt, 8 timeout.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NoReturn, TypeVar

import typer
from rich.console import RenderableType

from compass_cli import result_views
from compass_cli.display import console
from compass_cli.types import OutputFormat
from compass_core.contract.errors import ERROR_MAPPINGS, ErrorResponse, to_error_response
from compass_core.contract.params import (
    DEFAULT_IMPACT_DEPTH,
    DEFAULT_LIMIT,
    DEFAULT_MIN_CONFIDENCE,
    MAX_DEPTH,
    MAX_LIMIT,
    ImpactParams,
    SearchParams,
)
from compass_core.contract.results import AmbiguousReference, Lookup, SymbolNotFound
from compass_core.contract.serialize import Serializable, to_json
from compass_core.errors import ErrorCode, QueryError
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation, locate_index, locate_repo_index
from compass_core.query.detail import describe as describe_symbol
from compass_core.query.impact import impact as impact_of
from compass_core.query.overview import overview as repo_overview
from compass_core.query.search import find_symbols
from compass_core.query.status import index_status
from compass_core.render import (
    render_ambiguous,
    render_describe,
    render_error,
    render_impact,
    render_not_found,
    render_overview,
    render_search,
    render_status,
)
from compass_core.shared_types import SymbolKind

R = TypeVar("R")

FORMAT = typer.Option(
    OutputFormat.TEXT,
    "--format",
    "-f",
    help="text (default; tables in a terminal, compact lines when piped) or json.",
)
REPO = typer.Option(
    None,
    "--repo",
    help="Repository to query; default: the one containing the current directory.",
    file_okay=False,
)
KIND = typer.Option(None, "--kind", "-k", help="Only this kind of symbol.")
LIMIT = typer.Option(DEFAULT_LIMIT, "--limit", "-n", min=1, max=MAX_LIMIT, help="Most items.")


def _fail(error: ErrorResponse, fmt: OutputFormat) -> NoReturn:
    message = to_json(error) if fmt is OutputFormat.JSON else render_error(error)
    typer.echo(message, err=True)
    raise typer.Exit(code=ERROR_MAPPINGS[error.code].exit_code)


def _run(
    repo: Path | None, fmt: OutputFormat, operation: Callable[[GraphDB, IndexLocation], R]
) -> R:
    """Locate and open the index read-only, then run ``operation`` on it."""
    try:
        location = locate_repo_index(repo) if repo else locate_index()
        with GraphDB(location.db_path, read_only=True) as db:
            return operation(db, location)
    except QueryError as exc:
        _fail(to_error_response(exc), fmt)


def _print(result: Serializable, text: str, fmt: OutputFormat) -> None:
    typer.echo(to_json(result) if fmt is OutputFormat.JSON else text)


def _show(
    result: Serializable,
    text: Callable[[], str],
    view: Callable[[], RenderableType],
    fmt: OutputFormat,
) -> None:
    """Print a result: Rich ``view`` in a terminal, else compact ``text`` or JSON."""
    if fmt is OutputFormat.TEXT and console.is_terminal:
        console.print(view())
        console.print()
    else:
        _print(result, text(), fmt)


def _found(result: Lookup[R], fmt: OutputFormat) -> R:
    """Return a found result; print the candidates or suggestions and exit otherwise."""
    if isinstance(result, AmbiguousReference):
        _print(result, render_ambiguous(result), fmt)
        raise typer.Exit(code=ERROR_MAPPINGS[ErrorCode.AMBIGUOUS].exit_code)
    if isinstance(result, SymbolNotFound):
        _print(result, render_not_found(result), fmt)
        raise typer.Exit(code=ERROR_MAPPINGS[ErrorCode.NOT_FOUND].exit_code)
    return result


def status(fmt: OutputFormat = FORMAT, repo: Path | None = REPO) -> None:
    """Show which index is used, when it was built and whether files changed since."""
    result = _run(repo, fmt, lambda db, location: index_status(location, db))
    _show(result, lambda: render_status(result), lambda: result_views.status_view(result), fmt)


def search(
    text: str = typer.Argument(..., help="Name, qualified name, or part of either."),
    kind: SymbolKind | None = KIND,
    limit: int = LIMIT,
    fmt: OutputFormat = FORMAT,
    repo: Path | None = REPO,
) -> None:
    """Find files, classes, functions and methods by name. Best matches first."""
    params = SearchParams(query=text, kind=kind, limit=limit)
    result = _run(repo, fmt, lambda db, location: find_symbols(db, location, params))
    _show(result, lambda: render_search(result), lambda: result_views.search_view(result), fmt)


def describe(
    ref: str = typer.Argument(..., help="Symbol id, file path, qualified name or name."),
    source: bool = typer.Option(False, "--source", help="Also print the source text."),
    fmt: OutputFormat = FORMAT,
    repo: Path | None = REPO,
) -> None:
    """Show one symbol: location, signature, docstring, callers, callees and members."""
    detail = _found(_run(repo, fmt, lambda db, location: describe_symbol(db, location, ref)), fmt)
    _show(
        detail,
        lambda: render_describe(detail, include_source=source),
        lambda: result_views.describe_view(detail, include_source=source),
        fmt,
    )


def impact(
    ref: str = typer.Argument(..., help="Symbol id, file path, qualified name or name."),
    depth: int = typer.Option(
        DEFAULT_IMPACT_DEPTH, "--depth", "-d", min=1, max=MAX_DEPTH, help="Most hops."
    ),
    min_confidence: float = typer.Option(
        DEFAULT_MIN_CONFIDENCE, "--min-confidence", min=0.0, max=1.0, help="Skip weaker calls."
    ),
    limit: int = LIMIT,
    fmt: OutputFormat = FORMAT,
    repo: Path | None = REPO,
) -> None:
    """List what may break if a symbol or file changes, nearest first."""
    params = ImpactParams(depth=depth, min_confidence=min_confidence, limit=limit)
    result = _found(_run(repo, fmt, lambda db, location: impact_of(db, location, ref, params)), fmt)
    _show(result, lambda: render_impact(result), lambda: result_views.impact_view(result), fmt)


def overview(fmt: OutputFormat = FORMAT, repo: Path | None = REPO) -> None:
    """Summarise the repository: totals, entry points and the most connected symbols."""
    result = _run(repo, fmt, lambda db, location: repo_overview(db, location))
    _show(result, lambda: render_overview(result), lambda: result_views.overview_view(result), fmt)
