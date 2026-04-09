"""Public entry point for the resolution phase (Pass 2).

This module takes the raw output of Pass 1 (a list of ParsedFile objects) and
orchestrates the semantic resolution of symbols, imports, inheritance,
and function calls to produce a ResolvedGraph.

The resulting graph represents the complete architecture of the codebase in
a flat, serializable structure that is ready for ingestion into the graph
database (Pass 3).

Example:
    >>> from compass_core.parser.models import ParsedFile
    >>> from compass_core.resolver.resolver import resolve
    >>> files = [ParsedFile(path="main.py", functions=[], classes=[])]
    >>> graph = resolve(files)
    >>> print(f"Resolved {len(graph.call_edges)} call edges.")
"""

from __future__ import annotations

import logging

from compass_core.parser.models import ParsedFile
from compass_core.progress import ProgressReporter
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


def resolve(
    files: list[ParsedFile],
    reporter: ProgressReporter | None = None,
) -> ResolvedGraph:
    """Resolve all semantic relationships between parsed files.

    This function orchestrates a multi-stage resolution pipeline:
      1. Builds a global symbol table (qualified name -> node ID).
      2. Builds a per-file import map (local name -> origin file).
      3. Extracts file-level import dependencies.
      4. Extracted class-level inheritance relationships.
      5. Resolves function/method calls across the entire codebase.

    Args:
        files: A list of ParsedFile objects produced by the parser phase.
        reporter: Optional progress reporter. Receives ``"resolve"`` updates
            once after each of the 5 internal pipeline steps.

    Returns:
        A ResolvedGraph instance containing all files and resolved edges.
    """
    if not files:
        return ResolvedGraph()

    all_files: dict[str, ParsedFile] = {f.path: f for f in files}

    sym_table = symbol_table.build(files)
    if reporter:
        reporter.update("resolve", 1, 5)
    imp_map = import_map.build(files)
    if reporter:
        reporter.update("resolve", 2, 5)

    graph = ResolvedGraph(files=files)

    _collect_import_edges(graph, files, imp_map)
    if reporter:
        reporter.update("resolve", 3, 5)
    _collect_inherit_edges(graph, files, sym_table)
    if reporter:
        reporter.update("resolve", 4, 5)
    _collect_call_edges(graph, files, sym_table, imp_map, all_files)
    if reporter:
        reporter.update("resolve", 5, 5)

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
    """Extract and add file-level import dependencies to the graph.

    This analysis constructs the high-level module dependency graph by
    traversing the import maps of all files.

    Args:
        graph: The ResolvedGraph being populated with edges.
        files: The list of parsed files to process for imports.
        imp_map: The pre-calculated mapping of local names to source paths
            used to resolve relative and alias imports.
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
    """Extract and add class inheritance relationships to the graph.

    Traces the inheritance chain for every class in the input file list to
    connect children to their parent classes in the resolved graph.

    Args:
        graph: The ResolvedGraph being populated with edges.
        files: The list of parsed files containing classes to process.
        sym_table: The global symbol table used to resolve class names to
            canonical node IDs.
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

    This is the most complex phase of resolution, as it must trace calls
    through imports, same-module functions, and class methods.

    Note:
        Dynamic calls, wildcard imports that can't be resolved, and
        calls to standard libraries are documented in the graph but
        may result in ExternalCallEdge if not found in the local codebase.

    Args:
        graph: The ResolvedGraph being populated with edges.
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
