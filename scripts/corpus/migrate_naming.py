"""Unify naming and provenance fields per the corpus spec (section D).

Applied to command_docs, python_sdk_docs and references (the fish tree is
generator-owned: its index ``verification`` string becomes a list via
``generate_fish_docs.py``). Subtrees owned by later steps are left untouched:
``legacy_documentation`` (step A), ``dimension_differences`` /
``independent_dimensions`` (step B), ``plot_items`` (step E).

- ``parent`` / ``parent_item`` are deleted: the browse path already carries the
  hierarchy and no code reads them.
- ``base_syntax`` renames to ``syntax`` (those files have no ``syntax``).
- ``documented_syntax`` (the manual's spelling echo) is deleted; its only
  non-redundant payload, the "(PFC-specific)" tag on the shared ``contact``
  range element, becomes a note.
- ``alt_syntax`` (a real second calling form) folds into notes.
- ``source_url`` and ``official_documentation`` rename to ``source``.
- The live-test provenance family (``verified``, ``evidence``, ``live_notes``,
  ``live_verification*``, ``live_enumeration*``, ``binary_validated_*``)
  flattens into ``verification: list[str]``; ``validation_notes`` (workflow
  advice, not provenance) folds into ``notes``.
- command_docs example entries normalise to ``{command, description}``:
  bare strings become ``{command}``; ``use_case`` / ``model`` /
  ``output_example`` merge into ``description``.

Usage:
    uv run python scripts/corpus/migrate_naming.py [--write]
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"

DEFERRED_SUBTREES = {"legacy_documentation", "dimension_differences", "independent_dimensions", "plot_items"}

_TOKEN = re.compile(r"^[A-Za-z0-9?.<>=/'_-]+$")

_ENGINE_WORDS = {
    "flac3d": "FLAC3D",
    "flac2d": "FLAC2D",
    "mpoint3d": "MPoint3D",
    "mpoint2d": "MPoint2D",
    "pfc3d": "PFC3D",
    "pfc2d": "PFC2D",
}
_VERSION_WORDS = {"97": "9.7", "98": "9.8"}

_BINARY_VALIDATED_LABELS = {
    "binary_validated_modifier_set": "Binary-validated apply-modifier set",
    "binary_validated_modifier_set_3d_97": "Binary-validated apply-modifier set (FLAC3D 9.7)",
    "binary_validated_subcommands_flac3d": "Binary-validated subcommands (FLAC3D)",
}

# Field order inside a rendered verification dict, after the header.
_DICT_FIELD_ORDER = (
    "description",
    "keyword_lists",
    "result",
    "identical",
    "resolved",
    "runtime_seconds",
    "verified_state",
)


@dataclass
class Stats:
    renamed: int = 0
    deleted: int = 0
    folded_notes: int = 0
    verification_nodes: int = 0
    example_edits: int = 0
    files: int = 0
    oddities: list[str] = field(default_factory=list)


def _is_token_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and _TOKEN.match(v) for v in value)


_LABEL_WORDS = {
    "flac": "FLAC",
    "flac2d": "FLAC2D",
    "flac3d": "FLAC3D",
    "pfc": "PFC",
    "3dec": "3DEC",
    "2d": "2D",
    "3d": "3D",
}


def _label(key: str) -> str:
    words = [_LABEL_WORDS.get(w, w) for w in key.split("_")]
    if words[0] not in _LABEL_WORDS.values():
        words[0] = words[0][:1].upper() + words[0][1:]
    return " ".join(words)


def _build_from_suffix(key: str, prefix: str) -> str | None:
    suffix = key[len(prefix) :].strip("_")
    if not suffix or suffix == "notes":
        return None
    parts = [(_ENGINE_WORDS.get(p) or _VERSION_WORDS.get(p) or p) for p in suffix.split("_")]
    if all(p.isdigit() for p in parts):
        return ".".join(parts)
    return " ".join(parts)


def _render_dict(value: dict[str, Any], build: str | None, where: str, stats: Stats) -> list[str]:
    rest = dict(value)
    grade = rest.pop("grade", None)
    date = rest.pop("date", None)
    engine = rest.pop("engine", None)
    engines = rest.pop("engines", None)
    method = rest.pop("method", None)
    target = engine or (", ".join(engines) if engines else None) or build
    if grade or date or method or engine or engines:
        header = "Live-verified"
        if date:
            header += f" {date}"
        if target:
            header += f" on {target}"
        if grade:
            header += f" ({grade} grade)"
        entries = [f"{header}: {method}" if method else f"{header}."]
    else:
        entries = []

    def emit(key: str, val: Any) -> None:
        if key == "verified_state" and isinstance(val, dict):
            entries.extend(f"State-verified '{k}': {v}" for k, v in val.items())
        elif isinstance(val, (int, float)) and not isinstance(val, bool):
            entries.append(f"{_label(key)}: {val}")
        elif key == "notes" and isinstance(val, list):
            entries.extend(str(v) for v in val)
        elif key in ("corrections", "additions", "traps") and isinstance(val, list):
            prefix = {"corrections": "Correction", "additions": "Addition", "traps": "Trap"}[key]
            entries.extend(f"{prefix}: {v}" for v in val)
        elif isinstance(val, str):
            if " " in key:  # live enumeration keyed by command line
                tag = f" ({build})" if build else ""
                entries.append(f"Live enumeration{tag} of '{key}': {val}")
            else:
                entries.append(f"{_label(key)}: {val}")
        elif _is_token_list(val):
            entries.append(f"{_label(key)} ({len(val)}): {', '.join(val)}")
        elif isinstance(val, list) and all(isinstance(v, str) for v in val):
            entries.extend(f"{_label(key)}: {v}" for v in val)
        else:
            stats.oddities.append(f"{where}: unrenderable {key!r} = {type(val).__name__}")

    for key in _DICT_FIELD_ORDER:
        if key in rest:
            emit(key, rest.pop(key))
    notes_last = rest.pop("notes", None)
    for key, val in rest.items():
        emit(key, val)
    if notes_last is not None:
        emit("notes", notes_last)
    return entries


def _render(key: str, value: Any, prefix: str, where: str, stats: Stats) -> list[str]:
    build = _build_from_suffix(key, prefix)
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return _render_dict(value, build, where, stats)
    if _is_token_list(value):
        tag = f" ({build})" if build else ""
        return [f"Live enumeration{tag}, {len(value)} tokens: {', '.join(value)}"]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return list(value)
    stats.oddities.append(f"{where}: unrenderable {key!r} = {type(value).__name__}")
    return []


def _fold_verification(node: dict[str, Any], where: str, stats: Stats) -> bool:
    """Merge the live-test provenance family into ``verification: list[str]``."""
    family: list[tuple[str, list[str]]] = []
    for key in list(node):
        if key == "verified":
            family.append((key, _render(key, node[key], "verified", where, stats)))
        elif key == "evidence":
            family.append((key, [f"Evidence: {node[key]}"]))
        elif key in _BINARY_VALIDATED_LABELS:
            tokens = node[key]
            family.append((key, [f"{_BINARY_VALIDATED_LABELS[key]}: {', '.join(tokens)}"]))
        elif key.startswith("live_verification"):
            family.append((key, _render(key, node[key], "live_verification", where, stats)))
        elif key.startswith("live_enumeration"):
            family.append((key, _render(key, node[key], "live_enumeration", where, stats)))
        elif key == "live_notes":
            family.append((key, [str(v) for v in node[key]]))

    verification = node.get("verification")
    changed = False
    if isinstance(verification, str):
        node["verification"] = [verification]
        changed = True
    if family:
        entries = node.get("verification", [])
        entries = [entries] if isinstance(entries, str) else list(entries)
        for key, rendered in family:
            entries.extend(rendered)
            del node[key]
        node["verification"] = entries
        stats.verification_nodes += 1
        changed = True
    return changed


def _merge_example(ex: dict[str, Any], where: str, stats: Stats) -> None:
    description = str(ex.get("description", "")).rstrip().rstrip(".")
    extra = False
    if "model" in ex:
        description += f" (model: {ex.pop('model')})"
        extra = True
    if "use_case" in ex:
        description += f". Use case: {str(ex.pop('use_case')).rstrip('.')}"
        extra = True
    if "output_example" in ex:
        description += f". Output example: {ex.pop('output_example')}"
        extra = True
    if extra:
        ex["description"] = description + "."
        stats.example_edits += 1
    unknown = set(ex) - {"command", "description"}
    if unknown:
        stats.oddities.append(f"{where}: example keys {sorted(unknown)}")


def migrate_node(node: Any, rel: str, in_commands: bool, stats: Stats) -> bool:
    if isinstance(node, list):
        changed = False
        for child in node:
            changed = migrate_node(child, rel, in_commands, stats) or changed
        return changed
    if not isinstance(node, dict):
        return False
    changed = False

    for key in ("parent", "parent_item"):
        if isinstance(node.get(key), str):
            del node[key]
            stats.deleted += 1
            changed = True

    if "base_syntax" in node:
        if "syntax" in node:
            raise SystemExit(f"{rel}: both syntax and base_syntax present")
        node["syntax"] = node.pop("base_syntax")
        stats.renamed += 1
        changed = True

    if "documented_syntax" in node:
        del node["documented_syntax"]
        stats.deleted += 1
        changed = True
        if rel.endswith("range-elements/contact.json"):
            node.setdefault("notes", []).insert(
                0, "PFC-specific: selects objects by their PFC contacts; no contact data exists in the other engines."
            )
            stats.folded_notes += 1

    if "alt_syntax" in node:
        node.setdefault("notes", []).insert(0, f"Alternate form: {node.pop('alt_syntax')}")
        stats.folded_notes += 1
        changed = True

    for old in ("source_url", "official_documentation"):
        if old in node:
            if "source" in node:
                raise SystemExit(f"{rel}: both source and {old} present")
            value = node.pop(old)
            if isinstance(value, dict):  # one file: official_documentation = {source_urls: [...]}
                value = value["source_urls"]
            node["source"] = value
            stats.renamed += 1
            changed = True

    if "validation_notes" in node:
        node.setdefault("notes", []).extend(node.pop("validation_notes"))
        stats.folded_notes += 1
        changed = True

    changed = _fold_verification(node, rel, stats) or changed

    if in_commands and isinstance(node.get("examples"), list):
        examples = node["examples"]
        for i, ex in enumerate(examples):
            if isinstance(ex, str):
                examples[i] = {"command": ex}
                stats.example_edits += 1
                changed = True
            elif isinstance(ex, dict) and not set(ex) <= {"command", "description"}:
                _merge_example(ex, rel, stats)
                changed = True

    for key, child in list(node.items()):
        if key in DEFERRED_SUBTREES:
            continue
        changed = migrate_node(child, rel, in_commands, stats) or changed
    return changed


def main() -> int:
    write = "--write" in sys.argv
    stats = Stats()
    for tree in ("command_docs", "python_sdk_docs", "references"):
        for path in sorted(RESOURCES.glob(f"*/{tree}/**/*.json")):
            rel = path.relative_to(RESOURCES).as_posix()
            doc = json.loads(path.read_text(encoding="utf-8"))
            if migrate_node(doc, rel, tree == "command_docs", stats):
                stats.files += 1
                print(f"changed  {rel}")
                if write:
                    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"\nrenamed: {stats.renamed}; deleted: {stats.deleted}; folded notes: {stats.folded_notes}; "
        f"verification folds: {stats.verification_nodes}; example edits: {stats.example_edits}; "
        f"files changed: {stats.files}" + ("" if write else " (dry run)")
    )
    if stats.oddities:
        print("\nODDITIES:")
        print("\n".join(stats.oddities))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
