from pathlib import Path

import compass_core.languages.python  # noqa: F401
from compass_core.languages.python.extractor import PythonExtractor
from compass_core.phases.base import IngestContext
from compass_core.phases.symbol_table import SymbolTablePhase


def test_builds_symbol_table_from_definition_ids(tmp_path: Path):
    path = tmp_path / "mod.py"
    path.write_text("class Foo:\n    def bar(self):\n        pass\n")
    rel_path = path.relative_to(tmp_path)
    pf = PythonExtractor().parse(path.read_bytes(), rel_path)
    ctx = IngestContext(repo_root=tmp_path)
    ctx.parsed_files = [pf]

    result = SymbolTablePhase().run(ctx)

    assert result.symbol_table is not None
    assert "py::mod::Foo" in result.symbol_table
    assert "py::mod::Foo.bar" in result.symbol_table


def test_builds_import_map_dispatched_by_language(tmp_path: Path):
    a = tmp_path / "a.py"
    a.write_text("from b import thing\n")
    b = tmp_path / "b.py"
    b.write_text("thing = 1\n")
    rel_a = a.relative_to(tmp_path)
    rel_b = b.relative_to(tmp_path)
    pf_a = PythonExtractor().parse(a.read_bytes(), rel_a)
    pf_b = PythonExtractor().parse(b.read_bytes(), rel_b)
    ctx = IngestContext(repo_root=tmp_path)
    ctx.parsed_files = [pf_a, pf_b]

    result = SymbolTablePhase().run(ctx)

    assert result.import_map is not None
    assert result.import_map[str(rel_a)]["thing"] == str(rel_b)
