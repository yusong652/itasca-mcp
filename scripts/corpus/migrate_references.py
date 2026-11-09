"""Fold every references page onto its archetype (corpus spec, section F).

Five page kinds — model, range-element, plot/data item, topic, file-format —
plus the category indexes. Everything a file carries outside its archetype's
field set is folded by the C-E rules: live enumerations and binary-validation
records go to ``verification``; keyword vocabularies go to ``keywords`` (with
``group``); command patterns go to ``examples``; operative prose goes to
``notes``; restatement padding (application lists, theory essays, *_vs_*
comparisons, workflow boilerplate on model pages) is dropped — the dry run
prints every drop.

Deferred to step B (dimension): ``*/references/dimension-differences/``,
``dimension_differences`` / ``independent_dimensions`` / ``dimension_note``,
``flac3d_*_property_set`` / ``keywords_3d_only`` / ``related_3d_only`` /
``mpoint2d_only_elements``.

Usage:
    uv run python scripts/corpus/migrate_references.py [--write]
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"

DEFERRED_KEYS = {
    "legacy_documentation",
    "dimension_differences",
    "independent_dimensions",
    "dimension_note",
    "flac3d_liner_property_set",
    "flac3d_shell_property_set",
    "flac3d_geogrid_property_set",
    "keywords_3d_only",
    "related_3d_only",
    "mpoint2d_only_elements",
}
DEFERRED_PATHS = ("references/dimension-differences/",)

# Hand-condensed replacements for the chart-history troubleshooting table
# (reviewed: two real failure modes, the rest restates critical_note).
TROUBLESHOOTING_KEEP = {
    "_common/references/plot-items/chart-history.json": [
        "Empty chart with an absurd axis exponent (~1e301): no valid trace is bound — pass the exact Name "
        "from 'history list' (a numeric ID silently binds nothing).",
        "Curve flat at zero: the model has not cycled since the history was created, so only the initial "
        "sample exists.",
    ]
}


@dataclass
class Stats:
    folded: int = 0
    dropped: list[str] = field(default_factory=list)
    files: int = 0
    oddities: list[str] = field(default_factory=list)


class Page:
    """One file being folded; helpers accumulate into the canonical fields."""

    def __init__(self, doc: dict[str, Any], rel: str, stats: Stats):
        self.doc = doc
        self.rel = rel
        self.stats = stats
        self.changed = False

    def take(self, key: str) -> Any:
        self.changed = True
        self.stats.folded += 1
        return self.doc.pop(key)

    def drop(self, key: str) -> None:
        value = self.doc.pop(key)
        self.changed = True
        self.stats.dropped.append(f"{self.rel}: {key} = {json.dumps(value, ensure_ascii=False)[:150]}")

    def odd(self, message: str) -> None:
        self.stats.oddities.append(f"{self.rel}: {message}")

    def notes(self, *lines: str, first: bool = False) -> None:
        target = self.doc.setdefault("notes", [])
        if first:
            target[0:0] = list(lines)
        else:
            target.extend(lines)

    def verification(self, *lines: str) -> None:
        self.doc.setdefault("verification", []).extend(lines)

    def keywords(self, entries: list[dict[str, Any]]) -> None:
        self.doc.setdefault("keywords", []).extend(entries)

    def attributes(self, entries: list[dict[str, Any]]) -> None:
        self.doc.setdefault("attributes", []).extend(entries)

    def examples(self, entries: list[Any]) -> None:
        self.doc.setdefault("examples", []).extend(entries)


def _named(items: list[Any], group: str | None = None) -> list[dict[str, Any]]:
    out = []
    for item in items:
        entry = {"name": item} if isinstance(item, str) else dict(item)
        for alias in ("keyword", "type"):
            if alias in entry and "name" not in entry:
                entry["name"] = entry.pop(alias)
        if "trap" in entry:
            entry.setdefault("notes", []).append("Trap: " + entry.pop("trap"))
        if group:
            entry["group"] = group
        out.append(entry)
    return out


def _tokens_line(label: str, tokens: list[str]) -> str:
    return f"{label} ({len(tokens)}): {', '.join(tokens)}"


def _pattern_examples(page: Page, patterns: list[Any]) -> None:
    """common_usage_patterns / common_patterns -> examples entries."""
    for pattern in patterns:
        if isinstance(pattern, str):
            page.examples([{"command": pattern}])
            continue
        commands = pattern.get("commands") or [pattern[k] for k in ("command", "example") if k in pattern]
        description = pattern.get("description") or pattern.get("name") or ""
        use_case = pattern.get("use_case")
        if use_case:
            description = f"{description.rstrip('.')}. Use case: {use_case}" if description else use_case
        unknown = set(pattern) - {"commands", "command", "example", "description", "name", "use_case", "notes"}
        if unknown:
            page.odd(f"pattern keys {sorted(unknown)}")
            return
        entry: dict[str, Any] = {"command": "\n".join(commands)}
        if description:
            entry["description"] = description
        page.examples([entry])
        if pattern.get("notes"):
            page.notes(*pattern["notes"])


# --- handlers: field name -> fold action ------------------------------------


def h_drop(page: Page, key: str) -> None:
    page.drop(key)


def h_notes(page: Page, key: str) -> None:
    value = page.take(key)
    page.notes(*(value if isinstance(value, list) else [value]))


def h_notes_first(page: Page, key: str) -> None:
    value = page.take(key)
    page.notes(*(value if isinstance(value, list) else [value]), first=True)


def h_verification(page: Page, key: str) -> None:
    value = page.take(key)
    if isinstance(value, str):
        page.verification(value)
    elif isinstance(value, list) and all(isinstance(v, str) and " " not in v for v in value):
        page.verification(_tokens_line(f"{key.replace('_', ' ')}", value))
    elif isinstance(value, list):
        page.verification(*value)
    else:
        page.odd(f"{key}: unhandled verification shape {type(value).__name__}")


def h_patterns(page: Page, key: str) -> None:
    _pattern_examples(page, page.take(key))


def h_item_type(page: Page, key: str) -> None:
    value = page.take(key)
    # "structure-*" (family wildcard) and "pfc_specific" (an engine tag in the
    # pfc tree) carry nothing the path does not already say.
    if value in ("structure-*", "pfc_specific"):
        return
    if value not in page.rel and value != page.doc.get("name"):
        page.odd(f"item_type {value!r} not derivable from path")


def grouped_keywords(group: str | None) -> Callable[[Page, str], None]:
    def handler(page: Page, key: str) -> None:
        page.keywords(_named(page.take(key), group))

    return handler


def grouped_attributes(group: str | None) -> Callable[[Page, str], None]:
    def handler(page: Page, key: str) -> None:
        page.attributes(_named(page.take(key), group))

    return handler


def h_related_list(label: str) -> Callable[[Page, str], None]:
    def handler(page: Page, key: str) -> None:
        value = page.take(key)
        if isinstance(value, dict):
            page.notes(f"{label}: " + "; ".join(f"{k} — {v}" for k, v in value.items()))
        elif all(isinstance(v, str) for v in value):
            page.notes(f"{label}: " + ", ".join(value))
        else:
            page.notes(
                f"{label}: "
                + "; ".join(f"{e.get('model') or e.get('name')} — {e.get('description', '')}" for e in value)
            )

    return handler


def h_dict_note(label: str) -> Callable[[Page, str], None]:
    def handler(page: Page, key: str) -> None:
        value = page.take(key)
        page.notes(f"{label}: " + "; ".join(f"{k}: {v}" for k, v in value.items()))

    return handler


MODEL_HANDLERS: dict[str, Callable[[Page, str], None]] = {
    "typical_applications": h_drop,
    "workflow": h_drop,
    "comparison_to_linear_model": h_drop,
    "hertzian_contact_theory": h_drop,
    "key_differences_from_linearcbond": h_drop,
    "physical_interpretation": h_drop,
    "key_characteristics": h_notes,
    "related_models": h_related_list("Related models"),
    "common_usage_patterns": h_patterns,
}


def h_typical_values(page: Page, key: str) -> None:
    for material, params in page.take(key).items():
        page.notes(
            f"Typical values ({material.replace('_', ' ')}): " + ", ".join(f"{k} {v}" for k, v in params.items())
        )


def h_energy_partitions(page: Page, key: str) -> None:
    for e in page.take(key):
        line = f"Energy partition {e['name']} ({e.get('symbol', '')}): {e.get('description', '')}"
        if e.get("accumulated"):
            line += " Accumulated."
        page.notes(line)


def h_available_methods(page: Page, key: str) -> None:
    for group in page.take(key):
        parts = []
        for m in group.get("methods", []):
            text = f"{m['name']} — {m.get('description', '')}"
            if m.get("typical_args"):
                text += f" (args: {', '.join(m['typical_args'])})"
            parts.append(text)
        page.notes(f"Methods ({group.get('group', 'general')}): " + "; ".join(parts))


def h_callback_events(page: Page, key: str) -> None:
    value = page.doc[key]
    if isinstance(value, list):  # normalise to the {description?, events} form
        page.doc[key] = {"events": value}
        page.changed = True
        page.stats.folded += 1


def h_index_expansion(page: Page, key: str) -> None:
    # Load-bearing structure (tests check doc completeness against the live
    # 96-entry table through it); only the inner list takes the canonical name.
    value = page.doc[key]
    if "indexed_keywords" in value:
        value["keywords"] = [{"name": n} for n in value.pop("indexed_keywords")]
        page.changed = True
        page.stats.folded += 1


MODEL_HANDLERS.update(
    {
        "typical_parameter_values": h_typical_values,
        "energy_partitions": h_energy_partitions,
        "available_methods": h_available_methods,
        "callback_events": h_callback_events,
        "index_expansion": h_index_expansion,
    }
)

RANGE_HANDLERS: dict[str, Callable[[Page, str], None]] = {
    "command_examples": lambda page, key: page.examples(page.take(key)),
    "related": h_related_list("Related"),
    "element_type": h_item_type,
    "common_pitfall": h_notes,
}


def h_history_sources(page: Page, key: str) -> None:
    value = page.take(key)
    description = value.pop("description", "")
    page.notes((description + " " if description else "") + "; ".join(f"{k}: {v}" for k, v in value.items()))


def h_troubleshooting(page: Page, key: str) -> None:
    keep = TROUBLESHOOTING_KEEP.pop(page.rel, None)
    if keep is None:
        page.odd("troubleshooting with no reviewed replacement")
        return
    page.drop(key)
    page.notes(*keep)


def h_legend_settings(page: Page, key: str) -> None:
    value = page.take(key)
    if set(value) - {"description", "example", "keywords"}:
        page.odd(f"legend_settings keys {sorted(value)}")
        return
    page.notes("Legend: " + value["description"])
    if value.get("example"):
        page.examples([{"command": value["example"], "description": "Legend settings"}])
    page.keywords(_named(value.get("keywords", []), "legend"))


def h_usage_pattern(page: Page, key: str) -> None:
    value = page.take(key)
    if set(value) == {"inputs", "outputs"}:  # massflow file-formats index
        page.notes(f"Import: {value['inputs']}", f"Export: {value['outputs']}")
        return
    if set(value) - {"syntax", "examples", "notes"}:
        page.odd(f"usage_pattern keys {sorted(value)}")
        return
    if value.get("syntax"):
        if "syntax" in page.doc:
            page.odd("usage_pattern.syntax collides with doc syntax")
        else:
            page.doc["syntax"] = value["syntax"]
    page.examples(value.get("examples", []))
    page.notes(*value.get("notes", []))


def h_by_type_notes(page: Page, key: str) -> None:
    for kind, tokens in page.take(key).items():
        text = tokens if isinstance(tokens, str) else ", ".join(tokens)
        page.notes(f"{kind} top-level keywords: {text}")


def _argument_types(page: Page, types: dict[str, str]) -> None:
    """Attach each keyword's live-probed argument type to its keyword entry."""
    entries = {e.get("name"): e for e in page.doc.get("keywords", []) if isinstance(e, dict)}
    for name, description in types.items():
        entry = entries.get(name)
        if entry is None:
            page.odd(f"argument type for unknown keyword {name!r}")
            continue
        entry.setdefault("notes", []).append(f"Argument: {description}")


