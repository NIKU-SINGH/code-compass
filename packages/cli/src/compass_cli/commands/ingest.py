"""The `compass ingest` command."""

from __future__ import annotations

import time
from pathlib import Path

import typer

import compass_core.languages.python  # noqa: F401 — registers the Python plugin
from compass_cli import display
from compass_cli.errors import handle_errors
from compass_cli.progress import IngestReporter
from compass_cli.types import IngestSummary
from compass_core.ir.graph import ResolvedGraph
from compass_core.logger import setup as setup_logging
from compass_core.phases.base import IngestContext
from compass_core.phases.pipeline import Pipeline
from compass_core.shared_types import Language, SymbolKind


def _format_debug_section(phase: str, ctx: IngestContext) -> str:
    """Human-readable dump of everything a phase produced, for --debug-log."""
    lines: list[str] = [f"===== {phase} =====", ""]

    if phase == "discovery":
        assert ctx.manifest is not None
        m = ctx.manifest
        lines.append(
            f"dirs_scanned={m.dirs_scanned} ignored_count={m.ignored_count} files={len(m.files)}"
        )
        lines.append("")
        for f in m.files:
            lines.append(f"  {f.path}  [{f.language}]  {f.content_hash}")

    elif phase == "parse":
        assert ctx.parsed_files is not None
        for pf in ctx.parsed_files:
            lines.append(f"  {pf.path}  [{pf.language}]  module={pf.module_name}")
            if pf.degraded:
                lines.append(f"    DEGRADED: {pf.error}")
            lines.append(
                f"    definitions={len(pf.definitions)} imports={len(pf.imports)} "
                f"call_sites={len(pf.call_sites)}"
            )
            for d in pf.definitions:
                lines.append(f"      {d.kind.value}: {d.id}  (lines {d.line_start}-{d.line_end})")
                if d.signature:
                    lines.append(f"        signature: {d.signature}")
                if d.docstring:
                    lines.append(f"        docstring: {d.docstring!r}")
                if d.raw_calls:
                    lines.append(f"        raw_calls: {d.raw_calls}")
                lines.append("        source:")
                for src_line in d.source.splitlines():
                    lines.append(f"          {src_line}")

    elif phase == "symbol_table":
        assert ctx.symbol_table is not None
        assert ctx.import_map is not None
        lines.append(f"symbol_table ({len(ctx.symbol_table)} entries):")
        for symbol_key, symbol_id in ctx.symbol_table.items():
            lines.append(f"  {symbol_key} -> {symbol_id}")
        lines.append("")
        lines.append(f"import_map ({len(ctx.import_map)} entries):")
        for module_path, imported_names in ctx.import_map.items():
            lines.append(f"  {module_path} -> {imported_names}")

    elif phase == "resolution":
        assert ctx.resolved_graph is not None
        g = ctx.resolved_graph
        lines.append(f"call_edges ({len(g.call_edges)}):")
        for call in g.call_edges:
            lines.append(
                f"  {call.caller_id} -> {call.callee_id}  [{call.call_type} conf={call.confidence}]"
            )
        lines.append("")
        lines.append(f"external_call_edges ({len(g.external_call_edges)}):")
        for ext_call in g.external_call_edges:
            lines.append(f"  {ext_call.caller_id} -> {ext_call.full_ref}  [{ext_call.library}]")
        lines.append("")
        lines.append(f"import_edges ({len(g.import_edges)}):")
        for imp in g.import_edges:
            lines.append(f"  {imp.from_path} -> {imp.to_path}")
        lines.append("")
        lines.append(f"inherit_edges ({len(g.inherit_edges)}):")
        for inherit in g.inherit_edges:
            lines.append(f"  {inherit.child_id} -> {inherit.parent_id}")

    elif phase == "validation":
        assert ctx.report is not None
        r = ctx.report
        lines.append(f"orphan_node_count={r.orphan_node_count}")
        lines.append(f"dangling_import_count={r.dangling_import_count}")
        lines.append(f"degraded_file_count={r.degraded_file_count}")
        lines.append(f"resolved_by_language={_by_language_name(r.resolved_by_language)}")
        lines.append(f"unresolved_by_language={_by_language_name(r.unresolved_by_language)}")

    elif phase == "persistence":
        assert ctx.write_result is not None
        lines.append(f"node_count={ctx.write_result.node_count}")
        lines.append(f"edge_count={ctx.write_result.edge_count}")
        lines.append(f"dropped_edges={ctx.write_result.dropped_edges}")

    lines.append("")
    return "\n".join(lines)


