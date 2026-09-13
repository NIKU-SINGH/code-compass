"""Phase 3: SymbolTable + raw call sites -> ResolvedGraph. Typed,
confidence-scored edges. Moved from resolver/resolver.py +
resolver/call_resolver.py, operating on IR types. Cross-language resolution
(spec S5) is explicitly NOT implemented here -- same-language resolution only.

``ctx.symbol_table`` (built by SymbolTablePhase) is an identity map of
``Definition.id -> Definition.id`` -- effectively a set of known ids, not the
old resolver's rich multi-key lookup table (short name / class-qualified /
module-qualified). To resolve a raw call string this phase therefore looks up
the target *structurally* (walking a file's ``Definition`` list by name/kind/
parent, exactly as ``_find_class``/``_lookup_symbol_in_file`` did in the old
call_resolver, just against IR ``Definition`` objects instead of
``ParsedClass``/``ParsedFunction``) and then validates the resulting id
against ``ctx.symbol_table`` before returning it -- this is the "constructed
candidate ID" checked against the symbol table that the resolution pipeline
is built around.

The 10 resolution rules below preserve the exact CODE order of
resolver/call_resolver.py::_resolve_one (not the old docstring's numeric
order) and its per-raw_call ``try/except Exception`` isolation, which never
raises and falls back to UNRESOLVED on any internal error.

Confidence values come from ``ir.graph.CONFIDENCE`` where a bucket exists
(DIRECT_IMPORT, RE_EXPORT, MRO, WILDCARD, DYNAMIC, UNRESOLVED). Two of the old
call_resolver's buckets have no CONFIDENCE entry and keep their historical
literal values, same as before the move:
  - module-attribute calls (``import auth; auth.verify()``) stay at 0.9,
    distinct from the 1.0 used for bare direct-import calls.
  - EXTERNAL calls carry no confidence at all (ExternalCallEdge has no
    confidence field, matching today's behavior).
CIRCULAR never produces an edge (like UNRESOLVED/WILDCARD/DYNAMIC) so it does
not need a CONFIDENCE entry either. Note the old code's ``visited`` set is
never actually populated anywhere on the ``_resolve_one`` recursion path --
CIRCULAR is therefore unreachable via the public ``ResolutionPhase.run``
entry point today, same as it was via the old ``resolve()`` entry point. This
is a pre-existing quirk, preserved as-is, not fixed here.

**Intentional behavior change -- no global bare-name fallback.** The old
``_lookup_symbol_in_file`` fell back to ``symbol_table.get(name)`` (a bare,
unqualified global lookup) when the module-qualified lookup missed. This
phase's lookups (``_lookup_symbol_in_file``, ``_find_class``) are
file-scoped: given a specific file, they look for a match *within that file*
(and, for ``_find_class``, first consult the caller's import map to find the
base class's *actual* defining file before ever scanning). They never fall
back to "the first same-named thing anywhere in the repo". This is a
deliberate, permanent divergence from the old behavior, not an oversight: a
global bare-name fallback is exactly the same-name-collision hazard that
produced two Critical, non-deterministic bugs during review (MRO/inherit
edges picking whichever same-named class happened to be scanned first,
independent of what was actually imported) -- restoring it would reintroduce
that hazard. The tradeoff is that a few edge cases the old code coincidentally
resolved via its global fallback (e.g. a re-export chain that would have hit
1.0 confidence through an accidental global name match) now resolve at a
lower confidence, or not at all, here. That tradeoff is intentional.

**Intentional vocabulary change -- new call_type strings.** ``call_type``
values are renamed from the old resolver's vocabulary
(``RESOLVED``/``POLYMORPHIC``) to names that line up with the
``CONFIDENCE`` dict's own keys: ``DIRECT_IMPORT`` (self.method() and bare
direct-import, both old ``RESOLVED``@1.0), ``MODULE_ATTR`` (old
``RESOLVED``@0.9, still has no CONFIDENCE bucket -- see above), ``RE_EXPORT``
(old ``RESOLVED``@0.8 via __init__ chain), ``MRO`` (old ``POLYMORPHIC``@0.8).
``WILDCARD``, ``DYNAMIC``, ``EXTERNAL``, ``CIRCULAR``, and ``UNRESOLVED``
keep their old names unchanged. Nothing in-repo branches on the old string
values, so this rename is safe and was a deliberate choice, not a side
effect of the port.
"""