def h_official_sources(page: Page, key: str) -> None:
    value = page.take(key)
    if "source" in page.doc:
        existing = page.doc["source"]
        value = ([existing] if isinstance(existing, str) else list(existing)) + value
    page.doc["source"] = value


PLOT_HANDLERS: dict[str, Callable[[Page, str], None]] = {
    "usage_in_creation": lambda p, k: p.notes("During creation: " + p.take(k)),
    "usage_in_modification": lambda p, k: p.notes("On 'plot item modify': " + p.take(k)),
    "modifiers": grouped_keywords("modifier"),
    "label_types": grouped_keywords("label-type"),
    "available_types": grouped_keywords("label-type"),
    "size_by": grouped_keywords("size-by"),
    "top_level_keywords_9x": grouped_keywords(None),
    "top_level_keywords_9x_note": h_notes,
    "undocumented_modifiers": grouped_keywords("undocumented"),
    "item_type": h_item_type,
    "legend_settings": h_legend_settings,
    "critical_note": h_notes_first,
    "history_sources_per_engine": h_history_sources,
    "troubleshooting": h_troubleshooting,
    "unified_kernel_note": h_notes,
    "probing_recipe": h_notes,
    "attributes_by_type_note": h_notes,
    "flac3d_notes": h_notes,
    "shared_attributes": grouped_attributes("shared"),
    "beam_only_attributes": grouped_attributes("beam-only"),
    "cable_only_attributes": grouped_attributes("cable-only"),
    "available_attributes": grouped_attributes(None),
    "attributes_flac3d_97_beam_family": h_verification,
    "accepted_tokens_flac3d_97": h_verification,
    "available_types_flac3d_97": h_verification,
    "top_level_keywords_flac3d_97": h_verification,
    "verification_70": h_verification,
    "top_level_keywords_by_type": h_by_type_notes,
    "top_level_keywords_note": h_notes,
    "top_level_keywords_beam_family": lambda p, k: p.notes(_tokens_line("Beam-family top-level keywords", p.take(k))),
    "top_level_keywords_structure_vector": lambda p, k: p.notes(
        _tokens_line("structure-vector top-level keywords", p.take(k))
    ),
    "keyword_argument_types": lambda p, k: _argument_types(p, p.take(k)),
    "related_item_types": h_related_list("Related item types"),
    "related_note": h_notes,
    "related_commands": h_related_list("Related commands"),
    "common_usage_patterns": h_patterns,
    "common_patterns": h_patterns,
    "usage_pattern": h_usage_pattern,
    "usage_context": h_notes,
    "usage_contexts": h_notes,
    "official_sources": h_official_sources,
    "property_metadata_fields": h_drop,
    "navigation": h_drop,
    "related_documentation": h_dict_note("Related documentation"),
}


