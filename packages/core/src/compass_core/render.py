"""Compact text for every query result, shared by the CLI and the MCP server.

One line per item, ``file:line`` first, so the text is cheap for an agent to read and
easy to grep. Every answer that describes the index starts with a header saying when it
was built and whether files changed since. Caveats are prefixed with ``!``. JSON output
does not go through here; it is ``contract.serialize.to_json``.

This module imports only the contract and the shared vocabulary.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import assert_never

from compass_core.contract.errors import ErrorResponse
from compass_core.contract.models import Caveat, IndexStatus, ResultItem, SymbolRef, Via
from compass_core.contract.results import (
    AmbiguousReference,
    ImpactResult,
    NodeDetail,
    OverviewResult,
    RankedSymbol,
    SearchHit,
    SearchResult,
    SymbolNotFound,
)
from compass_core.contract.types import SearchMatch, ViaKind
from compass_core.shared_types import SymbolKind

_INDENT = "  "
_ID_SEPARATOR = "::"
"""Splits a public id into its file part and its ``[Class.]name`` part."""


def location(symbol: SymbolRef) -> str:
    """Where a symbol is: ``path:line`` for a definition, ``path`` for a file.

    Args:
        symbol: Any symbol.

    Returns:
        The 1-indexed location, or the external reference for an external function.

    Example:
        ``location(<User.save at app/models.py line 6>)`` returns ``"app/models.py:6"``.
    """
    if symbol.file_path is None:
        return symbol.qualified_name
    if symbol.line_start is None:
        return symbol.file_path
    return f"{symbol.file_path}:{symbol.line_start}"


def local_name(symbol: SymbolRef) -> str:
    """A symbol's name within its file: ``Class.method``, ``function`` or the file path.

    Shorter than the qualified name; shown next to ``location``, which names the file.

    Args:
        symbol: Any symbol.

    Returns:
        The part of the public id after ``::`` for a class or function, the path for a
        file, and the qualified name for an external function.

    Example:
        ``local_name(<User.save in app/models.py>)`` returns ``"User.save"``.
    """
    if symbol.kind is SymbolKind.FILE and symbol.file_path is not None:
        return symbol.file_path
    if symbol.kind in (SymbolKind.FILE, SymbolKind.EXTERNAL):
        return symbol.qualified_name
    _, separator, name = symbol.id.partition(_ID_SEPARATOR)
    return name if separator else symbol.name


def _span(symbol: SymbolRef) -> str:
    start, end = symbol.line_start, symbol.line_end
    if symbol.file_path and start and end and end != start:
        return f"{symbol.file_path}:{start}-{end}"
    return location(symbol)


def _symbol(symbol: SymbolRef, *extra: str) -> str:
    """``location  kind  qualified_name  [extra ...]`` on one line."""
    parts = [location(symbol), symbol.kind.value, symbol.qualified_name, *extra]
    return _INDENT.join(part for part in parts if part)


def plural(count: int, noun: str) -> str:
    """``count`` and ``noun``, pluralised.

    Args:
        count: How many.
        noun: The singular noun.

    Returns:
        The phrase.

    Example:
        ``plural(3, "class")`` returns ``"3 classes"``.
    """
    if count == 1:
        return f"{count} {noun}"
    return f"{count} {noun}es" if noun.endswith("s") else f"{count} {noun}s"


def render_status(status: IndexStatus) -> str:
    """One header line describing the index.

    Args:
        status: The index status every result carries.

    Returns:
        The commit, build time and freshness of the index.

    Example:
        ``index: a1b2c3d · built 2026-11-10 09:14 UTC · 2 files changed since; run
        `compass ingest```
    """
    commit = status.indexed_commit[:7] if status.indexed_commit else "no git commit"
    built = status.indexed_at.strftime("%Y-%m-%d %H:%M UTC")
    stale = status.stale_file_count
    fresh = (
        f"{plural(stale, 'file')} changed since; run `compass ingest`" if stale else "up to date"
    )
    return f"index: {commit} · built {built} · {fresh}"


def _caveats(caveats: Iterable[Caveat]) -> list[str]:
    return [f"! {caveat.message}" for caveat in caveats]


def _more(shown: int, total: int) -> list[str]:
    hidden = total - shown
    return [f"… {hidden} more; raise the limit to see them"] if hidden > 0 else []


def match_reason(hit: SearchHit) -> str:
    """Why a search hit matched, with its fan-in for files and functions.

    Args:
        hit: A search hit.

    Returns:
        The reason.

    Example:
        ``"exact name · 1 caller"``.
    """
    match hit.match:
        case SearchMatch.EXACT:
            reason = "exact name"
        case SearchMatch.QUALIFIED_SUFFIX:
            reason = "qualified name"
        case SearchMatch.PREFIX:
            reason = "name prefix"
        case SearchMatch.SUBSTRING:
            reason = "name contains"
        case _:
            assert_never(hit.match)
    if hit.symbol.kind is SymbolKind.FILE:
        return f"{reason} · {plural(hit.fan_in, 'importer')}"
    if hit.symbol.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD):
        return f"{reason} · {plural(hit.fan_in, 'caller')}"
    return reason


def render_search(result: SearchResult) -> str:
    """Search hits, best first, each with why it matched.

    Args:
        result: A search result.

    Returns:
        The text.

    Example:
        A search for ``save`` renders ``app/models.py:2  method  app.models.Base.save  exact
        name · 1 caller``.
    """
    lines = [
        render_status(result.index),
        f'search "{result.query}" · {plural(result.total, "hit")}',
        *(_symbol(hit.symbol, match_reason(hit)) for hit in result.hits),
        *_more(len(result.hits), result.total),
        *_caveats(result.caveats),
    ]
    return "\n".join(lines)


def _section(title: str, symbols: tuple[SymbolRef, ...]) -> list[str]:
    if not symbols:
        return []
    return ["", f"{title} ({len(symbols)}):", *(_INDENT + _symbol(s) for s in symbols)]


def render_describe(detail: NodeDetail, *, include_source: bool = False) -> str:
    """One symbol: where it is, its signature and docstring, and its neighbours.

    Args:
        detail: A describe result.
        include_source: Also print the symbol's source text (off by default to keep the
            answer short; the location says where to read it).

    Returns:
        The text.

    Example:
        Describing ``User.save`` renders ``method app.models.User.save  app/models.py:6-7``,
        its id, signature and docstring, then ``callees (1):`` and its callee.
    """
    symbol = detail.symbol
    lines = [
        render_status(detail.index),
        f"{symbol.kind.value} {symbol.qualified_name}  {_span(symbol)}",
        f"id: {symbol.id}",
    ]
    if symbol.signature:
        lines.append(symbol.signature)
    if detail.docstring:
        lines += ["", detail.docstring.strip()]
    lines += _section("bases", detail.bases)
    lines += _section("subclasses", detail.subclasses)
    lines += _section("members", detail.members)
    lines += _section("callers", detail.callers)
    lines += _section("callees", detail.callees)
    lines += _section("imports", detail.imports)
    lines += _section("imported by", detail.imported_by)
    if detail.truncated:
        lines += ["", "! some lists were cut short; describe the related symbols directly"]
    if include_source and symbol.source:
        lines += ["", "source:", symbol.source.rstrip()]
    lines += _caveats(detail.caveats)
    return "\n".join(lines)


def via_text(via: Via) -> str:
    """How an affected symbol depends on the one before it.

    Args:
        via: The link.

    Returns:
        A verb and a name.

    Example:
        ``"calls decode_token"``.
    """
    match via.kind:
        case ViaKind.CALLS:
            verb = "calls"
        case ViaKind.IMPORTS:
            verb = "imports"
        case ViaKind.INHERITS:
            verb = "inherits"
        case _:
            assert_never(via.kind)
    return f"{verb} {via.symbol.name}"


def _impact_item(item: ResultItem) -> str:
    via = via_text(item.via) if item.via else ""
    confidence = "" if item.min_confidence is None else f"{item.min_confidence:.2f}"
    return _INDENT + _symbol(item.symbol, via, confidence)


def render_impact(result: ImpactResult) -> str:
    """What may break if the target changes, nearest first.

    Args:
        result: An impact result.

    Returns:
        The text: the target, a summary, the affected items grouped by distance, and
        caveats (an empty answer is never shown as certain).

    Example:
        ``impact of function app.auth.decode_token (app/auth.py:3) · depth 3`` then
        ``distance 1`` and ``app/api.py:4  function  app.api.handle  calls decode_token
        1.00``.
    """
    target = result.target
    shown = sum(len(group.items) for group in result.groups)
    lines = [
        render_status(result.index),
        f"impact of {target.kind.value} {target.qualified_name} ({location(target)})"
        f" · depth {result.depth}",
        f"{plural(result.total, 'affected symbol')} in "
        f"{plural(result.affected_file_count, 'file')}",
    ]
    distance = None
    for group in result.groups:
        if group.distance != distance:
            distance = group.distance
            lines.append(f"distance {distance}")
        lines += [_impact_item(item) for item in group.items]
    lines += _more(shown, result.total)
    lines += _caveats(result.caveats)
    return "\n".join(lines)


def _ranked(title: str, ranked: tuple[RankedSymbol, ...], unit: str) -> list[str]:
    if not ranked:
        return []
    return [
        "",
        f"{title}:",
        *(_INDENT + _symbol(r.symbol, plural(r.count, unit)) for r in ranked),
    ]


def render_overview(result: OverviewResult) -> str:
    """The shape of the repository: totals, entry points and hot spots.

    Args:
        result: An overview result.

    Returns:
        The text.

    Example:
        ``8 files · 3 classes · 15 functions`` then ``calls resolved: 12 of 40 (30%)`` and
        the ranked lists.
    """
    counts = result.counts
    edges = " · ".join(f"{edge.value} {n}" for edge, n in counts.edges_by_type.items())
    resolution = result.call_resolution
    percent = round(100 * resolution.resolved / resolution.total) if resolution.total else 0
    lines = [
        render_status(result.index),
        f"{plural(counts.files, 'file')} · {plural(counts.classes, 'class')} · "
        f"{plural(counts.functions, 'function')}",
        f"edges: {edges}",
        f"calls resolved: {resolution.resolved} of {resolution.total} ({percent}%)",
    ]
    lines += _section("entry points", result.entry_points)
    lines += _ranked("most imported files", result.most_imported_files, "importer")
    lines += _ranked("most called functions", result.most_called_functions, "caller")
    lines += _ranked("riskiest to change", result.riskiest_to_change, "affected symbol")
    if result.top_external_libraries:
        lines += ["", "top external libraries:"]
        lines += [
            f"{_INDENT}{lib.library}  {plural(lib.call_count, 'call')}"
            for lib in result.top_external_libraries
        ]
    lines += _caveats(result.caveats)
    return "\n".join(lines)


def render_ambiguous(result: AmbiguousReference) -> str:
    """The candidates of an ambiguous reference, with how to pick one.

    Args:
        result: An ambiguous outcome.

    Returns:
        The text; each candidate's id resolves exactly when passed back.

    Example:
        ``"save" matches 2 symbols; pass one of these ids or a qualified name:`` then
        ``app/models.py::Base.save  method  app/models.py:2``.
    """
    lines = [
        f'"{result.reference}" matches {len(result.candidates)} symbols; '
        "pass one of these ids or a qualified name:",
        *(_INDENT + _INDENT.join((c.id, c.kind.value, location(c))) for c in result.candidates),
    ]
    return "\n".join(lines)


def render_not_found(result: SymbolNotFound) -> str:
    """A reference that matched nothing, with close suggestions.

    Args:
        result: A not-found outcome.

    Returns:
        The text.

    Example:
        ``no symbol matches "sav"; similar names:`` then ``app/models.py::User.save
        method  app/models.py:6``.
    """
    if not result.suggestions:
        return f'no symbol matches "{result.reference}"; try `compass search`'
    lines = [
        f'no symbol matches "{result.reference}"; similar names:',
        *(_INDENT + _INDENT.join((s.id, s.kind.value, location(s))) for s in result.suggestions),
    ]
    return "\n".join(lines)


def render_error(error: ErrorResponse) -> str:
    """A failure: its code and the sentence that says how to fix it.

    Args:
        error: The error envelope.

    Returns:
        ``error [CODE]: message``.

    Example:
        ``error [INDEX_NOT_FOUND]: No Compass index found from /repo. Run `compass
        ingest`.``
    """
    return f"error [{error.code.value}]: {error.message}"
