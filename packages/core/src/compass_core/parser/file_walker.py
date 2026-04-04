"""Core utilities for discovering Python source files in a repository.

Respects .gitignore rules and skips common development directories.
Applies a file size limit to avoid oversized or generated files.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pathspec

logger = logging.getLogger(__name__)

_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "dist",
        "build",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".eggs",
        "*.egg-info",
    }
)

# Limit for file discovery to avoid performance hits from large files.
_MAX_BYTES = 500 * 1024


def _load_gitignore(root: Path) -> pathspec.PathSpec | None:
    """Load and parse .gitignore rules from the repository root.

    Args:
        root: The root directory of the repository.

    Returns:
        A :class:`pathspec.PathSpec` object if .gitignore exists, or None.
    """
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return None
    try:
        lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
        return pathspec.PathSpec.from_lines("gitwildmatch", lines)
    except OSError as exc:
        logger.warning("Could not read .gitignore: %s", exc)
        return None


def walk_python_files(root: Path) -> Iterator[Path]:
    """Yield absolute paths for all eligible .py files under *root*.

    This function performs a recursive walk, respecting common skip directories
    and .gitignore rules.

    Args:
        root: Repository root directory. Resolved to an absolute path.

    Yields:
        Absolute :class:`~pathlib.Path` objects for discovered .py files.

    Raises:
        NotADirectoryError: If the provided root is not a directory.

    Example:
        >>> list(walk_python_files(Path(".")))
        [PosixPath('/abs/path/main.py'), PosixPath('/abs/path/utils/helpers.py')]
    """
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    spec = _load_gitignore(root)
    yield from _recurse(root, root, spec)


def _recurse(
    current: Path,
    root: Path,
    spec: pathspec.PathSpec | None,
) -> Iterator[Path]:
    """Recursively traverse directories to find Python source files.

    Args:
        current: The current directory being traversed.
        root: The repository root (used for relative path matching).
        spec: Parsed gitignore rules, if any.

    Yields:
        Paths to discovered .py files.
    """
    try:
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError as exc:
        logger.debug("Permission denied, skipping: %s (%s)", current, exc)
        return

    for entry in entries:
        if entry.is_dir():
            if _should_skip_dir(entry, root, spec):
                continue
            yield from _recurse(entry, root, spec)

        elif entry.is_file() and entry.suffix == ".py":
            if _should_skip_file(entry, root, spec):
                continue
            yield entry


def _should_skip_dir(entry: Path, root: Path, spec: pathspec.PathSpec | None) -> bool:
    """Determine if a directory should be skipped during traversal.

    Checks against common skip directories and .gitignore rules.

    Args:
        entry: The directory entry to check.
        root: Repository root for relative path calculation.
        spec: Gitignore rules.

    Returns:
        True if the directory should be skipped, False otherwise.
    """
    if entry.name in _SKIP_DIRS:
        return True
    if spec is not None:
        # pathspec expects forward-slash paths; append "/" for directory matching
        rel = entry.relative_to(root).as_posix() + "/"
        if spec.match_file(rel):
            return True
    return False


def _should_skip_file(entry: Path, root: Path, spec: pathspec.PathSpec | None) -> bool:
    """Determine if a file should be skipped during discovery.

    Checks against .gitignore rules and file size limits.

    Args:
        entry: The file entry to check.
        root: Repository root for relative path calculation.
        spec: Gitignore rules.

    Returns:
        True if the file should be skipped, False otherwise.
    """
    if spec is not None:
        rel = entry.relative_to(root).as_posix()
        if spec.match_file(rel):
            return True
    try:
        if entry.stat().st_size > _MAX_BYTES:
            logger.debug("Skipping large file (%d bytes): %s", entry.stat().st_size, entry)
            return True
    except OSError:
        return True
    return False