def h_group_dissolve(list_key: str) -> Callable[[Page, str], None]:
    """keyword_groups / field_groups -> keywords tagged with their group."""

    def handler(page: Page, key: str) -> None:
        for group in page.take(key):
            label = group.get("group") or group.get("name")
            page.keywords(_named(group.get(list_key, []) or group.get("names", []), label))
            for entry in _named(group.get("keywords_3d_only", []), label):
                page.keywords([{**entry, "dimension": "3D"}])
            page.notes(*group.get("notes", []))
            unknown = set(group) - {"group", "name", list_key, "names", "keywords_3d_only", "notes"}
            if unknown:
                page.odd(f"{key} group keys {sorted(unknown)}")

    return handler


def h_methods(page: Page, key: str) -> None:
    for method in page.take(key):
        name = method.get("method") or method.get("name") or ""
        description = method.get("description", "")
        commands = method.get("commands") or ([method["command"]] if "command" in method else [])
        unknown = set(method) - {"method", "name", "description", "commands", "command", "notes", "example"}
        if unknown:
            page.odd(f"{key} entry keys {sorted(unknown)}")
            return
        if method.get("example"):
            commands = commands or [method["example"]]
        entry: dict[str, Any] = {"command": "\n".join(commands)}
        text = f"{name}: {description}".strip(": ")
        if text:
            entry["description"] = text
        page.examples([entry])
        page.notes(*method.get("notes", []))


