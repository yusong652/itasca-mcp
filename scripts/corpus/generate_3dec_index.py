"""Generate resources/3dec/command_docs/index.json.

Two parts, mirroring how flac/command_docs/index.json is built:

1. 3DEC-proprietary families (block / feblock / fblock / flowknot / flowplane)
   are scanned from the generated command JSON; each command's ``file`` pointer
   is RESOURCES-root-relative ("3dec/command_docs/commands/<cat>/<stem>.json").

2. Shared-kernel commands are reused from the FLAC index: every command whose
   ``file`` points into ``_common/`` is copied verbatim. This is a single rule
   that keeps pure-kernel categories whole (data/fish/geometry/...), trims
   ``model`` to just its shared subset, and drops FLAC-only categories (body,
   zone, extruder, structure, group, domain) because none of their commands
   live under _common/. 3DEC is a 9.0 unified-kernel product, so it supports
   the same _common command set.

Usage:
    uv run python scripts/corpus/generate_3dec_index.py
"""

import json
from pathlib import Path
from typing import Any

RESOURCES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
COMMANDS_DIR = RESOURCES / "3dec" / "command_docs" / "commands"
FLAC_INDEX = RESOURCES / "flac" / "command_docs" / "index.json"
OUT_INDEX = RESOURCES / "3dec" / "command_docs" / "index.json"

# Metadata for the 3DEC-proprietary command families.
CATEGORY_META: dict[str, dict[str, Any]] = {
    "block": {
        "full_name": "Block Commands",
        "description": "Core 3DEC commands for the distinct-element block model: create/cut/join blocks, assign zone constitutive models, manage joint contacts and subcontacts, and drive deformable-block zoning, faces and gridpoints.",
        "command_prefix": "block",
        "notes": [
            "Sub-namespaces are part of the JSON key: 'block contact apply' -> commands/block/contact-apply.json, 'block zone generate' -> commands/block/zone-generate.json",
            "Rigid vs. deformable blocks: zoning/gridpoint/face subcommands apply to deformable blocks",
            "Joints between blocks are modeled through block contact / subcontacts",
        ],
    },
    "feblock": {
        "full_name": "Finite-Element Block Commands",
        "description": "Commands for finite-element blocks (high-order tetrahedral FE meshing of deformable blocks).",
        "command_prefix": "feblock",
    },
    "fblock": {
        "full_name": "Faceted Block Commands",
        "description": "Commands for faceted blocks (fblock): grouping, listing, and deletion of faceted block geometry.",
        "command_prefix": "fblock",
    },
    "flowknot": {
        "full_name": "Flow Knot Commands",
        "description": "Commands for flow knots — the nodal points of 3DEC's fracture-flow network used in hydro-mechanical coupling.",
        "command_prefix": "flowknot",
    },
    "flowplane": {
        "full_name": "Flow Plane Commands",
        "description": "Commands for flow planes — the planar fracture-flow elements (with edge/vertex/zone sub-namespaces) of 3DEC's hydro-mechanical fluid-flow model.",
        "command_prefix": "flowplane",
    },
    "sel": {
        "full_name": "Structural Element (SEL) Commands",
        "description": "3DEC 7.0 legacy structural-element family: hybrid bolt elements (sel hybrid), structural node settings (sel node), and local reinforcement elements (sel reinforcement).",
        "command_prefix": "sel",
        "notes": [
            "7.0-only family: in 3DEC 9.x these merged into the unified structure family (structure hybrid / structure dowel / ...)",
            "3DEC 7.0 also ships the unified structure family alongside sel (structure beam/cable/liner/... — documented on the FLAC side)",
        ],
    },
}

PROPRIETARY = list(CATEGORY_META.keys())


def _resolve_versioned(cmd_data: dict[str, Any]) -> dict[str, Any]:
    """Merge the newest available version block (9.0, else 7.0) for index fields."""
    versions = cmd_data.get("versions")
    if isinstance(versions, dict):
        for key in ("9.0", "7.0"):
            if key in versions:
                merged = dict(cmd_data)
                merged.update(versions[key])
                return merged
    return cmd_data


