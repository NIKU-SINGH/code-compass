"""Locate the on-disk Compass index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from compass_core.errors import IndexNotFoundError
from compass_core.index.metadata import load_metadata
from compass_core.settings import settings

_INDEX_DIR = ".compass"
_DB_NAME = "graph.ladybug"
_META_NAME = "metadata.json"


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexLocation:
    """Where an index lives on disk.

    Attributes:
        repo_root: Directory that contains ``.compass/``.
        db_path: Path to ``graph.ladybug``.
        metadata_path: Path to ``metadata.json``.

    Example:
        ``find_index(Path("/repo/pkg"))`` with ``/repo/.compass/graph.ladybug`` present
        returns ``IndexLocation(repo_root=Path("/repo"), ...)``.
    """

    repo_root: Path
    db_path: Path
    metadata_path: Path


def metadata_path_for(db_path: Path) -> Path:
    """Where the metadata of the database at ``db_path`` lives: beside it.

    Args:
        db_path: Path to a ``graph.ladybug`` database.

    Returns:
        ``db_path.parent / "metadata.json"``.

    Example:
        ``metadata_path_for(Path("/repo/.compass/graph.ladybug"))`` returns
        ``Path("/repo/.compass/metadata.json")``.
    """
    return db_path.parent / _META_NAME


def _location(repo_root: Path) -> IndexLocation:
    base = repo_root / _INDEX_DIR
    return IndexLocation(
        repo_root=repo_root, db_path=base / _DB_NAME, metadata_path=base / _META_NAME
    )


def find_index(start: Path) -> IndexLocation | None:
    """Walk up from ``start`` to the first directory holding ``.compass/graph.ladybug``.

    Args:
        start: Directory to begin searching from.

    Returns:
        The location, or ``None`` if none exists up to the filesystem root.
    """
    for candidate in (start, *start.parents):
        if (candidate / _INDEX_DIR / _DB_NAME).exists():
            return _location(candidate)
    return None


def require_index(start: Path, override: Path | None = None) -> IndexLocation:
    """Like ``find_index`` but an explicit ``override`` db path wins, and a miss raises.

    Args:
        start: Directory to begin searching from.
        override: Explicit path to a ``graph.ladybug`` file.

    Returns:
        The index location.

    Raises:
        IndexNotFoundError: If nothing is found.
    """
    if override is not None:
        return IndexLocation(
            repo_root=override.parent.parent,
            db_path=override,
            metadata_path=metadata_path_for(override),
        )
    location = find_index(start)
    if location is None:
        raise IndexNotFoundError(searched_from=start)
    return location


def locate_index(start: Path | None = None) -> IndexLocation:
    """Find and check the index every adapter should use: ``LADYBUG_DB_PATH``, else walk up.

    When the configured ``LADYBUG_DB_PATH`` exists it wins, resolved so ``repo_root``
    is absolute whatever the working directory. Otherwise the index is found by
    walking up from ``start``, as git does with ``.git/``. Its metadata is then read, so
    an index built by an incompatible version of compass is rejected before any query.

    Args:
        start: Directory to search from; defaults to the working directory.

    Returns:
        The index location.

    Raises:
        IndexNotFoundError: If no configured index exists and none is found above
            ``start``.
        IndexIncompatibleError: If the index's metadata is unreadable or its schema
            version is not the one this compass reads; the message says to re-ingest.

    Example:
        Run from ``/repo/pkg`` with ``/repo/.compass/graph.ladybug`` present and the
        default ``LADYBUG_DB_PATH``, ``locate_index()`` returns
        ``IndexLocation(repo_root=Path("/repo"), ...)``.
    """
    origin = start if start is not None else Path.cwd()
    configured = Path(settings.LADYBUG_DB_PATH).resolve()
    location = (
        require_index(origin, override=configured) if configured.exists() else require_index(origin)
    )
    load_metadata(location.metadata_path)
    return location
