"""Unit tests for compass_core.languages.python.extractor.

Ported from the pre-move packages/core/tests/test_extractor.py (411 lines).
Every test case from that file is present here, updated only for the new
call site and for the namespaced/IR shape of the result
(`Definition`/`DefinitionKind`/`ImportStatement`/`CallSite` instead of
`ParsedClass`/`ParsedFunction`/`Import`).

By calling convention, the `file_path` argument passed into
`LanguageExtractor.parse` is relative to the repository root -- relativizing
an absolute on-disk path is Phase 1/parse's job (a later task), not this
extractor's. So tests here decouple "where the file actually lives on disk"
(under pytest's tmp_path, so we can write and read real bytes) from "what
relative path is passed to .parse()" (a plain, repo-relative Path, e.g.
Path("f.py") or Path("pkg/sub.py")) -- see the `parse()` helper below.

All tests are pure -- no DB, no network. Each test writes a temporary .py
file to pytest's tmp_path fixture and asserts on the returned ParsedFile.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from textwrap import dedent

from compass_core.ir.models import DefinitionKind, ParsedFile
from compass_core.languages.python.extractor import PythonExtractor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_py(tmp_path: Path, name: str, source: str) -> Path:
    p = tmp_path / name
    p.write_text(dedent(source), encoding="utf-8")
    return p


def parse(disk_path: Path, rel_path: str | Path | None = None) -> ParsedFile:
    """Read real bytes from disk_path, but pass a repo-relative Path (not
    the absolute tmp_path location) as the `file_path` argument to
    `.parse()`, matching the calling convention. Defaults to just the
    filename (i.e. a flat, root-level relative path) when rel_path is
    omitted."""
    if rel_path is None:
        rel_path = Path(disk_path.name)
    elif isinstance(rel_path, str):
        rel_path = Path(rel_path)
    return PythonExtractor().parse(disk_path.read_bytes(), rel_path)


def classes(pf: ParsedFile):
    return [d for d in pf.definitions if d.kind is DefinitionKind.CLASS]


def functions(pf: ParsedFile):
    return [d for d in pf.definitions if d.kind is DefinitionKind.FUNCTION]


def methods(pf: ParsedFile):
    return [d for d in pf.definitions if d.kind is DefinitionKind.METHOD]


# ---------------------------------------------------------------------------
# Protocol metadata
# ---------------------------------------------------------------------------


def test_extractor_satisfies_protocol_metadata():
    ext = PythonExtractor()
    assert ext.language_id == "python"
    assert ext.file_extensions == {".py"}


# ---------------------------------------------------------------------------
# Basic function extraction
# ---------------------------------------------------------------------------


def test_extract_simple_function(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def add(a: int, b: int) -> int:
            return a + b
        """,
    )
    pf = parse(p)
    fns = functions(pf)
    assert len(fns) == 1
    fn = fns[0]
    assert fn.name == "add"
    assert "def add" in fn.signature
    assert fn.line_start == 1
    assert fn.line_end == 2
    assert fn.kind is DefinitionKind.FUNCTION
    assert fn.parent_id is None
    assert fn.id == "py::f::add"


def test_extract_function_docstring(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        '''\
        def greet(name: str) -> str:
            """Return a greeting."""
            return f"Hello, {name}"
        ''',
    )
    pf = parse(p)
    fn = functions(pf)[0]
    assert fn.docstring == "Return a greeting."


def test_extract_function_no_docstring(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def noop():
            pass
        """,
    )
    pf = parse(p)
    assert functions(pf)[0].docstring is None


def test_extract_decorator(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        import functools

        @functools.cache
        def fib(n):
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)
        """,
    )
    pf = parse(p)
    fn = functions(pf)[0]
    assert fn.decorators == ["functools.cache"]
    assert fn.line_start == 3  # decorator line


def test_extract_multiline_signature(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def process(
            items: list[int],
            multiplier: int = 1,
        ) -> list[int]:
            return [x * multiplier for x in items]
        """,
    )
    pf = parse(p)
    sig = functions(pf)[0].signature
    assert "def process" in sig
    assert "list[int]" in sig


# ---------------------------------------------------------------------------
# Class extraction
# ---------------------------------------------------------------------------


def test_extract_class_with_methods(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        class Counter:
            def __init__(self, start: int = 0) -> None:
                self.value = start

            def increment(self) -> None:
                self.value += 1
        """,
    )
    pf = parse(p)
    cls_defs = classes(pf)
    assert len(cls_defs) == 1
    cls = cls_defs[0]
    assert cls.name == "Counter"
    assert cls.id == "py::f::Counter"
    method_defs = methods(pf)
    assert len(method_defs) == 2
    for m in method_defs:
        assert m.kind is DefinitionKind.METHOD
        assert m.parent_id == "py::f::Counter"
        assert m.id.startswith("py::f::Counter.")


