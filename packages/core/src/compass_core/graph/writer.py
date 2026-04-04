"""Persist a ResolvedGraph into LadybugDB.

This module is a pure sink — it makes zero semantic decisions. Every node
and edge it writes has already been fully resolved by the resolver layer.

Write order (always nodes before edges):
  1. File nodes
  2. Class nodes
  3. Function nodes
  4. ExternalFunction nodes  (derived from external_call_edges)
  5. CONTAINS edges          (File→Class, File→Function, Class→Function)
  6. IMPORTS edges
  7. INHERITS edges
  8. CALLS edges
  9. CALLS_EXTERN edges
"""

from __future__ import annotations

import logging

from compass_core.graph.db import GraphDB
from compass_core.parser.models import ParsedClass, ParsedFile, ParsedFunction
from compass_core.resolver.models import ResolvedGraph
from compass_core.resolver.symbol_table import class_id, function_id

logger = logging.getLogger(__name__)


def write(db: GraphDB, graph: ResolvedGraph) -> None:
    """Write all nodes and edges from *graph* into *db*.

    Args:
        db:    Open GraphDB connection (schema must already exist).
        graph: Fully resolved graph produced by the resolver.
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
    db.execute(
        """
        MERGE (n:File {path: $path})
        ON CREATE SET n.module_name = $module_name, n.content_hash = $content_hash
        ON MATCH  SET n.module_name = $module_name, n.content_hash = $content_hash
        """,
        {"path": f.path, "module_name": f.module_name, "content_hash": f.content_hash},
    )


def _write_class(db: GraphDB, cls: ParsedClass) -> None:
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
    """Execute a query, logging and swallowing errors so one bad edge never aborts the batch."""
    try:
        db.execute(query, params)
    except Exception:
        logger.debug("DB write failed — query: %s | params: %s", query.strip(), params, exc_info=True)
