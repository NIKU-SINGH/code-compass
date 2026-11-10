# Code Compass

**A local-first code knowledge graph for AI coding agents.** Code Compass parses your
repository with Tree-sitter into a graph of files, classes, functions and the calls,
imports and inheritance between them, and answers structural questions from it: where
something is defined, who calls it, and what may break if it changes. Coding agents
(Claude Code, Codex, Cursor) ask over MCP; you ask with the `compass` command or in a 3D
web view. Parsing is deterministic and nothing leaves your machine: no API keys, no
embeddings, no network calls.

> **Alpha.** Python repositories only; call resolution is partial, and every answer says
> where it may be incomplete.

## Install

```bash
uv tool install compass-code      # or: pipx install compass-code
```

## Use

```bash
cd your-repo
compass ingest .                  # build the graph in .compass/
compass overview                  # entry points and hot spots
compass search save               # where is it defined?
compass describe app/models.py::User
compass impact decode_token       # what may break if it changes?
compass serve                     # explore the graph in the browser
compass setup --mcp               # let coding agents in this repo use it
```

For Codex, add to `~/.codex/config.toml`:

```toml
[mcp_servers.code-compass]
command = "compass"
args = ["mcp"]
```

Documentation, source and issues: https://github.com/NIKU-SINGH/code-compass
