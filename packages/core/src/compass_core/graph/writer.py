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

from compass_core.graph.db import GraphDB
from compass_core.parser.models import ParsedClass, ParsedFile, ParsedFunction
from compass_core.resolver.models import ResolvedGraph
from compass_core.resolver.symbol_table import class_id, function_id

logger = logging.getLogger(__name__)


def write(db: GraphDB, graph: ResolvedGraph) -> None:
    """Write all nodes and edges from a resolved graph into the database.

    This function orchestrates the batch writing of a complete `ResolvedGraph`
    structure. It ensures that all structural entities (files, classes,
    functions) are persisted as nodes before establishing the relationships
    (imports, inheritance, calls) as edges.

    Args:
        db: An active `GraphDB` connection. The database schema must already
            be initialized before calling this function.
        graph: A `ResolvedGraph` instance containing all extracted and
            resolved nodes and edges for the project.
    """
    # --- Nodes first ---
    for pf in graph.files:
        _write_file(db, pf)
        for cls in pf.classes:
            _write_class(db, cls)
            for method in cls.methods:
                _write_function(db, method)
        for func in pf.functions:
            _write_function(db, func)

    for ext_edge in graph.external_call_edges:
        _write_external_function(db, ext_edge.full_ref, ext_edge.library)

    # --- Edges second ---
    for pf in graph.files:
        _write_contains(db, pf)

    for edge in graph.import_edges:
        _exec(db, "MATCH (a:File {path: $src}), (b:File {path: $dst}) CREATE (a)-[:IMPORTS]->(b)",
              {"src": edge.from_path, "dst": edge.to_path})

    for edge in graph.inherit_edges:
        _exec(db, "MATCH (a:Class {id: $src}), (b:Class {id: $dst}) CREATE (a)-[:INHERITS]->(b)",
              {"src": edge.child_id, "dst": edge.parent_id})

    for edge in graph.call_edges:
        _exec(
            db,
            """
            MATCH (a:Function {id: $src}), (b:Function {id: $dst})
            CREATE (a)-[:CALLS {confidence: $conf, call_type: $ctype, line: $line}]->(b)
            """,
            {"src": edge.caller_id, "dst": edge.callee_id,
             "conf": edge.confidence, "ctype": edge.call_type, "line": edge.line},
        )

    for edge in graph.external_call_edges:
        _exec(
            db,
            "MATCH (a:Function {id: $src}), (b:ExternalFunction {full_ref: $dst}) CREATE (a)-[:CALLS_EXTERN {line: $line}]->(b)",
            {"src": edge.caller_id, "dst": edge.full_ref, "line": edge.line},
        )


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


def _write_contains(db: GraphDB, f: ParsedFile) -> None:
    """Write structural containment edges (CONTAINS) for a file.

    Establishes relationships between a file and its defined classes/functions,
    as well as between classes and their methods.

    Args:
        db: Active database connection.
        f: The `ParsedFile` whose internal structure is being persisted.
    """
    for cls in f.classes:
        _exec(db, "MATCH (a:File {path: $src}), (b:Class {id: $dst}) CREATE (a)-[:CONTAINS]->(b)",
              {"src": f.path, "dst": class_id(cls)})
        for method in cls.methods:
            _exec(db, "MATCH (a:Class {id: $src}), (b:Function {id: $dst}) CREATE (a)-[:CONTAINS]->(b)",
                  {"src": class_id(cls), "dst": function_id(method)})
    for func in f.functions:
        _exec(db, "MATCH (a:File {path: $src}), (b:Function {id: $dst}) CREATE (a)-[:CONTAINS]->(b)",
              {"src": f.path, "dst": function_id(func)})


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _exec(db: GraphDB, query: str, params: dict) -> None:
    """Execute a database query with error containment.

    This utility ensures that failures in individual edge creation (e.g., due to
    unexpected resolution states) do not abort the entire batch writing process.
    Errors are logged at DEBUG level.

    Args:
        db: Active database connection.
        query: The Cypher query string to execute.
        params: Key-value pairs for query parameterization.
    """
    try:
        db.execute(query, params)
    except Exception:
        logger.debug("DB write failed — query: %s | params: %s", query.strip(), params, exc_info=True)
