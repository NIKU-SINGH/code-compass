"""Tests for compass_cli.types."""

from pathlib import Path

from compass_cli.types import IngestSummary


def test_ingest_summary_holds_all_fields():
    summary = IngestSummary(
        file_count=10,
        class_count=3,
        function_count=25,
        elapsed=1.5,
        node_count=100,
        edge_count=200,
        db_path=Path("graph.ladybug"),
        db_size=4096,
        skipped=1,
    )

    assert summary.file_count == 10
    assert summary.class_count == 3
    assert summary.function_count == 25
    assert summary.elapsed == 1.5
    assert summary.node_count == 100
    assert summary.edge_count == 200
    assert summary.db_path == Path("graph.ladybug")
    assert summary.db_size == 4096
    assert summary.skipped == 1