def build_proprietary_category(category: str) -> dict[str, Any]:
    cat_dir = COMMANDS_DIR / category
    commands = []
    for cmd_path in sorted(cat_dir.glob("*.json")):
        data = _resolve_versioned(json.loads(cmd_path.read_text(encoding="utf-8")))
        description = data.get("description", "")
        short = description.split(".")[0] if description else ""
        if len(short) > 100:
            short = short[:97] + "..."
        python_alt = data.get("python_sdk_alternative", {})
        commands.append(
            {
                # Short, category-stripped, dash-joined name (e.g. "zone-generate"),
                # matching how PFC/FLAC index commands are keyed. CommandLoader looks
                # commands up by this name; browse maps "block zone generate" -> here.
                "name": cmd_path.stem,
                "file": f"3dec/command_docs/commands/{category}/{cmd_path.name}",
                "short_description": short,
                "syntax": data.get("syntax", ""),
                "python_available": python_alt.get("available", False),
            }
        )
    meta = dict(CATEGORY_META[category])
    meta["commands"] = commands
    return meta


def borrow_common_categories() -> dict[str, dict[str, Any]]:
    """Copy every command from the FLAC index whose file points into _common/."""
    flac = json.loads(FLAC_INDEX.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for name, info in flac.get("categories", {}).items():
        common_cmds = [c for c in info.get("commands", []) if str(c.get("file", "")).startswith("_common/")]
        if not common_cmds:
            continue
        meta = {k: v for k, v in info.items() if k != "commands"}
        meta["commands"] = common_cmds
        out[name] = meta
    return out


def merge_local_shared_overrides(categories: dict[str, Any]) -> list[str]:
    """Merge 3DEC-local files that live in a borrowed (shared) category.

    Some shared-kernel commands need a 3DEC-scoped doc because the engine's
    keyword set diverges from the FLAC/_common one (e.g. ``model configure``:
    no cfd/axisymmetry, 7.0 classic ``fluid``). Those files live under
    ``commands/<shared-category>/`` next to the proprietary families; this
    scans every non-proprietary directory and inserts/overrides the matching
    command entries so a rerun never drops them.
    """
    merged: list[str] = []
    for cat_dir in sorted(COMMANDS_DIR.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name in PROPRIETARY:
            continue
        category = cat_dir.name
        if category not in categories:
            continue
        commands = categories[category]["commands"]
        by_name = {c["name"]: i for i, c in enumerate(commands)}
        for cmd_path in sorted(cat_dir.glob("*.json")):
            data = _resolve_versioned(json.loads(cmd_path.read_text(encoding="utf-8")))
            description = data.get("description", "")
            short = description.split(".")[0] if description else ""
            if len(short) > 100:
                short = short[:97] + "..."
            entry = {
                "name": cmd_path.stem,
                "file": f"3dec/command_docs/commands/{category}/{cmd_path.name}",
                "short_description": short,
                "syntax": data.get("syntax", ""),
                "python_available": data.get("python_sdk_alternative", {}).get("available", False),
            }
            if cmd_path.stem in by_name:
                commands[by_name[cmd_path.stem]] = entry
            else:
                commands.append(entry)
                commands.sort(key=lambda c: c["name"])
            merged.append(f"{category}/{cmd_path.stem}")
    return merged


def main() -> None:
    categories: dict[str, Any] = {}
    for category in PROPRIETARY:
        categories[category] = build_proprietary_category(category)
    common = borrow_common_categories()
    for name, meta in common.items():
        categories[name] = meta
    merged = merge_local_shared_overrides(categories)

    index = {
        "version": "1.0",
        "description": "3DEC command documentation index for quick lookup and LLM-assisted command discovery",
        "categories": categories,
    }
    OUT_INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total = sum(len(c["commands"]) for c in categories.values())
    print(f"Wrote {OUT_INDEX}")
    print(f"  categories: {len(categories)}  total commands: {total}")
    print("  proprietary:", {c: len(categories[c]["commands"]) for c in PROPRIETARY})
    print("  reused _common:", {n: len(categories[n]["commands"]) for n in common})
    print("  local shared overrides:", merged)


if __name__ == "__main__":
    main()
