import pytest

from compass_core.ir.models import (
    CallSite,
    Definition,
    DefinitionKind,
    ImportStatement,
    ParsedFile,
)


def test_definition_is_slotted_and_typed():
    d = Definition(
        id="py::pkg.mod::Foo",
        kind=DefinitionKind.CLASS,
        name="Foo",
        file_path="pkg/mod.py",
        line_start=1,
        line_end=5,
        source="class Foo: ...",
        docstring=None,
        bases=[],
        parent_id=None,
        signature=None,
        decorators=[],
        raw_calls=[],
    )
    assert d.id == "py::pkg.mod::Foo"
    with pytest.raises(AttributeError):
        d.made_up_attr = "x"  # type: ignore[attr-defined]


def test_parsed_file_defaults_and_degraded_flag():
    pf = ParsedFile(
        path="pkg/mod.py",
        language="python",
        module_name="pkg.mod",
        content_hash="abc123",
        definitions=[],
        imports=[],
        call_sites=[],
    )
    assert pf.degraded is False
    assert pf.error is None


def test_import_statement_and_call_site_shapes():
    imp = ImportStatement(
        module="os.path",
        names=["join"],
        alias=None,
        is_relative=False,
        is_from=True,
        line=3,
    )
    assert imp.names == ["join"]

    call = CallSite(
        callee_name="join", receiver_expr=None, line=10, enclosing_definition_id="py::pkg.mod::run"
    )
    assert call.callee_name == "join"
