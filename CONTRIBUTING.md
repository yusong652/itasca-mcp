# Contributing to itasca-mcp

English | [简体中文](CONTRIBUTING.zh-CN.md)

Thanks for taking the time. Issues, corpus fixes, and code PRs are all welcome —
this guide exists so you do not have to reverse-engineer the conventions first.

## Which repository

This project spans two runtime targets that ship separately:

| Change | Repository |
| --- | --- |
| MCP server, tools, documentation corpus | this repo (`itasca-mcp`, Python >= 3.10) |
| Bridge that runs inside the Itasca GUI | [`itasca-mcp-bridge`](https://github.com/yusong652/itasca-mcp-bridge) |

The bridge is vendored here as a git submodule so you can edit both from one
checkout, but a bridge change has to be opened as a PR on the bridge repo — a
submodule pointer bump in this repo does not release anything.

## Where contributions land best

The documentation corpus is the most self-contained place to help, and the one
where domain knowledge matters more than familiarity with the codebase. If you
use PFC, FLAC, 3DEC, MPoint, or MassFlow and notice the agent being fed a
command that does not exist in your version — that is a corpus fix, and you are
better placed to make it than anyone reading the vendor docs.

## The documentation corpus

### Layout

```text
src/itasca_mcp/knowledge/resources/
├── _common/{command_docs,python_sdk_docs}/     # Itasca 9.0 unified-kernel docs, shared
└── <software>/                                 # pfc | flac | 3dec | mpoint | massflow
    ├── command_docs/index.json + commands/<category>/<name>.json
    ├── python_sdk_docs/index.json + modules/<module>/
    └── references/index.json + <family>/       # contact-models, plot-items, ...
```

Anything shared by the 9.0 kernel across engines belongs in `_common/`;
engine-specific behaviour belongs under that engine. When a command exists in
several engines but behaves differently, keep it engine-specific rather than
generalising the shared copy.

### A command entry

One command is one JSON file, keyed by version. For example
`pfc/command_docs/commands/ball/delete.json`:

```json
{
  "category": "ball",
  "search_keywords": ["delete", "remove"],
  "description": "Delete balls. If no range is specified, then all balls in the model are deleted.",
  "python_sdk_alternative": {
    "available": true,
    "workaround": "Ball.delete() method - requires iteration: for b in itasca.ball.list(): b.delete()"
  },
  "versions": {
    "7.0": {
      "command": "ball delete",
      "syntax": "ball delete [range]",
      "keywords": [],
      "examples": [
        { "command": "ball delete range group 'tunnel'", "description": "Delete all balls in group 'tunnel'" }
      ]
    }
  }
}
```

Then register it in that engine's `command_docs/index.json`, under
`categories.<category>.commands[]`. The `file` pointer is relative to the
`resources/` root, not to the index:

```json
{ "name": "delete",
  "file": "pfc/command_docs/commands/ball/delete.json",
  "short_description": "Delete balls",
  "syntax": "ball delete [range]" }
```

### The standard we hold corpus to

Every version key is meant to be **verified against a live engine**, not copied
from a manual and assumed to hold across versions. Most corpus in this repo was
written by dumping the real engine and reconciling the difference.

You are not required to own every version. If you verified `7.0` and cannot
check `6.0`, contribute the `7.0` key alone and say so in the PR — a missing
version is fine, an unverified guess is what breaks an agent six hours into a
run. Say which engine and build you verified on; that is the part a reviewer
cannot reproduce.

Worked examples of accepted corpus PRs: [#9](https://github.com/yusong652/itasca-mcp/pull/9)
(new `python_sdk_docs` modules plus their index entries and tests) and
[#12](https://github.com/yusong652/itasca-mcp/pull/12) (corpus split that also
touched the loader and its types).

## Code changes

Read `CLAUDE.md` at the repo root before touching tool surfaces — it carries the
architectural rules that reviews are held to, in particular the unified
`{ok, data, error}` envelope, the separation between MCP-side and bridge-side
concerns, and the two execution models (synchronous REPL vs. async task).

New behaviour comes with a test. `tests/` is mock-bridge based on purpose: the
suite must pass with no Itasca install and no license.

## Development setup

See the [Developer Guide](docs/development/source-install.md)
([简体中文](docs/development/source-install.zh-CN.md)) for the source install,
the submodule workflow, and how to point an MCP client at a local checkout.

## Before opening a PR

CI runs exactly these four commands on every push and PR; run them locally and
there will be no surprises:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/itasca_mcp/
uv run pytest tests/ --cov=itasca_mcp --cov-report=term-missing
```

Commit messages use conventional prefixes (`feat:`, `fix:`, `refactor:`,
`test:`, `docs:`) and should say **why** the change was needed — the diff
already says what changed.

**You do not need to edit `CHANGELOG.md`.** The maintainer curates the
`## [Unreleased]` section from commit history at release time. A clear commit
message is the whole contract.

## Reporting a problem

Open an [issue](https://github.com/yusong652/itasca-mcp/issues) for bugs and
[discussions](https://github.com/yusong652/itasca-mcp/discussions) for setup
and usage questions. 中文提问完全可以。

Please include:

- Engine and version (in the Itasca Python console, `sys.executable` encodes both)
- `itasca-mcp` and `itasca-mcp-bridge` versions
- Which MCP client you are running
- What the agent tried, and what the engine did instead

Version-specific findings are genuinely useful even without a fix attached —
"this command does not exist in PFC 6.00" is a corpus bug report, and it is the
kind only a user of that version can file.

## License

By contributing you agree that your contributions are licensed under the
project's [MIT license](LICENSE).
