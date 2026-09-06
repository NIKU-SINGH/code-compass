"""Phase 2: list[ParsedFile] -> SymbolTable, ImportMap. Global structure
built from all files' IR. Dispatches to per-language ImportResolver
strategy objects but feeds one shared global map."""

from __future__ import annotations

from compass_core.ir.models import ParsedFile
from compass_core.languages import registry
from compass_core.phases.base import IngestContext


class SymbolTablePhase:
    name = "symbol_table"

    def run(self, ctx: IngestContext) -> IngestContext:
        assert ctx.parsed_files is not None, "SymbolTablePhase requires ParsePhase to run first"

        symbol_table: dict[str, str] = {}
        for pf in ctx.parsed_files:
            for definition in pf.definitions:
                symbol_table[definition.id] = definition.id

        import_map: dict[str, dict[str, str | None]] = {}
        by_language: dict[str, list[ParsedFile]] = {}
        for pf in ctx.parsed_files:
            by_language.setdefault(pf.language, []).append(pf)
        for language_id, files in by_language.items():
            resolver = registry.get_import_resolver(language_id)
            import_map.update(resolver.resolve(files))

        ctx.symbol_table = symbol_table
        ctx.import_map = import_map
        if ctx.reporter is not None:
            ctx.reporter.update("symbol_table", 1, 1)
        return ctx
