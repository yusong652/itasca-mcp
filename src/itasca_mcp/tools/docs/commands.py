"""Itasca command documentation: browse by path, search by keywords.

Exposes ``browse(software, path, version)`` and ``search(software, query, limit, version)``
for the ``commands`` source of itasca_browse_doc / itasca_query_doc.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache, partial
from itertools import chain
from typing import Any

from itasca_mcp.contracts import build_docs_data, build_error, build_ok
from itasca_mcp.knowledge.commands import CommandLoader
from itasca_mcp.knowledge.commands.naming import full_name, group_of
from itasca_mcp.knowledge.query import CommandSearch
from itasca_mcp.tools.docs._common import (
    compact_field,
    first_sentence,
    omit_entry_fields,
    omit_largest,
    trim_to_response,
)
from itasca_mcp.utils import (
    normalize_input,
    supported_doc_versions,
)

# A sentence ends at '.', '!' or '?' followed by a capital: 'etc.)' and 'e.g. ball' do not.
_LISTING_SUMMARY_MAX = 80  # what a category too large for one response cuts summaries to


def _shorten_descriptions(entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        if entry.get("description"):
            entry["description"] = first_sentence(entry["description"], _LISTING_SUMMARY_MAX)


def browse(software: str, path: str | None, version: str) -> dict[str, Any]:
    """'' -> categories; 'ball' -> ball commands; 'ball create' -> the full command doc."""
    cmd = normalize_input(path, lowercase=True)
    if not cmd:
        return build_ok(_browse_root(version, software))

    parts = cmd.split()
    category = _category_key(parts[0], software, version)
    if len(parts) == 1:
        return _wrap_payload(_browse_category(category, version, software))

    # Names are the engine's spelling, so resolve the whole path against them first:
    # a command ('block contact apply'), a heading ('block contact'), or a command
    # plus one section or keyword ('measure create troubleshooting', 'measure create position').
    by_name = {command.name: command for command in _commands(software, version)}
    if command := by_name.get(cmd):
        return _wrap_payload(_browse_command(command.category, command.key, version, software))
    if (payload := _browse_group(cmd, version, software)) is not None:
        return _wrap_payload(payload)
    if (command := by_name.get(" ".join(parts[:-1]))) is not None:
        payload = _browse_command_part(command.category, command.key, parts[-1], version, software)
        if payload is not None:
            return _wrap_payload(payload)

    # Not an engine spelling: the corpus key form ('block contact-apply') or a command the
    # version does not have, which _browse_command reports as such.
    payload = _browse_command(category, " ".join(parts[1:]), version, software)
    if len(parts) > 2 and payload.get("error", {}).get("code") == "command_not_found":
        payload = _browse_command_part(category, " ".join(parts[1:-1]), parts[-1], version, software) or payload
    return _wrap_payload(payload)


# Fields every command page keeps when trimmed; the rest are per-command extra sections.
_COMMAND_CORE_FIELDS = (
    "command",
    "category",
    "syntax",
    "description",
    "keywords",
    "examples",
    "notes",
    "versions",
    "available",
    "python_sdk_alternative",
    "figure_reference",
)
_COMMAND_IDENTITY_FIELDS = ("command", "category", "syntax", "description", "keywords")


def _keyword_name(keyword: dict[str, Any]) -> str:
    """Path form of a keyword: 'kwd:bond_break' is addressed as 'bond_break'."""
    return str(keyword.get("name", "")).lower().removeprefix("kwd:")


@dataclass(frozen=True)
class _Command:
    """One command available in a version: its corpus key and the engine's spelling of it."""

    category: str
    key: str  # file key under the category directory, e.g. 'contact-apply'
    name: str  # what the engine accepts, e.g. 'block contact apply'
    syntax: str | None
    description: str
    python_available: bool

    @property
    def group(self) -> str | None:
        return group_of(self.name)

    def listing(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": first_sentence(self.description),
            "syntax": self.syntax,
            "python_available": self.python_available,
        }


def _command_prefix(category: str, software: str) -> str:
    """The word the engine puts first: 'building-blocks' for the FLAC category keyed 'body'."""
    category_data = CommandLoader.load_index(software=software).get("categories", {}).get(category, {})
    return str(category_data.get("command_prefix") or category)


