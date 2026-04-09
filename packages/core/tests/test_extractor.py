"""Unit tests for compass_core.parser.extractor.

All tests are pure — no DB, no network. Each test writes a temporary .py
file to pytest's tmp_path fixture and asserts on the returned ParsedFile.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from textwrap import dedent

from compass_core.parser.extractor import extract_file
from compass_core.parser.models import ParsedFile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_py(tmp_path: Path, name: str, source: str) -> Path:
    p = tmp_path / name
    p.write_text(dedent(source), encoding="utf-8")
    return p


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
    pf = extract_file(p)
    assert len(pf.functions) == 1
    fn = pf.functions[0]
    assert fn.name == "add"
    assert "def add" in fn.signature
    assert fn.line_start == 1
    assert fn.line_end == 2
    assert fn.is_method is False
    assert fn.parent_class is None


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
    pf = extract_file(p)
    fn = pf.functions[0]
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
    pf = extract_file(p)
    assert pf.functions[0].docstring is None


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
    pf = extract_file(p)
    fn = pf.functions[0]
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
    pf = extract_file(p)
    sig = pf.functions[0].signature
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
    pf = extract_file(p)
    assert len(pf.classes) == 1
    cls = pf.classes[0]
    assert cls.name == "Counter"
    assert len(cls.methods) == 2
    for m in cls.methods:
        assert m.is_method is True
        assert m.parent_class == "Counter"


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
    pf = extract_file(p)
    assert pf.classes[0].docstring == "A simple class."


def test_extract_class_bases(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        class Admin(User, Auditable):
            pass
        """,
    )
    pf = extract_file(p)
    assert pf.classes[0].bases == ["User", "Auditable"]


def test_extract_class_no_bases(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        class Plain:
            pass
        """,
    )
    pf = extract_file(p)
    assert pf.classes[0].bases == []


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
    pf = extract_file(p)
    assert len(pf.functions) == 1
    assert pf.functions[0].name == "standalone"
    assert len(pf.classes[0].methods) == 1
    assert pf.classes[0].methods[0].name == "method"


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------


def test_extract_import_basic(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "import os\n")
    pf = extract_file(p)
    assert len(pf.imports) == 1
    imp = pf.imports[0]
    assert imp.module == "os"
    assert imp.names == []
    assert imp.alias is None
    assert imp.is_from is False
    assert imp.line == 1


def test_extract_import_from(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "from os.path import join, exists\n")
    pf = extract_file(p)
    assert len(pf.imports) == 1
    imp = pf.imports[0]
    assert imp.module == "os.path"
    assert set(imp.names) == {"join", "exists"}
    assert imp.is_from is True


def test_extract_import_alias(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "import numpy as np\n")
    pf = extract_file(p)
    imp = pf.imports[0]
    assert imp.module == "numpy"
    assert imp.alias == "np"


def test_extract_import_from_alias(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "from os.path import join as j\n")
    pf = extract_file(p)
    imp = pf.imports[0]
    assert imp.module == "os.path"
    assert "join" in imp.names
    assert imp.alias == "j"


def test_extract_import_wildcard(tmp_path: Path) -> None:
    p = write_py(tmp_path, "f.py", "from utils import *\n")
    pf = extract_file(p)
    assert pf.imports[0].names == ["*"]


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
    pf = extract_file(p)
    calls = pf.functions[0].raw_calls
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
    pf = extract_file(p)
    calls = pf.functions[0].raw_calls
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
    pf = extract_file(p)
    assert pf.functions[0].raw_calls.count("foo") == 1


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
    pf = extract_file(p)
    calls = pf.functions[0].raw_calls
    assert "secret" not in calls


# ---------------------------------------------------------------------------
# content_hash and module_name
# ---------------------------------------------------------------------------


def test_content_hash(tmp_path: Path) -> None:
    source = "x = 1\n"
    p = write_py(tmp_path, "f.py", source)
    pf = extract_file(p)
    expected = hashlib.sha256(source.encode()).hexdigest()
    assert pf.content_hash == expected


def test_module_name_with_root(tmp_path: Path) -> None:
    pkg = tmp_path / "mypackage" / "sub"
    pkg.mkdir(parents=True)
    p = pkg / "module.py"
    p.write_text("x = 1\n", encoding="utf-8")
    pf = extract_file(p, root=tmp_path)
    assert pf.module_name == "mypackage.sub.module"


def test_module_name_without_root(tmp_path: Path) -> None:
    p = write_py(tmp_path, "helpers.py", "x = 1\n")
    pf = extract_file(p)
    assert pf.module_name == "helpers"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_file(tmp_path: Path) -> None:
    p = write_py(tmp_path, "empty.py", "")
    pf = extract_file(p)
    assert isinstance(pf, ParsedFile)
    assert pf.imports == []
    assert pf.classes == []
    assert pf.functions == []


def test_syntax_error_file_does_not_crash(tmp_path: Path) -> None:
    """tree-sitter is error-tolerant; extraction should not raise."""
    p = tmp_path / "bad.py"
    p.write_bytes(b"def broken(\n    !!invalid!!\n")
    pf = extract_file(p)
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
    pf = extract_file(p)
    assert pf.functions[0].file_path == str(p)


def test_source_stored_on_function(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        def hello():
            return "world"
        """,
    )
    pf = extract_file(p)
    assert "def hello" in pf.functions[0].source


def test_source_stored_on_class(tmp_path: Path) -> None:
    p = write_py(
        tmp_path,
        "f.py",
        """\
        class Foo:
            pass
        """,
    )
    pf = extract_file(p)
    assert "class Foo" in pf.classes[0].source
