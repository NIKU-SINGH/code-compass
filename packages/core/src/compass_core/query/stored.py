"""Nodes as the graph stores them: the stored key next to the public symbol.

Walks and lookups match on stored ids and paths, while results carry public
``SymbolRef`` values; these decoders return both from one row.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from compass_core.contract.models import SymbolRef
from compass_core.graph.db import Row
from compass_core.query.rows import class_from_row, file_from_row, function_from_row, text_value


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredNode:
    """A node as the graph stores it, with its public symbol.

    Attributes:
        key: Stored id of a class or function, or stored path of a file; what the graph
            matches on.
        path: Stored ``file_path`` (for a file, its stored path).
        symbol: The public symbol built from the row.

    Example:
        A ``Function`` row for ``parse`` in ``app/auth.py`` becomes
        ``StoredNode(key="py::app.auth::parse", path="app/auth.py",
        symbol=SymbolRef(id="app/auth.py::parse", ...))``.
    """

    key: str
    path: str
    symbol: SymbolRef


def stored_function(row: Row, repo_root: Path) -> StoredNode:
    """Decode a row of ``FUNCTION_FIELDS`` columns, keeping the stored id and path.

    Args:
        row: Columns in ``FUNCTION_FIELDS`` order.
        repo_root: Absolute repository root.

    Returns:
        The stored id, stored path and public symbol.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.

    Example:
        A row for ``User.save`` gives ``StoredNode(key="py::app.models::User.save",
        path="app/models.py", symbol=<METHOD app/models.py::User.save>)``.
    """
    symbol = function_from_row(row, repo_root)
    return StoredNode(
        key=text_value(row[0], "id"), path=text_value(row[2], "file_path"), symbol=symbol
    )


def stored_class(row: Row, repo_root: Path) -> StoredNode:
    """Decode a row of ``CLASS_FIELDS`` columns, keeping the stored id and path.

    Args:
        row: Columns in ``CLASS_FIELDS`` order.
        repo_root: Absolute repository root.

    Returns:
        The stored id, stored path and public symbol.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.

    Example:
        A row for ``User`` gives ``StoredNode(key="py::app.models::User",
        path="app/models.py", symbol=<CLASS app/models.py::User>)``.
    """
    symbol = class_from_row(row, repo_root)
    return StoredNode(
        key=text_value(row[0], "id"), path=text_value(row[2], "file_path"), symbol=symbol
    )


def stored_file(row: Row, repo_root: Path) -> StoredNode:
    """Decode a row of ``FILE_FIELDS`` columns, keeping the stored path.

    Args:
        row: Columns in ``FILE_FIELDS`` order.
        repo_root: Absolute repository root.

    Returns:
        The stored path (as both ``key`` and ``path``) and the public file symbol.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.

    Example:
        ``["app/auth.py", "app.auth"]`` gives ``StoredNode(key="app/auth.py",
        path="app/auth.py", symbol=<FILE file::app/auth.py>)``.
    """
    symbol = file_from_row(row, repo_root)
    path = text_value(row[0], "path")
    return StoredNode(key=path, path=path, symbol=symbol)
