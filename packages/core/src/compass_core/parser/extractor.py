"""Tree-sitter based extraction of Python source files into ParsedFile objects.

All functions are pure — no DB calls, no side effects, no module-level parser
state. A fresh Language + Parser is created on every call so the module is
safe to use inside ProcessPoolExecutor worker processes.
"""

from __future__ import annotations

import ast
import hashlib
import logging
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser

from compass_core.parser.models import Import, ParsedClass, ParsedFile, ParsedFunction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_file(path: Path, root: Path | None = None) -> ParsedFile:
    """Parse a single .py file and return a fully populated ParsedFile.

    Creates a fresh tree-sitter Parser on every call — safe for use inside
    worker processes spawned by ProcessPoolExecutor.

    Args:
        path: Absolute path to the Python source file.
        root: Optional repository root used to derive the dotted module name.
              If None, falls back to the file stem.

    Returns:
        A ParsedFile dataclass with imports, classes, and top-level functions.
    """
    source_bytes = path.read_bytes()
    content_hash = hashlib.sha256(source_bytes).hexdigest()
    module_name = _derive_module_name(path, root)

    _, parser = _make_parser()
    tree = parser.parse(source_bytes)
    root_node = tree.root_node

    imports = _extract_imports(source_bytes, root_node)
    classes = _extract_classes(source_bytes, root_node, str(path))
    functions = _extract_top_level_functions(source_bytes, root_node, str(path))

    return ParsedFile(
        path=str(path),
        module_name=module_name,
        imports=imports,
        classes=classes,
        functions=functions,
        content_hash=content_hash,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_parser() -> tuple[Language, Parser]:
    """Create and return a fresh Language + Parser pair."""
    lang = Language(tspython.language())
    parser = Parser(lang)
    return lang, parser


def _derive_module_name(path: Path, root: Path | None) -> str:
    """Convert a file path to a dotted Python module name.

    Args:
        path: The file path to convert.
        root: Repository root. If provided, the module name is derived
              relative to root; otherwise the file stem is used.

    Returns:
        A dotted module name string, e.g. "compass_core.parser.models".
    """
    if root is not None:
        try:
            rel = path.resolve().relative_to(root.resolve())
            parts = list(rel.with_suffix("").parts)
            # Drop trailing __init__ so packages are referenced by their name
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]
            return ".".join(parts) if parts else path.stem
        except ValueError:
            pass
    return path.stem


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------


def _extract_imports(source_bytes: bytes, root_node: Node) -> list[Import]:
    """Extract all import statements from the module-level AST node.

    Handles both `import X` and `from X import Y` forms, including aliases
    and wildcard imports.
    """
    imports: list[Import] = []
    for node in root_node.children:
        if node.type == "import_statement":
            imports.extend(_parse_import_statement(node, source_bytes))
        elif node.type == "import_from_statement":
            imports.append(_parse_import_from_statement(node, source_bytes))
    return imports


def _parse_import_statement(node: Node, source_bytes: bytes) -> list[Import]:
    """Parse `import X` and `import X as Y` nodes."""
    result: list[Import] = []
    line = node.start_point[0] + 1

    for child in node.named_children:
        if child.type == "dotted_name":
            result.append(Import(
                module=_node_text(child, source_bytes),
                names=[],
                alias=None,
                is_from=False,
                line=line,
            ))
        elif child.type == "aliased_import":
            # aliased_import: dotted_name "as" identifier
            name_node = child.child_by_field_name("name")
            alias_node = child.child_by_field_name("alias")
            result.append(Import(
                module=_node_text(name_node, source_bytes) if name_node else "",
                names=[],
                alias=_node_text(alias_node, source_bytes) if alias_node else None,
                is_from=False,
                line=line,
            ))
    return result


def _parse_import_from_statement(node: Node, source_bytes: bytes) -> Import:
    """Parse `from X import Y` nodes including wildcards and aliases."""
    line = node.start_point[0] + 1
    module = ""
    names: list[str] = []
    alias: str | None = None

    children = node.named_children
    if not children:
        return Import(module=module, names=names, alias=alias, is_from=True, line=line)

    # First named child is the module (dotted_name or relative_import)
    first = children[0]
    if first.type in ("dotted_name", "relative_import"):
        module = _node_text(first, source_bytes)

    # Remaining children are the imported names
    for child in children[1:]:
        if child.type == "wildcard_import":
            names = ["*"]
        elif child.type == "dotted_name":
            names.append(_node_text(child, source_bytes))
        elif child.type == "aliased_import":
            name_node = child.child_by_field_name("name")
            alias_node = child.child_by_field_name("alias")
            if name_node:
                names.append(_node_text(name_node, source_bytes))
            if alias_node:
                alias = _node_text(alias_node, source_bytes)

    return Import(module=module, names=names, alias=alias, is_from=True, line=line)


# ---------------------------------------------------------------------------
# Class extraction
# ---------------------------------------------------------------------------


def _extract_classes(
    source_bytes: bytes, root_node: Node, file_path: str
) -> list[ParsedClass]:
    """Extract all top-level class definitions from the module."""
    classes: list[ParsedClass] = []
    for node in root_node.children:
        if node.type == "class_definition":
            classes.append(_extract_class(node, source_bytes, file_path))
        elif node.type == "decorated_definition":
            inner = _unwrap_decorated(node)
            if inner and inner.type == "class_definition":
                classes.append(_extract_class(inner, source_bytes, file_path))
    return classes