def test_extract_class_docstring(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        '''\
        class MyClass:
            """A simple class."""
            pass
        ''',
    )
    pf = parse(p)
    assert classes(pf)[0].docstring == "A simple class."


def test_extract_class_bases(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        class Admin(User, Auditable):
            pass
        """,
    )
    pf = parse(p)
    assert classes(pf)[0].bases == ["User", "Auditable"]


def test_extract_class_no_bases(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        class Plain:
            pass
        """,
    )
    pf = parse(p)
    assert classes(pf)[0].bases == []


def test_class_methods_not_in_top_level_functions(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        class MyClass:
            def method(self):
                pass

        def standalone():
            pass
        """,
    )
    pf = parse(p)
    fns = functions(pf)
    assert len(fns) == 1
    assert fns[0].name == "standalone"
    method_defs = methods(pf)
    assert len(method_defs) == 1
    assert method_defs[0].name == "method"


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------


def test_extract_import_basic(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "import os\n")
    pf = parse(p)
    assert len(pf.imports) == 1
    imp = pf.imports[0]
    assert imp.module == "os"
    assert imp.names == []
    assert imp.alias is None
    assert imp.is_from is False
    assert imp.line == 1
    assert imp.is_relative is False


def test_extract_import_from(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "from os.path import join, exists\n")
    pf = parse(p)
    assert len(pf.imports) == 1
    imp = pf.imports[0]
    assert imp.module == "os.path"
    assert set(imp.names) == {"join", "exists"}
    assert imp.is_from is True


def test_extract_import_alias(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "import numpy as np\n")
    pf = parse(p)
    imp = pf.imports[0]
    assert imp.module == "numpy"
    assert imp.alias == "np"


def test_extract_import_from_alias(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "from os.path import join as j\n")
    pf = parse(p)
    imp = pf.imports[0]
    assert imp.module == "os.path"
    assert "join" in imp.names
    assert imp.alias == "j"


def test_extract_import_wildcard(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "from utils import *\n")
    pf = parse(p)
    assert pf.imports[0].names == ["*"]


def test_extract_import_relative(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "from . import sibling\n")
    pf = parse(p)
    imp = pf.imports[0]
    assert imp.is_relative is True


# ---------------------------------------------------------------------------
# Raw call extraction
# ---------------------------------------------------------------------------


def test_raw_calls_simple(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def run():
            foo()
            bar()
        """,
    )
    pf = parse(p)
    calls = functions(pf)[0].raw_calls
    assert "foo" in calls
    assert "bar" in calls


def test_raw_calls_dotted(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def run(self):
            self.save()
            db.fetch()
        """,
    )
    pf = parse(p)
    calls = functions(pf)[0].raw_calls
    assert "self.save" in calls
    assert "db.fetch" in calls


def test_raw_calls_deduplication(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def run():
            foo()
            foo()
            foo()
        """,
    )
    pf = parse(p)
    assert functions(pf)[0].raw_calls.count("foo") == 1


def test_raw_calls_not_in_nested_function(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def outer():
            x = 1
            def inner():
                secret()
        """,
    )
    pf = parse(p)
    calls = functions(pf)[0].raw_calls
    assert "secret" not in calls


def test_raw_calls_produce_call_sites(tmp_path: Path) -> None:
    """New in the IR shape: raw calls also populate ParsedFile.call_sites,
    one CallSite per raw call, tagged with the enclosing definition id."""
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def run():
            foo()
            bar()
        """,
    )
    pf = parse(p)
    fn = functions(pf)[0]
    call_names = {cs.callee_name for cs in pf.call_sites}
    assert call_names == {"foo", "bar"}
    for cs in pf.call_sites:
        assert cs.enclosing_definition_id == fn.id


# ---------------------------------------------------------------------------
# content_hash and module_name
# ---------------------------------------------------------------------------


def test_content_hash(tmp_path: Path) -> None:
    source = "x = 1\n"
    p = write_py(tmp_path, "f.py", source)
    pf = parse(p)
    expected = hashlib.sha256(source.encode()).hexdigest()
    assert pf.content_hash == expected


