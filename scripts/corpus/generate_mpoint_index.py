"""Generate resources/mpoint/command_docs/index.json.

Mirrors generate_3dec_index.py:

1. MPoint's one engine-specific family (``mpoint``) is scanned from the generated
   command JSON; each command's ``file`` pointer is RESOURCES-root-relative
   ("mpoint/command_docs/commands/mpoint/<stem>.json").

2. Shared-kernel commands are reused from the FLAC index: every command whose
   ``file`` points into ``_common/`` is copied verbatim (data/fish/geometry/
   history/plot/program/project/table + the shared ``model`` subset). MPoint is a
   9.0 unified-kernel product, so it supports the same _common command set.

3. The ``zone`` family is borrowed from the FLAC index under a filter. MPoint's
   documented model-building workflow *is* the zone workflow -- the official
   QuickStart builds geometry with ``zone create``/``cmodel``/``property`` and
   then converts with ``mpoint import from-zones`` -- so the family is
   load-bearing here, unlike in massflow (where zone is incidental to a coupled
   run and is deliberately not borrowed). Commands live-probed as absent from
   MPoint3D 9.7 are dropped; MPoint-local zone docs, if present under
   ``mpoint/command_docs/commands/zone/``, are merged in and win on name
   collision.

Usage:
    uv run python scripts/corpus/generate_mpoint_index.py
"""

import json
from pathlib import Path
from typing import Any

RESOURCES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
COMMANDS_DIR = RESOURCES / "mpoint" / "command_docs" / "commands"
FLAC_INDEX = RESOURCES / "flac" / "command_docs" / "index.json"
OUT_INDEX = RESOURCES / "mpoint" / "command_docs" / "index.json"

CATEGORY_META: dict[str, dict[str, Any]] = {
    "mpoint": {
        "full_name": "Material Point Commands",
        "description": "Core MPoint (Material Point Method) commands: create/generate/import material points, assign constitutive models and properties, manage the background-grid nodes (fix/free/damping/dynamic/spacing/skin), convert between material points and zones, and drive PIC/FLIP blending, locking adjustment and volume limiting.",
        "command_prefix": "mpoint",
        "notes": [
            "Sub-namespaces are part of the JSON key: 'mpoint node fix' -> commands/mpoint/node-fix.json, 'mpoint zone-conversion' -> commands/mpoint/zone-conversion.json",
            "Material points carry state/history and move through a fixed background grid whose nodes are managed by the 'mpoint node ...' subcommands",
            "'mpoint zone-conversion' / 'mpoint generate' bridge MPM material points with the shared zone kernel",
        ],
    },
}

PROPRIETARY = list(CATEGORY_META.keys())

# Live-probed against MPoint3D 9.7 (2026-09-14): every other FLAC zone command
# in the corpus is accepted by MPoint. These two re-enumerate the zone family
# keyword list instead, i.e. the engine does not know the subcommand.
#   - create2d: 2D-only command; expected absent from a 3D build. Re-probe on
#     mpoint2d9_gui.exe before drawing any conclusion about MPoint as a product.
#   - consolidation: FLAC 7.0-era command; no page in the Itasca 9.7 doc tree.
ZONE_ABSENT_IN_MPOINT3D = {"create2d", "consolidation"}

