"""Phase 0: repo path -> FileManifest. Walks the repo respecting
.gitignore/.compassignore, detects language per file via the registry's
known extensions, filters binaries/vendored/generated code, and computes a
content_hash per file (unused for skip-logic yet — captured now for future
incremental re-index, per spec)."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pathspec

from compass_core.errors import DiscoveryError
from compass_core.languages import registry
from compass_core.phases.base import FileManifest, FileMetadata, IngestContext

logger = logging.getLogger(__name__)

_SKIP_DIRS = frozenset(
    {
        ".git",
        ".claude",
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
_MAX_BYTES = 500 * 1024


@dataclass
class _WalkStats:
    """Counts skipped directories/files as a byproduct of the walk, so the
    manifest can report how much of the repo was filtered out without a
    second traversal."""

    dirs_scanned: int = 0
    ignored_count: int = 0


class DiscoveryPhase:
    name = "discovery"

    def run(self, ctx: IngestContext) -> IngestContext:
        root = ctx.repo_root.resolve()
        if not root.is_dir():
            raise DiscoveryError(f"not a directory: {root}", phase_name=self.name)

        spec = _load_ignore_spec(root)
        extensions = registry.registered_extensions()
        stats = _WalkStats()
        files: list[FileMetadata] = []
        for path in _walk(root, root, spec, extensions, stats):
            language = registry.get_extractor_for_extension(path.suffix).language_id
            content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            files.append(FileMetadata(path=path, language=language, content_hash=content_hash))

        ctx.manifest = FileManifest(
            files=files, dirs_scanned=stats.dirs_scanned, ignored_count=stats.ignored_count
        )
        ctx.repo_root = root
        if ctx.reporter is not None:
            ctx.reporter.update("discovery", len(files), len(files))
        return ctx


def _load_ignore_spec(root: Path) -> pathspec.PathSpec | None:
    """Load and merge .gitignore and .compassignore pattern sets from *root*.

    Moved from parser/file_walker.py::_load_gitignore, extended to also
    consider a .compassignore file (if present), merging both pattern sets
    into a single PathSpec.
    """
    lines: list[str] = []
    for name in (".gitignore", ".compassignore"):
        ignore_file = root / name
        if not ignore_file.is_file():
            continue
        try:
            lines.extend(ignore_file.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError as exc:
            logger.warning("Could not read %s: %s", name, exc)

    if not lines:
        return None
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def _walk(
    current: Path,
    root: Path,
    spec: pathspec.PathSpec | None,
    extensions: set[str],
    stats: _WalkStats,
) -> Iterator[Path]:
    """Recursively traverse directories to find files with a registered extension.

    Generalized from parser/file_walker.py::_recurse — same PermissionError
    isolation (catch, log at debug, skip) and _should_skip_dir/_should_skip_file
    logic, but filters on `entry.suffix in extensions` instead of `== ".py"`.
    """
    try:
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError as exc:
        logger.debug("Permission denied, skipping: %s (%s)", current, exc)
        return

    stats.dirs_scanned += 1
    for entry in entries:
        if entry.is_dir():
            if _should_skip_dir(entry, root, spec):
                stats.ignored_count += 1
                continue
            yield from _walk(entry, root, spec, extensions, stats)

        elif entry.is_file() and entry.suffix in extensions:
            if _should_skip_file(entry, root, spec):
                stats.ignored_count += 1
                continue
            yield entry


def _should_skip_dir(entry: Path, root: Path, spec: pathspec.PathSpec | None) -> bool:
    """Determine if a directory should be skipped during traversal.

    Checks against common skip directories and .gitignore/.compassignore rules.
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

    Checks against .gitignore/.compassignore rules and file size limits.
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
