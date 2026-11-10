# Code Compass

**A local-first code knowledge graph for coding agents and the people working with them.
Ask where something is defined, who calls it, and what may break if it changes, over MCP,
from the CLI, or in a 3D web view.**

Code Compass parses a repository with [Tree-sitter](https://tree-sitter.github.io/) into a
knowledge graph: files, classes, functions and methods are nodes, and the calls, imports
and inheritance between them are edges, each call with a confidence. The graph lives in an
embedded graph database ([LadybugDB](https://pypi.org/project/real-ladybug/)) inside the
repository's `.compass/` folder. Agents (Claude Code, Codex, Cursor) query it through an
MCP server, you query it with the `compass` CLI, and a web UI draws it in 3D.

**Local-first:** parsing is deterministic (an AST, not a language model), so there are no
API keys, no embeddings or vector store, and no network calls. Your code never leaves your
machine.

**Why:** grep finds text; it does not know that `save` on line 6 overrides `Base.save`, or
that changing `decode_token` reaches `handle` and then `nightly`. Code Compass answers those
questions in a few compact lines, each with a 1-indexed `file:line`, so an agent reads the
right code first instead of opening files one by one.

> **Status: alpha.** Python repositories only. Call resolution is partial: calls through
> imports, module attributes, re-exports and inherited methods are linked; constructor
> calls, calls on typed variables and dynamic dispatch are not yet. Every answer says so
> (lines starting with `!`), and an empty list never means "no callers".

## What you can ask

| Question | CLI | MCP tool |
|---|---|---|
| Where is `X` defined? | `compass search X` | `search` |
| What is `X`, who calls it, what does it call? | `compass describe X` | `describe` |
| What may break if I change `X` (a symbol or a file)? | `compass impact X` | `impact` |
| What are the entry points and hot spots of this repo? | `compass overview` | `overview` |
| Is the index there and up to date? | `compass status` | `status` |

## Install

Requires Python 3.11+. Install the `compass` command with [uv](https://docs.astral.sh/uv/)
or [pipx](https://pipx.pypa.io/):

```bash
uv tool install compass-code      # or: pipx install compass-code
```

Until the first release reaches PyPI, install from a clone instead:

```bash
git clone https://github.com/NIKU-SINGH/code-compass.git
cd code-compass
uv tool install ./packages/cli
```

Either way `compass` ends up on your `PATH` (run `uv tool update-shell` once if it is not).
To work on Code Compass itself, see [Development](#development); releases are described in
[docs/RELEASING.md](docs/RELEASING.md).

## Quick start

```bash
cd /path/to/your/repo
compass ingest .          # build the index in .compass/ (re-run after code changes)
compass overview          # entry points, most imported / called / risky
compass search save       # where is it? best matches first, and why
compass setup --mcp       # let coding agents in this repo use it
```

Add `.compass/` to the repository's `.gitignore`; the index is local to each checkout.

## Querying from the command line

Run these anywhere inside an indexed repository (or pass `--repo PATH`). In a terminal the
answer is laid out as panels and tables; piped (a script, or a coding agent running
`compass` in a shell) it is compact text, one line per item with `file:line` first. Add
`--format json` for the typed result. `compass help` lists every command.

```bash
compass status                          # which index, built when, files changed since
compass search save                     # where is it? best matches first, and why
compass describe app/models.py::User    # location, docstring, callers, callees, members
compass impact decode_token --depth 2   # what may break if it changes, nearest first
compass overview                        # entry points, most imported / called / risky
```

A reference can be a symbol id (`app/models.py::User.save`), a file path, a qualified name
(`app.models.User.save`) or a bare name. A bare name that matches several symbols prints
the candidates' ids; pass one back.

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
writing anything. `compass` must be on the `PATH` the agent starts the server with.

## Web UI

```bash
compass serve           # the API and the UI on http://127.0.0.1:8000, opened in a browser
```

The UI draws the whole graph in 3D and lets you search and open any node. The released
package serves a prebuilt copy of the UI from the API's own port. In a source checkout
without that copy (`make web-static` builds it), `compass serve` runs the Next.js dev
server on http://localhost:3000 instead, which needs pnpm and `make install-web`; `--dev`
forces that mode and `--no-frontend` starts only the API.

## How it works

`compass ingest` runs a pipeline over the repository:

1. **Discover** source files, skipping what `.gitignore` and `.compassignore` exclude.
2. **Parse** each file with Tree-sitter into files, classes, functions and methods, with
   their 1-indexed line ranges, signatures and docstrings.
3. **Resolve** imports, inheritance and calls to the symbols they reach; a call that
   reaches a library becomes an external call, and one that cannot be resolved is counted.
4. **Write** the graph to `.compass/graph.ladybug`, with `.compass/metadata.json` recording
   the commit and time it was built.

Every query opens that graph read-only and first checks which indexed files were modified
since the build, so an answer from a stale index says how many changed. Set
`LADYBUG_DB_PATH` to use an index stored elsewhere.

## Project structure

```
code-compass/
├── pyproject.toml                ← uv workspace (every Python package below)
├── pnpm-workspace.yaml           ← pnpm workspace (every JavaScript app below)
├── Makefile
│
├── packages/                     ← Python
│   ├── core/                     ← compass_core: the engine (ingest, graph, index, query)
│   ├── server/                   ← compass_server: HTTP API (FastAPI) and the bundled web UI
│   ├── cli/                      ← compass_cli: the `compass` command
│   └── mcp/                      ← compass_mcp: MCP server for coding agents
│
├── scripts/                      ← release tooling: version check/bump, wheel smoke test
│
└── apps/                         ← JavaScript
    └── web/                      ← Next.js UI, talks to compass_server over HTTP
```

**Layout rule:** Python packages go in `packages/`, JavaScript apps go in `apps/`.
They are published together as one PyPI package, `compass-code`, whose wheel bundles all
four (see [docs/RELEASING.md](docs/RELEASING.md)).

`compass_core` depends on none of the others. The CLI, the MCP server and the HTTP
server are adapters over it, and only the web app talks to the HTTP server:

```
            compass_core
           ▲      ▲      ▲
   compass_cli  compass_mcp  compass_server  ◄── HTTP ──  apps/web
```

## Development

```bash
# Python: install everything, then the same checks CI runs
uv sync --all-packages --all-groups
uv run compass --help
uv run pytest
uv run ruff check . && uv run ruff format --check .
(cd packages/core && uv run mypy) && (cd packages/server && uv run mypy) && (cd packages/mcp && uv run mypy) && (cd packages/cli && uv run mypy)

# Web: install, type-check, test, and regenerate API types from the server's schema
make install-web
(cd apps/web && pnpm exec tsc --noEmit && pnpm test)
make gen-api
```

Coding agents working in this repository follow [AGENTS.md](AGENTS.md).

## License

Apache-2.0
