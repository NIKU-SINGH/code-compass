"""Build the import map from a list of ParsedFile objects.

This module resolves each file's imported names to the file path of the
module they come from (if that module was indexed). It is the primary
structure used by the call resolver to trace `from X import Y` and
`import X; X.fn()` patterns.

The resulting structure maps the importing file's path to a dictionary
of its local symbols and their corresponding source file paths.
"""

from __future__ import annotations

from compass_core.parser.models import ParsedFile

# Type alias for the mapping of file paths to their resolved imports.
ImportMap = dict[str, dict[str, str | None]]


def build(files: list[ParsedFile]) -> ImportMap:
    """Build and return the import map for all parsed files.

    Args:
        files: A list of ParsedFile objects representing the entire repository.

    Returns:
        A dictionary mapping each source file path to its own import map.
        The inner map looks like {local_name: source_file_path | None}.
        A value of None indicates the module is an external dependency.
    """
    module_to_path = _module_index(files)
    result: ImportMap = {}
    for pf in files:
        result[pf.path] = _resolve_file_imports(pf, module_to_path)
    return result


def module_index(files: list[ParsedFile]) -> dict[str, str]:
    """Return a lookup mapping module names to their source file paths.

    Args:
        files: A list of ParsedFile objects.

    Returns:
        A dictionary where keys are dotted module names and values are file paths.
    """
    return _module_index(files)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _module_index(files: list[ParsedFile]) -> dict[str, str]:
    """Build a mapping of module names to their file paths.

    Args:
        files: A list of ParsedFile objects.

    Returns:
        A dictionary mapping module names to absolute file paths.
    """
    return {pf.module_name: pf.path for pf in files}


def _resolve_file_imports(
    pf: ParsedFile, module_to_path: dict[str, str]
) -> dict[str, str | None]:
    """Resolve all imports in a single file to their source file paths.

    Args:
        pf: The ParsedFile object to resolve.
        module_to_path: A lookup dictionary mapping module names to file paths.

    Returns:
        A dictionary mapping local symbols to their absolute source file paths.
    """
    mapping: dict[str, str | None] = {}
    for imp in pf.imports:
        resolved = _resolve_module(imp.module, module_to_path)
        if imp.names:
            # `from X import a, b, *` — each name gets its own entry
            for name in imp.names:
                local = imp.alias if (len(imp.names) == 1 and imp.alias) else name
                mapping[local] = resolved
        else:
            # `import X` or `import X as Y`
            local = imp.alias or imp.module.split(".")[0]
            mapping[local] = resolved
    return mapping


def _resolve_module(module: str, module_to_path: dict[str, str]) -> str | None:
    """Resolve a dotted module name to an absolute file path.

    Args:
        module: The dotted module name string (e.g., 'os.path' or '..utils').
        module_to_path: A lookup dictionary mapping module names to file paths.

    Returns:
        The absolute file path if the module is internal to the repo, or None
         if it is an external dependency.
    """
    if module in module_to_path:
        return module_to_path[module]
    # Relative imports (e.g. "..utils") — strip leading dots
    stripped = module.lstrip(".")
    if stripped in module_to_path:
        return module_to_path[stripped]
    return None
