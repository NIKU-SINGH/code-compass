"""Tests for the GraphDB wrapper module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestGraphDBInitialization:
    """Test GraphDB initialization and configuration."""

    def test_graphdb_init_with_default_path(self):
        """Test GraphDB initialization with default database path from settings."""
        with patch("compass_core.graph.db.lb") as mock_lb:
            with patch("compass_core.graph.db.settings") as mock_settings:
                mock_settings.LADYBUG_DB_PATH = "/tmp/default_db"
                mock_db_instance = MagicMock()
                mock_conn_instance = MagicMock()
                mock_lb.Database.return_value = mock_db_instance
                mock_lb.Connection.return_value = mock_conn_instance

                from compass_core.graph.db import GraphDB

                db = GraphDB()

                assert db._db == mock_db_instance
                assert db._conn == mock_conn_instance
                mock_lb.Database.assert_called_once_with("/tmp/default_db")
                mock_lb.Connection.assert_called_once_with(mock_db_instance)

    def test_graphdb_init_with_custom_path_string(self):
        """Test GraphDB initialization with custom database path as string."""
        with patch("compass_core.graph.db.lb") as mock_lb:
            mock_db_instance = MagicMock()
            mock_conn_instance = MagicMock()
            mock_lb.Database.return_value = mock_db_instance
            mock_lb.Connection.return_value = mock_conn_instance

            from compass_core.graph.db import GraphDB

            db = GraphDB("/custom/path")

            mock_lb.Database.assert_called_once_with("/custom/path")
            mock_lb.Connection.assert_called_once_with(mock_db_instance)


class TestGraphDBExecution:
    """Test GraphDB query execution methods."""

    def test_execute_simple_query(self):
        """Test executing a simple Cypher query without parameters."""
        with patch("compass_core.graph.db.lb"):
            from compass_core.graph.db import GraphDB

            mock_db = MagicMock()
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_conn.execute.return_value = mock_result

            db = GraphDB()
            db._db = mock_db
            db._conn = mock_conn

            query = "MATCH (n) RETURN n"
            result = db.execute(query)

            mock_conn.execute.assert_called_once_with(query)
            assert result == mock_result

    def test_execute_many(self):
        """Test executing multiple statements in sequence."""
        with patch("compass_core.graph.db.lb"):
            from compass_core.graph.db import GraphDB

            mock_db = MagicMock()
            mock_conn = MagicMock()

            db = GraphDB()
            db._db = mock_db
            db._conn = mock_conn

            statements = [
                "CREATE NODE TABLE File(path STRING, PRIMARY KEY(path))",
                "CREATE NODE TABLE Class(id STRING, PRIMARY KEY(id))",
            ]
            db.execute_many(statements)

            assert mock_conn.execute.call_count == len(statements)


class TestGraphDBLifecycle:
    """Test GraphDB connection lifecycle management."""

    def test_close_success(self):
        """Test closing database connections without errors."""
        with patch("compass_core.graph.db.lb"):
            from compass_core.graph.db import GraphDB

            mock_db = MagicMock()
            mock_conn = MagicMock()

            db = GraphDB()
            db._db = mock_db
            db._conn = mock_conn

            db.close()

            mock_conn.close.assert_called_once()
            mock_db.close.assert_called_once()

    def test_context_manager(self):
        """Test GraphDB as context manager."""
        with patch("compass_core.graph.db.lb"):
            from compass_core.graph.db import GraphDB

            mock_db = MagicMock()
            mock_conn = MagicMock()

            with GraphDB() as db:
                db._db = mock_db
                db._conn = mock_conn

            mock_conn.close.assert_called()
            mock_db.close.assert_called()
