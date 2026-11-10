# AGENTS.md

Rules for every coding agent working in this repo. They are not optional.
If a rule blocks you, stop and ask; do not work around it.

## 1. Search before you create
- Before adding a type, enum, constant, helper, hook or component, search the repo for an
  existing one. If it exists, use it or extend it. Never add a near-copy.
- Anything used in two or more places lives in its shared home (section 2), not in either caller.
  Code used by one feature stays next to that feature.

## 2. One home for each kind of thing

| What | Python | Web (`apps/web/src`) |
|---|---|---|
| Graph vocabulary used by parsing, ingest *and* queries (`SymbolKind`, `EdgeType`, `CallType`, `Language`) | `compass_core/shared_types.py` | from the generated API types |
| Query inputs, results, ids and query-only enums | `compass_core/contract/` | `@/lib/api` (wraps generated `lib/api-types.ts`) |
| Cypher and DB-row parsing | `compass_core/query/` only: every statement is a module-level `Query` (`query/cypher.py`) holding its full Cypher next to its row decoder; column lists and decoders in `query/rows.py` | n/a |
| Settings / env vars | `compass_core/settings.py`, `compass_server/settings.py` | n/a |
| Limits, bounds, named constants | `contract/params.py`, or a module-level `UPPER_CASE` constant | `lib/limits.ts` or another `lib/` module |
| Shared UI components | n/a | `components/ui/` (shadcn) |
| Shared non-UI helpers (formatting, labels) | the owning module | `lib/` |
| Feature-only code | next to the feature | `components/<feature>/` |

## 3. Layering (enforced by `tests/test_architecture.py`; fix the code, never the test)
- `packages/` is Python, `apps/` is JavaScript.
- `compass_core` never imports `compass_cli`, `compass_mcp`, `compass_server` or a web framework.
- `compass_core.contract` imports only itself, `shared_types` and `errors`.
- Adapters (CLI, MCP, server) are thin: parse input, call one `compass_core.query` function,
  render its `contract` result. No Cypher and no business logic in adapters.
- The CLI and MCP server call `compass_core` directly. Only the web app talks to
  `compass_server` over HTTP.

## 4. Type safety: Python
- `mypy --strict` must pass. No `Any`, bare `dict`/`list`, `dict[str, Any]` or untyped `def`
  in any public signature. `Any` is allowed only in `graph/db.py` and `query/rows.py`.
- A closed set of values is a `StrEnum`, never strings compared by hand. Ids are `NewType`s
  (`SymbolId`, `RepoPath`, `QualifiedName`).
- Models are `@dataclass(frozen=True, slots=True, kw_only=True)` with `tuple` fields and checks in
  `__post_init__`. No Pydantic, DB or I/O in models; Pydantic only in `contract/serialize.py`
  and settings.
- Expected outcomes (not found, ambiguous) are returned values. Environment failures raise a
  `QueryError` subclass. Never raise bare `Exception`/`RuntimeError`.
- No `# type: ignore` without an error code and a reason on the same line.

## 5. Type safety: TypeScript
- API types are generated (`make gen-api` writes `lib/api-types.ts`). Never edit that file and
  never hand-write a type that mirrors an API shape; derive it instead
  (`SymbolRef["kind"]`, `Pick<SymbolRef, "id" | "name">`).
- No `any`, no `as` casts to silence errors, no `string` where a union exists
  (`kind: SymbolKind`, not `kind: string`).
- Lookup tables over a union are `Record<Union, ...>`, and `switch`es end in an exhaustive check,
  so a new value is a compile error until every place handles it.

## 6. No magic values
- No meaningful literal inside logic: limits, depths, ports, timeouts, labels, colours.
  Name it once in its home (section 2) and import it.
- Values the backend owns (limits, enums) reach the web app through the API schema; do not
  copy them by hand.
- Colours come from theme tokens / CSS variables only. No hex values, no arbitrary Tailwind values.

## 7. Components (web)
- Use shadcn/ui; do not hand-roll a component shadcn has. Icons come from `lucide-react`.
- Components get data and callbacks through props. Only UI state (open, hover, focus) is local.
- No hardcoded user-facing text or behaviour that could reasonably vary; take it as a prop.
- Every clickable element has `cursor-pointer`.

## 8. Files and naming
- Max 500 lines per file; split by responsibility.
- Name files by what they do, without repeating the folder name
  (`graph/NodeModal.tsx`, not `graph/GraphModal.tsx`). No logic in `index.ts` / `__init__.py`.
- Python docstrings use Google style with `Args`, `Returns`, `Raises`, `Attributes` and an
  `Example`. Field docs go in the docstring, not inline comments. Line numbers are 1-indexed.

## 9. Definition of done
Run these and make them pass. Never skip, disable or loosen a test, lint rule or type check
to get green:
- `uv run pytest`
- `uv run ruff check . && uv run ruff format --check .`
- `cd packages/core && uv run mypy`, `cd packages/server && uv run mypy`,
  `cd packages/mcp && uv run mypy` and `cd packages/cli && uv run mypy`
- Web: `pnpm exec tsc --noEmit` and `pnpm build` in `apps/web`
- If an API shape changed: `make gen-api` and commit the regenerated `lib/api-types.ts`
