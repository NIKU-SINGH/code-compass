from compass_core.contract.results import AmbiguousReference, SymbolNotFound
from compass_core.contract.types import MatchRule
from compass_core.graph.db import GraphDB
from compass_core.index.locate import IndexLocation
from compass_core.query.references import ResolvedReference, resolve
from compass_core.shared_types import SymbolKind


def _resolved(out: object) -> ResolvedReference:
    assert isinstance(out, ResolvedReference), out
    return out


def test_exact_id(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = _resolved(
        resolve(fixture_db, "app/auth.py::decode_token", repo_root=fixture_index.repo_root)
    )
    assert out.rule is MatchRule.EXACT_ID and out.symbol.name == "decode_token"
    assert out.symbol.id == "app/auth.py::decode_token"
    assert out.symbol.qualified_name == "app.auth.decode_token"
    assert out.symbol.file_path == "app/auth.py"
    assert (out.symbol.line_start, out.symbol.line_end) == (3, 4)


def test_public_ids_never_leak_absolute_paths(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    root = str(fixture_index.repo_root)
    out = _resolved(resolve(fixture_db, "User.save", repo_root=fixture_index.repo_root))
    assert out.symbol.id == "app/models.py::User.save"
    assert out.symbol.qualified_name == "app.models.User.save"
    assert out.symbol.kind is SymbolKind.METHOD
    assert root not in out.symbol.id and root not in (out.symbol.file_path or "")


def test_class_resolves_with_kind(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = _resolved(resolve(fixture_db, "app/models.py::Admin", repo_root=fixture_index.repo_root))
    assert out.symbol.kind is SymbolKind.CLASS and out.symbol.signature is None


def test_file_path_requires_allow_file(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = _resolved(
        resolve(fixture_db, "app/auth.py", repo_root=fixture_index.repo_root, allow_file=True)
    )
    assert out.rule is MatchRule.FILE_PATH
    assert out.symbol.id == "file::app/auth.py" and out.symbol.kind is SymbolKind.FILE
    assert out.symbol.qualified_name == "app.auth"
    miss = resolve(fixture_db, "app/auth.py", repo_root=fixture_index.repo_root)
    assert isinstance(miss, SymbolNotFound)


def test_file_id_requires_allow_file(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    root = fixture_index.repo_root
    assert isinstance(resolve(fixture_db, "file::app/auth.py", repo_root=root), SymbolNotFound)
    out = _resolved(resolve(fixture_db, "file::app/auth.py", repo_root=root, allow_file=True))
    assert out.rule is MatchRule.EXACT_ID


def test_qualified_name(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    root = fixture_index.repo_root
    out = _resolved(resolve(fixture_db, "app.models.User.save", repo_root=root))
    assert out.rule is MatchRule.QUALIFIED_NAME and out.symbol.id == "app/models.py::User.save"
    out = _resolved(resolve(fixture_db, "app.auth.parse", repo_root=root))
    assert out.rule is MatchRule.QUALIFIED_NAME


def test_path_and_name_with_path_suffix(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = _resolved(resolve(fixture_db, "auth.py::parse", repo_root=fixture_index.repo_root))
    assert out.rule is MatchRule.PATH_AND_NAME and out.symbol.id == "app/auth.py::parse"


def test_external_id(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = _resolved(resolve(fixture_db, "ext::json.dumps", repo_root=fixture_index.repo_root))
    assert out.symbol.kind is SymbolKind.EXTERNAL and out.symbol.file_path is None
    assert out.symbol.id == "ext::json.dumps"


def test_bare_name_unique(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = _resolved(resolve(fixture_db, "decode_token", repo_root=fixture_index.repo_root))
    assert out.rule is MatchRule.BARE_NAME


def test_bare_name_ambiguity_lists_both(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = resolve(fixture_db, "run", repo_root=fixture_index.repo_root)
    assert isinstance(out, AmbiguousReference)
    assert {c.file_path for c in out.candidates} == {"app/cli.py", "app/jobs.py"}


def test_ambiguity_orders_by_fan_in(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = resolve(fixture_db, "save", repo_root=fixture_index.repo_root)
    assert isinstance(out, AmbiguousReference)
    # Base.save is called by User.save (MRO edge); User.save has no callers.
    assert [c.id for c in out.candidates] == [
        "app/models.py::Base.save",
        "app/models.py::User.save",
    ]


def test_class_member(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = _resolved(resolve(fixture_db, "User.save", repo_root=fixture_index.repo_root))
    assert out.rule is MatchRule.CLASS_MEMBER


def test_not_found_has_suggestions(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = resolve(fixture_db, "decode", repo_root=fixture_index.repo_root)
    # bare-name rule needs an exact name; "decode" is a substring only
    assert isinstance(out, SymbolNotFound)
    assert any(s.name == "decode_token" for s in out.suggestions)


def test_suggestions_are_capped_and_case_insensitive(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    out = resolve(fixture_db, "A", repo_root=fixture_index.repo_root, allow_file=False)
    assert isinstance(out, SymbolNotFound)
    assert 0 < len(out.suggestions) <= 5


def test_user_input_is_not_interpolated(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = resolve(fixture_db, "x' OR 1=1 //", repo_root=fixture_index.repo_root)
    assert isinstance(out, SymbolNotFound)


def test_empty_reference_not_found(fixture_db: GraphDB, fixture_index: IndexLocation) -> None:
    out = resolve(fixture_db, "  ", repo_root=fixture_index.repo_root)
    assert isinstance(out, SymbolNotFound) and out.suggestions == ()


def test_qualified_name_with_empty_or_too_many_segments_matches_nothing(
    fixture_db: GraphDB, fixture_index: IndexLocation
) -> None:
    from compass_core.query.references import _qualified

    assert _qualified(fixture_db, "a." * 250) == []
    assert _qualified(fixture_db, ".".join(["a"] * 65)) == []
    assert _qualified(fixture_db, "app.auth..decode_token") == []