@lru_cache(maxsize=32)
def _commands(software: str, version: str) -> tuple[_Command, ...]:
    """Every command available in this version, in index order."""
    rows: list[_Command] = []
    for category, category_data in CommandLoader.load_index(software=software).get("categories", {}).items():
        prefix = _command_prefix(category, software)
        for cmd_meta in category_data.get("commands", []):
            key = str(cmd_meta.get("name", ""))
            # KeyError = command doc has no entry for this version (e.g. FLAC 9.0-only
            # commands omit the 7.0 key); treat as not available in this version.
            try:
                cmd_doc = CommandLoader.load_command_doc(category, key, version, software=software)
            except KeyError:
                continue
            if not cmd_doc or cmd_doc.get("available") is False:
                continue
            rows.append(
                _Command(
                    category=category,
                    key=key,
                    name=full_name(prefix, key, cmd_doc),
                    syntax=cmd_doc.get("syntax"),
                    description=str(cmd_doc.get("description") or ""),
                    python_available=bool(cmd_meta.get("python_available", False)),
                )
            )
    return tuple(rows)


def _category_key(word: str, software: str, version: str) -> str:
    """Index key for a category word: 'building-blocks' and 'body' both reach the FLAC body
    category, and 'extrude' reaches extruder at 7.0 where the engine word was not yet 'sketch'."""
    categories = CommandLoader.load_index(software=software).get("categories", {})
    if word in categories:
        return word
    by_prefix: str | None = next((key for key, data in categories.items() if data.get("command_prefix") == word), None)
    if by_prefix:
        return by_prefix
    return next((c.category for c in _commands(software, version) if c.name.split()[0] == word), word)


def _engine_word(category: str, software: str, version: str) -> str:
    """What the engine calls a category: 'building-blocks' for the index key 'body',
    'model domain' for 'domain', 'extrude' for extruder at 7.0 and 'sketch' at 9.0.

    Read off the version's command names as the words they all start with (at most two,
    always leaving a word to the command itself); a category with fewer than two commands
    falls back to its index prefix.
    """
    names = [command.name.split() for command in _commands(software, version) if command.category == category]
    if len(names) < 2:
        return _command_prefix(category, software)
    shared: list[str] = []
    for i in range(2):
        heads = {words[i] for words in names if len(words) > i + 1}
        if len(heads) != 1 or len(heads) != len({words[i] for words in names}):
            break
        shared.append(heads.pop())
    return " ".join(shared) or _command_prefix(category, software)


