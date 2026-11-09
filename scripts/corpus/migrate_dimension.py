"""Unify 2D/3D dimension marking per the corpus spec (section B).

Canonical: ``dimension: "2D" | "3D"`` on the entry that is restricted, at any
level; omitted = both builds. Dimension prose goes in plain ``notes`` (section
C made notes the only free-prose field; the spec draft's separate
``dimension_notes`` was dropped for that reason). Live 2D-vs-3D probe records
go to ``verification``.

- python_sdk_docs: the "2D/3D builds only." notes (263) become ``dimension``
  on the module/function/method; a combined sentence keeps its remainder as a
  note.
- references: top-level ``dimension`` disappears where the engine has no 2D
  product (3dec, massflow) and where it said ``"mixed"`` (members carry the
  tags); sentence values normalise to ``"3D"``. The ``dimension_differences``
  blocks dissolve: X-only name lists become dimension tags on the matching
  keywords/attributes/models entries, prose to notes, ``verified`` records to
  verification. The parked FLAC3D-only property sets on liner/beam-pile become
  ``property_groups`` entries tagged ``dimension: "3D"``.
- The mpoint ``references/dimension-differences/`` category stays: it is the
  curated 2D-vs-3D correction page.
- fish: the index ``dimension_differences`` extra folds into index notes +
  verification via the curated generator data (the eight z-component
  intrinsics already carry entry-level ``dimension: "3D"``).

Usage:
    uv run python scripts/corpus/migrate_dimension.py [--write]
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"

SKIP_PATHS = ("references/dimension-differences/",)
NO_2D_PRODUCT = {"3dec", "massflow"}

BUILDS_ONLY = re.compile(r"^([23]D) builds? only\.?\s*(?:;\s*)?(.*)$", re.DOTALL)


@dataclass
class Stats:
    python_tags: int = 0
    folds: int = 0
    dropped: list[str] = field(default_factory=list)
    files: int = 0
    oddities: list[str] = field(default_factory=list)


# --- shared helpers ---------------------------------------------------------


def render_verified(value: dict[str, Any], out: list[str], odd) -> None:
    rest = dict(value)
    grade = rest.pop("grade", None)
    date = rest.pop("date", None)
    engines = rest.pop("engines", None) or ([rest.pop("engine")] if "engine" in rest else None)
    method = rest.pop("method", None)
    header = "Live-verified"
    if date:
        header += f" {date}"
    if engines:
        header += f" on {', '.join(engines)}"
    if grade:
        header += f" ({grade} grade)"
    out.append(f"{header}: {method}" if method else f"{header}.")
    for key in ("identical", "resolved", "result"):
        if key in rest:
            out.append(f"{key.capitalize()}: {rest.pop(key)}")
    out.extend(f"Trap: {t}" for t in rest.pop("traps", []))
    if rest:
        odd(f"verified keys left: {sorted(rest)}")


def tag_entries(entries: list[Any], names: list[str], dimension: str, odd, create: bool = True) -> None:
    by_name = {e.get("name"): e for e in entries if isinstance(e, dict)}
    for name in names:
        entry = by_name.get(name)
        if entry is None:
            if not create:
                odd(f"no entry named {name!r} to tag {dimension}")
                continue
            entries.append({"name": name, "dimension": dimension})
        else:
            existing = entry.get("dimension")
            if existing not in (None, dimension):
                odd(f"entry {name!r} dimension conflict {existing!r} vs {dimension}")
            entry["dimension"] = dimension


# --- python trees -----------------------------------------------------------


def migrate_python_node(node: Any, rel: str, stats: Stats) -> bool:
    changed = False
    if isinstance(node, dict):
        notes = node.get("notes")
        if isinstance(notes, list):
            kept: list[str] = []
            for note in notes:
                match = BUILDS_ONLY.match(note) if isinstance(note, str) else None
                if not match:
                    kept.append(note)
                    continue
                dimension, remainder = match.group(1), match.group(2).strip()
                if node.get("dimension") not in (None, dimension):
                    stats.oddities.append(f"{rel}: dimension conflict on {node.get('name')!r}")
                node["dimension"] = dimension
                stats.python_tags += 1
                changed = True
                if remainder:
                    kept.append(remainder[0].upper() + remainder[1:])
            if kept != notes:
                if kept:
                    node["notes"] = kept
                else:
                    del node["notes"]
        for value in node.values():
            changed = migrate_python_node(value, rel, stats) or changed
    elif isinstance(node, list):
        for item in node:
            changed = migrate_python_node(item, rel, stats) or changed
    return changed


# --- references -------------------------------------------------------------


def fold_dimension_differences(doc: dict[str, Any], rel: str, stats: Stats) -> None:
    block = doc.pop("dimension_differences")
    stats.folds += 1
    odd = lambda msg: stats.oddities.append(f"{rel}: {msg}")  # noqa: E731

    def notes(*lines: str) -> None:
        doc.setdefault("notes", []).extend(lines)

    engine = rel.split("/")[0]
    tags = {"3D": [], "2D": []}
    for key in ("3d_only", "3d_only_keywords", "flac3d_only", "flac3d_tokens_not_in_flac2d_list"):
        tags["3D"] += block.pop(key, [])
    for key in ("mpoint2d_only", "mpoint2d_only_keywords", "flac2d_only", "flac2d_attributes_rejected_by_flac3d"):
        tags["2D"] += block.pop(key, [])

    if "constitutive-models/index.json" in rel:
        target = doc["models"]
        create = False
    elif "attributes" in doc:
        target = doc["attributes"]
        create = True
    elif rel.startswith(f"{engine}/command_docs/"):
        target = None  # tagged inside version blocks below
        create = False
    else:
        target = doc.setdefault("keywords", [])
        create = True

    for dimension, names in tags.items():
        if not names:
            continue
        if target is not None:
            tag_entries(target, names, dimension, odd, create)
        else:
            matched: set[str] = set()
            for version_block in doc.get("versions", {}).values():
                keywords = version_block.get("keywords", [])
                present = [n for n in names if any(isinstance(k, dict) and k.get("name") == n for k in keywords)]
                tag_entries(keywords, present, dimension, odd, create=False)
                matched.update(present)
            label = "MPoint2D-only" if dimension == "2D" else "MPoint3D-only"
            for name in names:
                if name not in matched:
                    notes(f"{label} keyword: {name} (not in the documented keyword set).")

    if "plane" in block:
        plane = block.pop("plane")
        notes(*plane.get("notes", []))
        doc.setdefault("verification", []).extend(plane.get("verification", []))
    if "verified" in block:
        render_verified(block.pop("verified"), doc.setdefault("verification", []), odd)
    notes(*block.pop("notes", []))
    for key, value in block.items():
        if isinstance(value, (str, int)):
            notes(f"{key.replace('_', ' ')}: {value}")
        elif key == "listed_but_unreachable_in_2d":
            notes(*(f"{name}: {text}" for name, text in value.items()))
        elif key == "mpoint2d_only_applies_to":
            notes("MPoint2D-only keyword applies to: " + ", ".join(value))
        elif key == "mpoint2d_options":
            notes("MPoint2D 'model configure' options: " + ", ".join(value) + ".")
        else:
            odd(f"dimension_differences key {key!r} unhandled")


def property_set_group(doc: dict[str, Any], group_name: str, keywords: list[Any], dimension: str | None) -> None:
    properties = [{"keyword": k["name"] if isinstance(k, dict) else k} for k in keywords]
    group: dict[str, Any] = {"group_name": group_name, "properties": properties}
    if dimension:
        group["dimension"] = dimension
    doc.setdefault("property_groups", []).append(group)


def migrate_reference(doc: dict[str, Any], rel: str, stats: Stats) -> bool:
    before = json.dumps(doc, sort_keys=True)
    engine = rel.split("/")[0]
    odd = lambda msg: stats.oddities.append(f"{rel}: {msg}")  # noqa: E731

    def notes(*lines: str) -> None:
        doc.setdefault("notes", []).extend(lines)

    # top-level dimension value cleanup
    dimension = doc.get("dimension")
    if isinstance(dimension, str):
        if engine in NO_2D_PRODUCT or dimension == "mixed":
            del doc["dimension"]
        elif dimension.startswith("3D only"):
            doc["dimension"] = "3D"

    # normalise nested sentence values first so the folds below tag cleanly
    def normalise_early(node: Any) -> None:
        if isinstance(node, dict):
            value = node.get("dimension")
            if isinstance(value, str) and value.startswith("3D only"):
                node["dimension"] = "3D"
            for child in node.values():
                normalise_early(child)
        elif isinstance(node, list):
            for item in node:
                normalise_early(item)

    normalise_early(doc)

    if "dimension_differences" in doc:
        fold_dimension_differences(doc, rel, stats)

    if "dimension_caveat" in doc:
        notes("MPoint2D: " + doc.pop("dimension_caveat"))
        stats.folds += 1
    if "dimension_note" in doc:
        notes(doc.pop("dimension_note"))
        stats.folds += 1

    if "mpoint2d_only_elements" in doc:
        for name, info in doc.pop("mpoint2d_only_elements").items():
            notes(f"MPoint2D-only element: {name} — {info['description']} Syntax: {info['syntax']}.")
            doc.setdefault("verification", []).extend(info.get("verification", []))
        stats.folds += 1

    if "related_3d_only" in doc:
        block = doc.pop("related_3d_only")
        notes("FLAC3D-only structure types: " + ", ".join(block["structure_types"]) + ".", *block.get("notes", []))
        stats.folds += 1

    if "keywords_3d_only" in doc:  # beam-pile: the FLAC3D split principal-axis section set
        block = doc.pop("keywords_3d_only")
        property_set_group(
            doc, "beam/pile section (FLAC3D split principal-axis form)", block["beam_pile_section"], "3D"
        )
        notes(*block.get("notes", []))
        stats.folds += 1

    if "flac3d_liner_property_set" in doc:
        block = doc.pop("flac3d_liner_property_set")
        notes(block["description"], *block.get("notes", []))
        property_set_group(doc, "liner (FLAC3D-only keywords)", block["flac3d_only_keywords"], "3D")
        property_set_group(doc, "liner (FLAC2D-only keywords)", block["flac2d_only_keywords"], "2D")
        property_set_group(doc, "liner coupling (shared 2D/3D)", block["shared_coupling_keywords"], None)
        stats.folds += 1
    for key, label in (("flac3d_shell_property_set", "shell"), ("flac3d_geogrid_property_set", "geogrid")):
        if key in doc:
            block = doc.pop(key)
            notes(block["description"], *block.get("notes", []))
            property_set_group(doc, f"{label} (FLAC3D-only element type)", block["keywords"], "3D")
            stats.folds += 1

    # nested sentence dimensions (mpoint element entries)
    def normalise_nested(node: Any) -> None:
        if isinstance(node, dict):
            value = node.get("dimension")
            if isinstance(value, str) and value not in ("2D", "3D"):
                if value.startswith("3D only"):
                    node["dimension"] = "3D"
                elif value == "mixed":
                    del node["dimension"]
                else:
                    odd(f"nested dimension {value!r}")
            if "dimension_caveat" in node:
                node.setdefault("notes", []).append("MPoint2D: " + node.pop("dimension_caveat"))
                stats.folds += 1
            for child in node.values():
                normalise_nested(child)
        elif isinstance(node, list):
            for item in node:
                normalise_nested(item)

    normalise_nested(doc)
    return json.dumps(doc, sort_keys=True) != before


def main() -> int:
    write = "--write" in sys.argv
    stats = Stats()

    for pattern, migrate in (("*/python_sdk_docs/**/*.json", None), ("*/references/**/*.json", migrate_reference)):
        for path in sorted(RESOURCES.glob(pattern)):
            rel = path.relative_to(RESOURCES).as_posix()
            if any(skip in rel for skip in SKIP_PATHS):
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                continue
            changed = migrate(doc, rel, stats) if migrate else migrate_python_node(doc, rel, stats)
            if changed:
                stats.files += 1
                print(f"changed  {rel}")
                if write:
                    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # the mpoint command_docs configure block
    path = RESOURCES / "mpoint/command_docs/commands/model/configure.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    if "dimension_differences" in doc:
        fold_dimension_differences(doc, "mpoint/command_docs/commands/model/configure.json", stats)
        stats.files += 1
        print("changed  mpoint/command_docs/commands/model/configure.json")
        if write:
            path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"\npython dimension tags: {stats.python_tags}; reference folds: {stats.folds}; "
        f"files changed: {stats.files}" + ("" if write else " (dry run)")
    )
    if stats.oddities:
        print("\nODDITIES:")
        print("\n".join(stats.oddities))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