def h_concepts(page: Page, key: str) -> None:
    for c in page.take(key):
        name = c.get("concept") or c.get("name") or c.get("object")
        page.notes(f"{name}: {c.get('description') or c.get('role', '')}")


def h_property_sets(page: Page, key: str) -> None:
    value = page.take(key)
    description = value.pop("description", None)
    if description:
        page.notes(description)
    groups = page.doc.setdefault("property_groups", [])
    for cmodel, props in value.items():
        groups.append({"group_name": cmodel, "properties": [{"keyword": p} for p in props]})


def h_assignment_trap(page: Page, key: str) -> None:
    value = page.take(key)
    page.notes(value["description"], "Workaround: " + value["workaround"])
    page.verification(*(value["verification"] if isinstance(value["verification"], list) else [value["verification"]]))


def h_cmodel_support(page: Page, key: str) -> None:
    value = page.take(key)
    notes = value.pop("notes", [])
    for kind, models in value.items():
        page.notes(f"{kind} supports cmodels: " + ", ".join(models))
    page.notes(*(notes if isinstance(notes, list) else [notes]))


def h_flac3d_97_subcommands(page: Page, key: str) -> None:
    value = page.take(key)
    page.verification(_tokens_line("FLAC3D 9.7 subcommands", value["subcommands"]), *value.get("notes", []))


