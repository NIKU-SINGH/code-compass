import pytest

from compass_core.errors import IndexIncompatibleError
from compass_core.query.rows import (
    call_type_value,
    class_from_row,
    confidence_value,
    external_from_row,
    file_from_row,
    function_from_row,
    line_value,
    symbol_from_row,
    text_list_value,
)
from compass_core.shared_types import CallType, SymbolKind


def test_wrong_typed_column_raises_incompatible() -> None:
    with pytest.raises(IndexIncompatibleError):
        symbol_from_row(["f.py::f", 123, "f", "f.py", 1, 2, "def f()"], SymbolKind.FUNCTION)


def test_wrong_typed_line_and_short_row_raise() -> None:
    with pytest.raises(IndexIncompatibleError):
        symbol_from_row(["f.py::f", "f", "f", "f.py", "1", 2, "def f()"], SymbolKind.FUNCTION)
    with pytest.raises(IndexIncompatibleError):
        symbol_from_row(["f.py::f", "f"], SymbolKind.FUNCTION)


def test_stored_zero_line_becomes_none() -> None:
    sym = symbol_from_row(["f.py::f", "f", "f", "f.py", 0, 0, "def f()"], SymbolKind.FUNCTION)
    assert sym.line_start is None and sym.line_end is None


def test_stored_columns_are_the_public_symbol() -> None:
    sym = symbol_from_row(
        [
            "app/models.py::User.save",
            "save",
            "app.models.User.save",
            "app/models.py",
            6,
            7,
            "def save(self):",
        ],
        SymbolKind.METHOD,
    )
    assert sym.id == "app/models.py::User.save"
    assert sym.qualified_name == "app.models.User.save"
    assert (sym.file_path, sym.line_start, sym.signature) == ("app/models.py", 6, "def save(self):")


def test_class_row_has_no_signature_column() -> None:
    cls = class_from_row(["app/models.py::User", "User", "app.models.User", "app/models.py", 4, 9])
    assert (cls.id, cls.kind, cls.signature) == ("app/models.py::User", SymbolKind.CLASS, None)


def test_file_and_external_rows() -> None:
    f = file_from_row(["app/auth.py", "app.auth"])
    assert (f.id, f.kind, f.name, f.qualified_name) == (
        "file::app/auth.py",
        SymbolKind.FILE,
        "auth.py",
        "app.auth",
    )
    e = external_from_row(["json.dumps", "dumps"])
    assert (e.id, e.kind, e.file_path) == ("ext::json.dumps", SymbolKind.EXTERNAL, None)
    with pytest.raises(IndexIncompatibleError):
        file_from_row([1, "x"])


def test_function_from_row_uses_is_method_flag() -> None:
    row = [
        "app/models.py::User.save",
        "save",
        "app.models.User.save",
        "app/models.py",
        6,
        7,
        "def save(self):",
        True,
    ]
    symbol = function_from_row(row)
    assert symbol.kind is SymbolKind.METHOD and symbol.id == "app/models.py::User.save"


@pytest.mark.parametrize("value", [None, "0.5", True, -0.1, 1.5])
def test_confidence_value_rejects_bad_values(value: object) -> None:
    with pytest.raises(IndexIncompatibleError):
        confidence_value(value)


def test_call_type_value_maps_known_and_rejects_unknown() -> None:
    assert call_type_value("MRO") is CallType.MRO
    with pytest.raises(IndexIncompatibleError):
        call_type_value("UNRESOLVED")


def test_text_list_value_reads_lists_and_null() -> None:
    assert text_list_value(["parse"], "raw_calls") == ("parse",)
    assert text_list_value(None, "raw_calls") == ()
    with pytest.raises(IndexIncompatibleError):
        text_list_value("parse", "raw_calls")


def test_line_value_maps_zero_to_none() -> None:
    assert line_value(0, "line") is None and line_value(4, "line") == 4


def test_confidence_value_normalises_float32_noise() -> None:
    assert confidence_value(0.800000011920929) == 0.8
    assert confidence_value(0.8999999761581421) == 0.9
    assert confidence_value(1) == 1.0
