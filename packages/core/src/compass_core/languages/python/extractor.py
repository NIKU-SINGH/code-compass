"""tree-sitter-python -> IR. Pure, side-effect-free: no DB calls, no module-
level parser state -- a fresh Language + Parser is created on every call so
this class is safe to use inside ProcessPoolExecutor worker processes
(tree-sitter Parser/Language objects don't pickle cleanly).

Moved from compass_core.parser.extractor (Task 5). The tree-sitter
node-walking helpers below (`_extract_signature` through `_unwrap_decorated`,
plus `_make_parser`, `_extract_imports`) move verbatim/near-verbatim -- their
internal logic (tree-sitter node type strings, byte-offset slicing) is
unchanged. The outer assembly (`_extract_classes`, `_extract_top_level_functions`
and the removed `_extract_class`/`_extract_function`/`_extract_methods`) is
adapted to build `compass_core.ir.models` types directly instead of a nested
`parser.models.ParsedClass`/`ParsedFunction` tree, with `Definition.id`
namespaced `py::{module_name}::{name}` (class/function) or
`py::{module_name}::{parent}.{name}` (method) at construction time.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from compass_core.ir.models import CallSite, Definition, ImportStatement, ParsedFile
from compass_core.shared_types import Language as SourceLanguage
from compass_core.shared_types import SymbolKind


class PythonExtractor:
    language_id = SourceLanguage.PYTHON
    file_extensions = {".py"}

    def parse(self, source: bytes, file_path: Path) -> ParsedFile:
        content_hash = hashlib.sha256(source).hexdigest()
        module_name = _derive_module_name(file_path)

        _, parser = _make_parser()
        tree = parser.parse(source)
        root = tree.root_node

        imports = _extract_imports(source, root)
        definitions: list[Definition] = []
        call_sites: list[CallSite] = []
        _extract_classes(source, root, module_name, str(file_path), definitions, call_sites)
        _extract_top_level_functions(
            source, root, module_name, str(file_path), definitions, call_sites
        )

        return ParsedFile(
            path=str(file_path),
            language=self.language_id,
            module_name=module_name,
            content_hash=content_hash,
            definitions=definitions,
            imports=imports,
            call_sites=call_sites,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_parser() -> tuple[Language, Parser]:
    """Create and return a fresh Language + Parser pair."""
    lang = Language(tspython.language())
    parser = Parser(lang)
    return lang, parser


def _derive_module_name(path: Path) -> str:
    """Convert a file path to a dotted Python module name.

    By calling convention, ``file_path`` passed into
    ``LanguageExtractor.parse`` (and therefore into this helper) is already
    relative to the repository root -- relativizing an absolute path is
    Phase 1/parse's responsibility (a later task), not this extractor's.
    Given a root-relative path, every path component becomes a dotted
    segment, with a trailing ``__init__`` component stripped so packages are
    referenced by their directory name.

    A leading ``src`` segment is also stripped: under the standard Python
    src-layout (``packages/<pkg>/src/<import_name>/...``), imports are
    written relative to ``src/``, not the repo root, so keeping ``src`` in
    the dotted name would make every intra-repo import fail to resolve
    against this module name (see PythonImportResolver._resolve_module).
    Only the first ``src`` segment is stripped -- everything before it
    (e.g. ``packages/core``) is dropped too, since it plays no part in the
    actual import path.
    """
    parts = list(path.with_suffix("").parts)
    if "src" in parts:
        parts = parts[parts.index("src") + 1 :]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else path.stem


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------


def _extract_imports(source_bytes: bytes, root_node: Node) -> list[ImportStatement]:
    """Extract all import statements from the module-level AST node.

    Handles both `import X` and `from X import Y` forms, including aliases
    and wildcard imports.
    """
    imports: list[ImportStatement] = []
    for node in root_node.children:
        if node.type == "import_statement":
            imports.extend(_parse_import_statement(node, source_bytes))
        elif node.type == "import_from_statement":
            imports.extend(_parse_import_from_statement(node, source_bytes))
    return imports


def _parse_import_statement(node: Node, source_bytes: bytes) -> list[ImportStatement]:
    """Parse `import X` and `import X as Y` nodes."""
    result: list[ImportStatement] = []
    line = node.start_point[0] + 1

    for child in node.named_children:
        if child.type == "dotted_name":
            module = _node_text(child, source_bytes)
            result.append(
                ImportStatement(
                    module=module,
                    names=[],
                    alias=None,
                    is_relative=module.startswith("."),
                    is_from=False,
                    line=line,
                )
            )
        elif child.type == "aliased_import":
            # aliased_import: dotted_name "as" identifier
            name_node = child.child_by_field_name("name")
            alias_node = child.child_by_field_name("alias")
            module = _node_text(name_node, source_bytes) if name_node else ""
            result.append(
                ImportStatement(
                    module=module,
                    names=[],
                    alias=_node_text(alias_node, source_bytes) if alias_node else None,
                    is_relative=module.startswith("."),
                    is_from=False,
                    line=line,
                )
            )
    return result


def _parse_import_from_statement(node: Node, source_bytes: bytes) -> list[ImportStatement]:
    """Parse `from X import Y` nodes including wildcards and aliases.

    `ImportStatement` carries one `alias` field, so a statement renaming
    several names at once (`from x import a as b, c as d`) can't be
    represented as a single entry without losing all but the last alias.
    Each aliased name is therefore split into its own `ImportStatement`;
    plain (non-aliased) names stay grouped together in one, matching the
    pre-existing shape for the common `from x import a, b` case.
    """
    line = node.start_point[0] + 1
    module = ""

    children = node.named_children
    if not children:
        return [
            ImportStatement(
                module=module, names=[], alias=None, is_relative=False, is_from=True, line=line
            )
        ]

    # First named child is the module (dotted_name or relative_import)
    first = children[0]
    if first.type in ("dotted_name", "relative_import"):
        module = _node_text(first, source_bytes)
    is_relative = module.startswith(".") or first.type == "relative_import"

    # Remaining children are the imported names
    plain_names: list[str] = []
    aliased: list[tuple[str, str]] = []
    for child in children[1:]:
        if child.type == "wildcard_import":
            plain_names = ["*"]
        elif child.type == "dotted_name":
            plain_names.append(_node_text(child, source_bytes))
        elif child.type == "aliased_import":
            name_node = child.child_by_field_name("name")
            alias_node = child.child_by_field_name("alias")
            if name_node and alias_node:
                aliased.append(
                    (_node_text(name_node, source_bytes), _node_text(alias_node, source_bytes))
                )

    statements: list[ImportStatement] = []
    if plain_names:
        statements.append(
            ImportStatement(
                module=module,
                names=plain_names,
                alias=None,
                is_relative=is_relative,
                is_from=True,
                line=line,
            )
        )
    for name, alias in aliased:
        statements.append(
            ImportStatement(
                module=module,
                names=[name],
                alias=alias,
                is_relative=is_relative,
                is_from=True,
                line=line,
            )
        )
    if not statements:
        statements.append(
            ImportStatement(
                module=module,
                names=[],
                alias=None,
                is_relative=is_relative,
                is_from=True,
                line=line,
            )
        )
    return statements


# ---------------------------------------------------------------------------
# Class extraction
# ---------------------------------------------------------------------------


def _extract_classes(
    source_bytes: bytes,
    root_node: Node,
    module_name: str,
    file_path: str,
    out_definitions: list[Definition],
    out_call_sites: list[CallSite],
) -> None:
    """Extract all top-level class definitions from the module, appending
    Definition(kind=CLASS) and Definition(kind=METHOD) entries directly into
    out_definitions, and each method's raw-call CallSite entries into
    out_call_sites."""
    for node in root_node.children:
        if node.type == "class_definition":
            _extract_class(
                node, source_bytes, module_name, file_path, out_definitions, out_call_sites
            )
        elif node.type == "decorated_definition":
            inner = _unwrap_decorated(node)
            if inner and inner.type == "class_definition":
                _extract_class(
                    inner, source_bytes, module_name, file_path, out_definitions, out_call_sites
                )


def _extract_class(
    node: Node,
    source_bytes: bytes,
    module_name: str,
    file_path: str,
    out_definitions: list[Definition],
    out_call_sites: list[CallSite],
) -> None:
    """Build a Definition(kind=CLASS) from a class_definition AST node and
    append it (and its methods) into out_definitions."""
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source_bytes) if name_node else ""
    class_id = f"py::{module_name}::{name}"

    # Bases: argument_list child named "superclasses"
    bases: list[str] = []
    superclasses_node = node.child_by_field_name("superclasses")
    if superclasses_node:
        for child in superclasses_node.named_children:
            if child.type in ("identifier", "attribute", "dotted_name"):
                bases.append(_node_text(child, source_bytes))

    body_node = node.child_by_field_name("body")
    docstring = _extract_docstring(body_node, source_bytes) if body_node else None

    # If wrapped in decorated_definition, source/line includes decorators
    container = node.parent if node.parent and node.parent.type == "decorated_definition" else node
    line_start = container.start_point[0] + 1
    line_end = container.end_point[0] + 1
    source = _slice_source(source_bytes, container.start_byte, container.end_byte)

    out_definitions.append(
        Definition(
            id=class_id,
            kind=SymbolKind.CLASS,
            name=name,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            source=source,
            docstring=docstring,
            bases=bases,
            parent_id=None,
            signature=None,
            decorators=[],
            raw_calls=[],
        )
    )

    if body_node:
        _extract_methods(
            source_bytes,
            body_node,
            module_name,
            file_path,
            name,
            class_id,
            out_definitions,
            out_call_sites,
        )


def _extract_methods(
    source_bytes: bytes,
    body_node: Node,
    module_name: str,
    file_path: str,
    parent_class: str,
    parent_id: str,
    out_definitions: list[Definition],
    out_call_sites: list[CallSite],
) -> None:
    """Extract all method definitions from a class body node."""
    seen_ids: dict[str, int] = {}
    for child in body_node.children:
        if child.type == "function_definition":
            _extract_function(
                child,
                source_bytes,
                module_name,
                file_path,
                out_definitions,
                out_call_sites,
                is_method=True,
                parent_class=parent_class,
                parent_id=parent_id,
                seen_ids=seen_ids,
            )
        elif child.type == "decorated_definition":
            inner = _unwrap_decorated(child)
            if inner and inner.type == "function_definition":
                _extract_function(
                    inner,
                    source_bytes,
                    module_name,
                    file_path,
                    out_definitions,
                    out_call_sites,
                    is_method=True,
                    parent_class=parent_class,
                    parent_id=parent_id,
                    seen_ids=seen_ids,
                )


# ---------------------------------------------------------------------------
# Function extraction
# ---------------------------------------------------------------------------


def _extract_top_level_functions(
    source_bytes: bytes,
    root_node: Node,
    module_name: str,
    file_path: str,
    out_definitions: list[Definition],
    out_call_sites: list[CallSite],
) -> None:
    """Extract all top-level (non-method) function definitions."""
    seen_ids: dict[str, int] = {}
    for node in root_node.children:
        if node.type == "function_definition":
            _extract_function(
                node,
                source_bytes,
                module_name,
                file_path,
                out_definitions,
                out_call_sites,
                is_method=False,
                parent_class=None,
                parent_id=None,
                seen_ids=seen_ids,
            )
        elif node.type == "decorated_definition":
            inner = _unwrap_decorated(node)
            if inner and inner.type == "function_definition":
                _extract_function(
                    inner,
                    source_bytes,
                    module_name,
                    file_path,
                    out_definitions,
                    out_call_sites,
                    is_method=False,
                    seen_ids=seen_ids,
                    parent_class=None,
                    parent_id=None,
                )


def _extract_function(
    node: Node,
    source_bytes: bytes,
    module_name: str,
    file_path: str,
    out_definitions: list[Definition],
    out_call_sites: list[CallSite],
    is_method: bool = False,
    parent_class: str | None = None,
    parent_id: str | None = None,
    seen_ids: dict[str, int] | None = None,
) -> None:
    """Build a Definition(kind=FUNCTION|METHOD) from a function_definition AST
    node, appending it into out_definitions and its raw calls as CallSite
    entries into out_call_sites.

    `seen_ids`, when given, tracks how many definitions have already claimed
    each base id within the enclosing scope (a class body or a module's
    top level). Two defs can legitimately share a name+scope — most commonly
    a `@property` getter and its `@x.setter`/`@x.deleter` — and without
    disambiguation the later one would silently collide with (and overwrite)
    the earlier one's node in the symbol table and graph. On a collision the
    id is suffixed with the decorator that caused it (`#setter`, `#deleter`)
    when recognizable, else a `#2`, `#3`, ... counter.
    """
    # If inside decorated_definition, use the wrapper for source/line bounds
    container = node.parent if node.parent and node.parent.type == "decorated_definition" else node
    decorators = _extract_decorators(container, source_bytes) if container is not node else []

    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source_bytes) if name_node else ""

    if is_method and parent_class is not None:
        base_id = f"py::{module_name}::{parent_class}.{name}"
    else:
        base_id = f"py::{module_name}::{name}"

    def_id = base_id
    if seen_ids is not None:
        occurrence = seen_ids.get(base_id, 0)
        if occurrence:
            if any(d.endswith(".setter") for d in decorators):
                def_id = f"{base_id}#setter"
            elif any(d.endswith(".deleter") for d in decorators):
                def_id = f"{base_id}#deleter"
            else:
                def_id = f"{base_id}#{occurrence + 1}"
        seen_ids[base_id] = occurrence + 1

    signature = _extract_signature(node, source_bytes)

    body_node = node.child_by_field_name("body")
    docstring = _extract_docstring(body_node, source_bytes) if body_node else None
    raw_calls = _extract_raw_calls(body_node, source_bytes) if body_node else []

    line_start = container.start_point[0] + 1
    line_end = container.end_point[0] + 1
    source = _slice_source(source_bytes, container.start_byte, container.end_byte)

    out_definitions.append(
        Definition(
            id=def_id,
            kind=SymbolKind.METHOD if is_method else SymbolKind.FUNCTION,
            name=name,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            source=source,
            docstring=docstring,
            bases=[],
            parent_id=parent_id,
            signature=signature,
            decorators=decorators,
            raw_calls=raw_calls,
        )
    )

    for call in raw_calls:
        out_call_sites.append(
            CallSite(
                callee_name=call,
                receiver_expr=None,
                line=line_start,
                enclosing_definition_id=def_id,
            )
        )


def _extract_signature(node: Node, source_bytes: bytes) -> str:
    """Extract the def-line signature up to (not including) the body block.

    Handles both single-line and multi-line signatures. Includes the return
    type annotation if present.
    """
    body_node = node.child_by_field_name("body")
    if body_node:
        # Signature is everything from def to the byte before the body block
        sig_bytes = source_bytes[node.start_byte : body_node.start_byte]
        # Strip trailing whitespace/colon/newlines to get a clean def line
        sig = sig_bytes.decode("utf-8", errors="replace").rstrip().rstrip(":")
        return sig + ":"
    # Fallback: first line of the node
    full = source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
    return full.splitlines()[0]


# ---------------------------------------------------------------------------
# Docstring extraction
# ---------------------------------------------------------------------------


def _extract_docstring(body_node: Node | None, source_bytes: bytes) -> str | None:
    """Return the docstring of a function or class body, or None.

    The docstring is the first statement when it is a bare string literal.
    """
    if body_node is None:
        return None
    for child in body_node.children:
        if child.type == "expression_statement":
            for grandchild in child.children:
                if grandchild.type == "string":
                    raw = _node_text(grandchild, source_bytes)
                    return _strip_string_literal(raw)
            break  # only the first statement counts
        elif child.type not in ("comment", "\n"):
            break
    return None


def _strip_string_literal(raw: str) -> str:
    """Strip quotes from a Python string literal using ast.literal_eval."""
    try:
        value = ast.literal_eval(raw)
        if isinstance(value, str):
            return value
    except (ValueError, SyntaxError):
        pass
    # Fallback: strip common quote styles
    for prefix in ('"""', "'''", '"', "'"):
        if raw.startswith(prefix) and raw.endswith(prefix) and len(raw) >= 2 * len(prefix):
            return raw[len(prefix) : -len(prefix)]
    return raw


