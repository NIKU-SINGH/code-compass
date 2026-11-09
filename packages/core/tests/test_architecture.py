"""Layering rules for ``compass_core``: an engine with no adapter inside it.

The CLI, the MCP server and the HTTP server all consume the engine, so the engine may
not depend on any of them, and the shared vocabulary may not depend on anything.
"""

from __future__ import annotations

import ast
from pathlib import Path

import compass_core

PACKAGE_ROOT = Path(compass_core.__file__).parent


def _engine_sources() -> list[Path]:
    return list(PACKAGE_ROOT.rglob("*.py"))


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _is_under(module: str, parent: str) -> bool:
    return module == parent or module.startswith(f"{parent}.")


def test_engine_never_imports_an_adapter_or_a_web_framework() -> None:
    forbidden = (
        "compass_server",
        "compass_cli",
        "compass_mcp",
        "fastapi",
        "starlette",
        "uvicorn",
    )
    offenders = {
        str(path.relative_to(PACKAGE_ROOT)): module
        for path in _engine_sources()
        for module in _imports(path)
        if any(_is_under(module, f) for f in forbidden)
    }
    assert offenders == {}


def test_shared_vocabulary_depends_on_nothing_in_the_package() -> None:
    assert not [
        m for m in _imports(PACKAGE_ROOT / "shared_types.py") if _is_under(m, "compass_core")
    ]


def test_only_the_query_layer_imports_the_query_layer() -> None:
    query_dir = PACKAGE_ROOT / "query"
    offenders = {
        str(path.relative_to(PACKAGE_ROOT)): module
        for path in _engine_sources()
        if query_dir not in path.parents
        for module in _imports(path)
        if _is_under(module, "compass_core.query")
    }
    assert offenders == {}


def test_contract_depends_only_on_the_shared_vocabulary_and_errors() -> None:
    allowed = ("compass_core.contract", "compass_core.shared_types", "compass_core.errors")
    offenders = {
        str(path.relative_to(PACKAGE_ROOT)): module
        for path in (PACKAGE_ROOT / "contract").rglob("*.py")
        for module in _imports(path)
        if _is_under(module, "compass_core") and not any(_is_under(module, a) for a in allowed)
    }
    assert offenders == {}


def test_index_never_imports_the_query_layer() -> None:
    offenders = {
        str(path.relative_to(PACKAGE_ROOT)): module
        for path in (PACKAGE_ROOT / "index").rglob("*.py")
        for module in _imports(path)
        if _is_under(module, "compass_core.query")
    }
    assert offenders == {}


def test_only_the_query_layer_and_ingest_run_graph_queries() -> None:
    may_query = (PACKAGE_ROOT / "query", PACKAGE_ROOT / "graph", PACKAGE_ROOT / "phases")
    offenders = [
        str(path.relative_to(PACKAGE_ROOT))
        for path in PACKAGE_ROOT.rglob("*.py")
        if not any(d in path.parents for d in may_query)
        and ".execute(" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_query_layer_runs_cypher_only_through_query_objects() -> None:
    # Every statement in query/ is a ``Query`` (statement + row decoder); only
    # ``Query.run`` in query/cypher.py executes Cypher or reads raw result rows.
    runner = PACKAGE_ROOT / "query" / "cypher.py"
    offenders = [
        str(path.relative_to(PACKAGE_ROOT))
        for path in (PACKAGE_ROOT / "query").rglob("*.py")
        if path != runner
        and any(call in path.read_text(encoding="utf-8") for call in (".execute(", "as_rows("))
    ]
    assert offenders == []


def test_every_enum_name_is_defined_once() -> None:
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id.endswith("Enum") for base in node.bases
            ):
                if node.name in seen:
                    duplicates.append(node.name)
                seen[node.name] = str(path)
    assert duplicates == []