TOPIC_HANDLERS: dict[str, Callable[[Page, str], None]] = {
    "common_patterns": h_patterns,
    "common_usage_patterns": h_patterns,
    "workflow": lambda p, k: p.doc.__setitem__("steps", p.take(k)),
    "methods": h_methods,
    "validation_checks": h_notes,
    "keyword_groups": h_group_dissolve("keywords"),
    "field_groups": h_group_dissolve("fields"),
    "data_types": grouped_keywords("data-type"),
    "syntax_note": h_notes,
    "modifiers": grouped_keywords("modifier"),
    "notes_general": h_notes,
    "formats": lambda p, k: p.notes("Formats: " + ", ".join(p.take(k))),
    "default_behavior": h_notes,
    "quantity_names": grouped_keywords("quantity"),
    "quantity_notes": h_notes,
    "fish_patterns": h_patterns,
    "related_commands_not_properties": h_dict_note("Commands, not properties"),
    "compatibility_notes": h_notes,
    "version_notes": h_notes,
    "workflow_hints": h_notes,
    "binary_validation_notes": h_verification,
    "valid_subcommands_binary": h_verification,
    "rejected_subcommands_note": h_verification,
    "enumeration_caveats": h_verification,
    "flac3d_97_subcommands": h_flac3d_97_subcommands,
    "concepts": h_concepts,
    "objects": h_concepts,
    "sampling_targets": lambda p, k: p.notes(
        *(f"History sampling '{t['command']}': {t['samples']} Field names: {t['field_names']}" for t in p.take(k))
    ),
    "cmodel_support_by_type": h_cmodel_support,
    "property_sets_by_cmodel": h_property_sets,
    "assignment_trap": h_assignment_trap,
    # file-format pages
    "commands": lambda p, k: p.doc.__setitem__("primary_commands", p.take(k)),
    "related_formats": h_related_list("Related formats"),
}

INDEX_HANDLERS: dict[str, Callable[[Page, str], None]] = {
    "official_sources": h_official_sources,
    "verification_70": h_verification,
    "usage_context": h_notes,
    "usage_contexts": h_notes,
    "usage_pattern": h_usage_pattern,
    "related_commands": h_related_list("Related commands"),
    "related_documentation": h_dict_note("Related documentation"),
    "property_metadata_fields": h_drop,
    "navigation": h_drop,
    "common_patterns": h_patterns,
    "common_usage_patterns": h_patterns,
    "live_note": h_verification,
    "live_item_type_enumeration_97": h_verification,
    "live_item_type_enumeration_70": h_verification,
    "binary_item_types": lambda p, k: p.verification(_tokens_line("Live binary item-type enumeration", p.take(k))),
    "verified_example_commands": lambda p, k: p.verification(*(f"Verified: {c}" for c in p.take(k))),
    "universal_properties": lambda p, k: p.doc.setdefault("property_groups", []).append(
        {"group_name": "universal", "properties": p.take(k)}
    ),
    "mpoint_selection_counts": lambda p, k: p.doc.__setitem__("measured", p.take(k)),
}


