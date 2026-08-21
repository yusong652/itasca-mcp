# CLAUDE.md

Guidance for coding agents working in the `itasca-mcp` repository.

## Project Overview

`itasca-mcp` provides an MCP server for ITASCA PFC workflows. The bridge runtime that runs inside PFC GUI lives in the [`itasca-mcp-bridge`](https://github.com/yusong652/itasca-mcp-bridge) repo and is consumed here as a git submodule.

This repository has two runtime contexts:

- `src/itasca_mcp/` (Python >= 3.10): MCP server package used by clients/tooling
- `itasca-mcp-bridge/` (submodule, PFC embedded Python often 3.6): HTTP bridge running inside PFC GUI

Treat these as separate deployment targets. End users get the bridge from PyPI (`pip install itasca-mcp-bridge`): first install happens via the agentic bootstrap's terminal pip step or `addon.py`, and from then on `itasca_mcp_bridge.start()` self-upgrades on every start. The submodule exists only so contributors can edit bridge code alongside MCP code without two clones.

The legacy `pfc-mcp-bridge` PyPI package (last release `bridge-v0.3.3`) is deprecated and no longer maintained — its code lived in `pfc-mcp-bridge/` here and was removed when the submodule replaced it.

## Core Architecture

### MCP side (`src/itasca_mcp`)

- Exposes documentation tools and execution tools through FastMCP
- Communicates with bridge via HTTP client (`itasca_mcp.bridge.client`)
- Returns a unified tool envelope: `ok`, `data`, `error`
- Dual execution model: synchronous REPL (`itasca_execute_code`) for quick queries, script-first async (`itasca_execute_task` + `itasca_check_task_status`) for long-running simulations

### Bridge side (`itasca-mcp-bridge` submodule)

- Runs in PFC GUI process
- Owns thread-safe interaction with ITASCA SDK
- Handles long-running tasks and diagnostics
- Started inside PFC GUI via `itasca_mcp_bridge.start()`, which self-upgrades from PyPI first (best-effort); `addon.py` remains the manual first-install bootstrap
- The submodule pin in this repo controls which bridge revision contributors develop against; runtime users always get whatever is on PyPI

## Repository Layout

```text
itasca-mcp/
├── src/itasca_mcp/
│   ├── bridge/          # MCP-side bridge client/task manager
│   ├── knowledge/       # command/API/reference search system
│   ├── tools/           # MCP tool implementations
│   ├── formatting.py    # shared response formatting
│   └── server.py        # MCP server entrypoint
├── itasca-mcp-bridge/   # submodule → github.com/yusong652/itasca-mcp-bridge
├── addon.py             # PFC-side first-install bootstrap (pip-installs the bridge)
└── tests/               # MCP/tool contract tests
```

**Submodule workflow** (mirrors flac-mcp):

- Fresh clone needs `git clone --recurse-submodules <url>` or, after a non-recursive clone, `git submodule update --init --recursive`
- After `git pull` on this repo, re-sync with `git submodule update --recursive` if the pin moved
- To bump the bridge pin: `cd itasca-mcp-bridge`, fetch/checkout the new commit, then commit the gitlink update in this repo. Push order: bridge repo first (so the pinned commit exists on its origin), itasca-mcp second
- "Modified content" / "untracked content" in `git status` for the submodule is normal during local bridge dev — only commit the gitlink when you actually want to bump the pin

## Development Commands

Run from repository root.

```bash
uv sync
uv sync --group dev
uv run itasca-mcp
uv run pytest tests/test_phase2_tools.py
uv run pytest tests/test_tool_contracts.py
```

## Engineering Rules

1. Keep MCP and bridge concerns separate.
   - Do not couple MCP logic to PFC GUI internals.
   - Do not introduce application/session policy into bridge runtime.

2. Preserve execution semantics for each model.
   - `itasca_execute_code` runs synchronous snippets and returns stdout/result immediately.
   - `itasca_execute_task` submits scripts and returns quickly.
   - Progress/result retrieval goes through `itasca_check_task_status`.

3. Maintain structured tool contracts.
   - Prefer stable machine-readable keys over ad-hoc text parsing.
   - Use the unified envelope for all tool business payloads:
     - success: `{"ok": true, "data": ...}`
     - error: `{"ok": false, "error": {"code": str, "message": str, "details"?: object}}`
   - Enforce coherence: `ok=true` must not include `error`; `ok=false` must include `error`.
   - Do not require duplicate presentation fields (for example, `display`) when they mirror structured data.
   - Let clients render human-facing formatting from structured fields.
   - Documentation tools must keep `data` consistent as:
     - `source`: `"commands" | "python_api" | "reference"`
     - `action`: `"browse" | "query"`
     - `entries`: `list[object]`
     - `summary`: `object` (counts/hints/context)
   - Keep query/path/input echo minimal; prefer putting necessary context in `summary` or `error.details.input`.

4. Keep compatibility when practical.
   - If moving shared helpers, keep thin compatibility re-exports when tests or downstream code rely on old import paths.

5. Respect runtime constraints.
   - MCP package talks to the bridge over HTTP (`httpx`).
   - Bridge side is stdlib-only (HTTP + SSE via `http.server`): no third-party
     runtime dependency, so it installs into any ITASCA embedded Python (3.6+)
     with no version pins.

6. Judge each dependency by the complexity it carries, not by a blanket
   "fewer deps is better" rule. The two runtime contexts land on opposite
   answers for the same reason, not different ones:
   - Keep a dependency when it owns hard correctness you would not write
     better yourself. On the MCP side, FastMCP + Pydantic own tool-schema
     declaration, JSON Schema generation, input validation, and alignment
     with the MCP protocol — protocol-boundary complexity. Do not reimplement
     it; do not drop these deps to chase minimalism.
   - Drop a dependency when it is not carrying real complexity for your
     semantics. The bridge transport is self-hosted on stdlib HTTP + SSE
     because the interaction is just request → execute → result, with the
     server->client push reduced to a payload-free doorbell — a transport
     library's extra machinery (duplex/heartbeat/version negotiation) is not
     load-bearing here, and a pinned dependency is itself a liability in the
     engine's embedded Python.
   - The rule of thumb: validation at the protocol boundary is outsourced;
     the execution transport is self-hosted when the semantics are simple
     enough to not need a library. Minimalism is a consequence of this test,
     never the goal itself.

## Testing Expectations

- For tool/contract changes, run:
  - `tests/test_phase2_tools.py`
  - `tests/test_tool_contracts.py`
Mock bridge based tests are preferred for deterministic CI.

## Documentation Sources

PFC searchable docs live under:

- `src/itasca_mcp/knowledge/resources/command_docs/`
- `src/itasca_mcp/knowledge/resources/python_sdk_docs/`
- `src/itasca_mcp/knowledge/resources/references/`

When changing schema/content shape, verify browse/query tool behavior remains consistent.

## Release Process

`itasca-mcp` is published to PyPI via GitHub Actions, triggered by pushing a `v*` tag (e.g. `v0.3.16`). Version source: `src/itasca_mcp/__init__.py` (hatch dynamic versioning).

Steps to release `itasca-mcp`:

1. Bump `__version__` in `src/itasca_mcp/__init__.py` (the single source of truth).
2. Curate `## [Unreleased]` in `CHANGELOG.md` from `git log` since the previous release (grouped per the convention comment at the top of that file), rename it to `## [x.y.z] - YYYY-MM-DD`, then start a fresh empty `## [Unreleased]`. The publish workflow extracts the section whose header matches the tag version exactly and fails if it is missing.
3. **Sweep user-facing docs for claims the release invalidates** — `README.md` (supported engines/versions matrix, feature bullets, install flow) and `addon.py` messages. README is the PyPI long_description: anything stale at tag time is frozen into that PyPI release page and can only be fixed by the *next* release, so this check must happen BEFORE tagging, in the same release PR.
4. Commit and push to `main`.
5. Tag the commit: `git tag v0.x.x` and `git push origin v0.x.x`.

**Important**: tag version must match `__version__`. PyPI rejects duplicate version uploads.

CI runs on every push/PR to `main`: ruff check, ruff format, mypy, pytest with coverage.

**Bridge releases live in the [`itasca-mcp-bridge`](https://github.com/yusong652/itasca-mcp-bridge) repo** — not here. Bumping the bridge pin (gitlink) in this repo doesn't trigger a bridge release; it only affects what contributors see locally. End users always get whatever's on PyPI via `pip install itasca-mcp-bridge`.

The legacy `pfc-mcp-bridge` PyPI package is **frozen at `0.3.3`** (deprecation release). No future releases from this repo.

## Commit Style

Use conventional prefixes seen in repository history, for example:

- `feat: ...`
- `fix: ...`
- `refactor: ...`
- `test: ...`
- `docs: ...`

Keep commit messages focused on why the change was needed.

Documentation is first-class for this project -- agents rely on the docs and
the agentic install guides to understand and operate itasca-mcp, so notable
documentation/install-flow changes belong in the changelog alongside
behaviour changes.

Contributors only need a clear conventional commit message; they do NOT
edit `CHANGELOG.md`. The maintainer curates the `## [Unreleased]` section
from commit history at release time (see Release Process and the convention
comment at the top of `CHANGELOG.md`). This keeps the changelog complete
without putting changelog friction on any single change or PR.
