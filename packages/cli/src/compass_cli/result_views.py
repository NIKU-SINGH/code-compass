"""Rich views of query results, for a person reading them in a terminal.

The query commands print these only when stdout is a terminal. Piped output (scripts,
coding agents running ``compass`` in a shell) keeps the compact one-line-per-item text
from ``compass_core.render``, which is cheaper to read and easy to grep. Both show the same
facts; only the layout differs.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from compass_cli.display import GOLD
from compass_core.contract.models import Caveat, IndexStatus, ResultItem, SymbolRef
from compass_core.contract.results import (
    ImpactResult,
    NodeDetail,
    OverviewResult,
    RankedSymbol,
    SearchResult,
)
from compass_core.contract.types import CaveatCode
from compass_core.render import local_name, location, match_reason, plural, via_text
from compass_core.shared_types import EdgeType, SymbolKind

EDGE_LABELS: dict[EdgeType, str] = {
    EdgeType.CONTAINS: "Contains",
    EdgeType.IMPORTS: "Imports",
    EdgeType.INHERITS: "Inherits",
    EdgeType.CALLS: "Calls",
    EdgeType.CALLS_EXTERN: "External calls",
}
"""Row label for each edge type in the overview totals."""

_NO_WRAP = frozenset({"Location", "File", "Kind", "Hops"})
"""Columns kept on one line; narrow terminals wrap the others first."""

_LABEL_WIDTH = 13
"""Width of the dim label column in key/value grids, matching the ingest summary."""


def _title(text: str) -> Text:
    return Text(text, style=f"bold {GOLD}")


def _location(symbol: SymbolRef) -> Text:
    """``path:line`` with the directory dimmed, so the file name stands out."""
    where = location(symbol)
    directory, slash, rest = where.rpartition("/")
    text = Text(overflow="fold")
    if slash:
        text.append(directory + slash, style="dim")
    text.append(rest)
    return text


def _name(symbol: SymbolRef) -> Text:
    """The name within its file, last part bold (``User.`` **save**); a file's base name."""
    prefix, dot, last = local_name(symbol).rpartition(".")
    text = Text(overflow="fold")
    if dot and symbol.kind is not SymbolKind.FILE:
        text.append(prefix + dot, style="dim")
        text.append(last, style="bold")
    else:
        text.append(local_name(symbol).rpartition("/")[2], style="bold")
    return text


def _table(*headers: str, numeric: Sequence[str] = ()) -> Table:
    table = Table(box=box.SIMPLE_HEAD, header_style="dim", show_edge=False, pad_edge=False)
    for header in headers:
        table.add_column(
            header,
            justify="right" if header in numeric else "left",
            no_wrap=header in _NO_WRAP,
        )
    return table


def _section(title: str, body: RenderableType) -> Group:
    return Group(Text(""), _title(title), body)


def _caveats(caveats: Iterable[Caveat]) -> list[Text]:
    """Caveats in yellow; a stale index is already flagged by ``index_line``."""
    return [
        Text(f"! {caveat.message}", style="yellow")
        for caveat in caveats
        if caveat.code is not CaveatCode.STALE_INDEX
    ]


def _more(shown: int, total: int) -> list[Text]:
    hidden = total - shown
    if hidden <= 0:
        return []
    return [Text(f"… {hidden:,} more; raise --limit to see them", style="dim")]


def _freshness(status: IndexStatus) -> Text:
    if status.stale_file_count:
        changed = plural(status.stale_file_count, "file")
        return Text(f"⚠ {changed} changed since; run compass ingest", style="yellow")
    return Text("✓ up to date", style="green")


def index_line(status: IndexStatus) -> Text:
    """One dim line saying which index answered and whether it is fresh.

    Args:
        status: The index status every result carries.

    Returns:
        The line, e.g. ``index 5610406 · built 2026-11-10 09:30 UTC · ✓ up to date``.
    """
    commit = status.indexed_commit[:7] if status.indexed_commit else "no git commit"
    built = status.indexed_at.strftime("%Y-%m-%d %H:%M UTC")
    line = Text(f"index {commit} · built {built} · ", style="dim")
    line.append_text(_freshness(status))
    return line


