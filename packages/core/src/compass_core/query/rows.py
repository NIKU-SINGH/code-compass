"""Map raw graph rows to public query models.

This is, with ``graph/db.py``, the only module allowed to touch untyped (``Any``)
driver values. Every column is validated here so the rest of the query layer works
with typed models, and a schema mismatch surfaces as ``IndexIncompatibleError``.

The graph stores exactly what the public models carry: class and function ids are
public ids (``app/models.py::User.save``), ``file_path`` values are repo-relative POSIX
paths, and ``qualified_name`` is stored (``app.models.User.save``). Files and external
functions get their public ids here: ``file::<path>`` and ``ext::<full_ref>``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Any

from compass_core.contract.models import SymbolRef
from compass_core.contract.types import QualifiedName, RepoPath, SymbolId
from compass_core.errors import IndexIncompatibleError
from compass_core.shared_types import CallType, SymbolKind

_SEP = "::"
_CONFIDENCE_DIGITS = 6

FUNCTION_FIELDS = (
    "id",
    "name",
    "qualified_name",
    "file_path",
    "line_start",
    "line_end",
    "signature",
    "is_method",
)
"""``Function`` properties read by ``function_from_row``, in column order."""
CLASS_FIELDS = ("id", "name", "qualified_name", "file_path", "line_start", "line_end")
"""``Class`` properties read by ``class_from_row``, in column order."""
FILE_FIELDS = ("path", "module_name")
"""``File`` properties read by ``file_from_row``, in column order."""
FUNCTION_WIDTH = len(FUNCTION_FIELDS)
CLASS_WIDTH = len(CLASS_FIELDS)
FILE_WIDTH = len(FILE_FIELDS)


def columns(variable: str, fields: Sequence[str]) -> str:
    """Render a ``RETURN`` column list for one node variable.

    Used only to compose module-level ``Query`` constants, so the column order a query
    returns and the order its decoder reads are the same list.

    Args:
        variable: Cypher variable bound to the node, e.g. ``"n"``.
        fields: Property names, e.g. ``FUNCTION_FIELDS``.

    Returns:
        The comma-separated column list.

    Example:
        ``columns("a", FILE_FIELDS)`` returns ``"a.path, a.module_name"``.
    """
    return ", ".join(f"{variable}.{name}" for name in fields)


def _text(value: Any, column: str) -> str:
    if not isinstance(value, str):
        raise IndexIncompatibleError(
            f"unexpected column type for {column}: expected str, got {type(value).__name__}"
        )
    return value


def _line(value: Any, column: str) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IndexIncompatibleError(
            f"unexpected column type for {column}: expected int, got {type(value).__name__}"
        )
    return value if value > 0 else None


def _expect_width(row: Sequence[Any], width: int, what: str) -> None:
    if len(row) < width:
        raise IndexIncompatibleError(
            f"unexpected column count for {what}: expected {width}, got {len(row)}"
        )


def public_file_id(path: str) -> SymbolId:
    """Build the public id of a file from its stored path.

    Args:
        path: Repo-relative POSIX path, as stored.

    Returns:
        ``file::<path>``.

    Example:
        ``public_file_id("app/auth.py")`` returns ``"file::app/auth.py"``.
    """
    return SymbolId(f"file{_SEP}{path}")


def _definition(row: Sequence[Any], kind: SymbolKind, signature: str | None) -> SymbolRef:
    return SymbolRef(
        id=SymbolId(_text(row[0], "id")),
        kind=kind,
        name=_text(row[1], "name"),
        qualified_name=QualifiedName(_text(row[2], "qualified_name")),
        file_path=RepoPath(_text(row[3], "file_path")),
        line_start=_line(row[4], "line_start"),
        line_end=_line(row[5], "line_end"),
        signature=signature,
    )


def symbol_from_row(row: Sequence[Any], kind: SymbolKind) -> SymbolRef:
    """Build a function, method or class ``SymbolRef`` from a graph row.

    Args:
        row: Columns ``[id, name, qualified_name, file_path, line_start, line_end,
            signature]``; extra trailing columns are ignored. A stored line of ``0``
            means "unknown".
        kind: Kind to assign (``FUNCTION``, ``METHOD`` or ``CLASS``); a class gets no
            signature.

    Returns:
        The symbol.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.

    Example:
        ``["app/auth.py::parse", "parse", "app.auth.parse", "app/auth.py", 6, 7,
        "def parse(raw):"]`` becomes ``SymbolRef(id="app/auth.py::parse",
        qualified_name="app.auth.parse", line_start=6, ...)``.
    """
    _expect_width(row, 7, "symbol row")
    signature = _text(row[6], "signature") or None
    return _definition(row, kind, None if kind is SymbolKind.CLASS else signature)


def file_from_row(row: Sequence[Any]) -> SymbolRef:
    """Build a ``FILE`` ``SymbolRef`` from a row of ``FILE_FIELDS`` columns.

    Args:
        row: Columns ``[path, module_name]``.

    Returns:
        The file symbol with id ``file::<path>``.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.

    Example:
        ``["app/auth.py", "app.auth"]`` becomes ``SymbolRef(id="file::app/auth.py",
        name="auth.py", qualified_name="app.auth", ...)``.
    """
    _expect_width(row, FILE_WIDTH, "file row")
    path = _text(row[0], "path")
    return SymbolRef(
        id=public_file_id(path),
        kind=SymbolKind.FILE,
        name=PurePosixPath(path).name,
        qualified_name=QualifiedName(_text(row[1], "module_name")),
        file_path=RepoPath(path),
        line_start=None,
        line_end=None,
        signature=None,
    )


def external_from_row(row: Sequence[Any]) -> SymbolRef:
    """Build an ``EXTERNAL`` ``SymbolRef`` from a ``[full_ref, name]`` row.

    Args:
        row: Columns ``[full_ref, name]``.

    Returns:
        The external symbol with id ``ext::<full_ref>``.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.
    """
    _expect_width(row, 2, "external row")
    full_ref = _text(row[0], "full_ref")
    return SymbolRef(
        id=SymbolId(f"ext{_SEP}{full_ref}"),
        kind=SymbolKind.EXTERNAL,
        name=_text(row[1], "name"),
        qualified_name=QualifiedName(full_ref),
        file_path=None,
        line_start=None,
        line_end=None,
        signature=None,
    )


def is_method_flag(value: Any) -> bool:
    """Validate a ``Function.is_method`` column.

    Args:
        value: Raw column value.

    Returns:
        The flag as a ``bool``.

    Raises:
        IndexIncompatibleError: The value is not a boolean.
    """
    if not isinstance(value, bool):
        raise IndexIncompatibleError(
            f"unexpected column type for is_method: expected bool, got {type(value).__name__}"
        )
    return value


def count_value(value: Any) -> int:
    """Validate a count column.

    Args:
        value: Raw column value.

    Returns:
        The count as an ``int``.

    Raises:
        IndexIncompatibleError: The value is not an integer.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise IndexIncompatibleError(
            f"unexpected column type for count: expected int, got {type(value).__name__}"
        )
    return value


