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
    ],
)
def test_bad_metadata_raises_incompatible(tmp_path: Path, raw: str):
    path = tmp_path / "metadata.json"
    path.write_text(raw)
    with pytest.raises(IndexIncompatibleError):
        load_metadata(path)
