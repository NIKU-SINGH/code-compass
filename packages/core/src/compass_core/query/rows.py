"""Map raw graph rows to public query models.

This is, with ``graph/db.py``, the only module allowed to touch untyped (``Any``)
driver values. Every column is validated here so the rest of the query layer works
with typed models, and a schema mismatch surfaces as ``IndexIncompatibleError``.

Stored ids look like ``py::app.models::User.save`` and stored ``file_path`` values are
repo-relative POSIX paths (absolute paths are tolerated and made relative). The public
id is ``<repo-relative path>::<[Class.]name>``; the qualified name is the stored dotted
module plus the ``[Class.]name`` tail, e.g. ``app.models.User.save``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from compass_core.contract.models import SymbolRef
from compass_core.contract.types import QualifiedName, RepoPath, SymbolId
from compass_core.errors import IndexIncompatibleError
from compass_core.shared_types import CallType, SymbolKind

_SEP = "::"
_CONFIDENCE_DIGITS = 6


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


def to_repo_path(stored: str, repo_root: Path) -> RepoPath:
    """Convert a stored path to a repo-relative POSIX path.

    Args:
        stored: Path as stored in the graph; absolute or already repo-relative.
        repo_root: Absolute repository root.

    Returns:
        The repo-relative POSIX path. A stored path outside ``repo_root`` is returned
        unchanged rather than raising, so an odd row never hides the rest of an answer.

    Example:
        ``to_repo_path("/r/app/a.py", Path("/r"))`` returns ``"app/a.py"``.
    """
    path = Path(stored)
    if path.is_absolute():
        try:
            path = path.relative_to(repo_root)
        except ValueError:
            return RepoPath(path.as_posix())
    return RepoPath(path.as_posix())


def module_from_path(file_path: str) -> str:
    """Derive a dotted module name from a repo-relative path.

    Args:
        file_path: Repo-relative POSIX path.

    Returns:
        Dotted module, dropping ``.py`` and a trailing ``__init__``.

    Example:
        ``module_from_path("app/__init__.py")`` returns ``"app"``.
    """
    parts = list(PurePosixPath(file_path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def split_stored_id(stored_id: str, file_path: str) -> tuple[str, str]:
    """Split a stored definition id into its dotted module and ``[Class.]name`` tail.

    Args:
        stored_id: Stored id such as ``"py::app.models::User.save"``.
        file_path: Repo-relative path, used to derive the module for ids that carry none.

    Returns:
        ``(module, tail)``, e.g. ``("app.models", "User.save")``.

    Raises:
        IndexIncompatibleError: The id has no ``::`` separator.
    """
    if _SEP not in stored_id:
        raise IndexIncompatibleError(f"unexpected symbol id format: {stored_id!r}")
    head, tail = stored_id.rsplit(_SEP, 1)
    if _SEP in head:
        return head.split(_SEP, 1)[1], tail
    return module_from_path(file_path), tail


def public_definition_id(stored_id: str, stored_path: str, repo_root: Path) -> SymbolId:
    """Build the public id of a function, method or class from its stored columns.

    Args:
        stored_id: Stored id such as ``"py::app.models::User.save"``.
        stored_path: Path as stored in the graph; absolute or repo-relative.
        repo_root: Absolute repository root.

    Returns:
        ``<repo-relative POSIX path>::<[Class.]name>``.

    Raises:
        IndexIncompatibleError: The stored id has no ``::`` separator.

    Example:
        ``public_definition_id("py::app.models::User.save", "app/models.py", root)`` returns
        ``"app/models.py::User.save"``.
    """
    file_path = to_repo_path(stored_path, repo_root)
    _, tail = split_stored_id(stored_id, file_path)
    return SymbolId(f"{file_path}{_SEP}{tail}")


def public_file_id(stored_path: str, repo_root: Path) -> SymbolId:
    """Build the public id of a file from its stored path.

    Args:
        stored_path: Path as stored in the graph; absolute or repo-relative.
        repo_root: Absolute repository root.

    Returns:
        ``file::<repo-relative POSIX path>``.

    Example:
        ``public_file_id("/r/app/auth.py", Path("/r"))`` returns ``"file::app/auth.py"``.
    """
    return SymbolId(f"file{_SEP}{to_repo_path(stored_path, repo_root)}")


def symbol_from_row(row: Sequence[Any], kind: SymbolKind, repo_root: Path) -> SymbolRef:
    """Build a function or class ``SymbolRef`` from a graph row.

    Args:
        row: Columns ``[id, name, file_path, line_start, line_end, signature]``. Extra
            trailing columns are ignored. A stored line of ``0`` means "unknown".
        kind: Kind to assign (``FUNCTION``, ``METHOD`` or ``CLASS``).
        repo_root: Absolute repository root, used to make paths repo-relative.

    Returns:
        The symbol with a public id and qualified name.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.

    Example:
        ``["py::app.auth::parse", "parse", "app/auth.py", 6, 7, "def parse(raw):"]`` becomes
        ``SymbolRef(id="app/auth.py::parse", qualified_name="app.auth.parse", ...)``.
    """
    _expect_width(row, 6, "symbol row")
    stored_id = _text(row[0], "id")
    name = _text(row[1], "name")
    stored_path = _text(row[2], "file_path")
    line_start = _line(row[3], "line_start")
    line_end = _line(row[4], "line_end")
    signature = _text(row[5], "signature") or None
    file_path = to_repo_path(stored_path, repo_root)
    module, tail = split_stored_id(stored_id, file_path)
    qualified = f"{module}.{tail}" if module else tail
    if kind is SymbolKind.CLASS:
        signature = None
    return SymbolRef(
        id=public_definition_id(stored_id, stored_path, repo_root),
        kind=kind,
        name=name,
        qualified_name=QualifiedName(qualified),
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        signature=signature,
    )


def file_from_row(row: Sequence[Any], repo_root: Path) -> SymbolRef:
    """Build a ``FILE`` ``SymbolRef`` from a ``[path, module_name]`` row.

    Args:
        row: Columns ``[path, module_name]``.
        repo_root: Absolute repository root.

    Returns:
        The file symbol with id ``file::<repo-relative path>``.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.
    """
    _expect_width(row, 2, "file row")
    file_path = to_repo_path(_text(row[0], "path"), repo_root)
    module = _text(row[1], "module_name")
    return SymbolRef(
        id=public_file_id(_text(row[0], "path"), repo_root),
        kind=SymbolKind.FILE,
        name=PurePosixPath(file_path).name,
        qualified_name=QualifiedName(module),
        file_path=file_path,
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


def function_from_row(row: Sequence[Any], repo_root: Path) -> SymbolRef:
    """Build a function or method ``SymbolRef`` from a row carrying ``is_method``.

    Args:
        row: Columns ``[id, name, file_path, line_start, line_end, signature, is_method]``.
        repo_root: Absolute repository root.

    Returns:
        The symbol, with kind ``METHOD`` when ``is_method`` is true, else ``FUNCTION``.

    Raises:
        IndexIncompatibleError: A column is missing or has an unexpected type.

    Example:
        ``["py::app.models::User.save", "save", "app/models.py", 6, 7, "def save(self):",
        True]`` becomes a ``METHOD`` with id ``"app/models.py::User.save"``.
    """
    _expect_width(row, 7, "function row")
    kind = SymbolKind.METHOD if is_method_flag(row[6]) else SymbolKind.FUNCTION
    return symbol_from_row(row, kind, repo_root)


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
