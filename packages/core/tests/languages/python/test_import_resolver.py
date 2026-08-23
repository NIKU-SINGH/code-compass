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
