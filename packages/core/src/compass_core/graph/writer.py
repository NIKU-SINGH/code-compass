"""Persist a ResolvedGraph into LadybugDB.

This module acts as a pure sink for the graph resolution process. It is
responsible for taking a fully resolved graph and persisting its nodes
and edges into the underlying graph database.

The writing process follows a strict order, ensuring nodes are created
before the edges that connect them:
  1. File nodes
  2. Class nodes
  3. Function nodes
  4. ExternalFunction nodes (derived from call edges to external libraries)
  5. CONTAINS edges (File -> Class, File -> Function, Class -> Function)
  6. IMPORTS edges
  7. INHERITS edges
  8. CALLS edges (Internal)
  9. CALLS_EXTERN edges (External)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from compass_core.graph.db import GraphDB
from compass_core.parser.models import ParsedClass, ParsedFile, ParsedFunction
from compass_core.progress import ProgressReporter
from compass_core.resolver.models import ResolvedGraph
from compass_core.resolver.symbol_table import class_id, function_id

logger = logging.getLogger(__name__)


@dataclass
class WriteResult:
    """Statistics returned after persisting a graph to the database.

    Attributes:
        node_count: Number of nodes successfully written to the DB.
        edge_count: Number of edges successfully written to the DB.
    """

    node_count: int
    edge_count: int


def _calculate_expected_nodes(graph: ResolvedGraph) -> int:
    """Calculate the exact number of nodes the writer will attempt to persist.

    Counts one File node per file, one Class node per class, one Function
    node per top-level function and per method, and one ExternalFunction
    node per unique ``full_ref`` across all external call edges.
    """
    unique_ext = {e.full_ref for e in graph.external_call_edges}
    return (
        sum(
            1 + len(f.classes) + sum(len(c.methods) for c in f.classes) + len(f.functions)
            for f in graph.files
        )
        + len(unique_ext)
    )


def _calculate_expected_edges(graph: ResolvedGraph) -> int:
    """Calculate the exact number of edges the writer will attempt to persist.

    Counts one CONTAINS edge per class, top-level function, and method,
    plus one edge each for every import, inheritance, internal call, and
    external call relationship.
    """
    return (
        sum(
            len(f.classes) + len(f.functions) + sum(len(c.methods) for c in f.classes)
            for f in graph.files
        )
        + len(graph.import_edges)
        + len(graph.inherit_edges)
        + len(graph.call_edges)
        + len(graph.external_call_edges)
    )


def write(
    db: GraphDB,
    graph: ResolvedGraph,
    reporter: ProgressReporter | None = None,
) -> WriteResult:
    """Write all nodes and edges from a resolved graph into the database.

    Args:
        db: An active ``GraphDB`` connection with an initialized schema.
        graph: A ``ResolvedGraph`` with all extracted nodes and edges.
        reporter: Optional progress reporter. Receives ``"write_nodes"``
            updates during node insertion and ``"write_edges"`` updates
            during edge insertion.

    Returns:
        WriteResult with final node and edge counts. Counts reflect rows
        actually written — failed DB writes are not included.
    """
    node_total = _calculate_expected_nodes(graph)
    edge_total = _calculate_expected_edges(graph)
    node_count = 0
    edge_count = 0

    def _node() -> None:
        nonlocal node_count
        node_count += 1
        if reporter:
            reporter.update("write_nodes", node_count, node_total)

    def _edge() -> None:
        nonlocal edge_count
        edge_count += 1
        if reporter:
            reporter.update("write_edges", edge_count, edge_total)

    # --- Nodes first ---
    for pf in graph.files:
        _write_file(db, pf)
        _node()
        for cls in pf.classes:
            _write_class(db, cls)
            _node()
            for method in cls.methods:
                _write_function(db, method)
                _node()
        for func in pf.functions:
            _write_function(db, func)
            _node()

    seen_ext: set[str] = set()
    for ext_edge in graph.external_call_edges:
        if ext_edge.full_ref not in seen_ext:
            _write_external_function(db, ext_edge.full_ref, ext_edge.library)
            seen_ext.add(ext_edge.full_ref)
            _node()

    # --- Edges second ---
    for pf in graph.files:
        _write_contains(db, pf, _edge)

    for edge in graph.import_edges:
        if _exec(db, "MATCH (a:File {path: $src}), (b:File {path: $dst}) CREATE (a)-[:IMPORTS]->(b)",
                 {"src": edge.from_path, "dst": edge.to_path}):
            _edge()

    for edge in graph.inherit_edges:
        if _exec(db, "MATCH (a:Class {id: $src}), (b:Class {id: $dst}) CREATE (a)-[:INHERITS]->(b)",
                 {"src": edge.child_id, "dst": edge.parent_id}):
            _edge()

    for edge in graph.call_edges:
        if _exec(
            db,
            """
            MATCH (a:Function {id: $src}), (b:Function {id: $dst})
            CREATE (a)-[:CALLS {confidence: $conf, call_type: $ctype, line: $line}]->(b)
            """,
            {"src": edge.caller_id, "dst": edge.callee_id,
             "conf": edge.confidence, "ctype": edge.call_type, "line": edge.line},
        ):
            _edge()

    for edge in graph.external_call_edges:
        if _exec(
            db,
            "MATCH (a:Function {id: $src}), (b:ExternalFunction {full_ref: $dst}) CREATE (a)-[:CALLS_EXTERN {line: $line}]->(b)",
            {"src": edge.caller_id, "dst": edge.full_ref, "line": edge.line},
        ):
            _edge()

    return WriteResult(node_count=node_count, edge_count=edge_count)


# ---------------------------------------------------------------------------
# Node writers
# ---------------------------------------------------------------------------


def _write_file(db: GraphDB, f: ParsedFile) -> None:
    """Persist a file node to the database.

    Args:
        db: Active database connection.
        f: The `ParsedFile` metadata containing the path and module info.
    """
    db.execute(
        """
        MERGE (n:File {path: $path})
        ON CREATE SET n.module_name = $module_name, n.content_hash = $content_hash
        ON MATCH  SET n.module_name = $module_name, n.content_hash = $content_hash
        """,
        {"path": f.path, "module_name": f.module_name, "content_hash": f.content_hash},
    )


def _write_class(db: GraphDB, cls: ParsedClass) -> None:
    """Persist a class node to the database.

    Args:
        db: Active database connection.
        cls: The `ParsedClass` metadata, including 1-indexed line numbers
            and source content.
    """
    db.execute(
        """
        MERGE (n:Class {id: $id})
        ON CREATE SET n.name = $name, n.file_path = $file_path,
                      n.line_start = $line_start, n.line_end = $line_end,
                      n.source = $source, n.docstring = $docstring,
                      n.bases = $bases
        ON MATCH  SET n.name = $name, n.file_path = $file_path,
                      n.line_start = $line_start, n.line_end = $line_end,
                      n.source = $source, n.docstring = $docstring,
                      n.bases = $bases
        """,
        {
            "id": class_id(cls),
            "name": cls.name,
            "file_path": cls.file_path,
            "line_start": cls.line_start,
            "line_end": cls.line_end,
            "source": cls.source,
            "docstring": cls.docstring or "",
            "bases": cls.bases,
        },
    )


def _write_function(db: GraphDB, func: ParsedFunction) -> None:
    """Persist a function or method node to the database.

    Args:
        db: Active database connection.
        func: The `ParsedFunction` metadata, including 1-indexed line numbers,
            signature details, and decorators.
    """
    db.execute(
        """
        MERGE (n:Function {id: $id})
        ON CREATE SET n.name = $name, n.signature = $signature,
                      n.file_path = $file_path, n.line_start = $line_start,
                      n.line_end = $line_end, n.source = $source,
                      n.docstring = $docstring, n.is_method = $is_method,
                      n.parent_class = $parent_class,
                      n.decorators = $decorators, n.raw_calls = $raw_calls
        ON MATCH  SET n.name = $name, n.signature = $signature,
                      n.file_path = $file_path, n.line_start = $line_start,
                      n.line_end = $line_end, n.source = $source,
                      n.docstring = $docstring, n.is_method = $is_method,
                      n.parent_class = $parent_class,
                      n.decorators = $decorators, n.raw_calls = $raw_calls
        """,
        {
            "id": function_id(func),
            "name": func.name,
            "signature": func.signature,
            "file_path": func.file_path,
            "line_start": func.line_start,
            "line_end": func.line_end,
            "source": func.source,
            "docstring": func.docstring or "",
            "is_method": func.is_method,
            "parent_class": func.parent_class or "",
            "decorators": func.decorators,
            "raw_calls": func.raw_calls,
        },
    )


def _write_external_function(db: GraphDB, full_ref: str, library: str) -> None:
    """Persist an external function node to the database.

    External functions are identified during the call resolution phase
    when a call target is found to reside in an external library.

    Args:
        db: Active database connection.
        full_ref: The fully qualified reference to the function (e.g., 'os.path.join').
        library: The name of the external library containing the function.
    """
    db.execute(
        """
        MERGE (n:ExternalFunction {full_ref: $full_ref})
        ON CREATE SET n.name = $name, n.library = $library
        ON MATCH  SET n.name = $name, n.library = $library
        """,
        {"full_ref": full_ref, "name": full_ref.split(".")[-1], "library": library},
    )


# ---------------------------------------------------------------------------
# Edge writers
# ---------------------------------------------------------------------------


def _write_contains(db: GraphDB, f: ParsedFile, on_edge: Callable[[], None]) -> None:
    """Write structural containment edges (CONTAINS) for a file.

    Establishes relationships between a file and its defined classes/functions,
    as well as between classes and their methods. Calls ``on_edge`` once per
    edge successfully written, enabling granular progress reporting.

    Args:
        db: Active database connection.
        f: The `ParsedFile` whose internal structure is being persisted.
        on_edge: Callback invoked once for each edge successfully written.
    """
    for cls in f.classes:
        if _exec(db, "MATCH (a:File {path: $src}), (b:Class {id: $dst}) CREATE (a)-[:CONTAINS]->(b)",
                 {"src": f.path, "dst": class_id(cls)}):
            on_edge()
        for method in cls.methods:
            if _exec(db, "MATCH (a:Class {id: $src}), (b:Function {id: $dst}) CREATE (a)-[:CONTAINS]->(b)",
                     {"src": class_id(cls), "dst": function_id(method)}):
                on_edge()
    for func in f.functions:
        if _exec(db, "MATCH (a:File {path: $src}), (b:Function {id: $dst}) CREATE (a)-[:CONTAINS]->(b)",
                 {"src": f.path, "dst": function_id(func)}):
            on_edge()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _exec(db: GraphDB, query: str, params: dict) -> bool:
    """Execute a database query, returning whether it succeeded.

    Failures in individual edge creation (e.g. due to unresolved MATCH targets)
    do not abort the batch. Errors are logged at DEBUG level.

    Args:
        db: Active database connection.
        query: The Cypher query string to execute.
        params: Key-value pairs for query parameterization.

    Returns:
        ``True`` if the query executed without error, ``False`` otherwise.
    """
    try:
        db.execute(query, params)
        return True
    except Exception:
        logger.debug("DB write failed — query: %s | params: %s", query.strip(), params, exc_info=True)
        return False
