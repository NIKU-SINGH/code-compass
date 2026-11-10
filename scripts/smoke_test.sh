#!/usr/bin/env bash
# Install the built wheel into a fresh environment, the way a user would, and run every
# command once against the sample repository. Catches what the workspace tests cannot:
# missing files in a wheel, wrong dependency bounds, a UI that was not bundled.
#
# Usage: scripts/smoke_test.sh DIST_DIR [PYTHON_VERSION]
set -euo pipefail

dist=$(cd "$1" && pwd)
python=${2:-3.11}
root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'kill "${server_pid:-}" 2>/dev/null || true; rm -rf "$work"' EXIT

uv venv --quiet --python "$python" "$work/venv"
# compass-code comes from DIST_DIR only; its dependencies from PyPI.
VIRTUAL_ENV="$work/venv" uv pip install --quiet "$dist"/compass_code-*.whl
compass="$work/venv/bin/compass"
[ -x "$compass" ] || compass="$work/venv/Scripts/compass.exe"

cp -r "$root/packages/core/tests/fixtures/sample_repo" "$work/repo"
cd "$work/repo"

"$compass" --version
"$compass" ingest . > /dev/null
"$compass" status
"$compass" search save
"$compass" describe app/models.py::User.save > /dev/null
"$compass" impact decode_token > /dev/null
"$compass" overview --format json > /dev/null

# The MCP server answers an initialize request and lists its tools.
"$work/venv/bin/python" - "$compass" <<'PY'
import asyncio, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main() -> None:
    params = StdioServerParameters(command=sys.argv[1], args=["mcp"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = sorted(tool.name for tool in (await session.list_tools()).tools)
        assert tools == ["describe", "impact", "overview", "search", "status"], tools
        print("mcp tools:", ", ".join(tools))

asyncio.run(main())
PY

# The installed server serves the bundled UI and the API on one port.
port=8765
"$work/venv/bin/python" -m uvicorn compass_server.main:app --port "$port" > "$work/server.log" 2>&1 &
server_pid=$!
for _ in $(seq 1 40); do
  curl -fs "http://127.0.0.1:$port/health" > /dev/null && break
  sleep 0.25
done
curl -fs "http://127.0.0.1:$port/health" || { echo "server did not start:"; cat "$work/server.log"; exit 1; }
echo
curl -fs "http://127.0.0.1:$port/" | grep -q "<html" && echo "web UI served"
curl -fs "http://127.0.0.1:$port/api/status" > /dev/null && echo "API served"
echo "smoke test passed"
