# code-compass

A codebase intelligence engine that maps, indexes, and queries your code using graph databases and Tree-sitter parsing.

## Project Structure

```
code-compass/
├── pyproject.toml                ← uv workspace (every Python package below)
├── pnpm-workspace.yaml           ← pnpm workspace (every JavaScript app below)
├── Makefile
│
├── packages/                     ← Python
│   ├── core/                     ← compass_core: the engine (ingest, graph, index, query)
│   ├── server/                   ← compass_server: HTTP API (FastAPI) used by the web app
│   ├── cli/                      ← compass_cli: the `compass` command
│   └── mcp/                      ← compass_mcp: MCP server for coding agents
│
└── apps/                         ← JavaScript
    └── web/                      ← Next.js UI, talks to compass_server over HTTP
```

**Layout rule:** Python packages go in `packages/`, JavaScript apps go in `apps/`.

`compass_core` depends on none of the others. The CLI, the MCP server and the HTTP
server are adapters over it, and only the web app talks to the HTTP server:

```
            compass_core
           ▲      ▲      ▲
   compass_cli  compass_mcp  compass_server  ◄── HTTP ──  apps/web
```

## Getting Started

```bash
# Install Python dependencies
make install

# Install web dependencies
make install-web

# Ingest a repository (writes <repo>/.compass/)
compass ingest /path/to/repo

# Start the API server and the web UI
compass serve
```

## Querying from the command line

Run these anywhere inside an indexed repository (or pass `--repo PATH`). Output is compact
text with `file:line` first; add `--format json` for the typed result.

```bash
compass status                          # which index, built when, files changed since
compass search save                     # where is it? best matches first, and why
compass describe app/models.py::User    # location, docstring, callers, callees, members
compass impact decode_token --depth 2   # what may break if it changes, nearest first
compass overview                        # entry points, most imported / called / risky
```

Queries never modify the repository. Exit codes: `0` ok, `2` invalid argument,
`3` no such symbol (suggestions printed), `4` ambiguous (candidates printed), `5` no index,
`6` index busy, `7` index must be rebuilt (`compass ingest`), `8` query timed out.

## Use with coding agents (MCP)

```bash
compass ingest .        # index the repository
compass setup --mcp     # tell agents about it, and register the MCP server
```

`compass setup` keeps one managed section (between `<!-- compass:begin -->` and
`<!-- compass:end -->`) in `AGENTS.md` and `CLAUDE.md`, telling agents which question each
tool answers; text outside the section is never changed, and running it again only
refreshes the section. With `--mcp` it adds a `code-compass` server (`compass mcp`) to the
project's `.mcp.json`, which Claude Code picks up. For Codex, add to `~/.codex/config.toml`:

```toml
[mcp_servers.code-compass]
command = "compass"
args = ["mcp"]
```

The server exposes `status`, `search`, `describe`, `impact` and `overview`, the same
operations as the CLI. Every tool is read-only and returns compact text plus the typed
result as structured content. `compass setup --print` shows the agent guide without
writing anything.

## Development

```bash
# Python: tests, lint, types (the same checks CI runs)
uv sync --all-packages --all-groups
uv run pytest
uv run ruff check . && uv run ruff format --check .
(cd packages/core && uv run mypy) && (cd packages/server && uv run mypy) && (cd packages/mcp && uv run mypy) && (cd packages/cli && uv run mypy)

# Web: regenerate API types from the server's OpenAPI schema
make gen-api
```

## License

Apache-2.0
