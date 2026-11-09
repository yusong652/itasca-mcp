"""Unify keyword lists per the corpus spec (section E).

One structured ``keywords`` list per page; entries are
``{name, syntax?, description?, availability?, dimension?, optional?, group?}``
plus the cross-cutting ``notes``/``verification``. The fish tree migrates via
the generator (namespace ``engines`` folds into ``availability.engines``).

- Entry mechanics, every tree: bare-string entries become ``{name}``;
  ``keyword`` renames to ``name``; a keyword ``engines`` tag moves into
  ``availability.engines`` (the loader consumes it from there);
  entry ``examples`` / ``available_parameters`` / ``parameters`` fold into
  entry notes; ``required: false`` becomes ``optional: true``.
- references: the parallel ``*_keywords`` lists dissolve into ``keywords``
  (``group`` keeps the grouping where it mattered — management / result /
  shared / categorical / beam-family / condition families); the live
  ``top_level_keywords`` enumerations contribute name-only entries for
  what ``basic_keywords`` did not describe; ``flac3d_extra_keywords``
  become ``dimension: "3D"`` entries; ``common_sub_keywords`` compress into
  one note. ``sub_keywords`` (range-element archetype) stays.
- command_docs: the index ``common_keywords`` navigation sugar is dropped
  (it duplicates each command page); ``plot_items`` catalogs compress into
  notes naming the item types and pointing at the reference plot-items tree
  (per-type labels/descriptions reviewed: label expansion + pointer only).
- python_sdk: the two rblock keyword-aid files get the standard
  phrase-to-API-paths shape their siblings use (hand-written maps).

Deferred to later steps: ``*/references/dimension-differences/`` files,
``dimension_differences`` / ``independent_dimensions`` /
``flac3d_liner_property_set`` (step B), ``index_expansion`` (step F),
``legacy_documentation`` (step A).

Usage:
    uv run python scripts/corpus/migrate_keywords.py [--write]
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"

DEFERRED_SUBTREES = {
    "legacy_documentation",
    "dimension_differences",
    "independent_dimensions",
    "flac3d_liner_property_set",
    "index_expansion",
}
DEFERRED_PATHS = ("references/dimension-differences/",)

# The rblock keyword-aid files carried primary/action keyword lists no loader
# reads; their siblings map natural-language phrases to API paths. Hand-written
# replacements against the live module.json function lists.
KEYWORD_AID_REWRITE = {
    "pfc/python_sdk_docs/modules/rblock/keywords.json": {
        "module": "rblock",
        "description": "Natural language keywords for rblock module API search",
        "keywords": {
            "rigid block": ["itasca.rblock.list", "itasca.rblock.count"],
            "rblock count": ["itasca.rblock.count"],
            "count rblocks": ["itasca.rblock.count"],
            "list rblocks": ["itasca.rblock.list"],
            "find rblock": ["itasca.rblock.find"],
            "rblock near": ["itasca.rblock.near"],
            "rblock in box": ["itasca.rblock.inbox"],
            "rblock energy": ["itasca.rblock.energy", "itasca.rblock.energies"],
        },
    },
    "pfc/python_sdk_docs/modules/rblock/template/keywords.json": {
        "module": "rblock.template",
        "description": "Natural language keywords for rblock template module API search",
        "keywords": {
            "rblock template": ["itasca.rblock.template.list", "itasca.rblock.template.count"],
            "rigid block template": ["itasca.rblock.template.list"],
            "find template": ["itasca.rblock.template.find"],
            "count templates": ["itasca.rblock.template.count"],
            "template pebble": ["itasca.rblock.template.findpebble"],
        },
    },
}


# Operative facts from plot_items catalog descriptions that survive the fold
# (reviewed 2026-11-09; the rest is label expansion the type list already carries).
PLOT_ITEM_KEEP_NOTES = {
    "pfc/command_docs/commands/plot/item.json": [
        "dfn must be created as 'plot item create dfn contour' (bare 'plot item create dfn' is an error); it contours contact data on fractures — the fractures themselves are drawn by the 'fracture' item.",
        "fracture cannot color by parent DFN ('dfn' is not a color-by attribute): assign 'fracture group' per DFN and color by group.",
        "chart-history needs 'history <name>' (the history's Name from 'history list', not its numeric ID) or the chart renders empty.",
    ],
    "_common/command_docs/commands/plot/item.json": [
        "chart-history needs 'history <name>' (the history's Name from 'history list', not its numeric ID) or the chart renders empty.",
    ],
}


@dataclass
class Stats:
    dissolved: int = 0
    entry_edits: int = 0
    dropped_sections: list[str] = field(default_factory=list)
    plot_item_entries: list[str] = field(default_factory=list)
    files: int = 0
    oddities: list[str] = field(default_factory=list)


def _as_entries(value: Any, rel: str, stats: Stats, **extra: Any) -> list[dict[str, Any]]:
    """Normalise a str-or-dict keyword list into entry dicts, tagging ``extra``."""
    entries = []
    for item in value:
        if isinstance(item, str):
            entries.append({"name": item, **extra})
        elif isinstance(item, dict):
            entry = dict(item)
            if "keyword" in entry:
                entry["name"] = entry.pop("keyword")
            entries.append({**entry, **extra})
        else:
            stats.oddities.append(f"{rel}: non-str/dict keyword entry {item!r}")
    return entries


def _fix_entry(entry: dict[str, Any], rel: str, stats: Stats) -> bool:
    changed = False
    if "keyword" in entry:
        if "name" in entry:
            stats.oddities.append(f"{rel}: entry has both keyword and name")
            return changed
        entry["name"] = entry.pop("keyword")
        changed = True
    if "engines" in entry:
        availability = entry.setdefault("availability", {})
        if "engines" in availability:
            stats.oddities.append(f"{rel}: entry availability already has engines")
        availability["engines"] = entry.pop("engines")
        changed = True
    if isinstance(entry.get("examples"), list):
        entry.setdefault("notes", []).extend(f"Example: {ex}" for ex in entry.pop("examples"))
        changed = True
    if isinstance(entry.get("available_parameters"), dict):
        params = entry.pop("available_parameters")
        entry.setdefault("notes", []).append("Parameters: " + "; ".join(f"{k}: {v}" for k, v in params.items()))
        changed = True
    if isinstance(entry.get("parameters"), list):
        for p in entry.pop("parameters"):
            req = ", required" if p.get("required") else ""
            entry.setdefault("notes", []).append(
                f"Parameter {p.get('name')} ({p.get('type', 'value')}{req}): {p.get('description', '')}".rstrip()
            )
        changed = True
    if "required" in entry:
        required = entry.pop("required")
        if not required:
            entry["optional"] = True
        changed = True
    return changed


def _entry_pass(node: Any, rel: str, stats: Stats) -> bool:
    """Mechanical entry fixes in every keywords/sub_keywords list, recursively."""
    changed = False
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key in DEFERRED_SUBTREES:
                continue
            if key in ("keywords", "sub_keywords") and isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, str):
                        value[i] = {"name": item}
                        stats.entry_edits += 1
                        changed = True
                    elif isinstance(item, dict):
                        if _fix_entry(item, rel, stats):
                            stats.entry_edits += 1
                            changed = True
            changed = _entry_pass(value, rel, stats) or changed
    elif isinstance(node, list):
        for item in node:
            changed = _entry_pass(item, rel, stats) or changed
    return changed


def _dissolve_references(doc: dict[str, Any], rel: str, stats: Stats) -> bool:
    """Fold the parallel *_keywords spellings of one references file."""
    changed = False

    def keywords(create: bool = True) -> list[Any]:
        if "keywords" not in doc and create:
            doc["keywords"] = []
        return doc["keywords"]

    if "basic_keywords" in doc:
        basic = _as_entries(doc.pop("basic_keywords"), rel, stats)
        named = {e.get("name") for e in basic}
        extras = [t for t in doc.pop("top_level_keywords", []) if t not in named]
        keywords()[0:0] = basic + [{"name": t} for t in extras]
        stats.dissolved += 1
        changed = True
    elif "top_level_keywords" in doc:
        keywords()[0:0] = [{"name": t} for t in doc.pop("top_level_keywords")]
        stats.dissolved += 1
        changed = True

    for key, group in (
        ("management_keywords", "management"),
        ("result_keywords", "result"),
        ("categorical_keywords", "categorical"),
    ):
        if key in doc:
            keywords().extend(_as_entries(doc.pop(key), rel, stats, group=group))
            stats.dissolved += 1
            changed = True

    if "shared_keywords" in doc:
        shared = doc.pop("shared_keywords")
        doc.setdefault("notes", []).append(f"Shared keywords (group 'shared'): {shared['description']}")
        keywords().extend({"name": n, "group": "shared"} for n in shared["list"])
        stats.dissolved += 1
        changed = True

    if "beam_family_keywords" in doc:
        beam = doc.pop("beam_family_keywords")
        doc.setdefault("notes", []).append(
            "Beam-family item types (identical keyword sets): " + ", ".join(beam["types"])
        )
        doc["notes"].extend(beam.get("notes", []))
        keywords().extend({"name": n, "group": "beam-family"} for n in beam["keywords"])
        stats.dissolved += 1
        changed = True

    if "common_sub_keywords" in doc:
        subs = doc.pop("common_sub_keywords")
        doc.setdefault("notes", []).append(
            f"Common sub-keywords shared by every attribute ({len(subs)}): " + ", ".join(subs)
        )
        stats.dissolved += 1
        changed = True

    if "flac3d_extra_keywords" in doc:
        keywords().extend({"name": n, "dimension": "3D"} for n in doc.pop("flac3d_extra_keywords"))
        stats.dissolved += 1
        changed = True

    if "condition_families" in doc:
        for family in doc.pop("condition_families"):
            keywords().extend({"name": n, "group": family["family"]} for n in family.get("keywords", []))
            keywords().extend(
                {"name": n, "group": family["family"], "dimension": "3D"} for n in family.get("keywords_3d_only", [])
            )
            doc.setdefault("notes", []).extend(family.get("notes", []))
            unknown = set(family) - {"family", "keywords", "keywords_3d_only", "notes"}
            if unknown:
                stats.oddities.append(f"{rel}: condition family keys {sorted(unknown)}")
        stats.dissolved += 1
        changed = True

    return changed


def _command_docs_pass(doc: dict[str, Any], rel: str, stats: Stats) -> bool:
    changed = False
    if rel.endswith("command_docs/index.json"):
        for category in doc.get("categories", {}).values():
            if "common_keywords" in category:
                del category["common_keywords"]
                stats.dropped_sections.append(f"{rel}: common_keywords")
                changed = True
    if "plot_items" in doc:
        items = doc.pop("plot_items")
        for item in items:
            stats.plot_item_entries.append(
                f"{rel}: {item.get('keyword')} ({item.get('label')}) -- {item.get('description', '')[:110]}"
            )
        names = ", ".join(i["keyword"] for i in items)
        notes = [f"Item types for 'plot item create <type>' ({len(items)}): {names}."]
        coupled = [i["keyword"] for i in items if "(coupled zone models)" in i.get("description", "")]
        if coupled:
            notes.append("Coupled zone models only: " + ", ".join(coupled) + ".")
        notes.extend(PLOT_ITEM_KEEP_NOTES.pop(rel, []))
        notes.append(
            "Per-type configuration keywords: itasca_browse_doc(source='reference', path='plot-items <type>')."
        )
        doc.setdefault("notes", []).extend(notes)
        stats.dropped_sections.append(f"{rel}: plot_items ({len(items)} entries -> note)")
        changed = True
    return changed


def main() -> int:
    write = "--write" in sys.argv
    stats = Stats()
    for tree in ("command_docs", "python_sdk_docs", "references"):
        for path in sorted(RESOURCES.glob(f"*/{tree}/**/*.json")):
            rel = path.relative_to(RESOURCES).as_posix()
            if any(deferred in rel for deferred in DEFERRED_PATHS):
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            if rel in KEYWORD_AID_REWRITE:
                doc = KEYWORD_AID_REWRITE.pop(rel)
                changed = True
            elif isinstance(doc, dict):
                if tree == "references":
                    changed = _dissolve_references(doc, rel, stats)
                if tree == "command_docs":
                    changed = _command_docs_pass(doc, rel, stats) or changed
                changed = _entry_pass(doc, rel, stats) or changed
            if changed:
                stats.files += 1
                print(f"changed  {rel}")
                if write:
                    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if KEYWORD_AID_REWRITE:
        raise SystemExit(f"keyword-aid rewrites never matched: {sorted(KEYWORD_AID_REWRITE)}")
    if PLOT_ITEM_KEEP_NOTES:
        raise SystemExit(f"plot-item keep-notes never matched: {sorted(PLOT_ITEM_KEEP_NOTES)}")
    print("\nPLOT ITEM CATALOG (compressed to notes):")
    print("\n".join(stats.plot_item_entries))
    print("\n".join(f"dropped  {d}" for d in stats.dropped_sections))
    print(
        f"\ndissolved lists: {stats.dissolved}; entry edits: {stats.entry_edits}; "
        f"files changed: {stats.files}" + ("" if write else " (dry run)")
    )
    if stats.oddities:
        print("\nODDITIES:")
        print("\n".join(stats.oddities))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
