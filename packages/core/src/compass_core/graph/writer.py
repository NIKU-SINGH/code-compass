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

Every edge is written with ``MATCH (a ...), (b ...) CREATE ... RETURN
count(*)``. When an endpoint was never stored as a node the MATCH yields no
row and the CREATE silently does nothing, so the writer checks the returned
count and reports such edges as dropped instead of written.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from compass_core.graph.db import GraphDB, as_row
from compass_core.graph.stored_ids import with_stored_ids
from compass_core.ir.graph import CallEdge, ExternalCallEdge, ImportEdge, InheritEdge, ResolvedGraph
from compass_core.ir.models import Definition, ParsedFile
from compass_core.progress import ProgressReporter
from compass_core.shared_types import SymbolKind

logger = logging.getLogger(__name__)


@dataclass
class WriteResult:
    """Statistics returned after persisting a graph to the database.

    Attributes:
        node_count: Number of nodes successfully written to the DB.
        edge_count: Number of edges actually stored in the DB (verified per
            statement, so it equals ``MATCH ()-[r]->() RETURN count(r)`` on
            a fresh database).
        dropped_edges: Number of edges in the resolved graph that could not be
            stored, because an endpoint is not a stored node of the required
            label (e.g. a resolved call whose callee is a class constructor:
            CALLS only connects ``Function`` nodes) or the write failed.

    Example:
        A graph with ``run() -> helper()`` and ``build() -> Widget()``
        (``Widget`` a class) plus four CONTAINS edges yields
        ``WriteResult(node_count=..., edge_count=5, dropped_edges=1)``.
    """

    node_count: int
    edge_count: int
    dropped_edges: int = 0


def _calculate_expected_nodes(graph: ResolvedGraph) -> int:
    """Calculate the exact number of nodes the writer will attempt to persist.

    Counts one File node per file, one Class/Function/Method node per
    definition, and one ExternalFunction node per unique ``full_ref`` across
    all external call edges.
    """
    unique_ext = {e.full_ref for e in graph.external_call_edges}
    return sum(1 + len(f.definitions) for f in graph.files) + len(unique_ext)