from __future__ import annotations

import logging

from compass_core.ir.graph import (
    CONFIDENCE,
    CallEdge,
    ExternalCallEdge,
    ImportEdge,
    InheritEdge,
    ResolvedGraph,
)
from compass_core.ir.models import CallResult, Definition, DefinitionKind, ParsedFile
from compass_core.phases.base import IngestContext

logger = logging.getLogger(__name__)


class ResolutionPhase:
    name = "resolution"

    def run(self, ctx: IngestContext) -> IngestContext:
        assert ctx.parsed_files is not None
        assert ctx.symbol_table is not None
        assert ctx.import_map is not None

        graph = ResolvedGraph(files=list(ctx.parsed_files))
        by_path = {pf.path: pf for pf in ctx.parsed_files}

        _collect_import_edges(graph, ctx.parsed_files, ctx.import_map)
        _collect_inherit_edges(graph, ctx.parsed_files, ctx.symbol_table, ctx.import_map, by_path)
        _collect_call_edges(graph, ctx.parsed_files, ctx.symbol_table, ctx.import_map, by_path)

        ctx.resolved_graph = graph
        if ctx.reporter is not None:
            ctx.reporter.update("resolution", 1, 1)
        logger.info(
            "resolved %d call edges, %d external, %d imports, %d inherits",
            len(graph.call_edges),
            len(graph.external_call_edges),
            len(graph.import_edges),
            len(graph.inherit_edges),
        )
        return ctx


# ---------------------------------------------------------------------------
# Edge collectors
# ---------------------------------------------------------------------------


def _collect_import_edges(
    graph: ResolvedGraph, files: list[ParsedFile], import_map: dict[str, dict[str, str | None]]
) -> None:
    # moved from resolver/resolver.py::_collect_import_edges, iterating
    # pf.imports (resolved through import_map) -- same dedup-via-seen-set logic.
    seen: set[tuple[str, str]] = set()
    for pf in files:
        for target_path in import_map.get(pf.path, {}).values():
            if target_path is None or target_path == pf.path:
                continue
            pair = (pf.path, target_path)
            if pair in seen:
                continue
            seen.add(pair)
            graph.import_edges.append(ImportEdge(from_path=pf.path, to_path=target_path))


def _collect_inherit_edges(
    graph: ResolvedGraph,
    files: list[ParsedFile],
    symbol_table: dict[str, str],
    import_map: dict[str, dict[str, str | None]],
    by_path: dict[str, ParsedFile],
) -> None:
    # moved from resolver/resolver.py::_collect_inherit_edges -- iterates
    # Definition entries with kind=CLASS, looks up each base name via
    # _find_class (import-map-aware first, see its docstring); unresolved
    # bases still silently produce no edge (unchanged behavior).
    for pf in files:
        file_imports = import_map.get(pf.path, {})
        for defn in pf.definitions:
            if defn.kind != DefinitionKind.CLASS:
                continue
            for base in defn.bases:
                parent_def = _find_class(base, pf, file_imports, by_path)
                if parent_def is not None and parent_def.id in symbol_table:
                    graph.inherit_edges.append(
                        InheritEdge(child_id=defn.id, parent_id=symbol_table[parent_def.id])
                    )


def _collect_call_edges(
    graph: ResolvedGraph,
    files: list[ParsedFile],
    symbol_table: dict[str, str],
    import_map: dict[str, dict[str, str | None]],
    by_path: dict[str, ParsedFile],
) -> None:
    # moved from resolver/resolver.py::_collect_call_edges -- iterates
    # Definition entries with kind in {FUNCTION, METHOD}, calls resolve_calls
    # per raw_calls entry, converts each CallResult into CallEdge/ExternalCallEdge
    # exactly as today (UNRESOLVED/WILDCARD/DYNAMIC/CIRCULAR still produce no edge).
    method_index = _build_method_index(files)
    for pf in files:
        for defn in pf.definitions:
            if defn.kind not in (DefinitionKind.FUNCTION, DefinitionKind.METHOD):
                continue
            results = resolve_calls(defn, pf, symbol_table, import_map, by_path, method_index)
            caller_id = defn.id
            for res in results:
                if res.call_type == "EXTERNAL" and res.external_library:
                    graph.external_call_edges.append(
                        ExternalCallEdge(
                            caller_id=caller_id,
                            full_ref=res.raw,
                            library=res.external_library,
                        )
                    )
                elif res.target_id is not None:
                    graph.call_edges.append(
                        CallEdge(
                            caller_id=caller_id,
                            callee_id=res.target_id,
                            call_type=res.call_type,
                            confidence=res.confidence,
                        )
                    )
                # UNRESOLVED / WILDCARD / DYNAMIC / CIRCULAR -> no edge written


