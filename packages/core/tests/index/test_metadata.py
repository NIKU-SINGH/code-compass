import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from compass_core.errors import IndexIncompatibleError
from compass_core.index.metadata import IndexMetadata, load_metadata, save_metadata
from compass_core.query.types import Language


def test_round_trip(tmp_path: Path):
    meta = IndexMetadata(
        indexed_commit="abc",
        indexed_at=datetime(2026, 10, 10, tzinfo=UTC),
        schema_version=1,
        grammar_versions={Language.PYTHON: "0.25.0"},
    )
    path = tmp_path / "metadata.json"
    save_metadata(path, meta)
    assert load_metadata(path) == meta


def test_pre_v1_metadata_loads_with_defaults(tmp_path: Path):
    path = tmp_path / "metadata.json"
    path.write_text(
        json.dumps(
            {
                "indexed_commit": "x",
                "indexed_at": 1788431823,
                "grammar_versions": {"python": "0.25.0"},
            }
        )
    )
    meta = load_metadata(path)
    assert meta.schema_version == 1 and meta.indexed_at.tzinfo is not None


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
        schema_version=1,
        grammar_versions={},
    )

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("boom")

    monkeypatch.setattr("compass_core.index.metadata.os.replace", boom)
    with pytest.raises(OSError):
        save_metadata(path, meta)
    assert path.read_text() == "original"
    assert list(tmp_path.glob("*.tmp")) == []