def _count_definitions(resolved_graph: ResolvedGraph) -> tuple[int, int]:
    """Return (class_count, function_count) across all files in the graph."""
    class_count = 0
    function_count = 0
    for pf in resolved_graph.files:
        for d in pf.definitions:
            if d.kind is SymbolKind.CLASS:
                class_count += 1
            elif d.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD):
                function_count += 1
    return class_count, function_count


def _db_size(db_path: Path) -> int:
    """Total bytes on disk for the database — a single file or a directory."""
    if db_path.is_file():
        return db_path.stat().st_size
    if db_path.is_dir():
        return sum(f.stat().st_size for f in db_path.rglob("*") if f.is_file())
    return 0


def _resolved_pct(graph: ResolvedGraph) -> float:
    """Overall resolved-call ratio across all languages (1.0 if no calls at all)."""
    total_raw = sum(len(d.raw_calls) for pf in graph.files for d in pf.definitions)
    if total_raw == 0:
        return 1.0
    return len(graph.call_edges) / total_raw


def _by_language_name(ratios: dict[Language, float]) -> dict[str, float]:
    return {language.value: ratio for language, ratio in ratios.items()}


def _language_counts(ctx: IngestContext) -> dict[Language, int]:
    assert ctx.manifest is not None
    counts: dict[Language, int] = {}
    for f in ctx.manifest.files:
        counts[f.language] = counts.get(f.language, 0) + 1
    return counts


def _relative_db_path(db_path: Path, repo_path: Path) -> Path:
    """Express db_path relative to repo_path for display, falling back to the absolute path."""
    try:
        return db_path.relative_to(repo_path)
    except ValueError:
        return db_path


def _stage_result(
    phase: str, ctx: IngestContext, *, repo_path: Path, db_path: Path
) -> tuple[str, str, bool]:
    """Build (primary, secondary, warn) display text for a just-finished phase."""
    if phase == "discovery":
        assert ctx.manifest is not None
        m = ctx.manifest
        num_languages = len(_language_counts(ctx))
        language_word = "language" if num_languages == 1 else "languages"
        primary = f"{len(m.files):,} files"
        secondary = f"{num_languages} {language_word} · {m.dirs_scanned:,} dirs · {m.ignored_count:,} ignored"
        return primary, secondary, False

    if phase == "parse":
        assert ctx.parsed_files is not None
        degraded = sum(1 for pf in ctx.parsed_files if pf.degraded)
        primary = f"{len(ctx.parsed_files):,} parsed"
        secondary = f"{degraded:,} degraded"
        return primary, secondary, degraded > 0

    if phase == "symbol_table":
        assert ctx.symbol_table is not None
        assert ctx.import_map is not None
        primary = f"{len(ctx.symbol_table):,} symbols"
        secondary = f"{len(ctx.import_map):,} import entries"
        return primary, secondary, False

    if phase == "resolution":
        assert ctx.resolved_graph is not None
        g = ctx.resolved_graph
        total = (
            len(g.import_edges)
            + len(g.inherit_edges)
            + len(g.call_edges)
            + len(g.external_call_edges)
        )
        primary = f"{total:,} edges"
        secondary = (
            f"import {len(g.import_edges):,} · call {len(g.call_edges):,} · "
            f"external {len(g.external_call_edges):,} · inherit {len(g.inherit_edges):,}"
        )
        return primary, secondary, False

    if phase == "validation":
        assert ctx.report is not None
        assert ctx.resolved_graph is not None
        r = ctx.report
        primary = f"{r.orphan_node_count:,} orphan nodes"
        secondary = (
            f"{r.dangling_import_count:,} dangling imports · {r.degraded_file_count:,} degraded files · "
            f"{_resolved_pct(ctx.resolved_graph):.0%} resolved"
        )
        return primary, secondary, r.orphan_node_count > 0

    if phase == "persistence":
        assert ctx.write_result is not None
        display_db = _relative_db_path(db_path, repo_path)
        primary = f"{ctx.write_result.node_count:,} nodes · {ctx.write_result.edge_count:,} edges"
        secondary = f"{display.fmt_size(_db_size(db_path))} · {display_db}"
        dropped = ctx.write_result.dropped_edges
        if dropped:
            secondary = f"{dropped:,} skipped · {secondary}"
        return primary, secondary, dropped > 0

    return "", "", False


