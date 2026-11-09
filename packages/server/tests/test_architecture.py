"""Layering rules for ``compass_server``: a thin HTTP adapter over the engine.

Routes call ``compass_core.query`` functions and return ``compass_core.contract``
results. Graph queries and row parsing stay in the engine, so the same question gets
the same answer from the CLI, the MCP server and the web app.
"""

from __future__ import annotations

import ast
from pathlib import Path

import compass_server

PACKAGE_ROOT = Path(compass_server.__file__).parent


def _imports(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_server_holds_no_graph_queries_or_row_parsing() -> None:
    offenders: dict[str, str] = {}
    for path in PACKAGE_ROOT.rglob("*.py"):
        if "compass_core.query.rows" in _imports(path):
            offenders[str(path.relative_to(PACKAGE_ROOT))] = "imports query.rows"
        if ".execute(" in path.read_text(encoding="utf-8"):
            offenders[str(path.relative_to(PACKAGE_ROOT))] = "runs a query"
    assert offenders == {}


def test_server_never_imports_another_adapter() -> None:
    offenders = {
        str(path.relative_to(PACKAGE_ROOT)): module
        for path in PACKAGE_ROOT.rglob("*.py")
        for module in _imports(path)
        if module.split(".")[0] in {"compass_cli", "compass_mcp"}
    }
    assert offenders == {}
