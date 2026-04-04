"""Public entry point for the resolution phase.

This module takes the raw output of Pass 1 (a list of ParsedFile objects) and 
produces a ResolvedGraph. The ResolvedGraph contains a flat structure of nodes 
and fully resolved, typed edges that can be persisted by the graph writer 
without making further semantic decisions.

Example:
    >>> from compass_core.resolver.resolver import resolve
    >>> resolved = resolve(parsed_files)
"""

from __future__ import annotations

import logging

from compass_core.parser.models import ParsedFile
from compass_core.resolver import call_resolver, import_map, symbol_table
from compass_core.resolver.models import (
    EXTERNAL,
    CallEdge,
    ExternalCallEdge,
    ImportEdge,
    InheritEdge,
    ResolvedGraph,
)
from compass_core.resolver.symbol_table import class_id, function_id

logger = logging.getLogger(__name__)


def resolve(files: list[ParsedFile]) -> ResolvedGraph:
    """Resolve all semantic relationships between parsed files.

    This function orchestrates the resolution pipeline:
      1. Builds a global symbol table (qualified name -> node ID).
      2. Builds a per-file import map (local name -> origin file).
      3. Extracts file-level import dependencies.
      4. Extracted class-level inheritance relationships.
      5. Resolves function/method calls across the entire codebase.

    Args:
        files: A list of ParsedFile objects produced by the parser phase.

    Returns:
        A ResolvedGraph instance containing all files and resolved edges.
    """
    if not files:
        return ResolvedGraph()

    all_files: dict[str, ParsedFile] = {f.path: f for f in files}

    sym_table = symbol_table.build(files)
    imp_map = import_map.build(files)

    graph = ResolvedGraph(files=files)

    _collect_import_edges(graph, files, imp_map)
    _collect_inherit_edges(graph, files, sym_table)
    _collect_call_edges(graph, files, sym_table, imp_map, all_files)

    logger.info(
        "Resolution complete: %d import, %d inherit, %d call, %d external-call edges",
        len(graph.import_edges),
        len(graph.inherit_edges),
        len(graph.call_edges),
        len(graph.external_call_edges),
    )
    return graph


# ---------------------------------------------------------------------------
# Edge collectors
# ---------------------------------------------------------------------------


def _collect_import_edges(
    graph: ResolvedGraph,
    files: list[ParsedFile],
    imp_map: import_map.ImportMap,
) -> None:
    """Extract and add ImportEdge objects to the graph.

    Args:
        graph: The ResolvedGraph being populated.
        files: The list of parsed files to process.
        imp_map: The pre-calculated mapping of local names to source paths.
    """
    seen: set[tuple[str, str]] = set()
    for pf in files:
        for target_path in imp_map.get(pf.path, {}).values():
            if target_path is None or target_path == pf.path:
                continue
            pair = (pf.path, target_path)
            if pair in seen:
                continue
            seen.add(pair)
            graph.import_edges.append(ImportEdge(from_path=pf.path, to_path=target_path))


def _collect_inherit_edges(
    graph: ResolvedGraph,
    files: list[ParsedFile],
    sym_table: symbol_table.SymbolTable,
) -> None:
    """Extract and add InheritEdge objects to the graph.

    Args:
        graph: The ResolvedGraph being populated.
        files: The list of parsed files to process.
        sym_table: The global symbol table used to resolve class names.
    """
    for pf in files:
        for cls in pf.classes:
            child = class_id(cls)
            for base in cls.bases:
                parent = sym_table.get(base)
                if parent is not None:
                    graph.inherit_edges.append(InheritEdge(child_id=child, parent_id=parent))


def _collect_call_edges(
    graph: ResolvedGraph,
    files: list[ParsedFile],
    sym_table: symbol_table.SymbolTable,
    imp_map: import_map.ImportMap,
    all_files: dict[str, ParsedFile],
) -> None:
    """Analyze all function bodies to resolve call sites into graph edges.

    Args:
        graph: The ResolvedGraph being populated.
        files: The list of parsed files to process.
        sym_table: The global symbol table for looking up target IDs.
        imp_map: The per-file import map for tracing external vs internal names.
        all_files: A lookup dictionary of all files keyed by their path.
    """
    for pf in files:
        all_funcs = list(pf.functions)
        for cls in pf.classes:
            all_funcs.extend(cls.methods)

        for func in all_funcs:
            results = call_resolver.resolve_calls(func, pf, sym_table, imp_map, all_files)
            caller = function_id(func)
            for res in results:
                if res.call_type == EXTERNAL and res.external_library:
                    graph.external_call_edges.append(
                        ExternalCallEdge(
                            caller_id=caller,
                            full_ref=res.raw,
                            library=res.external_library,
                        )
                    )
                elif res.target_id is not None:
                    graph.call_edges.append(
                        CallEdge(
                            caller_id=caller,
                            callee_id=res.target_id,
                            call_type=res.call_type,
                            confidence=res.confidence,
                        )
                    )
                # UNRESOLVED / WILDCARD / DYNAMIC / CIRCULAR → no edge written