def _group_counts(commands: list[_Command]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for command in commands:
        if command.group:
            counts[command.group] = counts.get(command.group, 0) + 1
    return dict(sorted(counts.items()))


def _listing_payload(
    category: str, items: list[dict[str, Any]], summary: dict[str, Any], version: str, software: str
) -> dict[str, Any]:
    payload = build_docs_data(
        source="commands",
        action="browse",
        entries=items,
        summary={"count": len(items), "category": category, **summary, "version": version, "software": software},
    )
    trim_to_response(
        payload,
        chain(
            omit_entry_fields(payload["entries"], "syntax", "python_available"),
            [("compact", "description", partial(_shorten_descriptions, payload["entries"]))],
            omit_entry_fields(payload["entries"], "description"),
        ),
        hint="Trimmed to fit one response: browse an entry's name for the command's syntax and description.",
    )
    return payload


def _browse_root(version: str, software: str) -> dict[str, Any]:
    """Level 0: Return overview of all command categories."""
    index = CommandLoader.load_index(software=software)
    categories = index.get("categories", {})
    commands = _commands(software, version)
    category_items: list[dict[str, Any]] = []
    total_commands = 0

    for category_name, category_data in categories.items():
        command_count = sum(1 for command in commands if command.category == category_name)
        if not command_count:
            # e.g. 3DEC 'sel' is 7.0-only: a category empty in this version is not offered
            continue
        total_commands += command_count
        category_items.append(
            {
                "name": _engine_word(category_name, software, version),
                "description": category_data.get("description", ""),
                "command_count": command_count,
            }
        )

    category_items.sort(key=lambda item: item["name"])
    return build_docs_data(
        source="commands",
        action="browse",
        entries=category_items,
        summary={
            "count": len(category_items),
            "total_commands": total_commands,
            "version": version,
            "software": software,
        },
    )


def _browse_category(category: str, version: str, software: str) -> dict[str, Any]:
    """Level 1: Return list of commands in a category."""
    index = CommandLoader.load_index(software=software)
    categories = index.get("categories", {})

    if category not in categories:
        return {
            "source": "commands",
            "action": "browse",
            "error": {
                "code": "category_not_found",
                "message": f"Category '{category}' not found.",
            },
            "input": {"category": category, "version": version, "software": software},
            "available_categories": sorted(_engine_word(key, software, version) for key in categories),
        }

    commands = [command for command in _commands(software, version) if command.category == category]
    if not commands:
        available_versions = [
            v
            for v in sorted(supported_doc_versions(software))
            if any(c.category == category for c in _commands(software, v))
        ]
        return {
            "source": "commands",
            "action": "browse",
            "error": {
                "code": "category_unavailable_for_version",
                "message": f"Category '{category}' has no commands in {software} {version}.",
            },
            "input": {"category": category, "version": version, "software": software},
            "available_versions": available_versions,
        }
    summary: dict[str, Any] = {"description": categories[category].get("description", "")}
    groups = _group_counts(commands)
    if groups:
        # 'block contact' is a heading over 22 commands, not a command: browse it as a level of its own.
        summary["groups"] = groups
    items = [command.listing() for command in commands]
    return _listing_payload(_engine_word(category, software, version), items, summary, version, software)


def _browse_group(group: str, version: str, software: str) -> dict[str, Any] | None:
    """Level 1.5: the commands under one manual heading, 'block contact ...'; None if no such group."""
    commands = [command for command in _commands(software, version) if command.group == group]
    if not commands:
        return None
    category = _engine_word(commands[0].category, software, version)
    return _listing_payload(category, [command.listing() for command in commands], {"group": group}, version, software)


def _browse_command(category: str, command_name: str, version: str, software: str) -> dict[str, Any]:
    """Level 2: Return full documentation for a specific command."""
    # JSON filenames use dash as sub-command separator (e.g. edge-create,
    # cmat-add, scalar-create) while Itasca command syntax separates them with spaces.
    # Accept either form on input.
    try:
        cmd_doc = CommandLoader.load_command_doc(category, command_name, version, software=software)
        if not cmd_doc and " " in command_name:
            cmd_doc = CommandLoader.load_command_doc(
                category, command_name.replace(" ", "-"), version, software=software
            )
    except KeyError:
        # Command exists but its doc has no entry for this version.
        return {
            "source": "commands",
            "action": "browse",
            "error": {
                "code": "command_unavailable_for_version",
                "message": f"Command '{command_name}' is not available in {software} {version}.",
            },
            "input": {"category": category, "command": command_name, "version": version, "software": software},
        }

    if not cmd_doc:
        index = CommandLoader.load_index(software=software)
        categories = index.get("categories", {})

        if category not in categories:
            return {
                "source": "commands",
                "action": "browse",
                "error": {
                    "code": "category_not_found",
                    "message": f"Category '{category}' not found.",
                },
                "input": {"category": category, "command": command_name, "version": version, "software": software},
                "available_categories": sorted(categories.keys()),
            }

        commands = [command for command in _commands(software, version) if command.category == category]
        not_found: dict[str, Any] = {
            "source": "commands",
            "action": "browse",
            "error": {
                "code": "command_not_found",
                "message": f"Command '{command_name}' not found in '{category}'.",
            },
            "input": {"category": category, "command": command_name, "version": version, "software": software},
            "available_commands": [command.name for command in commands],
        }
        groups = _group_counts(commands)
        if groups:
            not_found["groups"] = groups
        return not_found

    if cmd_doc.get("available") is False:
        return {
            "source": "commands",
            "action": "browse",
            "error": {
                "code": "command_unavailable_for_version",
                "message": f"Command '{command_name}' is not available in {software} {version}.",
            },
            "input": {"category": category, "command": command_name, "version": version, "software": software},
            "available_versions": cmd_doc.get("versions", []),
        }

    key = command_name if " " not in command_name else command_name.replace(" ", "-")
    name = full_name(_command_prefix(category, software), key, cmd_doc)
    payload = build_docs_data(
        source="commands",
        action="browse",
        entries=[
            {
                "category": _engine_word(category, software, version),
                "command": name,
                "version": version,
                "doc": cmd_doc,
            }
        ],
        summary={"count": 1, "version": version, "software": software},
    )
    doc = payload["entries"][0]["doc"]  # model_dump copy: safe to trim
    trim_to_response(
        payload,
        chain(
            omit_largest(doc, keep=_COMMAND_CORE_FIELDS),
            compact_field(
                doc,
                "keywords",
                lambda keywords: [{"name": k.get("name"), "syntax": k.get("syntax")} for k in keywords],
            ),
            omit_largest(doc, keep=_COMMAND_IDENTITY_FIELDS),
        ),
        hint=f"Trimmed to fit one response: browse '{name} <name>' for an omitted section or one keyword.",
    )
    return payload


def _browse_command_part(
    category: str, command_name: str, part: str, version: str, software: str
) -> dict[str, Any] | None:
    """One section ('troubleshooting') or keyword ('position') of a command doc; None if no such command."""
    try:
        cmd_doc = CommandLoader.load_command_doc(category, command_name, version, software=software)
        if not cmd_doc and " " in command_name:
            cmd_doc = CommandLoader.load_command_doc(
                category, command_name.replace(" ", "-"), version, software=software
            )
    except KeyError:
        return None
    if not cmd_doc or cmd_doc.get("available") is False:
        return None

    entry: dict[str, Any] = {"category": category, "command": command_name, "version": version}
    keywords = [k for k in cmd_doc.get("keywords") or [] if isinstance(k, dict)]
    if part in cmd_doc and part not in _COMMAND_IDENTITY_FIELDS:
        entry["section"] = part
        entry["content"] = cmd_doc[part]
    else:
        keyword = next((k for k in keywords if _keyword_name(k) == part.removeprefix("kwd:")), None)
        if keyword is None:
            return {
                "source": "commands",
                "action": "browse",
                "error": {
                    "code": "section_not_found",
                    "message": f"'{category} {command_name}' has no section or keyword '{part}'.",
                },
                "input": {"category": category, "command": command_name, "part": part, "version": version},
                "available_sections": [key for key in cmd_doc if key not in _COMMAND_IDENTITY_FIELDS],
                "available_keywords": [_keyword_name(k) for k in keywords],
            }
        entry["keyword"] = keyword
    return build_docs_data(
        source="commands",
        action="browse",
        entries=[entry],
        summary={"count": 1, "version": version, "software": software},
    )


def _wrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap tool payload into unified envelope."""
    if "error" in payload:
        err = payload.get("error") or {}
        details = {k: v for k, v in payload.items() if k != "error"}
        return build_error(
            code=str(err.get("code") or "browse_error"),
            message=str(err.get("message") or "Browse failed"),
            details=details or None,
        )
    return build_ok(payload)


def search(software: str, query: str, limit: int, version: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return ``(entries, summary extras)``; entries carry ``path`` for ``itasca_browse_doc``."""
    results = CommandSearch.search_commands_only(query, top_k=limit, version=version, software=software)
    matches: list[dict[str, Any]] = []
    for result in results:
        metadata = result.document.metadata or {}
        matches.append(
            {
                "path": result.document.title,
                "name": result.document.name,
                "category": result.document.category,
                "syntax": result.document.syntax,
                "description": first_sentence(result.document.description),
                "score": round(result.score, 2),
                "rank": result.rank,
                "version": metadata.get("version", version),
            }
        )

    extras: dict[str, Any] = {}
    if not matches:
        examples = ", ".join(_example_commands(software, version))
        extras["hints"] = [
            "Try broader keywords (for example: create, property, solve).",
            f"Try category + action (for example: {examples}).",
        ]
        categories = CommandLoader.load_index(software=software).get("categories", {})
        extras["available_categories"] = sorted(categories.keys())
    return matches, extras


_EXAMPLE_CATEGORY = {"pfc": "ball", "flac": "zone", "3dec": "block", "mpoint": "mpoint", "massflow": "massflow"}


def _example_commands(software: str, version: str) -> list[str]:
    """Two real commands on the engine's main object: 'ball create, ball generate' on PFC, 'zone ...' on FLAC."""
    commands = _commands(software, version)
    category = _EXAMPLE_CATEGORY.get(software)
    own = sorted((c for c in commands if c.category == category), key=lambda c: c.group is not None)
    names = [c.name for c in own] or [c.name for c in commands]
    if not names:
        return ["model new", "model solve"]
    picked = [n for n in names if n.rsplit(" ", 1)[-1] in ("create", "generate", "list", "property")]
    return (picked or names)[:2]