# ---------------------------------------------------------------------------
# Result type public API -- resolve_calls, _resolve_one, and helpers move
# from resolver/call_resolver.py with the same code-order and the same outer
# try/except Exception per raw_call (never raises), now operating on
# Definition instead of ParsedFunction/ParsedClass.
# ---------------------------------------------------------------------------


def resolve_calls(
    caller: Definition,
    file: ParsedFile,
    symbol_table: dict[str, str],
    import_map: dict[str, dict[str, str | None]],
    by_path: dict[str, ParsedFile],
    method_index: dict[tuple[str, str], str],
) -> list[CallResult]:
    """Resolve every raw call in *caller* into a typed CallResult.

    Args:
        caller:       The Definition (FUNCTION or METHOD) whose raw_calls we
                      are resolving.
        file:         The ParsedFile that contains *caller*.
        symbol_table: Global known-id set (Definition.id -> Definition.id).
        import_map:   Per-file local_name -> file_path lookup.
        by_path:      All indexed files keyed by path.
        method_index: (parent_class_id, method_name) -> Definition.id, built
                      once per _collect_call_edges call.

    Returns:
        One CallResult per entry in caller.raw_calls (same order).
    """
    results: list[CallResult] = []
    for raw in caller.raw_calls:
        try:
            result = _resolve_one(
                raw, caller, file, symbol_table, import_map, by_path, method_index, frozenset()
            )
        except Exception:
            logger.debug("Unexpected error resolving %r in %s", raw, file.path, exc_info=True)
            result = CallResult(
                raw=raw, target_id=None, call_type="UNRESOLVED", confidence=CONFIDENCE["UNRESOLVED"]
            )
        results.append(result)
    return results


def _resolve_one(
    raw: str,
    caller: Definition,
    file: ParsedFile,
    symbol_table: dict[str, str],
    import_map: dict[str, dict[str, str | None]],
    by_path: dict[str, ParsedFile],
    method_index: dict[tuple[str, str], str],
    visited: frozenset[str],
) -> CallResult:
    file_imports = import_map.get(file.path, {})
    parts = raw.split(".", 1)
    head, tail = parts[0], parts[1] if len(parts) > 1 else None

    # Rule 7: dynamic -- check early so we don't try to look up "getattr"
    if "getattr" in raw:
        return CallResult(
            raw=raw, target_id=None, call_type="DYNAMIC", confidence=CONFIDENCE["DYNAMIC"]
        )

    # Rule 1: self.method() -- same-class lookup
    if raw.startswith("self.") and caller.parent_id is not None and tail is not None:
        method_name = raw[len("self.") :]
        target_id = method_index.get((caller.parent_id, method_name))
        if target_id is not None and target_id in symbol_table:
            return CallResult(
                raw=raw,
                target_id=symbol_table[target_id],
                call_type="DIRECT_IMPORT",
                confidence=CONFIDENCE["DIRECT_IMPORT"],
            )

    # Rule 2: direct import -- bare name imported explicitly
    if tail is None and head in file_imports:
        resolved_path = file_imports[head]
        if resolved_path is None:
            # Imported but not in indexed repo -> external
            return _external(raw, head)
        target_id = _lookup_symbol_in_file(head, resolved_path, symbol_table, by_path)
        if target_id:
            return CallResult(
                raw=raw,
                target_id=target_id,
                call_type="DIRECT_IMPORT",
                confidence=CONFIDENCE["DIRECT_IMPORT"],
            )

    # Rule 3: module attribute -- import auth; auth.verify()
    if tail and head in file_imports:
        resolved_path = file_imports[head]
        if resolved_path is None:
            return _external(raw, head)
        if resolved_path in visited:
            return CallResult(raw=raw, target_id=None, call_type="CIRCULAR", confidence=0.0)
        target_id = _lookup_symbol_in_file(tail, resolved_path, symbol_table, by_path)
        if target_id:
            # No CONFIDENCE bucket for this rule -- preserved literal 0.9,
            # distinct from the 1.0 used by direct-import (rule 2).
            return CallResult(raw=raw, target_id=target_id, call_type="MODULE_ATTR", confidence=0.9)

    # Rule 4: __init__ chain -- re-export through a package __init__.py
    init_result = _resolve_via_init(
        raw, head, tail, file, file_imports, symbol_table, import_map, by_path, visited
    )
    if init_result is not None:
        return init_result

    # Rule 5: MRO walk -- look for the method on base classes
    if tail and caller.parent_id is not None:
        owning_class = _find_definition_by_id(files_lookup=by_path, def_id=caller.parent_id)
        if owning_class is not None:
            mro_result = _resolve_via_mro(
                raw, tail, owning_class, file, file_imports, symbol_table, by_path, method_index
            )
            if mro_result is not None:
                return mro_result

    # Rule 6: wildcard import -- can't resolve name but a wildcard import exists
    if _has_wildcard(file):
        return CallResult(
            raw=raw, target_id=None, call_type="WILDCARD", confidence=CONFIDENCE["WILDCARD"]
        )

    # Rule 8: explicit external -- head is a module-level import not in our repo
    if _is_explicit_external(head, file):
        return _external(raw, head)

    # Rule 10: unresolved
    logger.debug("Unresolved call %r in %s::%s", raw, file.path, caller.name)
    return CallResult(
        raw=raw, target_id=None, call_type="UNRESOLVED", confidence=CONFIDENCE["UNRESOLVED"]
    )


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


