"""Full-corpus resolution sweep: the safety net for corpus format migrations.

These tests pin the *resolved* (served) view of every tree for every engine and
version, not the raw JSON shape, so a format migration (docs/development/
corpus-spec.md) can rewrite the files freely — as long as the loaders keep
serving the same content, the sweep stays green. fish already has its own
full-reachability tests in test_doc_tools_merged.py.

A failure here names the exact path that stopped resolving, so a migration
script that corrupts one file out of 2,300 is caught by name.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from itasca_mcp.knowledge.commands.loader import CommandLoader
from itasca_mcp.knowledge.config import SUPPORTED_SOFTWARE
from itasca_mcp.knowledge.python_api import PythonAPILoader
from itasca_mcp.knowledge.references.loader import ReferenceLoader
from itasca_mcp.tools.docs import commands as commands_tool
from itasca_mcp.tools.docs import reference as reference_tool
from itasca_mcp.utils import supported_doc_versions

ALL_VERSIONS = {"6.0", "7.0", "9.0"}


def _versions(software: str) -> list[str]:
    return sorted(supported_doc_versions(software))


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("software", SUPPORTED_SOFTWARE)
def test_every_command_doc_resolves(software: str) -> None:
    """Every index entry resolves for at least one version, with sound fields."""
    problems: list[str] = []
    for cmd_meta in CommandLoader.get_all_commands(software=software):
        category, name = cmd_meta["category"], cmd_meta["name"]
        where = f"{software}:{category}/{name}"
        resolved_any = tombstone = False
        for version in _versions(software):
            try:
                doc = CommandLoader.load_command_doc(category, name, version, software=software)
            except KeyError:
                continue  # no entry for this version: fine, as long as some version has one
            if doc is None:
                problems.append(f"{where}@{version}: index entry points at no loadable doc")
                continue
            if doc.get("available") is False:
                # Deliberate tombstone: the manual documents it, the engine rejects it
                # (e.g. 3DEC fblock delete). Kept as negative knowledge.
                tombstone = True
                continue
            resolved_any = True
            problems.extend(f"{where}@{version}: {p}" for p in _command_doc_problems(doc))
        if not resolved_any and not tombstone:
            problems.append(f"{where}: no version resolves to an available doc")
    assert problems == []


def _command_doc_problems(doc: dict[str, Any]) -> list[str]:
    problems = []
    if not (isinstance(doc.get("command"), str) and doc["command"].strip()):
        problems.append("missing/empty 'command'")
    if not (isinstance(doc.get("description"), str) and doc["description"].strip()):
        problems.append("missing/empty 'description'")
    versions = doc.get("versions")
    if not (isinstance(versions, list) and versions and set(versions) <= ALL_VERSIONS):
        problems.append(f"bad resolved 'versions': {versions!r}")
    keywords = doc.get("keywords", [])
    if not isinstance(keywords, list):
        problems.append("'keywords' is not a list")
        keywords = []
    for kw in keywords:
        if not isinstance(kw, dict) or not isinstance(kw.get("name"), str) or not kw["name"].strip():
            problems.append(f"keyword without a name: {kw!r}")
        elif not isinstance(kw.get("syntax"), str):
            problems.append(f"keyword {kw['name']!r} without syntax")
    examples = doc.get("examples", [])
    if not isinstance(examples, list):
        problems.append("'examples' is not a list")
        examples = []
    for ex in examples:
        if not isinstance(ex, dict) or not isinstance(ex.get("command"), str):
            problems.append(f"example without a command: {ex!r}")
        elif not set(ex) <= {"command", "description"}:
            problems.append(f"example with non-canonical keys: {sorted(set(ex) - {'command', 'description'})}")
    return problems


@pytest.mark.parametrize("software", SUPPORTED_SOFTWARE)
def test_every_listed_command_is_browsable(software: str) -> None:
    """The names the listings hand out must resolve as browse paths (the same
    round-trip promise the fish tree keeps)."""
    failures = []
    for version in _versions(software):
        for command in commands_tool._commands(software, version):
            envelope = commands_tool.browse(software, command.name, version)
            if not envelope["ok"]:
                failures.append(f"{software}@{version}: {command.name!r} -> {envelope['error']['code']}")
    assert failures == []


# ---------------------------------------------------------------------------
# references
# ---------------------------------------------------------------------------


def _reference_items(software: str) -> list[tuple[str, str]]:
    pairs = []
    for category in ReferenceLoader.load_index(software=software).get("categories", {}):
        for entry in ReferenceLoader.get_item_list(category, None, software=software):
            item = entry.get("name") or entry.get("model") or entry.get("element")
            if isinstance(item, str) and item:
                pairs.append((category, item))
    return pairs


@pytest.mark.parametrize("software", SUPPORTED_SOFTWARE)
def test_every_reference_item_loads(software: str) -> None:
    problems = []
    for category, item in _reference_items(software):
        where = f"{software}:{category}/{item}"
        doc = ReferenceLoader.load_item_doc(category, item, software=software)
        if not isinstance(doc, dict) or not doc:
            problems.append(f"{where}: index entry points at no loadable doc")
            continue
        availability = doc.get("availability")
        if availability is not None and not (
            isinstance(availability, dict)
            and set(availability) <= {"versions", "engines"}
            and all(isinstance(v, list) for v in availability.values())
            and all(str(v) in ALL_VERSIONS for v in availability.get("versions", []))
        ):
            problems.append(f"{where}: malformed availability {availability!r}")
    assert problems == []


@pytest.mark.parametrize("software", SUPPORTED_SOFTWARE)
def test_every_reference_item_is_browsable(software: str) -> None:
    failures = []
    for category, item in _reference_items(software):
        envelope = reference_tool.browse(software, f"{category} {item}", "9.0")
        if envelope["ok"]:
            continue
        code = envelope["error"]["code"]
        if code == "item_unavailable_for_version":
            # Gated out of 9.0: it must then be browsable in a version it names.
            available = (envelope["error"].get("details") or {}).get("available_versions") or []
            if available and reference_tool.browse(software, f"{category} {item}", available[0])["ok"]:
                continue
        failures.append(f"{software}: {category} {item} -> {code}")
    assert failures == []


# ---------------------------------------------------------------------------
# python_api
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("software", SUPPORTED_SOFTWARE)
def test_every_python_api_entry_is_sound(software: str) -> None:
    """Every module function and object method carries name+signature+description,
    and availability (where present) keeps the canonical shape."""
    problems = []
    index = PythonAPILoader.load_index(software=software)
    for module_key in index.get("modules", {}):
        doc = PythonAPILoader.load_module(module_key, software=software)
        if doc is None:
            problems.append(f"{software}:{module_key}: module doc does not load")
            continue
        problems.extend(_entry_problems(f"{software}:{module_key}", doc.get("functions")))
    for object_name in index.get("objects", {}):
        doc = PythonAPILoader.load_object(object_name, software=software)
        if doc is None:
            problems.append(f"{software}:{object_name}: object doc does not load")
            continue
        problems.extend(_entry_problems(f"{software}:{object_name}", doc.get("methods")))
    assert problems == []


def _entry_problems(where: str, entries: Any) -> list[str]:
    problems = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            problems.append(f"{where}: non-dict entry {entry!r}")
            continue
        name = entry.get("name")
        if not (isinstance(name, str) and name.strip()):
            problems.append(f"{where}: entry without a name: {str(entry)[:80]}")
            continue
        for field in ("signature", "description"):
            if not (isinstance(entry.get(field), str) and entry[field].strip()):
                problems.append(f"{where}.{name}: missing/empty {field!r}")
        availability = entry.get("availability")
        if availability is not None and not (
            isinstance(availability, dict)
            and set(availability) <= {"versions", "engines"}
            and all(isinstance(v, list) and v for v in availability.values())
        ):
            problems.append(f"{where}.{name}: malformed availability {availability!r}")
    return problems


# ---------------------------------------------------------------------------
# raw spec-shape scan (corpus-spec section D: naming and provenance)
# ---------------------------------------------------------------------------

_RESOURCES = Path(__file__).resolve().parents[1] / "src" / "itasca_mcp" / "knowledge" / "resources"

# Subtrees owned by later migration steps; their internals are not judged yet.
# (flac3d_liner_property_set and index_expansion: dimension step B / archetype step F.)
_DEFERRED_SUBTREES = {
    "legacy_documentation",
    "dimension_differences",
    "independent_dimensions",
    "flac3d_liner_property_set",
    "index_expansion",
}
# Whole categories owned by the dimension step.
_DEFERRED_PATHS = ("references/dimension-differences/",)

# Legacy spellings that section D retires. `source_urls` survives only inside
# command_docs version blocks (the removed-command apparatus, step A).
_BANNED_KEYS = {
    "parent",
    "parent_item",
    "base_syntax",
    "documented_syntax",
    "alt_syntax",
    "source_url",
    "official_documentation",
    "verified",
    "evidence",
    "live_notes",
    "validation_notes",
}
_BANNED_PREFIXES = ("live_verification", "live_enumeration", "binary_validated")

# Section E: one structured keyword list. Every parallel *_keywords spelling is
# retired except the curated search field and the range-element sub-keywords.
_ALLOWED_KEYWORD_FIELDS = {"search_keywords", "sub_keywords"}
_BANNED_SECTION_KEYS = {"plot_items", "condition_families", "common_keywords"}
_KEYWORD_ENTRY_BANNED = {"keyword", "engines", "examples", "available_parameters", "required", "parameters"}


def _keyword_entry_problems(entries: Any, rel: str, jp: str) -> list[str]:
    problems: list[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"{rel} @{jp}[{i}]: keyword entry is not a dict: {entry!r}")
            continue
        name = entry.get("name")
        if not (isinstance(name, str) and name.strip()):
            problems.append(f"{rel} @{jp}[{i}]: keyword entry without a name")
        for banned in _KEYWORD_ENTRY_BANNED & set(entry):
            problems.append(f"{rel} @{jp}[{i}]: keyword entry field {banned!r}")
    return problems


def _shape_problems(node: Any, rel: str, jp: str, in_command_docs: bool, parent_key: str = "") -> list[str]:
    problems: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _BANNED_KEYS or key.startswith(_BANNED_PREFIXES):
                problems.append(f"{rel} @{jp}: legacy field {key!r}")
            if key in _BANNED_SECTION_KEYS:
                problems.append(f"{rel} @{jp}: retired section {key!r}")
            if key.endswith("_keywords") and key not in _ALLOWED_KEYWORD_FIELDS:
                problems.append(f"{rel} @{jp}: parallel keyword list {key!r}")
            if key == "engines" and parent_key != "availability":
                problems.append(f"{rel} @{jp}: bare 'engines' outside availability")
            if key == "source_urls" and not in_command_docs:
                problems.append(f"{rel} @{jp}: legacy field 'source_urls'")
            if key in ("keywords", "sub_keywords") and isinstance(value, list):
                problems.extend(_keyword_entry_problems(value, rel, f"{jp}.{key}"))
            if key == "verification" and not (
                isinstance(value, list) and value and all(isinstance(v, str) and v.strip() for v in value)
            ):
                problems.append(f"{rel} @{jp}: 'verification' is not a non-empty list[str]")
            if key == "source" and not (
                isinstance(value, str) or (isinstance(value, list) and all(isinstance(v, str) for v in value))
            ):
                problems.append(f"{rel} @{jp}: 'source' is not str | list[str]")
            if key not in _DEFERRED_SUBTREES:
                problems.extend(_shape_problems(value, rel, f"{jp}.{key}", in_command_docs, key))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            problems.extend(_shape_problems(value, rel, f"{jp}[{i}]", in_command_docs, parent_key))
    return problems


def test_no_legacy_naming_or_provenance_fields_remain() -> None:
    problems: list[str] = []
    for path in sorted(_RESOURCES.rglob("*.json")):
        rel = path.relative_to(_RESOURCES).as_posix()
        if any(deferred in rel for deferred in _DEFERRED_PATHS):
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        problems.extend(_shape_problems(doc, rel, "$", "/command_docs/" in f"/{rel}"))
    assert problems == []
