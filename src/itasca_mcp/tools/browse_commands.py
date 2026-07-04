"""Itasca Command Browse Tool - Navigate and retrieve command documentation."""

from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from itasca_mcp.contracts import build_docs_data, build_error, build_ok
from itasca_mcp.knowledge.commands import CommandLoader
from itasca_mcp.utils import (
    CommandDocVersion,
    SoftwareParam,
    effective_doc_version,
    normalize_command_doc_version,
    normalize_input,
    normalize_software_value,
    supported_doc_versions,
)


def register(mcp: FastMCP) -> None:
    """Register itasca_browse_commands tool with the MCP server."""

    @mcp.tool()
    def itasca_browse_commands(
        software: SoftwareParam,
        command: str | None = Field(
            None,
            description=(
                "Itasca command to browse (space-separated, matching Itasca command syntax). Examples:\n"
                "- None or '': List all command categories\n"
                "- 'ball': List all ball commands\n"
                "- 'ball create': Get ball create documentation\n"
                "- 'contact': List all contact commands\n"
                "- 'contact property': Get contact property command documentation"
            ),
        ),
        version: CommandDocVersion = Field(
            CommandDocVersion.V7_0,
            description=(
                "Documentation version to browse. Defaults to 7.0 for multi-version engines "
                "(PFC: 6.0/7.0/9.0, FLAC: 7.0/9.0); 9.0-only engines (3DEC, MPoint, MassFlow) "
                "always resolve at 9.0."
            ),
        ),
    ) -> dict[str, Any]:
        """Browse Itasca command documentation by path (like glob + cat).

        Navigation levels:
        - No command: All command categories overview
        - Category only (e.g., "ball"): List commands in category
        - Full command (e.g., "ball create"): Full documentation

        When to use:
        - You know the command category or exact command
        - You want to explore available commands

        Related tools:
        - itasca_query_command: Search commands by keywords (when path unknown)
        - itasca_browse_reference: Browse reference docs (e.g., "contact-models linear")
        """
        cmd = normalize_input(command, lowercase=True)
        sw = normalize_software_value(software)
        version_value = effective_doc_version(sw, normalize_command_doc_version(version))

        supported = supported_doc_versions(sw)
        if version_value not in supported:
            return build_error(
                code="unsupported_version",
                message=f"{sw} documentation covers versions: {', '.join(sorted(supported))}.",
                details={"input": {"software": sw, "version": version_value}},
            )

        if not cmd:
            return build_ok(_browse_root(version_value, sw))

        parts = cmd.split()

        if len(parts) == 1:
            payload = _browse_category(parts[0], version_value, sw)
        else:
            category = parts[0]
            command_name = " ".join(parts[1:])
            payload = _browse_command(category, command_name, version_value, sw)
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
