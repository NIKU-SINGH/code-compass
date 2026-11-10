"""``compass mcp`` speaks MCP over stdio, as Claude Code or Codex would run it."""

from __future__ import annotations

import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from compass_core.index.locate import IndexLocation


async def test_a_client_can_list_and_call_tools_over_stdio(fixture_index: IndexLocation) -> None:
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "compass_cli.main", "mcp", "--repo", str(fixture_index.repo_root)],
    )
    async with stdio_client(server) as (read, write), ClientSession(read, write) as session:
        init = await session.initialize()
        assert init.serverInfo.name == "code-compass"
        assert init.instructions and "compass ingest" in init.instructions
        tools = {tool.name for tool in (await session.list_tools()).tools}
        assert tools == {"status", "search", "describe", "impact", "overview"}

        result = await session.call_tool("impact", {"ref": "decode_token", "depth": 2})
        assert result.isError is False
        block = result.content[0]
        assert isinstance(block, TextContent)
        assert "app/scheduler.py:4  function  app.scheduler.tick  calls nightly" in block.text
        assert result.structuredContent is not None
        assert result.structuredContent["operation"] == "IMPACT"