ZONE_META: dict[str, Any] = {
    "full_name": "Zone Commands (model building)",
    "description": (
        "Commands for building and configuring the continuum grid that MPoint models are "
        "authored on. In MPM the zone grid is scaffolding, not the simulated body: you build "
        "geometry with 'zone create', attach a constitutive model and properties, initialize "
        "stresses, and then convert the grid into material points with 'mpoint import "
        "from-zones' (which deletes the zones). Shares the 9.0 zone kernel with FLAC3D."
    ),
    "command_prefix": "zone",
    "python_module": "itasca.zone",
    "python_object_class": "Zone",
    "related_categories": ["mpoint", "model", "geometry"],
    "notes": [
        "Canonical MPoint workflow: zone create -> zone cmodel assign -> zone property -> "
        "zone initialize-stresses -> mpoint node spacing -> mpoint import from-zones",
        "'mpoint import from-zones' consumes the zones: it converts each zone to material "
        "points and then deletes the zones and their gridpoints",
        "itasca.zone / itasca.gridpoint read back zone state from Python, but only before "
        "conversion -- material points themselves are not exposed to the Python API at all "
        "(use FISH: mpoint.list, mpoint.pos, ...)",
        "Docs are shared with FLAC3D. 'zone create2d' and 'zone consolidation' are not "
        "available in MPoint3D 9.7 and are omitted from this index",
    ],
}


def _resolve_9_0(cmd_data: dict[str, Any]) -> dict[str, Any]:
    versions = cmd_data.get("versions")
    if isinstance(versions, dict) and "9.0" in versions:
        merged = dict(cmd_data)
        merged.update(versions["9.0"])
        return merged
    return cmd_data


def build_proprietary_category(category: str) -> dict[str, Any]:
    cat_dir = COMMANDS_DIR / category
    commands = []
    for cmd_path in sorted(cat_dir.glob("*.json")):
        data = _resolve_9_0(json.loads(cmd_path.read_text(encoding="utf-8")))
        description = data.get("description", "")
        short = description.split(".")[0] if description else ""
        if len(short) > 100:
            short = short[:97] + "..."
        python_alt = data.get("python_sdk_alternative", {})
        commands.append(
            {
                "name": cmd_path.stem,
                "file": f"mpoint/command_docs/commands/{category}/{cmd_path.name}",
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


def borrow_flac_zone() -> dict[str, Any]:
    """Borrow the FLAC zone family, minus the commands MPoint does not have."""
    flac = json.loads(FLAC_INDEX.read_text(encoding="utf-8"))
    zone = flac.get("categories", {}).get("zone", {})
    commands = [c for c in zone.get("commands", []) if c.get("name") not in ZONE_ABSENT_IN_MPOINT3D]

    local_dir = COMMANDS_DIR / "zone"
    if local_dir.is_dir():
        by_name = {c["name"]: c for c in commands}
        for cmd_path in sorted(local_dir.glob("*.json")):
            data = _resolve_9_0(json.loads(cmd_path.read_text(encoding="utf-8")))
            description = data.get("description", "")
            short = description.split(".")[0] if description else ""
            if len(short) > 100:
                short = short[:97] + "..."
            by_name[cmd_path.stem] = {
                "name": cmd_path.stem,
                "file": f"mpoint/command_docs/commands/zone/{cmd_path.name}",
                "short_description": short,
                "syntax": data.get("syntax", ""),
                "python_available": data.get("python_sdk_alternative", {}).get("available", False),
            }
        commands = [by_name[n] for n in sorted(by_name)]

    meta = dict(ZONE_META)
    meta["commands"] = commands
    return meta


def main() -> None:
    categories: dict[str, Any] = {}
    for category in PROPRIETARY:
        categories[category] = build_proprietary_category(category)
    categories["zone"] = borrow_flac_zone()
    common = borrow_common_categories()
    for name, meta in common.items():
        categories[name] = meta

    index = {
        "version": "1.0",
        "description": "MPoint (MPM) command documentation index for quick lookup and LLM-assisted command discovery",
        "categories": categories,
    }
    OUT_INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total = sum(len(c["commands"]) for c in categories.values())
    print(f"Wrote {OUT_INDEX}")
    print(f"  categories: {len(categories)}  total commands: {total}")
    print("  proprietary:", {c: len(categories[c]["commands"]) for c in PROPRIETARY})
    print("  reused _common:", {n: len(categories[n]["commands"]) for n in common})
    print("  borrowed zone:", len(categories["zone"]["commands"]))


if __name__ == "__main__":
    main()