# ---------------------------------------------------------------------------
# Call extraction
# ---------------------------------------------------------------------------


def _extract_raw_calls(body_node: Node, source_bytes: bytes) -> list[str]:
    """Collect all call expression strings from a function body.

    Walks the AST recursively. Does not descend into nested function or
    class definitions to avoid polluting the caller's call list.
    """
    calls: list[str] = []
    _walk_calls(body_node, source_bytes, calls)
    return list(dict.fromkeys(calls))  # deduplicate while preserving order


def _walk_calls(node: Node, source_bytes: bytes, calls: list[str]) -> None:
    """Recursively visit nodes, collecting call strings."""
    for child in node.children:
        if child.type in ("function_definition", "class_definition"):
            # Don't cross into nested definitions
            continue
        if child.type == "call":
            fn_node = child.child_by_field_name("function")
            if fn_node:
                call_str = _call_to_string(fn_node, source_bytes)
                if call_str:
                    calls.append(call_str)
            # Still descend into arguments (calls within calls)
            args = child.child_by_field_name("arguments")
            if args:
                _walk_calls(args, source_bytes, calls)
        else:
            _walk_calls(child, source_bytes, calls)


def _call_to_string(fn_node: Node, source_bytes: bytes) -> str:
    """Convert a call's function field node to a dotted string.

    e.g. `self.save` for `self.save()`, `foo` for `foo()`.
    """
    if fn_node.type == "identifier":
        return _node_text(fn_node, source_bytes)
    if fn_node.type == "attribute":
        obj_node = fn_node.child_by_field_name("object")
        attr_node = fn_node.child_by_field_name("attribute")
        if obj_node and attr_node:
            obj = _call_to_string(obj_node, source_bytes)
            attr = _node_text(attr_node, source_bytes)
            return f"{obj}.{attr}"
    # For other expressions (subscript, etc.) return the raw text
    return _node_text(fn_node, source_bytes)