def _extract_class(
    node: Node, source_bytes: bytes, file_path: str
) -> ParsedClass:
    """Build a ParsedClass from a class_definition AST node."""
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source_bytes) if name_node else ""

    # Bases: argument_list child named "superclasses"
    bases: list[str] = []
    superclasses_node = node.child_by_field_name("superclasses")
    if superclasses_node:
        for child in superclasses_node.named_children:
            if child.type in ("identifier", "attribute", "dotted_name"):
                bases.append(_node_text(child, source_bytes))

    body_node = node.child_by_field_name("body")
    docstring = _extract_docstring(body_node, source_bytes) if body_node else None
    methods = _extract_methods(source_bytes, body_node, file_path, name) if body_node else []

    # If wrapped in decorated_definition, source/line includes decorators
    container = node.parent if node.parent and node.parent.type == "decorated_definition" else node
    line_start = container.start_point[0] + 1
    line_end = container.end_point[0] + 1
    source = _slice_source(source_bytes, container.start_byte, container.end_byte)

    return ParsedClass(
        name=name,
        bases=bases,
        methods=methods,
        docstring=docstring,
        line_start=line_start,
        line_end=line_end,
        source=source,
        file_path=file_path,
    )


def _extract_methods(
    source_bytes: bytes, body_node: Node, file_path: str, parent_class: str
) -> list[ParsedFunction]:
    """Extract all method definitions from a class body node."""
    methods: list[ParsedFunction] = []
    for child in body_node.children:
        if child.type == "function_definition":
            methods.append(
                _extract_function(child, source_bytes, file_path, is_method=True, parent_class=parent_class)
            )
        elif child.type == "decorated_definition":
            inner = _unwrap_decorated(child)
            if inner and inner.type == "function_definition":
                methods.append(
                    _extract_function(inner, source_bytes, file_path, is_method=True, parent_class=parent_class)
                )
    return methods


# ---------------------------------------------------------------------------
# Function extraction
# ---------------------------------------------------------------------------


def _extract_top_level_functions(
    source_bytes: bytes, root_node: Node, file_path: str
) -> list[ParsedFunction]:
    """Extract all top-level (non-method) function definitions."""
    functions: list[ParsedFunction] = []
    for node in root_node.children:
        if node.type == "function_definition":
            functions.append(
                _extract_function(node, source_bytes, file_path, is_method=False, parent_class=None)
            )
        elif node.type == "decorated_definition":
            inner = _unwrap_decorated(node)
            if inner and inner.type == "function_definition":
                functions.append(
                    _extract_function(inner, source_bytes, file_path, is_method=False, parent_class=None)
                )
    return functions


def _extract_function(
    node: Node,
    source_bytes: bytes,
    file_path: str,
    is_method: bool = False,
    parent_class: str | None = None,
) -> ParsedFunction:
    """Build a ParsedFunction from a function_definition AST node."""
    # If inside decorated_definition, use the wrapper for source/line bounds
    container = node.parent if node.parent and node.parent.type == "decorated_definition" else node
    decorators = _extract_decorators(container, source_bytes) if container is not node else []

    name_node = node.child_by_field_name("name")
    name = _node_text(name_node, source_bytes) if name_node else ""

    signature = _extract_signature(node, source_bytes)

    body_node = node.child_by_field_name("body")
    docstring = _extract_docstring(body_node, source_bytes) if body_node else None
    raw_calls = _extract_raw_calls(body_node, source_bytes) if body_node else []

    line_start = container.start_point[0] + 1
    line_end = container.end_point[0] + 1
    source = _slice_source(source_bytes, container.start_byte, container.end_byte)

    return ParsedFunction(
        name=name,
        signature=signature,
        docstring=docstring,
        line_start=line_start,
        line_end=line_end,
        source=source,
        file_path=file_path,
        raw_calls=raw_calls,
        decorators=decorators,
        is_method=is_method,
        parent_class=parent_class,
    )


def _extract_signature(node: Node, source_bytes: bytes) -> str:
    """Extract the def-line signature up to (not including) the body block.

    Handles both single-line and multi-line signatures. Includes the return
    type annotation if present.
    """
    body_node = node.child_by_field_name("body")
    if body_node:
        # Signature is everything from def to the byte before the body block
        sig_bytes = source_bytes[node.start_byte: body_node.start_byte]
        # Strip trailing whitespace/colon/newlines to get a clean def line
        sig = sig_bytes.decode("utf-8", errors="replace").rstrip().rstrip(":")
        return sig + ":"
    # Fallback: first line of the node
    full = source_bytes[node.start_byte: node.end_byte].decode("utf-8", errors="replace")
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
            return raw[len(prefix): -len(prefix)]
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
    return source_bytes[node.start_byte: node.end_byte].decode("utf-8", errors="replace")


def _slice_source(source_bytes: bytes, start: int, end: int) -> str:
    """Decode a byte slice from the source."""
    return source_bytes[start:end].decode("utf-8", errors="replace")


def _unwrap_decorated(node: Node) -> Node | None:
    """Return the inner function_definition or class_definition from a decorated_definition."""
    for child in node.children:
        if child.type in ("function_definition", "class_definition"):
            return child
    return None
