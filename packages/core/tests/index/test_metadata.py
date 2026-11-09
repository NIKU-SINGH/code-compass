import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from compass_core.errors import IndexIncompatibleError
from compass_core.index.metadata import (
    SCHEMA_VERSION,
    IndexMetadata,
    load_metadata,
    save_metadata,
)
from compass_core.shared_types import Language


def test_round_trip(tmp_path: Path):
    meta = IndexMetadata(
        indexed_commit="abc",
        indexed_at=datetime(2026, 10, 10, tzinfo=UTC),
        schema_version=SCHEMA_VERSION,
        grammar_versions={Language.PYTHON: "0.25.0"},
    )
    path = tmp_path / "metadata.json"
    save_metadata(path, meta)
    assert load_metadata(path) == meta


@pytest.mark.parametrize("version", [None, 1])
def test_older_schema_is_rejected_with_reingest_hint(tmp_path: Path, version: int | None):
    raw: dict[str, object] = {
        "indexed_commit": "x",
        "indexed_at": 1788431823,
        "grammar_versions": {"python": "0.25.0"},
    }
    if version is not None:
        raw["schema_version"] = version
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(IndexIncompatibleError, match="compass ingest"):
        load_metadata(path)


@pytest.mark.parametrize(
    "raw",
    [
        "{not json",
        json.dumps({"schema_version": 99}),
        json.dumps({"indexed_at": 1, "grammar_versions": {"cobol": "1"}}),
        json.dumps({"grammar_versions": {}}),
        json.dumps({"indexed_at": "yesterday"}),
        json.dumps([1, 2]),
        json.dumps({"indexed_at": 1e20}),
        '{"indexed_at": Infinity}',
        json.dumps({"indexed_at": 1, "schema_version": 0}),
        json.dumps({"indexed_at": True}),
    ],
)
def test_bad_metadata_raises_incompatible(tmp_path: Path, raw: str):
    path = tmp_path / "metadata.json"
    path.write_text(raw)
    with pytest.raises(IndexIncompatibleError):
        load_metadata(path)


def test_missing_file_raises_incompatible(tmp_path: Path):
    with pytest.raises(IndexIncompatibleError):
        load_metadata(tmp_path / "nope.json")


def test_failed_save_cleans_tmp_and_keeps_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "metadata.json"
    path.write_text("original")
    meta = IndexMetadata(
        indexed_commit=None,
        indexed_at=datetime(2026, 10, 10, tzinfo=UTC),
        schema_version=SCHEMA_VERSION,
        grammar_versions={},
    )

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("boom")

    monkeypatch.setattr("compass_core.index.metadata.os.replace", boom)
    with pytest.raises(OSError):
        save_metadata(path, meta)
    assert path.read_text() == "original"
    assert list(tmp_path.glob("*.tmp")) == []