def _calculate_expected_edges(graph: ResolvedGraph) -> int:
    """Calculate the exact number of edges the writer will attempt to persist.

    Counts one CONTAINS edge per class, top-level function, and method,
    plus one edge each for every import, inheritance, internal call, and
    external call relationship.
    """
    return (
        sum(len(f.definitions) for f in graph.files)
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
        actually written — failed DB writes and edges whose endpoints do not
        exist are not included; they are counted in ``dropped_edges``.
    """
    stored = with_stored_ids(graph)
    graph = stored.graph
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

    id_to_name: dict[str, str] = {d.id: d.name for f in graph.files for d in f.definitions}

    # --- Nodes first ---
    for pf in graph.files:
        _write_file(db, pf)
        _node()
        for d in pf.definitions:
            qualified = stored.qualified_names[d.id]
            if d.kind is SymbolKind.CLASS:
                _write_class(db, d, qualified)
            else:
                _write_function(db, d, qualified, id_to_name)
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

    for import_edge in graph.import_edges:
        if _write_import_edge(db, import_edge):
            _edge()

    for inherit_edge in graph.inherit_edges:
        if _write_inherit_edge(db, inherit_edge):
            _edge()

    for call_edge in graph.call_edges:
        if _write_call_edge(db, call_edge):
            _edge()

    for extern_call_edge in graph.external_call_edges:
        if _write_external_call_edge(db, extern_call_edge):
            _edge()

    dropped = edge_total - edge_count
    if dropped:
        logger.info(
            "%d of %d edges were not stored (endpoint not a stored node)", dropped, edge_total
        )
    return WriteResult(node_count=node_count, edge_count=edge_count, dropped_edges=dropped)


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


def _write_class(db: GraphDB, cls: Definition, qualified_name: str) -> None:
    """Persist a class node to the database.

    Args:
        db: Active database connection.
        cls: The `Definition` (kind=CLASS) metadata, keyed by its public id, including
            1-indexed line numbers and source content.
        qualified_name: Dotted qualified name, e.g. ``app.models.User``.
    """
    db.execute(
        """
        MERGE (n:Class {id: $id})
        ON CREATE SET n.name = $name, n.qualified_name = $qualified_name,
                      n.file_path = $file_path,
                      n.line_start = $line_start, n.line_end = $line_end,
                      n.source = $source, n.docstring = $docstring,
                      n.bases = $bases
        ON MATCH  SET n.name = $name, n.qualified_name = $qualified_name,
                      n.file_path = $file_path,
                      n.line_start = $line_start, n.line_end = $line_end,
                      n.source = $source, n.docstring = $docstring,
                      n.bases = $bases
        """,
        {
            "id": cls.id,
            "name": cls.name,
            "qualified_name": qualified_name,
            "file_path": cls.file_path,
            "line_start": cls.line_start,
            "line_end": cls.line_end,
            "source": cls.source,
            "docstring": cls.docstring or "",
            "bases": cls.bases,
        },
    )


def _write_function(
    db: GraphDB, func: Definition, qualified_name: str, id_to_name: dict[str, str]
) -> None:
    """Persist a function or method node to the database.

    Args:
        db: Active database connection.
        func: The `Definition` (kind=FUNCTION or METHOD) metadata, keyed by its public
            id, including 1-indexed line numbers, signature details, and decorators.
        qualified_name: Dotted qualified name, e.g. ``app.models.User.save``.
        id_to_name: Maps every `Definition.id` in the graph to its short name,
            used to recover the parent class's short name from `func.parent_id`.
    """
    is_method = func.kind is SymbolKind.METHOD
    parent_class = id_to_name.get(func.parent_id, "") if func.parent_id else ""
    db.execute(
        """
        MERGE (n:Function {id: $id})
        ON CREATE SET n.name = $name, n.qualified_name = $qualified_name,
                      n.signature = $signature,
                      n.file_path = $file_path, n.line_start = $line_start,
                      n.line_end = $line_end, n.source = $source,
                      n.docstring = $docstring, n.is_method = $is_method,
                      n.parent_class = $parent_class,
                      n.decorators = $decorators, n.raw_calls = $raw_calls
        ON MATCH  SET n.name = $name, n.qualified_name = $qualified_name,
                      n.signature = $signature,
                      n.file_path = $file_path, n.line_start = $line_start,
                      n.line_end = $line_end, n.source = $source,
                      n.docstring = $docstring, n.is_method = $is_method,
                      n.parent_class = $parent_class,
                      n.decorators = $decorators, n.raw_calls = $raw_calls
        """,
        {
            "id": func.id,
            "name": func.name,
            "qualified_name": qualified_name,
            "signature": func.signature or "",
            "file_path": func.file_path,
            "line_start": func.line_start,
            "line_end": func.line_end,
            "source": func.source,
            "docstring": func.docstring or "",
            "is_method": is_method,
            "parent_class": parent_class,
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
    for d in f.definitions:
        if d.kind is SymbolKind.CLASS:
            if _exec(
                db,
                "MATCH (a:File {path: $src}), (b:Class {id: $dst}) CREATE (a)-[:CONTAINS]->(b) "
                "RETURN count(*)",
                {"src": f.path, "dst": d.id},
            ):
                on_edge()
        elif d.kind is SymbolKind.METHOD:
            if d.parent_id is not None and _exec(
                db,
                "MATCH (a:Class {id: $src}), (b:Function {id: $dst}) CREATE (a)-[:CONTAINS]->(b) "
                "RETURN count(*)",
                {"src": d.parent_id, "dst": d.id},
            ):
                on_edge()
        else:
            if _exec(
                db,
                "MATCH (a:File {path: $src}), (b:Function {id: $dst}) CREATE (a)-[:CONTAINS]->(b) "
                "RETURN count(*)",
                {"src": f.path, "dst": d.id},
            ):
                on_edge()


def _write_import_edge(db: GraphDB, edge: ImportEdge) -> bool:
    """Write an IMPORTS edge (File -> File).

    Args:
        db: Active database connection.
        edge: The `ImportEdge` describing the importing and imported files.

    Returns:
        ``True`` if the edge was stored, ``False`` if either endpoint was
        not found or the write failed.
    """
    return _exec(
        db,
        "MATCH (a:File {path: $src}), (b:File {path: $dst}) CREATE (a)-[:IMPORTS]->(b) "
        "RETURN count(*)",
        {"src": edge.from_path, "dst": edge.to_path},
    )


def _write_inherit_edge(db: GraphDB, edge: InheritEdge) -> bool:
    """Write an INHERITS edge (Class -> Class).

    Args:
        db: Active database connection.
        edge: The `InheritEdge` describing the child and parent classes.

    Returns:
        ``True`` if the edge was stored, ``False`` if either endpoint was
        not found or the write failed.
    """
    return _exec(
        db,
        "MATCH (a:Class {id: $src}), (b:Class {id: $dst}) CREATE (a)-[:INHERITS]->(b) "
        "RETURN count(*)",
        {"src": edge.child_id, "dst": edge.parent_id},
    )


def _write_call_edge(db: GraphDB, edge: CallEdge) -> bool:
    """Write a CALLS edge (Function -> Function) for an internal call.

    A resolved call whose callee is a class (constructor or exception call)
    has no ``Function`` node to match, so it is not stored and is reported
    as dropped. OPEN DESIGN DECISION: storing calls to classes (a CALLS
    Function -> Class relation, or mapping the call to ``__init__``) needs a
    schema and impact-walker change and is deliberately out of scope here.

    Args:
        db: Active database connection.
        edge: The `CallEdge` describing the caller, callee, and call metadata.

    Returns:
        ``True`` if the edge was stored, ``False`` if either endpoint was
        not found or the write failed.
    """
    return _exec(
        db,
        """
        MATCH (a:Function {id: $src}), (b:Function {id: $dst})
        CREATE (a)-[:CALLS {confidence: $conf, call_type: $ctype, line: $line}]->(b)
        RETURN count(*)
        """,
        {
            "src": edge.caller_id,
            "dst": edge.callee_id,
            "conf": edge.confidence,
            "ctype": str(edge.call_type),
            "line": edge.line,
        },
    )


def _write_external_call_edge(db: GraphDB, edge: ExternalCallEdge) -> bool:
    """Write a CALLS_EXTERN edge (Function -> ExternalFunction).

    Args:
        db: Active database connection.
        edge: The `ExternalCallEdge` describing the caller and external target.

    Returns:
        ``True`` if the edge was stored, ``False`` if either endpoint was
        not found or the write failed.
    """
    return _exec(
        db,
        "MATCH (a:Function {id: $src}), (b:ExternalFunction {full_ref: $dst}) "
        "CREATE (a)-[:CALLS_EXTERN {line: $line}]->(b) RETURN count(*)",
        {
            "src": edge.caller_id,
            "dst": edge.full_ref,
            "line": edge.line,
        },
    )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _exec(db: GraphDB, query: str, params: dict[str, object]) -> bool:
    """Execute an edge ``MATCH ... CREATE ... RETURN count(*)``; report if it stored one.

    A MATCH that finds no endpoint yields no row, so the CREATE silently
    does nothing and ``count(*)`` is 0 (verified against LadybugDB: a
    matching statement returns ``[[1]]``, a non-matching one ``[[0]]``).
    Neither a missing endpoint nor a DB error aborts the batch; both are
    logged at DEBUG level.

    Args:
        db: Active database connection.
        query: The Cypher edge statement, ending in ``RETURN count(*)``.
        params: Key-value pairs for query parameterization.

    Returns:
        ``True`` if exactly one edge was created, ``False`` otherwise.
    """
    try:
        row = as_row(db.execute(query, params))
    except Exception:
        logger.debug(
            "DB write failed — query: %s | params: %s", query.strip(), params, exc_info=True
        )
        return False
    stored = int(row[0]) == 1
    if not stored:
        logger.debug("Edge not stored (endpoint missing) — params: %s", params)
    return stored
