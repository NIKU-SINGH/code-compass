"""The MCP tools: read-only, typed inputs, and text plus structured JSON in every answer."""

from __future__ import annotations

from pathlib import Path

import pytest
from mcp.types import CallToolResult, TextContent

from compass_core.contract.params import MAX_DEPTH, MAX_LIMIT
from compass_core.index.locate import IndexLocation
from compass_mcp.server import EVIDENCE_NOTE, build_server

TOOLS = {"status", "search", "describe", "impact", "overview"}


async def _call(repo: Path, tool: str, **arguments: object) -> CallToolResult:
    result = await build_server(repo).call_tool(tool, arguments)
    assert isinstance(result, CallToolResult)
    return result


def _text(result: CallToolResult) -> str:
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


async def test_tools_are_listed_read_only_with_bounded_inputs(fixture_index: IndexLocation) -> None:
    tools = {t.name: t for t in await build_server(fixture_index.repo_root).list_tools()}
    assert set(tools) == TOOLS
    for tool in tools.values():
        assert tool.annotations is not None and tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert tool.description and len(tool.description) > 40
    impact = tools["impact"].inputSchema["properties"]
    assert impact["depth"]["maximum"] == MAX_DEPTH
    assert tools["search"].inputSchema["properties"]["limit"]["maximum"] == MAX_LIMIT
    assert tools["impact"].inputSchema["required"] == ["ref"]


async def test_search_returns_text_and_structured_result(fixture_index: IndexLocation) -> None:
    result = await _call(fixture_index.repo_root, "search", text="save")
    assert result.isError is False
    assert "app/models.py:2  method  app.models.Base.save  exact name · 1 caller" in _text(result)
    assert result.structuredContent is not None
    assert result.structuredContent["operation"] == "FIND"
    assert len(result.structuredContent["hits"]) == 2


async def test_describe_marks_repository_text_as_evidence(fixture_index: IndexLocation) -> None:
    result = await _call(fixture_index.repo_root, "describe", ref="app/models.py::User.save")
    assert result.isError is False
    text = _text(result)
    assert text.startswith(EVIDENCE_NOTE)
    assert "id: app/models.py::User.save" in text and "source:" not in text
    with_source = await _call(
        fixture_index.repo_root, "describe", ref="app/models.py::User.save", include_source=True
    )
    assert "source:" in _text(with_source)


async def test_impact_and_overview(fixture_index: IndexLocation) -> None:
    impact = await _call(fixture_index.repo_root, "impact", ref="decode_token", depth=1)
    assert impact.isError is False and "distance 1" in _text(impact)
    assert impact.structuredContent is not None and impact.structuredContent["total"] == 3
    overview = await _call(fixture_index.repo_root, "overview")
    assert "8 files · 3 classes · 11 functions" in _text(overview)


async def test_ambiguous_reference_is_an_answer_not_an_error(fixture_index: IndexLocation) -> None:
    result = await _call(fixture_index.repo_root, "describe", ref="save")
    assert result.isError is False
    assert "app/models.py::Base.save" in _text(result)
    assert result.structuredContent is not None
    assert result.structuredContent["outcome"] == "ambiguous"


async def test_missing_index_is_an_error_saying_how_to_fix_it(tmp_path: Path) -> None:
    result = await _call(tmp_path, "status")
    assert result.isError is True
    assert _text(result).startswith("error [INDEX_NOT_FOUND]") and "compass ingest" in _text(result)
    assert result.structuredContent is not None
    assert result.structuredContent["code"] == "INDEX_NOT_FOUND"


async def test_out_of_range_arguments_are_rejected(fixture_index: IndexLocation) -> None:
    with pytest.raises(Exception, match="depth"):
        await build_server(fixture_index.repo_root).call_tool(
            "impact", {"ref": "decode_token", "depth": MAX_DEPTH + 1}
        )