def function_from_row(row: Sequence[Any]) -> SymbolRef:
    """Build a function or method ``SymbolRef`` from a row of ``FUNCTION_FIELDS`` columns.

    Args:
        row: Columns in ``FUNCTION_FIELDS`` order.

    Returns:
        The symbol, with kind ``METHOD`` when ``is_method`` is true, else ``FUNCTION``.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.

    Example:
        ``["app/models.py::User.save", "save", "app.models.User.save", "app/models.py", 6,
        7, "def save(self):", True]`` becomes a ``METHOD`` with id
        ``"app/models.py::User.save"``.
    """
    _expect_width(row, FUNCTION_WIDTH, "function row")
    kind = SymbolKind.METHOD if is_method_flag(row[7]) else SymbolKind.FUNCTION
    return symbol_from_row(row, kind)


def class_from_row(row: Sequence[Any]) -> SymbolRef:
    """Build a ``CLASS`` ``SymbolRef`` from a row of ``CLASS_FIELDS`` columns.

    Args:
        row: Columns in ``CLASS_FIELDS`` order; extra trailing columns are ignored.

    Returns:
        The class symbol; classes have no signature.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.

    Example:
        ``["app/models.py::User", "User", "app.models.User", "app/models.py", 4, 9]``
        becomes ``SymbolRef(id="app/models.py::User", kind=SymbolKind.CLASS, ...)``.
    """
    _expect_width(row, CLASS_WIDTH, "class row")
    return _definition(row, SymbolKind.CLASS, None)


def text_value(value: Any, column: str) -> str:
    """Validate a string column.

    Args:
        value: Raw column value.
        column: Column name, for the error message.

    Returns:
        The value as a ``str``.

    Raises:
        IndexIncompatibleError: The value is not a string.
    """
    return _text(value, column)


def text_list_value(value: Any, column: str) -> tuple[str, ...]:
    """Validate a ``STRING[]`` column such as ``Function.raw_calls``.

    Args:
        value: Raw column value; a stored ``NULL`` reads as an empty tuple.
        column: Column name, for the error message.

    Returns:
        The strings, in stored order.

    Raises:
        IndexIncompatibleError: The value is not a list of strings.

    Example:
        ``text_list_value(["parse"], "raw_calls")`` returns ``("parse",)``.
    """
    if value is None:
        return ()
    if not isinstance(value, list):
        raise IndexIncompatibleError(
            f"unexpected column type for {column}: expected list, got {type(value).__name__}"
        )
    return tuple(_text(item, column) for item in value)


def line_value(value: Any, column: str) -> int | None:
    """Validate a 1-indexed line column; a stored ``0`` (unknown) becomes ``None``.

    Args:
        value: Raw column value.
        column: Column name, for the error message.

    Returns:
        The 1-indexed line, or ``None`` when unknown.

    Raises:
        IndexIncompatibleError: The value is not an integer.

    Example:
        ``line_value(0, "line")`` returns ``None``; ``line_value(4, "line")`` returns ``4``.
    """
    return _line(value, column)


def confidence_value(value: Any) -> float:
    """Validate a ``CALLS.confidence`` column.

    Args:
        value: Raw column value.

    Returns:
        The confidence as a ``float`` in ``[0, 1]``, rounded to 6 decimals: the column
        is float32, so a written ``0.9`` reads back as ``0.8999999761581421``.

    Raises:
        IndexIncompatibleError: The value is not a number in ``[0, 1]``.

    Example:
        ``confidence_value(0.800000011920929)`` returns ``0.8``.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise IndexIncompatibleError(f"unexpected value for confidence: {value!r}")
    return round(float(value), _CONFIDENCE_DIGITS)


def call_type_value(value: Any) -> CallType:
    """Validate a ``CALLS.call_type`` column.

    Args:
        value: Raw column value.

    Returns:
        The call type.

    Raises:
        IndexIncompatibleError: The value is not one of the ``CallType`` values.

    Example:
        ``call_type_value("MRO")`` returns ``CallType.MRO``.
    """
    try:
        return CallType(_text(value, "call_type"))
    except ValueError as exc:
        raise IndexIncompatibleError(f"unexpected value for call_type: {value!r}") from exc
