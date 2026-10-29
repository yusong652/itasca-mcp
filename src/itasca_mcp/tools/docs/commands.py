"""Itasca command documentation: browse by path, search by keywords.

Exposes ``browse(software, path, version)`` and ``search(software, query, limit, version)``
for the ``commands`` source of itasca_browse_doc / itasca_query_doc.
"""

from __future__ import annotations

from functools import partial
from itertools import chain
from typing import Any

from itasca_mcp.contracts import build_docs_data, build_error, build_ok
from itasca_mcp.knowledge.commands import CommandLoader
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
    if len(parts) == 1:
        payload = _browse_category(parts[0], version, software)
    else:
        payload = _browse_command(parts[0], " ".join(parts[1:]), version, software)
        # 'measure create troubleshooting' / 'measure create position': one section or keyword
        if len(parts) > 2 and payload.get("error", {}).get("code") == "command_not_found":
            payload = _browse_command_part(parts[0], " ".join(parts[1:-1]), parts[-1], version, software) or payload
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


def _iter_available_category_commands(
    category: str, version: str, software: str
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return commands that are available in the requested version."""
    index = CommandLoader.load_index(software=software)
    category_data = index.get("categories", {}).get(category, {})
    available: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for cmd_meta in category_data.get("commands", []):
        # KeyError = command doc has no entry for this version (e.g. FLAC 9.0-only
        # commands omit the 7.0 key); treat as not available in this version.
        try:
            cmd_doc = CommandLoader.load_command_doc(category, cmd_meta.get("name", ""), version, software=software)
        except KeyError:
            continue
        if cmd_doc and cmd_doc.get("available") is not False:
            available.append((cmd_meta, cmd_doc))

    return available


def _group_of(name: str, syntax: str | None) -> str | None:
    """Engine word group a command belongs to, or None.

    JSON file names write the engine's spaces as dashes, so 'contact-generate-subcontacts'
    cannot say on its own that 'block contact generate-subcontacts' is a 'contact' command
    while 'block merge-start' is one hyphenated word. The syntax keeps the engine's spelling:
    the first dash stands for a space exactly when the syntax's second word is the first segment.
    """
    head, dash, _ = name.partition("-")
    words = (syntax or "").lower().split()
    if dash and len(words) > 1 and words[1] == head:
        return head
    return None


def _command_items(available: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        {
            "name": cmd.get("name", ""),
            "description": first_sentence(cmd_doc.get("description")),
            "syntax": cmd_doc.get("syntax"),
            "python_available": bool(cmd.get("python_available", False)),
        }
        for cmd, cmd_doc in available
    ]


def _group_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        group = _group_of(item["name"], item.get("syntax"))
        if group:
            counts[group] = counts.get(group, 0) + 1
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
        hint=f"Trimmed to fit one response: browse '{category} <command>' for a command's syntax and description.",
    )
    return payload


def _browse_root(version: str, software: str) -> dict[str, Any]:
    """Level 0: Return overview of all command categories."""
    index = CommandLoader.load_index(software=software)
    categories = index.get("categories", {})
    category_items: list[dict[str, Any]] = []
    total_commands = 0

    for category_name, category_data in categories.items():
        available_commands = _iter_available_category_commands(category_name, version, software)
        command_count = len(available_commands)
        total_commands += command_count
        category_items.append(
            {
                "name": category_name,
                "description": category_data.get("description", ""),
                "command_count": command_count,
            }
        )

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
            "available_categories": sorted(categories.keys()),
        }

    command_items = _command_items(_iter_available_category_commands(category, version, software))
    summary: dict[str, Any] = {"description": categories[category].get("description", "")}
    groups = _group_counts(command_items)
    if groups:
        # 'block contact' is a word group of 23 commands, not a command: browse it as a level of its own.
        summary["groups"] = groups
    return _listing_payload(category, command_items, summary, version, software)


def _browse_group(category: str, group: str, version: str, software: str) -> dict[str, Any] | None:
    """Level 1.5: the commands the engine spells '<category> <group> ...'; None if no such group."""
    items = [
        item
        for item in _command_items(_iter_available_category_commands(category, version, software))
        if _group_of(item["name"], item.get("syntax")) == group
    ]
    if not items:
        return None
    return _listing_payload(category, items, {"group": group}, version, software)


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

        group_payload = _browse_group(category, command_name, version, software)
        if group_payload is not None:
            return group_payload

        items = _command_items(_iter_available_category_commands(category, version, software))
        not_found: dict[str, Any] = {
            "source": "commands",
            "action": "browse",
            "error": {
                "code": "command_not_found",
                "message": f"Command '{command_name}' not found in '{category}'.",
            },
            "input": {"category": category, "command": command_name, "version": version, "software": software},
            "available_commands": [item["name"] for item in items],
        }
        groups = _group_counts(items)
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

    payload = build_docs_data(
        source="commands",
        action="browse",
        entries=[
            {
                "category": category,
                "command": command_name,
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
        hint=f"Trimmed to fit one response: browse '{category} {command_name} <name>' for an omitted section or one keyword.",
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
        extras["hints"] = [
            "Try broader keywords (for example: create, property, solve).",
            "Try category + action (for example: ball create, contact property).",
        ]
        categories = CommandLoader.load_index(software=software).get("categories", {})
        extras["available_categories"] = sorted(categories.keys())
    return matches, extras
