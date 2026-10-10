from pathlib import Path

import pytest

from compass_core.errors import IndexIncompatibleError
from compass_core.query.rows import (
    external_from_row,
    file_from_row,
    symbol_from_row,
    to_repo_path,
)
from compass_core.query.types import SymbolKind


def test_wrong_typed_column_raises_incompatible(tmp_path: Path) -> None:
    with pytest.raises(IndexIncompatibleError):
        symbol_from_row(["id", 123, "f.py", 1, 2, "def f()"], SymbolKind.FUNCTION, tmp_path)


def test_wrong_typed_line_and_short_row_raise(tmp_path: Path) -> None:
    with pytest.raises(IndexIncompatibleError):
        symbol_from_row(["f.py::f", "f", "f.py", "1", 2, "def f()"], SymbolKind.FUNCTION, tmp_path)
    with pytest.raises(IndexIncompatibleError):
        symbol_from_row(["f.py::f", "f"], SymbolKind.FUNCTION, tmp_path)


def test_stored_zero_line_becomes_none(tmp_path: Path) -> None:
    sym = symbol_from_row(["f.py::f", "f", "f.py", 0, 0, "def f()"], SymbolKind.FUNCTION, tmp_path)
    assert sym.line_start is None and sym.line_end is None


def test_stored_id_becomes_public_id(tmp_path: Path) -> None:
    sym = symbol_from_row(
        ["py::app.models::User.save", "save", "app/models.py", 6, 7, "def save(self):"],
        SymbolKind.METHOD,
        tmp_path,
    )
    assert sym.id == "app/models.py::User.save"
    assert sym.qualified_name == "app.models.User.save"


def test_absolute_stored_path_is_made_relative(tmp_path: Path) -> None:
    stored = (tmp_path / "app" / "a.py").as_posix()
    sym = symbol_from_row(
        [f"{stored}::f", "f", stored, 1, 2, "def f():"], SymbolKind.FUNCTION, tmp_path
    )
    assert sym.id == "app/a.py::f" and sym.file_path == "app/a.py"
    assert sym.qualified_name == "app.a.f"


def test_to_repo_path_outside_root_unchanged(tmp_path: Path) -> None:
    assert to_repo_path("/elsewhere/a.py", tmp_path) == "/elsewhere/a.py"


def test_file_and_external_rows(tmp_path: Path) -> None:
    f = file_from_row(["app/auth.py", "app.auth"], tmp_path)
    assert (f.id, f.kind, f.name, f.qualified_name) == (
        "file::app/auth.py",
        SymbolKind.FILE,
        "auth.py",
        "app.auth",
    )
    e = external_from_row(["json.dumps", "dumps"])
    assert (e.id, e.kind, e.file_path) == ("ext::json.dumps", SymbolKind.EXTERNAL, None)
    with pytest.raises(IndexIncompatibleError):
        file_from_row([1, "x"], tmp_path)
