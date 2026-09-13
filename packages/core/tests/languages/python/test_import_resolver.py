from compass_core.ir.models import ImportStatement, ParsedFile
from compass_core.languages.python.import_resolver import PythonImportResolver


def _pf(path: str, module_name: str, imports: list[ImportStatement]) -> ParsedFile:
    return ParsedFile(
        path=path,
        language="python",
        module_name=module_name,
        content_hash="x",
        definitions=[],
        imports=imports,
        call_sites=[],
    )


def test_resolver_conforms_to_protocol():
    r = PythonImportResolver()
    assert r.language_id == "python"


def test_resolve_maps_local_import_to_source_path():
    files = [
        _pf(
            "pkg/a.py",
            "pkg.a",
            [
                ImportStatement(
                    module="pkg.b",
                    names=["thing"],
                    alias=None,
                    is_relative=False,
                    is_from=True,
                    line=1,
                )
            ],
        ),
        _pf("pkg/b.py", "pkg.b", []),
    ]
    result = PythonImportResolver().resolve(files)
    assert result["pkg/a.py"]["thing"] == "pkg/b.py"


def test_resolve_marks_external_import_as_none():
    files = [
        _pf(
            "pkg/a.py",
            "pkg.a",
            [
                ImportStatement(
                    module="requests",
                    names=["get"],
                    alias=None,
                    is_relative=False,
                    is_from=True,
                    line=1,
                )
            ],
        ),
    ]
    result = PythonImportResolver().resolve(files)
    assert result["pkg/a.py"]["get"] is None


def test_resolve_single_dot_relative_import_from_sibling_module():
    # from .b import thing   (inside pkg/a.py)
    files = [
        _pf(
            "pkg/a.py",
            "pkg.a",
            [
                ImportStatement(
                    module=".b",
                    names=["thing"],
                    alias=None,
                    is_relative=True,
                    is_from=True,
                    line=1,
                )
            ],
        ),
        _pf("pkg/b.py", "pkg.b", []),
    ]
    result = PythonImportResolver().resolve(files)
    assert result["pkg/a.py"]["thing"] == "pkg/b.py"


def test_resolve_relative_import_inside_package_init():
    # pkg/__init__.py: from .user import User
    files = [
        _pf(
            "pkg/__init__.py",
            "pkg",
            [
                ImportStatement(
                    module=".user",
                    names=["User"],
                    alias=None,
                    is_relative=True,
                    is_from=True,
                    line=1,
                )
            ],
        ),
        _pf("pkg/user.py", "pkg.user", []),
    ]
    result = PythonImportResolver().resolve(files)
    assert result["pkg/__init__.py"]["User"] == "pkg/user.py"


def test_resolve_multi_dot_relative_import_climbs_parent_packages():
    # pkg/sub/a.py: from ..utils import helper  -> pkg/utils.py
    files = [
        _pf(
            "pkg/sub/a.py",
            "pkg.sub.a",
            [
                ImportStatement(
                    module="..utils",
                    names=["helper"],
                    alias=None,
                    is_relative=True,
                    is_from=True,
                    line=1,
                )
            ],
        ),
        _pf("pkg/utils.py", "pkg.utils", []),
    ]
    result = PythonImportResolver().resolve(files)
    assert result["pkg/sub/a.py"]["helper"] == "pkg/utils.py"


def test_resolve_bare_relative_import_of_submodule():
    # pkg/__init__.py: from . import user  -> pkg/user.py
    files = [
        _pf(
            "pkg/__init__.py",
            "pkg",
            [
                ImportStatement(
                    module=".",
                    names=["user"],
                    alias=None,
                    is_relative=True,
                    is_from=True,
                    line=1,
                )
            ],
        ),
        _pf("pkg/user.py", "pkg.user", []),
    ]
    result = PythonImportResolver().resolve(files)
    assert result["pkg/__init__.py"]["user"] == "pkg/user.py"
