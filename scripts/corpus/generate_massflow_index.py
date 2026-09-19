"""Generate resources/massflow/command_docs/index.json.

Mirrors generate_mpoint_index.py:

1. MassFlow's one engine-specific family (``massflow``) is scanned from the
   generated command JSON; each command's ``file`` pointer is RESOURCES-root-
   relative ("massflow/command_docs/commands/massflow/<stem>.json").

2. Shared-kernel commands are reused from the FLAC index: every command whose
   ``file`` points into ``_common/`` is copied verbatim (data/fish/fracture/
   geometry/history/plot/program/project/table + the shared ``model`` subset).
   MassFlow is a 9.0 unified-kernel product, so it supports the same _common
   command set (verified live: model/data/fish/geometry/history/plot/program/
   project/table/fracture all answer ``<family> ?`` on the massflow binary).

The FLAC3D ``zone`` family is intentionally NOT borrowed (see parse_massflow.py).

Usage:
    uv run python scripts/corpus/generate_massflow_index.py
"""

import json
from pathlib import Path
from typing import Any

RESOURCES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
COMMANDS_DIR = RESOURCES / "massflow" / "command_docs" / "commands"
FLAC_INDEX = RESOURCES / "flac" / "command_docs" / "index.json"
OUT_INDEX = RESOURCES / "massflow" / "command_docs" / "index.json"

CATEGORY_META: dict[str, dict[str, Any]] = {
    "massflow": {
        "full_name": "MassFlow (Gravity Flow / Caving) Commands",
        "description": "Core MassFlow commands for gravity-flow and caving simulation: configure and run the flow solution (initialize/compute), define and report on drawpoints and draw periods, place and trace markers, import mine-blocks, toggle fines migration and secondary fragmentation, and record results.",
        "command_prefix": "massflow",
        "notes": [
            "Sub-namespaces are part of the JSON key: 'massflow drawpoint import' -> commands/massflow/drawpoint-import.json, 'massflow mine-block group' -> commands/massflow/mine-block-group.json",
            "17 of the 47 commands have no page in the MassFlow manual and are authored from live 9.7 enumeration (scripts/corpus/author_massflow_live_commands.py); each carries a note saying so",
            "Workflow: 'massflow initialize' sets the run parameters, then 'massflow compute' advances the flow solution by days/periods",
            "Drawpoints drive extraction; markers trace material provenance; mine-blocks tag the orebody for grade tracking",
            "The FLAC3D 'zone' family is available on the massflow binary for coupled mechanical analysis but is documented under software='flac'",
        ],
    },
}

PROPRIETARY = list(CATEGORY_META.keys())


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
                "file": f"massflow/command_docs/commands/{category}/{cmd_path.name}",
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


def main() -> None:
    categories: dict[str, Any] = {}
    for category in PROPRIETARY:
        categories[category] = build_proprietary_category(category)
    common = borrow_common_categories()
    for name, meta in common.items():
        categories[name] = meta

    index = {
        "version": "1.0",
        "description": "MassFlow (gravity flow / caving) command documentation index for quick lookup and LLM-assisted command discovery",
        "categories": categories,
    }
    OUT_INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total = sum(len(c["commands"]) for c in categories.values())
    print(f"Wrote {OUT_INDEX}")
    print(f"  categories: {len(categories)}  total commands: {total}")
    print("  proprietary:", {c: len(categories[c]["commands"]) for c in PROPRIETARY})
    print("  reused _common:", {n: len(categories[n]["commands"]) for n in common})


if __name__ == "__main__":
    main()
