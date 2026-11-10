"""Cypher DDL statements to initialise the Compass knowledge graph schema.

This module defines the graph database schema for storing Python source code
information, including nodes for files, classes, and functions, and their
inter-relationships.
"""

from __future__ import annotations

from compass_core.graph.db import GraphDB

# ---------------------------------------------------------------------------
# DDL — node tables (must be created before rel tables)
# ---------------------------------------------------------------------------

_NODE_TABLES: list[str] = [
    # File: A source file entry.
    #   - path (PK): Repo-relative POSIX path of the source file.
    #   - module_name: Dotted Python module name (e.g., "os.path").
    #   - content_hash: SHA-256 hex digest for change detection.
    """
    CREATE NODE TABLE IF NOT EXISTS File(
        path         STRING,
        module_name  STRING,
        content_hash STRING,
        PRIMARY KEY(path)
    )
    """,
    # Class: A class definition extracted from source.
    #   - id (PK): Public id, format: '<repo-relative path>::ClassName'.
    #   - name: The unqualified name of the class.
    #   - qualified_name: Dotted module plus class name, e.g. 'app.models.User'.
    #   - file_path: Reference to the file where the class is defined.
    #   - line_start: 1-indexed line where the class definition starts.
    #   - line_end: 1-indexed line where the class definition ends.
    #   - source: The entire source code block of the class.
    #   - docstring: The extracted class-level docstring.
    #   - bases: A list of raw names for base classes (STRING[]).
    """
    CREATE NODE TABLE IF NOT EXISTS Class(
        id             STRING,
        name           STRING,
        qualified_name STRING,
        file_path      STRING,
        line_start     INT64,
        line_end       INT64,
        source         STRING,
        docstring      STRING,
        bases          STRING[],
        PRIMARY KEY(id)
    )
    """,
    # Function: A function or method definition.
    #   - id (PK): Public id, format: '<repo-relative path>::[ClassName.]name'.
    #   - name: The name of the function or method.
    #   - qualified_name: Dotted module plus '[ClassName.]name', e.g. 'app.models.User.save'.
    #   - signature: The full 'def' line including arguments and return type.
    #   - file_path: Reference to the file where the function is defined.
    #   - line_start: 1-indexed line (including decorators) where it starts.
    #   - line_end: 1-indexed line where the function body ends.
    #   - source: The entire source code block of the function.
    #   - docstring: The extracted function-level docstring.
    #   - is_method: Boolean indicating if it's defined inside a class.
    #   - parent_class: The name of the owning class if is_method=True.
    #   - decorators: A list of decorator names applied (STRING[]).
    #   - raw_calls: Unresolved call strings within the body (STRING[]).
    """
    CREATE NODE TABLE IF NOT EXISTS Function(
        id             STRING,
        name           STRING,
        qualified_name STRING,
        signature      STRING,
        file_path      STRING,
        line_start     INT64,
        line_end       INT64,
        source         STRING,
        docstring      STRING,
        is_method      BOOLEAN,
        parent_class   STRING,
        decorators     STRING[],
        raw_calls      STRING[],
        PRIMARY KEY(id)
    )
    """,
    # ExternalFunction: A call to an external library function.
    #   - full_ref (PK): Fully qualified name (e.g., "jwt.decode").
    #   - name: The name of the function.
    #   - library: The name of the library or package.
    """
    CREATE NODE TABLE IF NOT EXISTS ExternalFunction(
        full_ref STRING,
        name     STRING,
        library  STRING,
        PRIMARY KEY(full_ref)
    )
    """,
]

# ---------------------------------------------------------------------------
# DDL — relationship tables
# ---------------------------------------------------------------------------

_REL_TABLES: list[str] = [
    # CONTAINS: Unified containment model (File→Class, File→Function, Class→Function).
    """
    CREATE REL TABLE IF NOT EXISTS CONTAINS(
        FROM File TO Class,
        FROM File TO Function,
        FROM Class TO Function
    )
    """,
    # IMPORTS: Dependency between files when one module imports another.
    """
    CREATE REL TABLE IF NOT EXISTS IMPORTS(
        FROM File TO File
    )
    """,
    # INHERITS: Class inheritance relationship (Subclass → Superclass).
    """
    CREATE REL TABLE IF NOT EXISTS INHERITS(
        FROM Class TO Class
    )
    """,
    # CALLS: Internal function execution flow with metadata.
    #   - confidence (FLOAT): Probability score from the call graph analyzer.
    #   - call_type (STRING): A ``CallType`` value (e.g., "DIRECT_IMPORT", "MRO").
    #   - line (INT64): 1-indexed line number where the call occurs.
    """
    CREATE REL TABLE IF NOT EXISTS CALLS(
        FROM Function TO Function,
        confidence FLOAT,
        call_type  STRING,
        line       INT64
    )
    """,
    # CALLS_EXTERN: Function execution flow to external library functions.
    #   - line (INT64): 1-indexed line number where the call occurs.
    """
    CREATE REL TABLE IF NOT EXISTS CALLS_EXTERN(
        FROM Function TO ExternalFunction,
        line INT64
    )
    """,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_schema(db: GraphDB) -> None:
    """Create all node and relationship tables if they do not already exist.

    All statements use the 'IF NOT EXISTS' clause to ensure safety when
    running against an initialized database. Node tables are always
    created before relationship tables to avoid schema violations.

    Args:
        db: An instance of GraphDB to execute the DDL statements against.
    """
    for stmt in _NODE_TABLES:
        db.execute(stmt)
    for stmt in _REL_TABLES:
        db.execute(stmt)
