"""Data models for parsed Python source files.

All models are plain dataclasses — no DB, no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Import:
    """A single import statement, raw and unresolved.

    Captured from a source file's AST, this model represents what is being imported 
    without checking if the module exists on the filesystem.

    Attributes:
        module: The dotted path of the module being imported (e.g., "os.path").
        names: Specific objects or sub-modules imported from the module 
            (e.g., ["join", "exists"]). Empty for basic imports like `import os`.
        alias: The rename target if the 'as' keyword is used.
        is_from: True if the statement is `from X import Y`, False for `import X`.
        line: The 1-indexed line number in the source file where the statement occurs.

    Examples:
        `from os import path as p` maps to:
        Import(
            module="os",
            names=["path"],
            alias="p",
            is_from=True,
            line=1
        )
    """

    module: str
    names: list[str]
    alias: str | None
    is_from: bool
    line: int


@dataclass
class ParsedFunction:
    """A function or method definition extracted from a source file.

    Attributes:
        name: The name of the function (e.g., "process_data").
        signature: The full definition line including arguments and return type 
            (e.g., "def foo(x: int) -> int:").
        docstring: The function's docstring content, if any.
        line_start: 1-indexed line number where the function (or its decorator) starts.
        line_end: 1-indexed line number where the function body ends (inclusive).
        source: The complete source code of the function and its decorators.
        file_path: The absolute path to the file containing this function.
        raw_calls: A list of function/method call strings found within the body, 
            captured raw (e.g., ["db.fetch", "print"]).
        decorators: List of decorator names applied to the function 
            (e.g., ["staticmethod", "cache"]).
        is_method: True if the function is defined inside a class.
        parent_class: The name of the class if this is a method, otherwise None.

    Examples:
        `@cache\ndef add(a, b):\n    'Sum.'\n    return a + b` maps to:
        ParsedFunction(
            name="add",
            signature="def add(a, b):",
            docstring="Sum.",
            line_start=1,
            line_end=4,
            source="@cache...",
            file_path="/app.py",
            raw_calls=[],
            decorators=["cache"],
            is_method=False,
            parent_class=None
        )
    """

    name: str
    signature: str
    docstring: str | None
    line_start: int
    line_end: int
    source: str
    file_path: str
    raw_calls: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    is_method: bool = False
    parent_class: str | None = None


@dataclass
class ParsedClass:
    """A class definition extracted from a source file.

    Attributes:
        name: The name of the class (e.g., "UserManager").
        bases: The raw names of the base classes (e.g., ["BaseModel", "Observable"]).
        methods: A list of `ParsedFunction` objects representing the class methods.
        docstring: The class's docstring content, if any.
        line_start: 1-indexed line number where the class starts.
        line_end: 1-indexed line number where the class body ends (inclusive).
        source: The complete source code of the class.
        file_path: The absolute path to the file containing this class.

    Examples:
        `class API(Base):\n    'Doc.'\n    def get(self): ...` maps to:
        ParsedClass(
            name="API",
            bases=["Base"],
            methods=[ParsedFunction(...)],
            docstring="Doc.",
            line_start=1,
            line_end=3,
            source="class API...",
            file_path="/app.py"
        )
    """

    name: str
    bases: list[str]
    methods: list[ParsedFunction]
    docstring: str | None
    line_start: int
    line_end: int
    source: str
    file_path: str


@dataclass
class ParsedFile:
    """Comprehensive data model representing a fully parsed Python source file.

    This serves as the root container for all structured information extracted 
    from a single file by the parser.

    Attributes:
        path: The absolute path to the source file.
        module_name: The dotted module name derived from the path 
            (e.g., "compass_core.parser.models").
        imports: A list of `Import` objects found in the file.
        classes: A list of `ParsedClass` objects found in the file.
        functions: A list of top-level `ParsedFunction` objects 
            (does not include class methods).
        content_hash: A SHA-256 hex digest of the file content used for 
            caching and change detection.

    Examples:
        `main.py` with 1 import and 1 class maps to:
        ParsedFile(
            path="/src/main.py",
            module_name="main",
            imports=[Import(...)],
            classes=[ParsedClass(...)],
            functions=[],
            content_hash="abc123def..."
        )
    """

    path: str
    module_name: str
    imports: list[Import]
    classes: list[ParsedClass]
    functions: list[ParsedFunction]
    content_hash: str
