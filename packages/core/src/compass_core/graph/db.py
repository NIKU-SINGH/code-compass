"""LadybugDB wrapper — the primary interface for graph database operations.

This module provides a thin wrapper around the real_ladybug database driver,
ensuring consistent connection handling and query execution. It is the only
file in the codebase permitted to import real_ladybug directly.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType
from typing import Any

import real_ladybug as lb

from compass_core.settings import settings

logger = logging.getLogger(__name__)


class GraphDB:
    """Thin wrapper around a LadybugDB database and its connection pair.

    This class manages the lifecycle of the database handle and its associated
    connection, providing a simplified interface for executing Cypher queries.

    Attributes:
        _db: The underlying LadybugDB database instance.
        _conn: The active connection to the database instance.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initializes the GraphDB wrapper and opens a database connection.

        If no database path is provided, it defaults to the value specified
        in the LADYBUG_DB_PATH environment variable via the settings module.

        Args:
            db_path: Path to the LadybugDB database directory. Defaults to
                settings.LADYBUG_DB_PATH.
        """
        path = db_path or settings.LADYBUG_DB_PATH
        self._db = lb.Database(str(path))
        self._conn = lb.Connection(self._db)

    # ------------------------------------------------------------------
    # Core query interface
    # ------------------------------------------------------------------

    def execute(self, query: str, params: dict[str, Any] | None = None) -> lb.QueryResult:
        """Executes a single Cypher query.

        Args:
            query: The Cypher query string to execute.
            params: Optional dictionary of parameters to pass as
                prepared-statement arguments.

        Returns:
            The raw Result object containing the query output.
        """
        if params:
            stmt = self._conn.prepare(query)
            return self._conn.execute(stmt, params)
        return self._conn.execute(query)

    def execute_many(self, statements: list[str]) -> None:
        """Executes multiple Cypher statements in sequence.

        Results from these statements are ignored. High-level DDL or bulk
        initialisation should use this method.

        Args:
            statements: A list of Cypher query strings to execute.
        """
        for stmt in statements:
            self._conn.execute(stmt)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def node_table_names(self) -> list[str]:
        """Retrieves the names of all node tables (labels) in the database.

        Returns:
            A list of strings representing the node table names.
        """
        return self._conn._get_node_table_names()

    def rel_table_names(self) -> list[str]:
        """Retrieves the names of all relationship tables in the database.

        Returns:
            A list of strings representing the relationship table names.
        """
        return self._conn._get_rel_table_names()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Safely closes the connection and the database handle.

        Any errors during closure are logged and suppressed to ensure
        cleanup completes without crashing the caller.
        """
        try:
            self._conn.close()
        except Exception:
            logger.exception("Error closing database connection")
        try:
            self._db.close()
        except Exception:
            logger.exception("Error closing database handle")

    def __enter__(self) -> GraphDB:
        """Enables usage of GraphDB as a context manager.

        Returns:
            The GraphDB instance itself.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Automatically closes the database on exit from a context block.

        Args:
            exc_type: The type of the exception raised, if any.
            exc_val: The exception instance raised, if any.
            tb: The traceback object, if any.
        """
        self.close()
