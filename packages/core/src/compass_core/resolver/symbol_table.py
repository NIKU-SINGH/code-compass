"""Global symbol table construction for symbol resolution.

This module provides functionality to build a global symbol table from parsed
source files. The symbol table maps various qualified symbol names (classes,
methods, and functions) to their canonical graph node IDs, enabling efficient
lookup during the call resolution phase.

The symbol table handles multiple lookup patterns for each symbol, including:
  - Unqualified names (e.g., "MyClass")
  - Module-qualified names (e.g., "my_module.MyClass")
  - Class-qualified names (e.g., "MyClass.my_method")
  - Fully qualified names (e.g., "my_module.MyClass.my_method")
"""

from __future__ import annotations

from compass_core.parser.models import ParsedClass, ParsedFile, ParsedFunction

# SymbolTable maps qualified symbol names (e.g., "my_module.MyClass") to graph node IDs.
SymbolTable = dict[str, str]


def build(files: list[ParsedFile]) -> SymbolTable:
    """Builds and returns the global symbol table from all parsed files.

    This function iterates through all parsed files, extracting class and
    function definitions to populate a flat dictionary mapping every resolvable
    symbol name to its canonical node ID.

    Examples:
        >>> files = [ParsedFile(module_name="auth", ...)]
        >>> table = build(files)
        >>> table["User"]
        "auth/models.py::User"
        >>> table["auth.User"]
        "auth/models.py::User"

    Args:
        files: All ParsedFile objects from the initial parsing pass.

    Returns:
        A flat dictionary mapping every resolvable symbol name to its node ID.
    """
    table: SymbolTable = {}
    for pf in files:
        for cls in pf.classes:
            _index_class(table, cls, pf.module_name)
        for func in pf.functions:
            _index_function(table, func, pf.module_name)
    return table


def class_id(cls: ParsedClass) -> str:
    """Returns the canonical node ID for a class.

    The class ID is used for unique identification in the graph and is
    composed of the file path and class name separated by double colons.

    Args:
        cls: The ParsedClass object to generate an ID for.

    Returns:
        A unique string identifier for the class (e.g., "models.py::User").
    """
    return f"{cls.file_path}::{cls.name}"


def function_id(func: ParsedFunction) -> str:
    """Returns the canonical node ID for a function or method.

    For methods, the ID includes the parent class name. For top-level functions,
    it only includes the function name.

    Args:
        func: The ParsedFunction object to generate an ID for.

    Returns:
        A unique string identifier for the function (e.g., "utils.py::helper"
        or "models.py::User.save").
    """
    if func.is_method and func.parent_class:
        return f"{func.file_path}::{func.parent_class}.{func.name}"
    return f"{func.file_path}::{func.name}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _index_class(table: SymbolTable, cls: ParsedClass, module_name: str) -> None:
    """Indexes a class and its methods in the symbol table.

    Updates the table with both the class's short name and its
    module-qualified name.

    Args:
        table: The symbol table dictionary to update.
        cls: The class object to index.
        module_name: The name of the module containing the class.
    """
    node_id = class_id(cls)
    table[cls.name] = node_id
    table[f"{module_name}.{cls.name}"] = node_id
    for method in cls.methods:
        _index_method(table, method, cls.name, module_name)


def _index_method(
    table: SymbolTable,
    method: ParsedFunction,
    class_name: str,
    module_name: str,
) -> None:
    """Indexes a class method in the symbol table.

    Updates the table with both the class-qualified and module-qualified names.

    Args:
        table: The symbol table dictionary to update.
        method: The method function object to index.
        class_name: The name of the class containing the method.
        module_name: The name of the module containing the class.
    """
    node_id = function_id(method)
    table[f"{class_name}.{method.name}"] = node_id
    table[f"{module_name}.{class_name}.{method.name}"] = node_id


def _index_function(table: SymbolTable, func: ParsedFunction, module_name: str) -> None:
    """Indexes a top-level function in the symbol table.

    Updates the table with both the function's short name and its
    module-qualified name.

    Args:
        table: The symbol table dictionary to update.
        func: The function object to index.
        module_name: The name of the module containing the function.
    """
    node_id = function_id(func)
    table[func.name] = node_id
    table[f"{module_name}.{func.name}"] = node_id
