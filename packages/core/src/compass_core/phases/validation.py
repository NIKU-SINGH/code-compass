"""Phase 4: ResolvedGraph -> IngestReport. Regression gate before
persistence: % resolved vs. unresolved (per language), dangling-import
count, orphan-node count. Catches grammar upgrades / broken extractors
before they silently degrade agent answers."""

from __future__ import annotations

from compass_core.ir.graph import ResolvedGraph
from compass_core.phases.base import IngestContext, IngestReport


class ValidationPhase:
    name = "validation"

    def run(self, ctx: IngestContext) -> IngestContext:
        assert ctx.resolved_graph is not None
        graph = ctx.resolved_graph

        degraded = sum(1 for pf in graph.files if pf.degraded)

        known_paths = {pf.path for pf in graph.files}
        dangling = sum(1 for e in graph.import_edges if e.to_path not in known_paths)

        resolved_by_language = _resolved_ratio_by_language(graph)
        unresolved_by_language = {lang: 1.0 - ratio for lang, ratio in resolved_by_language.items()}

        ctx.report = IngestReport(
            resolved_by_language=resolved_by_language,
            unresolved_by_language=unresolved_by_language,
            dangling_import_count=dangling,
            orphan_node_count=_orphan_node_count(graph),
            degraded_file_count=degraded,
        )
        if ctx.reporter is not None:
            ctx.reporter.update("validation", 1, 1)
        return ctx


def _resolved_ratio_by_language(graph: ResolvedGraph) -> dict[str, float]:
    call_count_by_language: dict[str, int] = {}
    for pf in graph.files:
        call_count_by_language.setdefault(pf.language, 0)
        for d in pf.definitions:
            call_count_by_language[pf.language] += len(d.raw_calls)

    id_to_language: dict[str, str] = {}
    for pf in graph.files:
        for d in pf.definitions:
            id_to_language[d.id] = pf.language

    resolved_by_language: dict[str, int] = {}
    for edge in graph.call_edges:
        lang = id_to_language.get(edge.caller_id, "unknown")
        resolved_by_language[lang] = resolved_by_language.get(lang, 0) + 1

    result: dict[str, float] = {}
    for lang, total_calls in call_count_by_language.items():
        if total_calls == 0:
            result[lang] = 1.0
            continue
        result[lang] = resolved_by_language.get(lang, 0) / total_calls
    return result


def _orphan_node_count(graph: ResolvedGraph) -> int:
    referenced: set[str] = set()
    for call_edge in graph.call_edges:
        referenced.add(call_edge.caller_id)
        referenced.add(call_edge.callee_id)
    for inherit_edge in graph.inherit_edges:
        referenced.add(inherit_edge.child_id)
        referenced.add(inherit_edge.parent_id)
    all_ids = {d.id for pf in graph.files for d in pf.definitions}
    return len(all_ids - referenced)
