"""Unify availability to the corpus-spec form in references and python_sdk docs.

Spec (docs/development/corpus-spec.md, section A): the canonical form on any
object is ``"availability": {"versions": [...], "engines": [...]}``; an
omitted field means no restriction. This script converts:

- references: bool maps ``{"7.0": false, "9.0": true}`` -> ``{"versions":
  ["9.0"]}`` anywhere they appear (category indexes, item docs, properties).
  A map that allows every corpus version (6.0+7.0+9.0) is a no-op restriction
  and is dropped. Property-level ``since: "X"`` becomes ``availability`` with
  every corpus version >= X.
- python_sdk_docs: per-build straggler keys (``available_in_3dec_97`` etc.)
  are deleted after asserting they agree with the entry's ``availability``;
  top-level ``versions`` lists in module files that name every version are
  deleted (no restriction).

The fish tree is NOT touched here: its format is owned by
scripts/corpus/generate_fish_docs.py and migrates by regenerating.
command_docs migrates separately with its version-block restructure.

Usage:
    uv run python scripts/corpus/migrate_availability.py [--write]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"
ALL_VERSIONS = ("6.0", "7.0", "9.0")


def is_bool_map(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(value)
        and all(k in ALL_VERSIONS and isinstance(v, bool) for k, v in value.items())
    )


def canonical(bool_map: dict[str, bool]) -> dict[str, Any] | None:
    """Canonical availability for a bool map; None when it restricts nothing."""
    versions = [v for v in ALL_VERSIONS if bool_map.get(v)]
    if versions == list(ALL_VERSIONS):
        return None
    return {"versions": versions}


def since_versions(since: str) -> list[str]:
    if since not in ALL_VERSIONS:
        raise SystemExit(f"unexpected 'since' value: {since!r}")
    return [v for v in ALL_VERSIONS if v >= since]


class Stats:
    def __init__(self) -> None:
        self.maps = 0
        self.dropped = 0
        self.since = 0
        self.straggler_keys = 0
        self.version_lists = 0
        self.files = 0


def convert_references(node: Any, stats: Stats) -> bool:
    """Rewrite availability bool maps and ``since`` in place. Returns True if changed."""
    changed = False
    if isinstance(node, dict):
        value = node.get("availability")
        if is_bool_map(value):
            new = canonical(value)
            if new is None:
                del node["availability"]
                stats.dropped += 1
            else:
                node["availability"] = new
                stats.maps += 1
            changed = True
        if isinstance(node.get("since"), str):
            if "availability" in node:
                raise SystemExit(f"'since' next to 'availability': {node}")
            node["availability"] = {"versions": since_versions(node.pop("since"))}
            stats.since += 1
            changed = True
        for child in node.values():
            changed = convert_references(child, stats) or changed
    elif isinstance(node, list):
        for child in node:
            changed = convert_references(child, stats) or changed
    return changed


def convert_python(node: Any, stats: Stats, where: str) -> bool:
    changed = False
    if isinstance(node, dict):
        for key in [k for k in node if k.startswith("available_in_")]:
            flag = node[key]
            availability = node.get("availability")
            versions = availability.get("versions", []) if isinstance(availability, dict) else []
            # The straggler says whether the entry exists in the 9.x build; it must
            # agree with availability, which is the single source of truth now.
            if not isinstance(flag, bool) or ("9.0" in versions) != flag:
                raise SystemExit(f"{where}: {key}={flag!r} disagrees with availability {availability!r}")
            del node[key]
            stats.straggler_keys += 1
            changed = True
        for child in node.values():
            changed = convert_python(child, stats, where) or changed
    elif isinstance(node, list):
        for child in node:
            changed = convert_python(child, stats, where) or changed
    return changed


def main() -> int:
    write = "--write" in sys.argv
    stats = Stats()

    for path in sorted(RESOURCES.glob("*/references/**/*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if convert_references(doc, stats):
            stats.files += 1
            print(f"references: {path.relative_to(RESOURCES)}")
            if write:
                path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for path in sorted(RESOURCES.glob("*/python_sdk_docs/**/*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        changed = convert_python(doc, stats, str(path.relative_to(RESOURCES)))
        if path.name == "module.json" and "versions" in doc:
            if doc["versions"] != list(ALL_VERSIONS):
                # A partial list would be a real restriction; none exists today,
                # so seeing one means this script needs a decision, not silence.
                raise SystemExit(f"{path}: module-level versions {doc['versions']!r} is not the full list")
            del doc["versions"]
            stats.version_lists += 1
            changed = True
        if changed:
            stats.files += 1
            print(f"python_sdk: {path.relative_to(RESOURCES)}")
            if write:
                path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"\nbool maps -> versions: {stats.maps}; no-op maps dropped: {stats.dropped}; "
        f"since converted: {stats.since}; straggler keys removed: {stats.straggler_keys}; "
        f"module version lists removed: {stats.version_lists}; files changed: {stats.files}"
        + ("" if write else " (dry run)")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