def h_mpoint_elements(label: str) -> Callable[[Page, str], None]:
    def handler(page: Page, key: str) -> None:
        for e in page.take(key):
            name = e.get("name") or e.get("element")
            rest = "; ".join(f"{k}: {v}" for k, v in e.items() if k not in ("name", "element"))
            page.notes(f"{label}: {name} — {rest}")

    return handler


INDEX_HANDLERS.update(
    {
        "mpoint_additional_elements": h_mpoint_elements("Additional element (live-verified on material points)"),
        "mpoint_inapplicable_elements": h_mpoint_elements("Inapplicable element on material points"),
    }
)

MODEL_CATS = {"constitutive-models", "contact-models", "joint-models"}


def archetype(rel: str) -> str:
    parts = rel.split("/")
    if parts[-1] == "index.json" and len(parts) <= 4:
        return "index"
    category = parts[2]
    if category in MODEL_CATS:
        return "model"
    if category == "range-elements":
        return "range-element"
    if category == "plot-items":
        return "plot-item"
    return "topic"


HANDLERS = {
    "model": MODEL_HANDLERS,
    "range-element": RANGE_HANDLERS,
    "plot-item": PLOT_HANDLERS,
    "topic": TOPIC_HANDLERS,
    "file-format": TOPIC_HANDLERS,
    "index": INDEX_HANDLERS,
}

ALLOWED_AFTER = {  # mirror of the sweep's archetype sets, for the strict check
    "model": {"model", "property_groups", "usage", "examples", "callback_events", "index_expansion"},
    "range-element": {
        "syntax",
        "category",
        "category_name",
        "parameters",
        "sub_keywords",
        "supports_extent",
        "examples",
    },
    "plot-item": {
        "syntax",
        "keywords",
        "modes",
        "attributes",
        "dimension",
        "examples",
        "sub_items",
        "items",
        "item_types",
    },
    "topic": {"dimension", "primary_commands", "keywords", "examples", "property_groups", "steps", "measured"},
    "file-format": {
        "dimension",
        "primary_commands",
        "keywords",
        "examples",
        "direction",
        "layout",
        "columns",
        "example",
    },
    "index": {
        "type",
        "category",
        "items",
        "models",
        "elements",
        "categories",
        "item_types",
        "sub_items",
        "keywords",
        "examples",
        "syntax",
        "dimension",
        "measured",
        "demo_mode_limits",
        "property_groups",
    },
}
CROSS = {"name", "full_name", "description", "notes", "verification", "source", "availability", "search_keywords"}


def main() -> int:
    write = "--write" in sys.argv
    stats = Stats()
    for path in sorted(RESOURCES.glob("*/references/**/*.json")):
        rel = path.relative_to(RESOURCES).as_posix()
        if any(deferred in rel for deferred in DEFERRED_PATHS):
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        arch = archetype(rel)
        if arch == "topic" and rel.split("/")[2] == "file-formats":
            arch = "file-format"
        page = Page(doc, rel, stats)
        handlers = HANDLERS[arch]
        for key in list(doc):
            if key in handlers:
                handlers[key](page, key)
        extra = set(doc) - ALLOWED_AFTER[arch] - CROSS - DEFERRED_KEYS
        if extra:
            page.odd(f"({arch}) unhandled keys {sorted(extra)}")
        if page.changed:
            stats.files += 1
            print(f"changed  {rel}")
            if write:
                path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if TROUBLESHOOTING_KEEP:
        raise SystemExit(f"troubleshooting keep-notes never matched: {sorted(TROUBLESHOOTING_KEEP)}")
    print("\nDROPPED:")
    print("\n".join(stats.dropped))
    print(
        f"\nfolds: {stats.folded}; drops: {len(stats.dropped)}; files changed: {stats.files}"
        + ("" if write else " (dry run)")
    )
    if stats.oddities:
        print("\nODDITIES:")
        print("\n".join(stats.oddities))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