# ---------------------------------------------------------------------------
# Decorator extraction
# ---------------------------------------------------------------------------


def _extract_decorators(node: Node, source_bytes: bytes) -> list[str]:
    """Extract decorator names from a decorated_definition node.

    Args:
        node: A ``decorated_definition`` AST node.
        source_bytes: Raw file bytes for text slicing.

    Returns:
        List of decorator name strings without the leading ``@``.
    """
    decorators: list[str] = []
    if node.type != "decorated_definition":
        return decorators
    for child in node.children:
        if child.type == "decorator":
            # decorator children: "@" followed by the decorator expression
            # Skip the "@" token (anonymous child) and decode the rest
            deco_text = _node_text(child, source_bytes).lstrip("@").strip()
            # Strip trailing () if it's a decorator call like @app.route("/")
            deco_name = deco_text.split("(")[0].strip()
            decorators.append(deco_name)
    return decorators


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _node_text(node: Node | None, source_bytes: bytes) -> str:
    """Decode the source text covered by a tree-sitter node."""
    if node is None:
        return ""
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _slice_source(source_bytes: bytes, start: int, end: int) -> str:
    """Decode a byte slice from the source."""
    return source_bytes[start:end].decode("utf-8", errors="replace")


def _unwrap_decorated(node: Node) -> Node | None:
    """Return the inner function_definition or class_definition from a decorated_definition."""
    for child in node.children:
        if child.type in ("function_definition", "class_definition"):
            return child
    return None