def _resolve_via_init(
    raw: str,
    head: str,
    tail: str | None,
    file: ParsedFile,
    file_imports: dict[str, str | None],
    symbol_table: dict[str, str],
    import_map: dict[str, dict[str, str | None]],
    by_path: dict[str, ParsedFile],
    visited: frozenset[str],
) -> CallResult | None:
    """Rule 4: chase re-exports through a package __init__.py.

    The __init__.py's own re-export is resolved via ``import_map`` (the same
    per-file local_name -> file_path table SymbolTablePhase already built for
    every file, including __init__.py itself) rather than re-deriving it from
    raw ``ImportStatement.module`` text here. Re-deriving it used to mean a
    second, hand-rolled copy of module-name resolution that didn't know an
    __init__.py's relative imports (``from .inner import helper``) are
    relative to its own module_name -- silently failing on the relative-import
    style used by real `__init__.py` re-exports, unlike the plain absolute
    form (`from pkg.inner import helper`) it happened to handle.
    """
    resolved_path = file_imports.get(head)
    if not resolved_path or not resolved_path.endswith("__init__.py"):
        return None
    if resolved_path in visited:
        return CallResult(raw=raw, target_id=None, call_type="CIRCULAR", confidence=0.0)

    symbol = tail or head
    inner_path = import_map.get(resolved_path, {}).get(symbol)
    if inner_path and inner_path not in visited:
        target_id = _lookup_symbol_in_file(symbol, inner_path, symbol_table, by_path)
        if target_id:
            return CallResult(
                raw=raw,
                target_id=target_id,
                call_type="RE_EXPORT",
                confidence=CONFIDENCE["RE_EXPORT"],
            )
    return None


def _resolve_via_mro(
    raw: str,
    method_name: str,
    owning_class: Definition,
    file: ParsedFile,
    file_imports: dict[str, str | None],
    symbol_table: dict[str, str],
    by_path: dict[str, ParsedFile],
    method_index: dict[tuple[str, str], str],
) -> CallResult | None:
    """Rule 5: look up method_name on each base class of owning_class."""
    for base in owning_class.bases:
        base_def = _find_class(base, file, file_imports, by_path)
        if base_def is None:
            continue
        target_id = method_index.get((base_def.id, method_name))
        if target_id is not None and target_id in symbol_table:
            return CallResult(
                raw=raw,
                target_id=symbol_table[target_id],
                call_type="MRO",
                confidence=CONFIDENCE["MRO"],
            )
    return None


