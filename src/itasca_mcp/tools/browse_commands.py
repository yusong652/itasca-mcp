"""Itasca Command Browse Tool - Navigate and retrieve command documentation."""

from typing import Any

from itasca_mcp.contracts import build_docs_data, build_error, build_ok
from itasca_mcp.knowledge.commands import CommandLoader
from itasca_mcp.utils import (
    normalize_input,
)


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
    return _wrap_payload(payload)


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

    cat_data = categories[category]
    command_items: list[dict[str, Any]] = []
    for cmd, cmd_doc in _iter_available_category_commands(category, version, software):
        command_items.append(
            {
                "name": cmd.get("name", ""),
                "short_description": cmd.get("short_description", ""),
                "syntax": cmd_doc.get("syntax"),
                "python_available": bool(cmd.get("python_available", False)),
            }
        )

    return build_docs_data(
        source="commands",
        action="browse",
        entries=command_items,
        summary={
            "count": len(command_items),
            "category": category,
            "description": cat_data.get("description", ""),
            "version": version,
            "software": software,
        },
    )


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

        available_cmds = [
            cmd_meta.get("name")
            for cmd_meta, _cmd_doc in _iter_available_category_commands(category, version, software)
        ]
        return {
            "source": "commands",
            "action": "browse",
            "error": {
                "code": "command_not_found",
                "message": f"Command '{command_name}' not found in '{category}'.",
            },
            "input": {"category": category, "command": command_name, "version": version, "software": software},
            "available_commands": available_cmds,
        }

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

    return build_docs_data(
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