def _run_ingest(
    repo_path: Path,
    db_path: Path,
    *,
    workers: int | None,
    verbose: bool,
    debug_log: Path | None,
) -> IngestSummary:
    """Run the ingest pipeline and return its summary."""
    start = time.monotonic()

    display.ingest_header(repo_path)

    if debug_log is not None:
        debug_log.parent.mkdir(parents=True, exist_ok=True)
        debug_log.write_text("", encoding="utf-8")

    with IngestReporter(console=display.console) as reporter:

        def _on_phase_complete(phase: str, ctx: IngestContext) -> None:
            primary, secondary, warn = _stage_result(
                phase, ctx, repo_path=repo_path, db_path=db_path
            )
            reporter.complete(phase, primary, secondary, warn=warn)
            if debug_log is not None:
                with debug_log.open("a", encoding="utf-8") as f:
                    f.write(_format_debug_section(phase, ctx) + "\n")

        ctx = Pipeline(max_workers=workers).run(
            repo_path, db_path, reporter=reporter, on_phase_complete=_on_phase_complete
        )
        reporter.finalize()
    display.console.print()

    assert ctx.manifest is not None
    assert ctx.resolved_graph is not None
    assert ctx.report is not None
    assert ctx.write_result is not None

    display_db = _relative_db_path(db_path, repo_path)
    class_count, function_count = _count_definitions(ctx.resolved_graph)

    return IngestSummary(
        file_count=len(ctx.manifest.files),
        class_count=class_count,
        function_count=function_count,
        elapsed=time.monotonic() - start,
        node_count=ctx.write_result.node_count,
        edge_count=ctx.write_result.edge_count,
        db_path=display_db,
        db_size=_db_size(db_path),
        skipped=ctx.report.degraded_file_count,
        resolved_pct=_resolved_pct(ctx.resolved_graph),
        orphan_count=ctx.report.orphan_node_count,
        language_counts=_language_counts(ctx),
        dropped_edges=ctx.write_result.dropped_edges,
    )


@handle_errors
def ingest(
    path: str = typer.Argument(..., help="Path to the repository to ingest"),
    db: str | None = typer.Option(
        None, "--db", help="Path to LadybugDB database (default: <repo>/.compass/graph.ladybug)"
    ),
    workers: int | None = typer.Option(None, "--workers", help="Number of parallel parse workers"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    debug_log: bool = typer.Option(
        False, "--debug-log", help="Append phase-by-phase output to .compass/ingest_debug.log"
    ),
) -> None:
    """Ingest a repository for code intelligence."""
    setup_logging(level="DEBUG" if verbose else "WARNING", show_path=verbose)

    repo_path = Path(path).resolve()
    db_path = Path(db).resolve() if db else repo_path / ".compass" / "graph.ladybug"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    debug_log_path = repo_path / ".compass" / "ingest_debug.log" if debug_log else None

    summary = _run_ingest(
        repo_path, db_path, workers=workers, verbose=verbose, debug_log=debug_log_path
    )

    display.summary(summary)
    display.next_steps()
