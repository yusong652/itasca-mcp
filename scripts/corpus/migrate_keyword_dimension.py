"""Move the inline "(3D ONLY)" / "2D ONLY" marker of command keywords into ``dimension``.

The manuals print the marker after a keyword's syntax in every version, but
the 6.0/7.0 parsers dropped it and the 9.0 parser kept it as syntax text. So
the restriction was missing from the older views, was invisible to anything
reading the structured ``dimension`` field (corpus spec, section B), and made
hundreds of syntax version maps differ by nothing but the marker.

For each keyword entry of a command doc:

- a marker outside any ``{...}`` / ``[...]`` group restricts the keyword:
  it becomes ``dimension`` and leaves the syntax text of every version;
- "(y and z components 3D ONLY)" restricts part of a vector argument: it
  leaves the syntax and becomes an entry note;
- a marker inside a group restricts one sub-option and stays where it is;
- a syntax version map whose values are equal afterwards collapses to one
  string when it covered every version the entry is served for.

Idempotent. Usage:
    uv run python scripts/corpus/migrate_keyword_dimension.py [--write]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from itasca_mcp.utils import supported_doc_versions

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"
VERSION_LABELS = ("6.0", "7.0", "9.0")

MARKER = re.compile(r"\(\s*([23])D[ -]only\.?\s*\)|\b([23])D[ -]only\b", re.IGNORECASE)
PARTIAL = re.compile(r"\(([^()]*\b[23]D[ -]only\b[^()]*)\)", re.IGNORECASE)
PARTIAL_NOTES = {"y and z components 3d only": "The y and z components are 3D only."}


def _depth(text: str, pos: int) -> int:
    """Nesting depth of ``{`` / ``[`` groups at ``pos``."""
    depth = 0
    for char in text[:pos]:
        if char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
    return depth


def strip_markers(text: str) -> tuple[str, set[str], list[str], list[str]]:
    """-> (text without keyword-level markers, dimensions, partial notes, unknown partial phrases)."""
    dims: set[str] = set()
    notes: list[str] = []
    unknown: list[str] = []
    spans: list[tuple[int, int]] = []
    partial_spans: list[tuple[int, int]] = []
    for match in PARTIAL.finditer(text):
        if MARKER.fullmatch(match.group(0)):
            continue
        partial_spans.append(match.span())
        if _depth(text, match.start()) > 0:
            continue
        note = PARTIAL_NOTES.get(" ".join(match.group(1).lower().split()))
        if note is None:
            unknown.append(match.group(0))
            continue
        notes.append(note)
        spans.append(match.span())
    for match in MARKER.finditer(text):
        if any(start <= match.start() < end for start, end in partial_spans):
            continue
        if _depth(text, match.start()) > 0:
            continue
        dims.add((match.group(1) or match.group(2)) + "D")
        spans.append(match.span())
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + " " + text[end:]
    return re.sub(r"\s{2,}", " ", text).strip(), dims, notes, unknown


def _served_versions(entry: dict[str, Any], doc: dict[str, Any], engine: str) -> set[str]:
    for holder in (entry, doc):
        availability = holder.get("availability")
        versions = availability.get("versions") if isinstance(availability, dict) else None
        if isinstance(versions, list):
            return set(versions)
    return set(VERSION_LABELS) if engine == "_common" else set(supported_doc_versions(engine))


def migrate_entry(entry: dict[str, Any], doc: dict[str, Any], engine: str, where: str, stats: Counter[str]) -> bool:
    syntax = entry.get("syntax")
    is_map = isinstance(syntax, dict) and bool(syntax) and set(syntax) <= set(VERSION_LABELS)
    values = dict(syntax) if is_map else {"*": syntax}
    dims: set[str] = set()
    notes: list[str] = []
    new_values: dict[str, Any] = {}
    for label, text in values.items():
        if not isinstance(text, str):
            new_values[label] = text
            continue
        stripped, found, partial, unknown = strip_markers(text)
        for phrase in unknown:
            print(f"  ODD unknown partial marker {phrase!r}: {where}")
            stats["odd"] += 1
        new_values[label] = stripped
        dims |= found
        notes += [n for n in partial if n not in notes]
    if not dims and not notes:
        return False
    if len(dims) > 1 or (dims and entry.get("dimension") not in (None, *dims)):
        print(f"  ODD conflicting dimensions {sorted(dims)} vs {entry.get('dimension')!r}: {where}")
        stats["odd"] += 1
        return False
    if any(not text for text in new_values.values() if isinstance(text, str)):
        print(f"  ODD syntax would become empty: {where}")
        stats["odd"] += 1
        return False

    if is_map:
        distinct = {json.dumps(v) for v in new_values.values()}
        if len(distinct) == 1 and set(new_values) >= _served_versions(entry, doc, engine):
            new_syntax: Any = next(iter(new_values.values()))
            stats["maps_collapsed"] += 1
        else:
            new_syntax = new_values
    else:
        new_syntax = new_values["*"]

    rebuilt: dict[str, Any] = {}
    for key, value in entry.items():
        rebuilt[key] = new_syntax if key == "syntax" else value
        if key == "syntax" and dims and "dimension" not in entry:
            rebuilt["dimension"] = next(iter(dims))
    if notes:
        existing = rebuilt.get("notes")
        merged = list(existing) if isinstance(existing, list) else ([existing] if existing else [])
        rebuilt["notes"] = merged + [n for n in notes if n not in merged]
        stats["partial_notes"] += 1
    entry.clear()
    entry.update(rebuilt)
    if dims:
        stats["dimension_tags"] += 1
    return True


def main() -> None:
    write = "--write" in sys.argv
    stats: Counter[str] = Counter()
    for path in sorted(RESOURCES.glob("*/command_docs/commands/**/*.json")):
        engine = path.relative_to(RESOURCES).parts[0]
        raw = path.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
        changed = False
        for entry in doc.get("keywords") or []:
            if isinstance(entry, dict):
                where = f"{path.relative_to(RESOURCES).as_posix()} :: {entry.get('name')}"
                changed |= migrate_entry(entry, doc, engine, where, stats)
        if changed:
            stats["files"] += 1
            if write:
                newline = "\r\n" if b"\r\n" in raw else "\n"
                with open(path, "w", encoding="utf-8", newline=newline) as handle:
                    json.dump(doc, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
    print(dict(stats), "WRITTEN" if write else "(dry run)")


if __name__ == "__main__":
    main()