def status_view(status: IndexStatus) -> Panel:
    """The index: which repository, which commit, when it was built and if it is fresh.

    Args:
        status: The index status.

    Returns:
        A gold panel with one labelled row per fact.

    Example:
        ``Repository  /home/me/app``, ``Commit  5610406``, ``Built  2026-11-10 09:30 UTC``
        and ``Status  ✓ up to date``.
    """
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="dim", min_width=_LABEL_WIDTH)
    grid.add_column()
    grid.add_row("Repository", Text(str(status.repo_root), style="bold"))
    grid.add_row("Commit", status.indexed_commit[:7] if status.indexed_commit else "no git commit")
    grid.add_row("Built", status.indexed_at.strftime("%Y-%m-%d %H:%M UTC"))
    grid.add_row("Status", _freshness(status))
    return Panel(grid, title=_title("compass index"), border_style=GOLD, padding=(1, 2))


def _totals(result: OverviewResult) -> Table:
    counts, calls = result.counts, result.call_resolution
    percent = round(100 * calls.resolved / calls.total) if calls.total else 0

    left = Table.grid(padding=(0, 3))
    left.add_column(style="dim", min_width=_LABEL_WIDTH)
    left.add_column(style="bold")
    left.add_row("Files", f"{counts.files:,}")
    left.add_row("Classes", f"{counts.classes:,}")
    left.add_row("Functions", f"{counts.functions:,}")
    resolved = Text(f"{percent}%", style="bold")
    resolved.append(f"  ({calls.resolved:,} of {calls.total:,})", style="dim")
    left.add_row("Calls resolved", resolved)

    right = Table.grid(padding=(0, 3))
    right.add_column(style="dim", min_width=_LABEL_WIDTH)
    right.add_column(style="bold")
    for edge, count in counts.edges_by_type.items():
        right.add_row(EDGE_LABELS[edge], f"{count:,}")

    columns = Table.grid(padding=(0, 8))
    columns.add_column()
    columns.add_column()
    columns.add_row(left, right)
    return columns


def _ranked(ranked: tuple[RankedSymbol, ...], count_header: str) -> Table:
    """One row per symbol with its count; files show only their path."""
    if all(item.symbol.kind is SymbolKind.FILE for item in ranked):
        files = _table("File", count_header, numeric=(count_header,))
        for item in ranked:
            files.add_row(_location(item.symbol), f"{item.count:,}")
        return files
    table = _table("Name", "Location", count_header, numeric=(count_header,))
    for item in ranked:
        table.add_row(_name(item.symbol), _location(item.symbol), f"{item.count:,}")
    return table


def overview_view(result: OverviewResult) -> Group:
    """The shape of the repository: totals, then one table per hot-spot list.

    Args:
        result: An overview result.

    Returns:
        The index line, a gold panel of totals, the entry points and the ranked tables,
        then any caveats.

    Example:
        A panel with ``Files 147`` and ``Calls 225``, then ``Most called functions`` as a
        table of ``Name``, ``Location`` and ``Callers``.
    """
    parts: list[RenderableType] = [
        index_line(result.index),
        Panel(_totals(result), title=_title("compass overview"), border_style=GOLD, padding=(1, 2)),
    ]
    if result.entry_points:
        entries = _table("File", "Module")
        for symbol in result.entry_points:
            entries.add_row(_location(symbol), Text(symbol.qualified_name, style="dim"))
        parts.append(_section("Entry points  (files nothing imports)", entries))
    sections = (
        ("Most imported files", result.most_imported_files, "Importers"),
        ("Most called functions", result.most_called_functions, "Callers"),
        ("Riskiest to change", result.riskiest_to_change, "Affected"),
    )
    for title, ranked, header in sections:
        if ranked:
            parts.append(_section(title, _ranked(ranked, header)))
    if result.top_external_libraries:
        libraries = _table("Library", "Calls", numeric=("Calls",))
        for lib in result.top_external_libraries:
            libraries.add_row(Text(lib.library, style="bold"), f"{lib.call_count:,}")
        parts.append(_section("Top external libraries", libraries))
    parts += _caveats(result.caveats)
    return Group(*parts)


def search_view(result: SearchResult) -> Group:
    """Search hits as a table, best first, with why each matched.

    Args:
        result: A search result.

    Returns:
        The index line, a title with the hit count, the table and any caveats.

    Example:
        ``search "save" · 2 hits`` then rows like ``save  method  app/models.py:2  exact
        name · 1 caller``.
    """
    table = _table("Name", "Kind", "Location", "Match")
    for hit in result.hits:
        table.add_row(
            _name(hit.symbol),
            Text(hit.symbol.kind.value, style="dim"),
            _location(hit.symbol),
            Text(match_reason(hit), style="dim"),
        )
    title = Text(f'search "{result.query}"', style=f"bold {GOLD}")
    title.append(f" · {plural(result.total, 'hit')}", style="dim")
    return Group(
        index_line(result.index),
        Text(""),
        title,
        table,
        *_more(len(result.hits), result.total),
        *_caveats(result.caveats),
    )