def test_module_name_with_root(tmp_path: Path) -> None:
    # `file_path` is, by calling convention, already relative to the repo
    # root (relativizing an absolute path is Phase 1/parse's job, a later
    # task) -- so this replaces the old test_module_name_with_root case,
    # which passed an explicit `root=` kwarg to `extract_file`. Here we
    # pass an already-relative, nested Path directly as `file_path` and
    # confirm every path component becomes a dotted module-name segment.
    pkg = tmp_path / "mypackage" / "sub"
    pkg.mkdir(parents=True)
    p = pkg / "module.py"
    p.write_text("x = 1\n", encoding="utf-8")
    pf = parse(p, rel_path="mypackage/sub/module.py")
    assert pf.module_name == "mypackage.sub.module"


def test_module_name_without_root(tmp_path: Path) -> None:
    p = write_py(tmp_path, "helpers.py", "x = 1\n")
    pf = parse(p)
    assert pf.module_name == "helpers"


def test_module_name_nested_package(tmp_path: Path) -> None:
    """A repo-relative nested path derives a fully dotted module name from
    every path component, not just the file stem."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    p = pkg / "sub.py"
    p.write_text("x = 1\n", encoding="utf-8")
    pf = parse(p, rel_path="pkg/sub.py")
    assert pf.module_name == "pkg.sub"


def test_module_name_strips_trailing_init(tmp_path: Path) -> None:
    """A trailing __init__ path component is dropped so the package is
    referenced by its directory name, not literally `.__init__`."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    p = pkg / "__init__.py"
    p.write_text("x = 1\n", encoding="utf-8")
    pf = parse(p, rel_path="pkg/__init__.py")
    assert pf.module_name == "pkg"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_file(tmp_path: Path) -> None:
    p = write_py(tmp_path, "empty.py", "")
    pf = parse(p)
    assert isinstance(pf, ParsedFile)
    assert pf.imports == []
    assert pf.definitions == []
    assert pf.call_sites == []


def test_syntax_error_file_does_not_crash(tmp_path: Path) -> None:
    """tree-sitter is error-tolerant; extraction should not raise."""
    p = tmp_path / "bad.py"
    p.write_bytes(b"def broken(\n    !!invalid!!\n")
    pf = parse(p)
    assert isinstance(pf, ParsedFile)


def test_file_path_stored_on_function(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def foo():
            pass
        """,
    )
    pf = parse(p)
    assert functions(pf)[0].file_path == "f.py"


def test_source_stored_on_function(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def hello():
            return "world"
        """,
    )
    pf = parse(p)
    assert "def hello" in functions(pf)[0].source


def test_source_stored_on_class(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        class Foo:
            pass
        """,
    )
    pf = parse(p)
    assert "class Foo" in classes(pf)[0].source


# ---------------------------------------------------------------------------
# Namespaced ID / IR-shape specific cases (Task 5 additions from the brief)
# ---------------------------------------------------------------------------


def test_parse_class_and_method_get_namespaced_ids(tmp_path: Path):
    p = write_py(
        tmp_path,
        "mod.py",
        """
        class Foo:
            def bar(self):
                return 1
        """,
    )
    pf = parse(p)
    cls_defs = classes(pf)
    method_defs = methods(pf)
    assert len(cls_defs) == 1
    assert cls_defs[0].id == "py::mod::Foo"
    assert len(method_defs) == 1
    assert method_defs[0].id == "py::mod::Foo.bar"
    assert method_defs[0].parent_id == "py::mod::Foo"


def test_parse_top_level_function(tmp_path: Path):
    p = write_py(
        tmp_path,
        "mod.py",
        """
        def run():
            helper()
        """,
    )
    pf = parse(p)
    fn_defs = functions(pf)
    assert len(fn_defs) == 1
    assert fn_defs[0].id == "py::mod::run"
    assert fn_defs[0].raw_calls == ["helper"]


def test_parse_imports(tmp_path: Path):
    p = write_py(
        tmp_path,
        "mod.py",
        """
        from os import path
        import sys
        """,
    )
    pf = parse(p)
    assert len(pf.imports) == 2
    from_import = next(i for i in pf.imports if i.is_from)
    assert from_import.module == "os"
    assert from_import.names == ["path"]


def test_parse_populates_degraded_false_on_success(tmp_path: Path):
    p = write_py(tmp_path, "mod.py", "x = 1\n")
    pf = parse(p)
    assert pf.degraded is False
    assert pf.error is None


def test_parse_language_is_python(tmp_path: Path):
    p = write_py(tmp_path, "mod.py", "x = 1\n")
    pf = parse(p)
    assert pf.language == "python"
