# code-compass

A codebase intelligence engine that maps, indexes, and queries your code using graph databases, Tree-sitter parsing, and LLMs.

## Project Structure

```
code-compass/
├── pnpm-workspace.yaml
├── pyproject.toml
├── Makefile
│
├── apps/
│   ├── cli/                      ← `compass index`, `compass ui`
│   ├── mcp/                      ← Cursor/Claude Integration
│   └── web/                      ← React + Vite UI
│
└── packages/
    └── core/                     ← The Engine
```

## Getting Started

```bash
# Install Python dependencies
make install

# Install web dependencies
make install-web

# Index a repository
compass index /path/to/repo

# Launch the web UI
compass ui
```

## License

Apache-2.0
