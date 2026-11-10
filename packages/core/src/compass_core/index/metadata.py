"""Typed read/write of ``.compass/metadata.json``."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from compass_core.errors import IndexIncompatibleError
from compass_core.shared_types import Language

SCHEMA_VERSION = 2
"""Graph schema written by this version of compass; indexes in any other version are
rejected and must be rebuilt with ``compass ingest``.

History: 1 stored internal ids (``py::app.models::User``); 2 stores public ids
(``app/models.py::User``) and a ``qualified_name`` on classes and functions.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class IndexMetadata:
    """Facts recorded about an index at ingest time.

    Attributes:
        indexed_commit: Git HEAD commit at ingest, or ``None`` if unknown.
        indexed_at: Ingest time (timezone-aware).
        schema_version: Metadata/index schema version; pre-v1 files count as 1.
        grammar_versions: Installed grammar package version per language.

    Example:
        ``{"indexed_commit": "abc", "indexed_at": 1788431823, "grammar_versions":
        {"python": "0.25.0"}}`` loads as ``IndexMetadata(indexed_commit="abc",
        indexed_at=datetime(..., tzinfo=UTC), schema_version=2,
        grammar_versions={Language.PYTHON: "0.25.0"})``.
    """

    indexed_commit: str | None
    indexed_at: datetime
    schema_version: int
    grammar_versions: Mapping[Language, str]


def save_metadata(path: Path, meta: IndexMetadata) -> None:
    """Atomically write ``meta`` to ``path`` as JSON.

    Args:
        path: Destination ``metadata.json``; parent directories are created.
        meta: Metadata to store. ``indexed_at`` is stored as epoch seconds.
    """
    payload = {
        "schema_version": meta.schema_version,
        "indexed_commit": meta.indexed_commit,
        "indexed_at": int(meta.indexed_at.timestamp()),
        "grammar_versions": {lang.value: v for lang, v in meta.grammar_versions.items()},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def load_metadata(path: Path) -> IndexMetadata:
    """Read metadata from ``path``.

    Args:
        path: Path to ``metadata.json``.

    Returns:
        The parsed metadata. A missing ``schema_version`` counts as 1.

    Raises:
        IndexIncompatibleError: If the file is unreadable, malformed, has an unknown
            language, or its ``schema_version`` is not ``SCHEMA_VERSION``.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        schema_version = raw.get("schema_version", 1)
        if isinstance(schema_version, bool) or not isinstance(schema_version, int):
            raise ValueError(f"invalid schema_version {schema_version!r}")
        if schema_version != SCHEMA_VERSION:
            raise IndexIncompatibleError(
                f"The index at {path.parent} uses schema version {schema_version}; this "
                f"compass reads version {SCHEMA_VERSION}. Run `compass ingest` to rebuild it."
            )
        indexed_at = raw["indexed_at"]
        if isinstance(indexed_at, bool) or not isinstance(indexed_at, int | float):
            raise ValueError(f"invalid indexed_at {indexed_at!r}")
        commit = raw.get("indexed_commit")
        return IndexMetadata(
            indexed_commit=None if commit is None else str(commit),
            indexed_at=datetime.fromtimestamp(indexed_at, UTC),
            schema_version=schema_version,
            grammar_versions={
                Language(lang): str(v) for lang, v in raw.get("grammar_versions", {}).items()
            },
        )
    except (OSError, KeyError, ValueError, TypeError, AttributeError, OverflowError) as exc:
        # JSONDecodeError is a ValueError subclass.
        raise IndexIncompatibleError(f"Unreadable index metadata at {path}: {exc}") from exc
