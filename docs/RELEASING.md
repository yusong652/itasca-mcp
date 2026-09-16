# Releasing itasca-mcp

Maintainer checklist. Contributor-facing rules live in [`AGENTS.md`](../AGENTS.md).

`itasca-mcp` is published to PyPI via GitHub Actions, triggered by pushing a `v*` tag (e.g. `v0.3.16`). Version source: `src/itasca_mcp/__init__.py` (hatch dynamic versioning).

Steps to release `itasca-mcp`:

1. Bump `__version__` in `src/itasca_mcp/__init__.py` (the single source of truth).
2. Curate `## [Unreleased]` in `CHANGELOG.md` from `git log` since the previous release (grouped per the convention comment at the top of that file), rename it to `## [x.y.z] - YYYY-MM-DD`, then start a fresh empty `## [Unreleased]`. The publish workflow extracts the section whose header matches the tag version exactly and fails if it is missing.
3. **Sweep user-facing docs for claims the release invalidates** — `README.md` (supported engines/versions matrix, feature bullets, install flow) and `addon.py` messages. README is the PyPI long_description: anything stale at tag time is frozen into that PyPI release page and can only be fixed by the *next* release, so this check must happen BEFORE tagging, in the same release PR.
4. Bump both `version` fields in `server.json` (top-level and `packages[0]`) to the same version, in the same release PR. Keep the `description` there at or under 100 characters; the registry rejects longer ones. Also re-check that `pyproject.toml` `description`/`keywords` still list every supported engine.
5. Commit and push to `main`.
6. Tag the commit: `git tag v0.x.x` and `git push origin v0.x.x`.
7. **Publish to the MCP registry** once the PyPI release is live: run `mcp-publisher publish` from the repo root. The registry does not follow PyPI or GitHub tags on its own, so skipping this leaves the registry entry frozen at the last published version. If the token has expired, run `mcp-publisher login github` first (device-code flow; log in as `yusong652`). Verify with the registry API:

   ```bash
   curl -s "https://registry.modelcontextprotocol.io/v0.1/servers?search=itasca-mcp"
   ```

**Important**: tag version must match `__version__` and `server.json`. PyPI rejects duplicate version uploads.

**Bridge releases live in the [`itasca-mcp-bridge`](https://github.com/yusong652/itasca-mcp-bridge) repo** — not here. Bumping the bridge pin (gitlink) in this repo doesn't trigger a bridge release; it only affects what contributors see locally. End users always get whatever's on PyPI via `pip install itasca-mcp-bridge`.

The legacy `pfc-mcp-bridge` PyPI package is **frozen at `0.3.3`** (deprecation release). No future releases from this repo.