def _lookup_symbol_in_file(
    name: str,
    file_path: str,
    symbol_table: dict[str, str],
    by_path: dict[str, ParsedFile],
) -> str | None:
    """Look for *name* defined in *file_path*, module-level first.

    *name* may be dotted (e.g. ``"Worker.run"`` from ``mod.Worker.run()``,
    where rule 3 already stripped the leading module alias): the first
    segment is looked up as a module-level CLASS/FUNCTION, then each
    remaining segment is walked as a METHOD child of the previous segment's
    Definition (via ``parent_id``). A bare, single-segment *name* behaves
    exactly as before this dotted-tail support was added.
    """
    pf = by_path.get(file_path)
    if pf is None:
        return None

    parts = name.split(".")
    current = _find_definition_by_name(
        pf, parts[0], (DefinitionKind.CLASS, DefinitionKind.FUNCTION)
    )
    if current is None:
        return None
    for part in parts[1:]:
        current = _find_definition_by_name(pf, part, (DefinitionKind.METHOD,), parent_id=current.id)
        if current is None:
            return None

    if current.id in symbol_table:
        return symbol_table[current.id]
    return None


def _find_definition_by_name(
    pf: ParsedFile,
    name: str,
    kinds: tuple[DefinitionKind, ...],
    parent_id: str | None = None,
) -> Definition | None:
    """Find a Definition in *pf* by name/kind, optionally scoped to a
    specific ``parent_id`` (used to walk one dotted segment at a time)."""
    for defn in pf.definitions:
        if (
            defn.name == name
            and defn.kind in kinds
            and (parent_id is None or defn.parent_id == parent_id)
        ):
            return defn
    return None


def _find_class(
    class_name: str,
    file: ParsedFile,
    file_imports: dict[str, str | None],
    by_path: dict[str, ParsedFile],
) -> Definition | None:
    """Find a CLASS Definition by name.

    Import-map-aware first: if *class_name* is a name *file* actually
    imported, resolve it to that specific source file and look there --
    this is what makes MRO/inherit-edge resolution deterministic when two
    files define same-named classes (see the Critical fix in this phase's
    review history: a bare cross-file name scan previously picked whichever
    same-named class happened to be enumerated first, independent of what
    was actually imported).

    Only when *class_name* is not a known import of *file* do we fall back
    to scanning: current file first (deterministic, single file), then a
    global scan across every indexed file as a last resort for the
    remaining ambiguous case (a base class referenced without a traceable
    import, e.g. a dotted module-attribute base) -- that residual fallback
    can still theoretically pick an arbitrary same-named class, but it is no
    longer reachable for the common, tested, import-traceable case.
    """
    resolved_path = file_imports.get(class_name)
    if resolved_path is not None:
        target_file = by_path.get(resolved_path)
        if target_file is not None:
            found = _find_definition_by_name(target_file, class_name, (DefinitionKind.CLASS,))
            if found is not None:
                return found

    for defn in file.definitions:
        if defn.kind == DefinitionKind.CLASS and defn.name == class_name:
            return defn
    for pf in by_path.values():
        for defn in pf.definitions:
            if defn.kind == DefinitionKind.CLASS and defn.name == class_name:
                return defn
    return None


def _find_definition_by_id(files_lookup: dict[str, ParsedFile], def_id: str) -> Definition | None:
    """Find a Definition by its exact id, searching all indexed files."""
    for pf in files_lookup.values():
        for defn in pf.definitions:
            if defn.id == def_id:
                return defn
    return None


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
        call_type="EXTERNAL",
        confidence=0.0,
        external_library=library,
    )


def _build_method_index(files: list[ParsedFile]) -> dict[tuple[str, str], str]:
    """(parent_class_definition_id, method_name) -> method Definition.id, for
    O(1) self.method()/MRO lookups instead of the old string-keyed multi-key
    symbol table (which ctx.symbol_table, an id->id identity map, no longer
    carries)."""
    index: dict[tuple[str, str], str] = {}
    for pf in files:
        for defn in pf.definitions:
            if defn.kind == DefinitionKind.METHOD and defn.parent_id is not None:
                index[(defn.parent_id, defn.name)] = defn.id
    return index