def _neighbours(title: str, symbols: tuple[SymbolRef, ...]) -> list[RenderableType]:
    if not symbols:
        return []
    table = _table("Name", "Kind", "Location")
    for symbol in symbols:
        table.add_row(_name(symbol), Text(symbol.kind.value, style="dim"), _location(symbol))
    return [_section(f"{title} ({len(symbols)})", table)]


def describe_view(detail: NodeDetail, *, include_source: bool = False) -> Group:
    """One symbol: a panel with where and what it is, then a table per neighbour list.

    Args:
        detail: A describe result.
        include_source: Also show the symbol's source text.

    Returns:
        The index line, the symbol panel, the neighbour tables and any caveats.

    Example:
        A panel titled ``method User.save`` with ``Location app/models.py:6-7`` and
        ``Id app/models.py::User.save``, then ``Callees (1)``.
    """
    symbol = detail.symbol
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="dim", min_width=_LABEL_WIDTH)
    grid.add_column()
    grid.add_row("Name", _name(symbol))
    span = location(symbol)
    if symbol.file_path and symbol.line_start and symbol.line_end != symbol.line_start:
        span = f"{span}-{symbol.line_end}"
    grid.add_row("Location", span)
    grid.add_row("Id", Text(symbol.id, style="dim"))
    if symbol.signature:
        grid.add_row("Signature", Text(symbol.signature, style="bold"))
    body: list[RenderableType] = [grid]
    if detail.docstring:
        body += [Text(""), Text(detail.docstring.strip(), style="italic")]
    parts: list[RenderableType] = [
        index_line(detail.index),
        Panel(
            Group(*body),
            title=_title(f"{symbol.kind.value} {symbol.name}"),
            border_style=GOLD,
            padding=(1, 2),
        ),
    ]
    parts += _neighbours("Bases", detail.bases)
    parts += _neighbours("Subclasses", detail.subclasses)
    parts += _neighbours("Members", detail.members)
    parts += _neighbours("Callers", detail.callers)
    parts += _neighbours("Callees", detail.callees)
    parts += _neighbours("Imports", detail.imports)
    parts += _neighbours("Imported by", detail.imported_by)
    if detail.truncated:
        parts.append(
            Text("! some lists were cut short; describe the related symbols directly", "yellow")
        )
    if include_source and symbol.source:
        parts.append(_section("Source", Text(symbol.source.rstrip())))
    parts += _caveats(detail.caveats)
    return Group(*parts)


def _impact_row(table: Table, item: ResultItem) -> None:
    via = via_text(item.via) if item.via else ""
    confidence = "" if item.min_confidence is None else f"{item.min_confidence:.2f}"
    table.add_row(
        str(item.distance),
        _name(item.symbol),
        _location(item.symbol),
        Text(via, style="dim"),
        confidence,
    )


def impact_view(result: ImpactResult) -> Group:
    """What may break if the target changes: a summary panel, then one row per symbol.

    Args:
        result: An impact result.

    Returns:
        The index line, the summary panel, the affected symbols nearest first and the
        caveats (an empty answer is never shown as certain).

    Example:
        A panel ``impact of function decode_token`` with ``Affected 3 symbols in 2
        files``, then rows like ``1  app.api.handle  app/api.py:4  calls decode_token
        1.00``.
    """
    target = result.target
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="dim", min_width=_LABEL_WIDTH)
    grid.add_column()
    grid.add_row("Target", _name(target))
    grid.add_row("Location", location(target))
    grid.add_row("Depth", str(result.depth))
    grid.add_row(
        "Affected",
        Text(
            f"{plural(result.total, 'symbol')} in {plural(result.affected_file_count, 'file')}",
            style="bold",
        ),
    )
    table = _table("Hops", "Name", "Location", "Via", "Confidence", numeric=("Hops", "Confidence"))
    shown = 0
    for group in result.groups:
        for item in group.items:
            _impact_row(table, item)
            shown += 1
    parts: list[RenderableType] = [
        index_line(result.index),
        Panel(
            grid,
            title=_title(f"impact of {target.kind.value} {target.name}"),
            border_style=GOLD,
            padding=(1, 2),
        ),
    ]
    if shown:
        parts.append(table)
    parts += _more(shown, result.total)
    parts += _caveats(result.caveats)
    return Group(*parts)
