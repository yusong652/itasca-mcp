"""Fold free prose into ``notes: list[str]`` per the corpus spec (section C).

Two layers, applied to command_docs, python_sdk_docs and references (the fish
tree is generator-owned and migrates by regenerating):

1. Mechanical, at every nesting level:
   - scalar ``note`` merges into ``notes``; string ``notes`` becomes a one-item
     list; empty ``notes`` lists are dropped
   - ``warning``/``caveat`` strings become ``Warning:``/``Caveat:`` notes;
     ``tips`` lists merge into ``notes``

2. Curated fold of the ad-hoc top-level sections in command_docs (the 2025-era
   hand-written PFC enrichments). Reviewed instance by instance on 2026-11-09:
   - sections whose content restates the command's description, keywords or
     examples (workflows, use cases, troubleshooting Q&A, performance boiler-
     plate, *_vs_* comparisons, when-to-use advice) are DROPPED - the dry run
     prints every dropped instance
   - operative engine facts they contained survive as hand-condensed notes in
     KEEP_NOTES below
   - keyword-shaped lists (modifiers, export/bin keywords, history quantity
     tables) fold into one compact note each; ``important_notes`` merge into
     ``notes`` verbatim; ``related_commands`` become one ``Related commands:``
     note
   - keys belonging to later spec concerns are left in place: ``plot_items``
     (keywords step), ``dimension_differences``/``independent_dimensions``
     (dimension step), ``live_verification`` (verification step)

Usage:
    uv run python scripts/corpus/migrate_notes.py [--write]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"

# ---------------------------------------------------------------------------
# Curated decisions for command_docs ad-hoc sections
# ---------------------------------------------------------------------------

# Top-level keys that are part of the command schema, never sections.
CORE_KEYS = {
    "category",
    "search_keywords",
    "description",
    "python_sdk_alternative",
    "versions",
    "notes",
    "note",
    "command",
    "syntax",
    "keywords",
    "examples",
    "available",
    "engines",
    "figure_reference",
    "warning",
    "warnings",
    "tips",
}

# Handled by later migration steps; left untouched.
DEFERRED_KEYS = {"plot_items", "dimension_differences", "independent_dimensions", "live_verification"}

RELATED_KEYS = {"related_commands", "related_models", "related_modules", "see_also", "related"}

# Sections folded by a generic renderer: key -> note title.
KEYWORD_LIST_SECTIONS = {
    "modifiers": "Modifiers",
    "geometry_keywords": "Geometry set keywords",
    "bin_keywords": "Bin keywords",
    "attribute_keywords": "Listable attributes",
    "common_attributes": "Recordable attributes",
    "quantity_categories": "History quantities",
    "common_properties": "Common properties per model",
}

# Engine facts condensed by hand from the dropped sections (2026-11-09 review).
_C = "pfc/command_docs/commands"
KEEP_NOTES: dict[str, list[str]] = {
    f"{_C}/contact/activate.json": [
        "Priority: inhibit overrides activate; the contact model only controls activity when both "
        "flags are off. Setting activate on automatically clears the inhibit flag.",
        "For ball-facet and pebble-facet contacts, activate on sets the activity state directly, "
        "regardless of the contact resolution strategy.",
        "An activated contact can still be deleted by the contact detection system once the pieces "
        "move beyond the detection distance.",
    ],
    f"{_C}/contact/apply-group.json": [
        "A piece or body touched by several differently-grouped contacts gets the group of whichever "
        "contact is traversed last - effectively non-deterministic. Restrict with the group keyword.",
    ],
    f"{_C}/contact/cmat-default.json": [
        "Without the type keyword every default slot changes; with type only that contact type. "
        "The default entry is the fallback; add creates rules that are checked before it.",
    ],
    f"{_C}/contact/cmat-list.json": [
        "Entries are checked lowest index first; entry 0 is the default fallback.",
    ],
    f"{_C}/contact/cmat-modify.json": [
        "Only the specified keywords change; the entry's other settings are retained - except a model "
        "change, which discards the previous model's properties.",
    ],
    f"{_C}/contact/cmat-proximity.json": [
        "Negative proximity requires that much overlap before a contact is created; pieces can "
        "interpenetrate noticeably before forces appear.",
        "Changing proximity affects future detection only: existing contacts are not re-detected, and "
        "contact cmat apply does not re-run detection - use model clean.",
    ],
    f"{_C}/contact/cmat-remove.json": [
        "Removing entry i shifts all later entries down by one. Entry 0 is the fallback default and "
        "should normally not be removed. Removal only affects future contacts; existing contacts keep "
        "their models until contact cmat apply.",
    ],
    f"{_C}/contact/delete.json": [
        "Deletion is only permanent while contact detection is off or once the pieces are beyond the "
        "detection distance; otherwise detection recreates the contact. Reversible alternatives: "
        "contact model null, or contact inhibit.",
    ],
    f"{_C}/contact/detection.json": [
        "model clean has no effect while detection is off.",
        "Detection can be toggled independently per contact type (ball-ball, ball-facet, ball-pebble, "
        "pebble-pebble, pebble-facet, ball-rblock, pebble-rblock, rblock-facet, rblock-rblock); all "
        "start on.",
    ],
    f"{_C}/contact/fix.json": [
        "fix on freezes all force components at their current values until fix off; the model still "
        "evaluates but cannot update them. Unfixing can make forces jump to match the current "
        "configuration.",
    ],
    f"{_C}/contact/group.json": [
        "add assigns the name to the first empty slot of every contact and cannot be combined with "
        "range; remove strips the name from every slot where it appears.",
    ],
    f"{_C}/contact/inhibit.json": [
        "Inhibit has the highest priority: an inhibited contact stays inactive regardless of the "
        "activate flag. contact activate on clears the inhibit flag.",
    ],
    f"{_C}/contact/method.json": [
        "Methods per model: deformability (emod, kratio) on linear, linearpbond, linearcbond, "
        "rrlinear, arrlinear, smoothjoint and flatjoint; bond (gap) on the bonded models; "
        "pb_deformability additionally on linearpbond. kratio relates to Poisson's ratio roughly as "
        "(2-2v)/(1-2v).",
        "Set bond strength properties before invoking bond; the method activates the bond and "
        "initializes its geometry at contacts with gap at or below the given value.",
    ],
    f"{_C}/contact/model.json": [
        "Assigning a model replaces the previous one and discards all of its property data; set the "
        "new model's properties afterwards.",
    ],
    f"{_C}/contact/persist.json": [
        "Setting persistence on a non-mechanical (e.g. thermal) contact also turns it on for the "
        "corresponding mechanical contact.",
        "Persistence does not survive piece deletion: deleting either piece deletes the contact.",
    ],
    f"{_C}/contact/property.json": [
        "Inheritable from piece properties: kn, ks, fric, hz_shear, hz_poiss, rr_fric. Not "
        "inheritable: rgap, lin_mode, dp_nratio, pb_ten, pb_coh.",
    ],
    f"{_C}/fragment/activate.json": [
        "Requires contact persistence (pb_persist true) on the registered contact types; activation fails without it.",
        "Auto-computation does not notice manual contact changes (contact delete, unbonding); call "
        "fragment compute afterwards.",
    ],
    f"{_C}/fragment/compute.json": [
        "With fragment persistence on, isolated bodies get fragment ID 0 (tag them with "
        "group-isolated); with persistence off they get unique IDs instead.",
    ],
    f"{_C}/fragment/clear.json": [
        "Resets every fragment ID to 0 and erases the history; the auto-computation state is left as "
        "it was. Not undoable.",
    ],
    f"{_C}/fragment/deactivate.json": [
        "Stops auto-computation only; fragment IDs and history survive, and fragment compute still works manually.",
    ],
    f"{_C}/fragment/list.json": [
        "The same fragment ID in different catalogs may be different physical clusters; use "
        "fragment list id <i> to trace one fragment through time.",
    ],
    f"{_C}/fragment/register.json": [
        "Needs at least one active contact (run model clean first). By default only bonded contacts "
        "connect a fragment; ignorebond counts every active contact.",
        "persist false keeps only the current state and disallows fragment activate. A range given "
        "here sticks until fragment clear.",
    ],
    f"{_C}/measure/create.json": [
        "Measurements are computed only on model clean or when a FISH intrinsic queries them, never continuously.",
        "Bodies cut by the region boundary are processed in decreasing volume order until the "
        "remainder is below tolerance x total volume, so porosity is slightly overestimated for "
        "tolerance > 0; clump intersections are voxelized (5 recursive bisections).",
    ],
    f"{_C}/measure/delete.json": [
        "No undo; the freed ID can be reused explicitly with measure create id <i>.",
    ],
    f"{_C}/measure/dump.json": [
        "Requires bins on the measurement. The file keyword is not implemented - dump to a table and "
        "use table export. An existing table is overwritten silently.",
    ],
    f"{_C}/measure/history.json": [
        "Two id keywords: the first (right after history) is the optional history ID, the second "
        "(after the quantity) is the measurement ID.",
        "3D-only tensor components (zz, xz, yz, zx, zy) are errors in 2D models.",
    ],
    f"{_C}/measure/list.json": [
        "Values are stale until model clean recalculates them.",
    ],
    f"{_C}/measure/modify.json": [
        "Only the attributes given change; results update only after model clean. The position vector "
        "form and the x/y/z component form cannot be mixed in one command.",
    ],
    f"{_C}/wall/initialize.json": [
        "Synonym of wall attribute.",
    ],
    f"{_C}/wall/resolution.json": [
        "full: sliver penetration handled, cutoff-angle active, proximity contacts and state "
        "propagation, slow but accurate. reduced: none of those, medium cost. none: fastest, but may "
        "create many contacts.",
    ],
    f"{_C}/wall/servo.json": [
        "Servo mechanism: v_s(new) = v_s(old) + G(F_target - F_reaction) with G = a*dt/K_eff "
        "(a = gain-factor, default 0.8; K_eff = sum of contact stiffnesses); only the velocity "
        "component along the target force direction is adjusted.",
    ],
    f"{_C}/wall/tolerance.json": [
        "Facet extent = min_extent + 2*(max_interaction_dist + tol_constant + "
        "max_extent_length*tol_extent + max_velocity*tol_velocity); the constant tolerance is "
        "per-facet, the extent and velocity tolerances are global.",
    ],
    f"{_C}/wall/velocity-conveyor.json": [
        "The wall geometry never rotates; facet conveyor velocities (omega x r, projected onto the "
        "facet plane) are added to the wall velocity in relative-velocity calculations.",
    ],
}


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_keyword_list(title: str, value: Any) -> str:
    if isinstance(value, dict):  # quantity_categories / common_properties dict form
        body = "; ".join(f"{k}: {', '.join(map(str, v))}" for k, v in value.items())
    elif isinstance(value, list) and value and isinstance(value[0], dict):
        parts = []
        for e in value:
            name = e.get("syntax") or e.get("name") or e.get("model") or ""
            desc = e.get("description") or ", ".join(map(str, e.get("properties", [])))
            parts.append(f"{name}: {desc}" if desc else str(name))
        body = "; ".join(parts)
    else:
        body = ", ".join(map(str, value))
    return f"{title}: {body}"


def ensure_notes(node: dict[str, Any]) -> list[str]:
    notes = node.get("notes")
    if isinstance(notes, str):
        notes = [notes]
    elif not isinstance(notes, list):
        notes = []
    node["notes"] = notes
    return notes


# ---------------------------------------------------------------------------
# Passes
# ---------------------------------------------------------------------------


class Stats:
    def __init__(self) -> None:
        self.dropped: list[str] = []
        self.folded = 0
        self.kept_notes = 0
        self.mechanical = 0
        self.files = 0


def fold_command_sections(doc: dict[str, Any], rel: str, stats: Stats) -> bool:
    changed = False
    for key in [k for k in doc if k not in CORE_KEYS and k not in DEFERRED_KEYS]:
        value = doc.pop(key)
        changed = True
        if key in RELATED_KEYS:
            ensure_notes(doc).append("Related commands: " + ", ".join(map(str, value)))
            stats.folded += 1
        elif key == "important_notes":
            ensure_notes(doc).extend(str(v) for v in value)
            stats.folded += 1
        elif key == "synonym_of":
            # covered by the hand-written note in KEEP_NOTES
            stats.dropped.append(f"{rel}: {key}")
        elif key in KEYWORD_LIST_SECTIONS:
            ensure_notes(doc).append(render_keyword_list(KEYWORD_LIST_SECTIONS[key], value))
            stats.folded += 1
        else:
            stats.dropped.append(f"{rel}: {key}")
    if rel in KEEP_NOTES:
        ensure_notes(doc).extend(KEEP_NOTES.pop(rel))
        stats.kept_notes += 1
        changed = True
    return changed


def mechanical(node: Any, stats: Stats, *, drop_warning_dicts: bool) -> bool:
    """note/notes/warning/caveat/tips normalisation at every level."""
    changed = False
    if isinstance(node, dict):
        if isinstance(node.get("notes"), str):
            node["notes"] = [node["notes"]]
            stats.mechanical += 1
            changed = True
        if node.get("notes") == []:
            del node["notes"]
            stats.mechanical += 1
            changed = True
        if isinstance(node.get("note"), str):
            ensure_notes(node).append(node.pop("note"))
            stats.mechanical += 1
            changed = True
        if isinstance(node.get("warning"), str):
            ensure_notes(node).append("Warning: " + node.pop("warning"))
            stats.mechanical += 1
            changed = True
        if isinstance(node.get("caveat"), str):
            ensure_notes(node).append("Caveat: " + node.pop("caveat"))
            stats.mechanical += 1
            changed = True
        if isinstance(node.get("tips"), list):
            ensure_notes(node).extend(str(v) for v in node.pop("tips"))
            stats.mechanical += 1
            changed = True
        if drop_warning_dicts and isinstance(node.get("warnings"), list):
            # command_docs 'warnings' dicts restate description/keep-notes; reviewed and dropped.
            del node["warnings"]
            stats.mechanical += 1
            changed = True
        for child in list(node.values()):
            changed = mechanical(child, stats, drop_warning_dicts=drop_warning_dicts) or changed
    elif isinstance(node, list):
        for child in node:
            changed = mechanical(child, stats, drop_warning_dicts=drop_warning_dicts) or changed
    return changed


def main() -> int:
    write = "--write" in sys.argv
    stats = Stats()

    for tree, is_commands in (("command_docs", True), ("python_sdk_docs", False), ("references", False)):
        for path in sorted(RESOURCES.glob(f"*/{tree}/**/*.json")):
            rel = path.relative_to(RESOURCES).as_posix()
            doc = json.loads(path.read_text(encoding="utf-8"))
            changed = False
            if is_commands and "/commands/" in rel and isinstance(doc, dict):
                changed = fold_command_sections(doc, rel, stats)
            changed = mechanical(doc, stats, drop_warning_dicts=is_commands) or changed
            if changed:
                stats.files += 1
                if write:
                    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if KEEP_NOTES:
        raise SystemExit(f"KEEP_NOTES entries never matched a file: {sorted(KEEP_NOTES)}")
    print("\n".join(f"dropped  {d}" for d in stats.dropped))
    print(
        f"\nsections dropped: {len(stats.dropped)}; sections folded: {stats.folded}; "
        f"files with hand-written keep-notes: {stats.kept_notes}; mechanical edits: {stats.mechanical}; "
        f"files changed: {stats.files}" + ("" if write else " (dry run)")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
