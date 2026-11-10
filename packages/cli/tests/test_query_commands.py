"""The query commands print compact text or JSON and exit with the contract's codes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from compass_cli.main import app
from compass_core.index.locate import IndexLocation

runner = CliRunner()


def _run(*args: str) -> tuple[int, str, str]:
    result = runner.invoke(app, list(args))
    return result.exit_code, result.stdout, result.stderr


@pytest.fixture
def repo(fixture_index: IndexLocation) -> str:
    return str(fixture_index.repo_root)


def test_status_prints_the_index_header(repo: str) -> None:
    code, out, _ = _run("status", "--repo", repo)
    assert code == 0
    assert out.startswith("index: ") and out.strip().endswith("up to date")


def test_search_text_and_json(repo: str) -> None:
    code, out, _ = _run("search", "save", "--repo", repo)
    assert code == 0
    assert "app/models.py:2  method  app.models.Base.save  exact name · 1 caller" in out

    code, out, _ = _run("search", "save", "--kind", "method", "--format", "json", "--repo", repo)
    assert code == 0
    body = json.loads(out)
    assert body["operation"] == "FIND"
    assert [h["symbol"]["id"] for h in body["hits"]] == [
        "app/models.py::Base.save",
        "app/models.py::User.save",
    ]


def test_search_limit_is_respected(repo: str) -> None:
    code, out, _ = _run("search", "a", "--limit", "1", "--format", "json", "--repo", repo)
    body = json.loads(out)
    assert code == 0 and len(body["hits"]) == 1 and body["truncated"] is True


def test_describe_and_source_flag(repo: str) -> None:
    code, out, _ = _run("describe", "app/models.py::User.save", "--repo", repo)
    assert code == 0
    assert "id: app/models.py::User.save" in out and "callees (1):" in out
    assert "source:" not in out
    _, with_source, _ = _run("describe", "app/models.py::User.save", "--source", "--repo", repo)
    assert "source:" in with_source


def test_impact_respects_depth(repo: str) -> None:
    code, out, _ = _run("impact", "decode_token", "--depth", "1", "--repo", repo)
    assert code == 0
    assert "distance 1" in out and "distance 2" not in out


def test_overview(repo: str) -> None:
    code, out, _ = _run("overview", "--repo", repo)
    assert code == 0 and "8 files · 3 classes · 11 functions" in out


def test_ambiguous_reference_lists_candidates_and_exits_4(repo: str) -> None:
    code, out, _ = _run("describe", "save", "--repo", repo)
    assert code == 4
    assert "app/models.py::Base.save" in out and "app/models.py::User.save" in out
    code, out, _ = _run("impact", "save", "--format", "json", "--repo", repo)
    assert code == 4 and json.loads(out)["outcome"] == "ambiguous"


def test_unknown_reference_suggests_names_and_exits_3(repo: str) -> None:
    code, out, _ = _run("describe", "decode_tokn", "--repo", repo)
    assert code == 3 and out.startswith('no symbol matches "decode_tokn"')


def test_missing_index_is_an_error_on_stderr_with_exit_5(tmp_path: Path) -> None:
    code, out, err = _run("search", "x", "--repo", str(tmp_path))
    assert code == 5 and out == ""
    assert err.startswith("error [INDEX_NOT_FOUND]") and "compass ingest" in err
    code, _, err = _run("status", "--format", "json", "--repo", str(tmp_path))
    assert code == 5 and json.loads(err)["code"] == "INDEX_NOT_FOUND"


def test_index_from_an_older_compass_exits_7(fixture_index: IndexLocation, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(fixture_index.repo_root, repo)
    (repo / ".compass" / "metadata.json").write_text(json.dumps({"indexed_at": 1}))
    code, _, err = _run("search", "x", "--repo", str(repo))
    assert code == 7 and "compass ingest" in err


def test_out_of_range_options_are_usage_errors(repo: str) -> None:
    assert _run("impact", "decode_token", "--depth", "99", "--repo", repo)[0] == 2
    assert _run("search", "x", "--limit", "0", "--repo", repo)[0] == 2
