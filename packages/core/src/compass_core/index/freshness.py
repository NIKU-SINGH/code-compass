"""Whether indexed files changed on disk since the last ingest.

Pure file-system checks with no database access: the caller supplies the indexed
paths (the query layer reads them from the graph) and the ingest time from
``metadata.json``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


def is_stale(path: Path, indexed_at: int) -> bool:
    """Whether a file is missing or was modified after the ingest.

    Metadata stores whole seconds, so mtimes are compared at second resolution to keep
    a just-ingested file from looking stale. Consequently an edit made within the same
    second as the ingest is invisible (a false negative).

    Args:
        path: Absolute path of an indexed file.
        indexed_at: Ingest time in epoch seconds.

    Returns:
        ``True`` if the file no longer exists or its mtime is later than ``indexed_at``.

    Example:
        After ``touch app/auth.py`` post-ingest,
        ``is_stale(Path("/repo/app/auth.py"), meta_indexed_at)`` returns ``True``.
    """
    try:
        return int(path.stat().st_mtime) > indexed_at
    except OSError:
        return True


def count_stale(repo_root: Path, paths: Iterable[str], indexed_at: int) -> int:
    """Count the indexed files that are missing or changed since the ingest.

    Every path is stat'ed on each call, so callers may want to cache the result.

    Args:
        repo_root: Absolute repository root.
        paths: Repo-relative POSIX paths of the indexed files.
        indexed_at: Ingest time in epoch seconds.

    Returns:
        How many of ``paths`` are stale.

    Example:
        With ``app/auth.py`` deleted after ingest,
        ``count_stale(Path("/repo"), ["app/auth.py", "app/db.py"], t)`` returns ``1``.
    """
    return sum(1 for path in paths if is_stale(repo_root / path, indexed_at))
