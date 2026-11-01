"""Python import resolution: relative imports, packages, __init__.py.

Moved from resolver/import_map.py, adapted to the ImportResolver Protocol
and IR types. Relative imports (`.user`, `..utils`) are resolved against the
importing file's own package, per Python's relative-import level rules:
one leading dot means "this file's package", each additional dot walks up
one more parent package. A package's `__init__.py` *is* its package, so its
own leading-dot imports resolve relative to its own module_name rather than
a parent of it.
"""

from __future__ import annotations

from compass_core.ir.models import ParsedFile
from compass_core.shared_types import Language


class PythonImportResolver:
    language_id = Language.PYTHON

    def resolve(self, files: list[ParsedFile]) -> dict[str, dict[str, str | None]]:
        module_to_path = _module_index(files)
        return {pf.path: _resolve_file_imports(pf, module_to_path) for pf in files}


def _module_index(files: list[ParsedFile]) -> dict[str, str]:
    """Build a mapping of module names to their file paths."""
    return {pf.module_name: pf.path for pf in files}


def _resolve_file_imports(pf: ParsedFile, module_to_path: dict[str, str]) -> dict[str, str | None]:
    """Resolve all imports in a single file to their source file paths."""
    mapping: dict[str, str | None] = {}
    for imp in pf.imports:
        resolved = _resolve_module(imp.module, pf, module_to_path)
        if imp.names:
            # `from X import a, b, *` — each name gets its own entry
            for name in imp.names:
                local = imp.alias if (len(imp.names) == 1 and imp.alias) else name
                target = resolved
                if imp.is_relative and not imp.module.lstrip("."):
                    # `from . import name` / `from .. import name` — each
                    # imported name is usually a submodule of the base
                    # package (try that first); fall back to the generic
                    # resolution (the base package's own file) for names
                    # that are attributes defined in its __init__.py itself.
                    target = (
                        _resolve_bare_relative(imp.module, name, pf, module_to_path) or resolved
                    )
                mapping[local] = target
        else:
            # `import X` or `import X as Y`
            local = imp.alias or imp.module.split(".")[0]
            mapping[local] = resolved
    return mapping


def _resolve_module(
    module: str, importer: ParsedFile, module_to_path: dict[str, str]
) -> str | None:
    """Resolve a dotted module name to an absolute file path.

    Returns the file path if the module is internal to the repo, or None
    if it is an external dependency.
    """
    if not module.startswith("."):
        return module_to_path.get(module)

    base_parts = _base_package_parts(module, importer)
    remainder = module.lstrip(".")
    target_parts = base_parts + remainder.split(".") if remainder else base_parts
    candidate = ".".join(part for part in target_parts if part)
    return module_to_path.get(candidate)


def _base_package_parts(module: str, importer: ParsedFile) -> list[str]:
    """Compute the dotted package an import's leading dots are relative to.

    One dot means "the importing file's own package". A package's
    `__init__.py` *is* that package, so its own module_name is the base;
    any other file's base is its module_name with the last (leaf module)
    segment stripped. Each dot beyond the first walks up one more level.
    """
    level = len(module) - len(module.lstrip("."))
    is_package_init = importer.path.endswith("__init__.py") or importer.path.endswith(
        "__init__.pyi"
    )
    parts = importer.module_name.split(".") if importer.module_name else []
    if not is_package_init:
        parts = parts[:-1]
    climb = level - 1
    if climb:
        parts = parts[:-climb] if climb <= len(parts) else []
    return parts


def _resolve_bare_relative(
    module: str, name: str, importer: ParsedFile, module_to_path: dict[str, str]
) -> str | None:
    """Resolve one name from `from . import name` / `from .. import name`.

    Each name here is a submodule of the base package rather than an
    attribute of a single target module, so it must be resolved per-name.
    """
    base_parts = _base_package_parts(module, importer)
    candidate = ".".join([*base_parts, name])
    return module_to_path.get(candidate)
