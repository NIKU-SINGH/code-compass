from dataclasses import replace

import pytest

from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation
from compass_core.query.detail import describe
from compass_core.query.results import AmbiguousReference, NodeDetail, SymbolNotFound
from compass_core.query.types import SymbolKind


def _detail(db: GraphDB, loc: IndexLocation, ref: str) -> NodeDetail:
    result = describe(db, loc, ref)
    assert isinstance(result, NodeDetail), result
    return result


def _ids(symbols) -> list[str]:  # type: ignore[no-untyped-def]
    return [s.id for s in symbols]


def test_class_has_source_bases_subclasses_and_methods(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    user = _detail(fixture_db, fixture_index, "app/models.py::User")
    assert user.symbol.kind is SymbolKind.CLASS
    assert user.symbol.source is not None and user.symbol.source.startswith("class User(Base):")
    assert _ids(user.bases) == ["app/models.py::Base"]
    assert _ids(user.subclasses) == ["app/models.py::Admin"]
    assert _ids(user.members) == ["app/models.py::User.save"]
    assert user.callees == () and user.imports == ()


def test_class_without_relations_has_empty_lists(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    admin = _detail(fixture_db, fixture_index, "app/models.py::Admin")
    assert admin.subclasses == () and admin.members == ()
    assert _ids(admin.bases) == ["app/models.py::User"]


def test_function_has_callees_callers_and_signature(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    decode = _detail(fixture_db, fixture_index, "app/auth.py::decode_token")
    assert decode.symbol.kind is SymbolKind.FUNCTION
    assert decode.symbol.signature == "def decode_token(raw):"
    assert _ids(decode.callers) == [
        "app/api.py::handle",
        "app/cli.py::run",
        "app/jobs.py::nightly",
    ]
    assert decode.bases == () and decode.members == ()

    nightly = _detail(fixture_db, fixture_index, "app/jobs.py::nightly")
    assert _ids(nightly.callees) == ["app/auth.py::decode_token"]


def test_method_is_described_by_qualified_id(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    save = _detail(fixture_db, fixture_index, "app/models.py::Base.save")
    assert save.symbol.kind is SymbolKind.METHOD
    assert "app/models.py::User.save" in _ids(save.callers)


def test_file_lists_definitions_and_import_neighbours(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    models = _detail(fixture_db, fixture_index, "file::app/models.py")
    assert models.symbol.kind is SymbolKind.FILE
    assert {"app/models.py::Base", "app/models.py::User", "app/models.py::Admin"} <= set(
        _ids(models.members)
    )
    assert models.symbol.source is not None and models.symbol.source.startswith("class Base:")

    auth = _detail(fixture_db, fixture_index, "file::app/auth.py")
    assert auth.imported_by, "auth.py is imported by other files in the sample repo"


def test_unknown_reference_is_not_found(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    result = describe(fixture_db, fixture_index, "app/models.py::Nope")
    assert isinstance(result, SymbolNotFound)


def test_ambiguous_bare_name_is_reported(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    result = describe(fixture_db, fixture_index, "save")
    assert isinstance(result, AmbiguousReference)


@pytest.mark.parametrize("ref", ["app/models.py::User", "file::app/models.py"])
def test_result_is_json_serialisable(
    fixture_db: GraphDB, fixture_index: IndexLocation, ref: str
) -> None:
    from compass_core.query.serialize import to_json

    assert to_json(_detail(fixture_db, fixture_index, ref)).startswith("{")


def test_file_without_a_readable_copy_on_disk_has_no_source(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    from compass_core.query.detail import _file_source

    models = _detail(fixture_db, fixture_index, "file::app/models.py").symbol
    root = fixture_index.repo_root.resolve()
    assert _file_source(models, root) is not None
    # A path that escapes the repository root is never read.
    escaping = type(models)(
        id="file::../x",
        kind=SymbolKind.FILE,
        name="x",
        qualified_name="x",
        file_path="../../etc/hosts",
        line_start=None,
        line_end=None,
        signature=None,
    )
    assert _file_source(escaping, root) is None
    # Neither is a file that no longer exists.
    gone = replace(models, file_path="app/missing.py")
    assert _file_source(gone, root) is None
