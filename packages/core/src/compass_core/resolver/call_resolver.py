"""Resolve raw call strings into typed, confidence-scored CallResult objects.

Resolution rules (applied in priority order):
  1. self.method()     — same-class lookup                → RESOLVED,     1.0
  2. direct import     — from auth import fn; fn()        → RESOLVED,     1.0
  3. module attr       — import auth; auth.verify()       → RESOLVED,     0.9
  4. __init__ chain    — re-export through package init   → RESOLVED,     0.8
  5. MRO walk          — base class method lookup         → POLYMORPHIC,  0.8
  6. wildcard import   — from utils import *              → WILDCARD,     0.6
  7. dynamic           — getattr(obj, name)()             → DYNAMIC,      0.0
  8. external          — import requests; requests.get()  → EXTERNAL,     n/a
  9. circular          — A→B→A import cycle               → CIRCULAR,     0.0
  10. unknown          — everything else                  → UNRESOLVED,   0.0

Never raises. Every raw_call receives exactly one CallResult.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from compass_core.parser.models import ParsedClass, ParsedFile, ParsedFunction
from compass_core.resolver.import_map import ImportMap
from compass_core.resolver.models import (
    CIRCULAR,
    DYNAMIC,
    EXTERNAL,
    POLYMORPHIC,
    RESOLVED,
    UNRESOLVED,
    WILDCARD,
)
from compass_core.resolver.symbol_table import SymbolTable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class CallResult:
    """Outcome of resolving one raw call string."""

    raw: str
    target_id: str | None       # Function node ID if resolved internally
    call_type: str
    confidence: float
    external_library: str | None = None  # set only for EXTERNAL calls


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_calls(
    func: ParsedFunction,
    file: ParsedFile,
    symbol_table: SymbolTable,
    import_map: ImportMap,
    all_files: dict[str, ParsedFile],
) -> list[CallResult]:
    """Resolve every raw call in *func* into a typed CallResult.

    Args:
        func:         The function whose raw_calls we are resolving.
        file:         The ParsedFile that contains *func*.
        symbol_table: Global symbol → node ID lookup.
        import_map:   Per-file local_name → file_path lookup.
        all_files:    All indexed files keyed by path.

    Returns:
        One CallResult per entry in func.raw_calls (same order).
    """
    results: list[CallResult] = []
    for raw in func.raw_calls:
        try:
            result = _resolve_one(raw, func, file, symbol_table, import_map, all_files, frozenset())
        except Exception:
            logger.debug("Unexpected error resolving %r in %s", raw, func.file_path, exc_info=True)
            result = CallResult(raw=raw, target_id=None, call_type=UNRESOLVED, confidence=0.0)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Resolution pipeline
# ---------------------------------------------------------------------------


def _resolve_one(
    raw: str,
    func: ParsedFunction,
    file: ParsedFile,
    symbol_table: SymbolTable,
    import_map: ImportMap,
    all_files: dict[str, ParsedFile],
    visited: frozenset[str],
) -> CallResult:
    file_imports = import_map.get(file.path, {})
    parts = raw.split(".", 1)
    head, tail = parts[0], parts[1] if len(parts) > 1 else None

    # Rule 7: dynamic — check early so we don't try to look up "getattr"
    if "getattr" in raw:
        return CallResult(raw=raw, target_id=None, call_type=DYNAMIC, confidence=0.0)

    # Rule 1: self.method() — same-class lookup
    if raw.startswith("self.") and func.parent_class and tail is not None:
        method_name = raw[len("self."):]
        key = f"{func.parent_class}.{method_name}"
        if key in symbol_table:
            return CallResult(raw=raw, target_id=symbol_table[key], call_type=RESOLVED, confidence=1.0)

    # Rule 2: direct import — bare name imported explicitly
    if tail is None and head in file_imports:
        resolved_path = file_imports[head]
        if resolved_path is None:
            # Imported but not in indexed repo → external
            return _external(raw, head)
        target_id = _lookup_symbol_in_file(head, resolved_path, symbol_table, all_files)
        if target_id:
            return CallResult(raw=raw, target_id=target_id, call_type=RESOLVED, confidence=1.0)

    # Rule 3: module attribute — import auth; auth.verify()
    if tail and head in file_imports:
        resolved_path = file_imports[head]
        if resolved_path is None:
            return _external(raw, head)
        if resolved_path in visited:
            return CallResult(raw=raw, target_id=None, call_type=CIRCULAR, confidence=0.0)
        target_id = _lookup_symbol_in_file(tail, resolved_path, symbol_table, all_files)
        if target_id:
            return CallResult(raw=raw, target_id=target_id, call_type=RESOLVED, confidence=0.9)

    # Rule 4: __init__ chain — re-export through a package __init__.py
    init_result = _resolve_via_init(raw, head, tail, file, file_imports, symbol_table, all_files, visited)
    if init_result is not None:
        return init_result

    # Rule 5: MRO walk — look for the method on base classes
    if tail and func.parent_class:
        mro_result = _resolve_via_mro(raw, tail, func.parent_class, file, symbol_table, all_files)
        if mro_result is not None:
            return mro_result

    # Rule 6: wildcard import — can't resolve name but a wildcard import exists
    if _has_wildcard(file):
        return CallResult(raw=raw, target_id=None, call_type=WILDCARD, confidence=0.6)

    # Rule 8: explicit external — head is a module-level import not in our repo
    if _is_explicit_external(head, file):
        return _external(raw, head)

    # Rule 10: unresolved
    logger.debug("Unresolved call %r in %s::%s", raw, file.path, func.name)
    return CallResult(raw=raw, target_id=None, call_type=UNRESOLVED, confidence=0.0)


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _resolve_via_init(
    raw: str,
    head: str,
    tail: str | None,
    file: ParsedFile,
    file_imports: dict[str, str | None],
    symbol_table: SymbolTable,
    all_files: dict[str, ParsedFile],
    visited: frozenset[str],
) -> CallResult | None:
    """Rule 4: chase re-exports through a package __init__.py."""
    resolved_path = file_imports.get(head)
    if not resolved_path or not resolved_path.endswith("__init__.py"):
        return None
    if resolved_path in visited:
        return CallResult(raw=raw, target_id=None, call_type=CIRCULAR, confidence=0.0)

    init_file = all_files.get(resolved_path)
    if init_file is None:
        return None

    symbol = tail or head
    module_to_path = {pf.module_name: pf.path for pf in all_files.values()}
    for imp in init_file.imports:
        if symbol not in imp.names:
            continue
        inner_path = _resolve_module_name(imp.module, module_to_path)
        if inner_path and inner_path not in visited:
            target_id = _lookup_symbol_in_file(symbol, inner_path, symbol_table, all_files)
            if target_id:
                return CallResult(raw=raw, target_id=target_id, call_type=RESOLVED, confidence=0.8)
    return None


def _resolve_via_mro(
    raw: str,
    method_name: str,
    parent_class: str,
    file: ParsedFile,
    symbol_table: SymbolTable,
    all_files: dict[str, ParsedFile],
) -> CallResult | None:
    """Rule 5: look up method_name on each base class of parent_class."""
    cls = _find_class(parent_class, file, all_files)
    if cls is None:
        return None
    for base in cls.bases:
        key = f"{base}.{method_name}"
        if key in symbol_table:
            return CallResult(raw=raw, target_id=symbol_table[key], call_type=POLYMORPHIC, confidence=0.8)
    return None


def _lookup_symbol_in_file(
    name: str,
    file_path: str,
    symbol_table: SymbolTable,
    all_files: dict[str, ParsedFile],
) -> str | None:
    """Look for *name* defined in *file_path* via the symbol table."""
    pf = all_files.get(file_path)
    if pf is None:
        return None
    return symbol_table.get(f"{pf.module_name}.{name}") or symbol_table.get(name)


def _find_class(
    class_name: str, file: ParsedFile, all_files: dict[str, ParsedFile]
) -> ParsedClass | None:
    """Find a class by name, checking the current file first."""
    for cls in file.classes:
        if cls.name == class_name:
            return cls
    for pf in all_files.values():
        for cls in pf.classes:
            if cls.name == class_name:
                return cls
    return None


def _resolve_module_name(module: str, module_to_path: dict[str, str]) -> str | None:
    if module in module_to_path:
        return module_to_path[module]
    stripped = module.lstrip(".")
    return module_to_path.get(stripped)


def _has_wildcard(file: ParsedFile) -> bool:
    return any("*" in imp.names for imp in file.imports)


def _is_explicit_external(head: str, file: ParsedFile) -> bool:
    """True if *head* was imported at module level as a bare `import X` statement."""
    for imp in file.imports:
        if imp.is_from:
            continue
        top = (imp.alias or imp.module).split(".")[0]
        if top == head:
            return True
    return False


def _external(raw: str, library: str) -> CallResult:
    return CallResult(
        raw=raw,
        target_id=None,
        call_type=EXTERNAL,
        confidence=0.0,
        external_library=library,
    )
