"""Itasca Command Query Tool - Keyword search for command documentation."""

from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from itasca_mcp.contracts import build_docs_data, build_error, build_ok
from itasca_mcp.knowledge.commands import CommandLoader
from itasca_mcp.knowledge.query import CommandSearch
from itasca_mcp.utils import (
    CommandDocVersion,
    SearchLimit,
    SearchQuery,
    SoftwareParam,
    effective_doc_version,
    normalize_command_doc_version,
    normalize_software_value,
    supported_doc_versions,
)


def register(mcp: FastMCP) -> None:
    """Register itasca_query_command tool with the MCP server."""

    @mcp.tool()
    def itasca_query_command(
        query: SearchQuery,
        software: SoftwareParam,
        limit: SearchLimit = 10,
        version: CommandDocVersion = Field(
            CommandDocVersion.V7_0,
            description=(
                "Documentation version to search. Defaults to 7.0 for multi-version engines "
                "(PFC: 6.0/7.0/9.0, FLAC: 7.0/9.0, 3DEC: 7.0/9.0); 9.0-only engines "
                "(MPoint, MassFlow) always resolve at 9.0."
            ),
        ),
    ) -> dict[str, Any]:
        """Search Itasca command documentation by keywords (like grep).

        Returns matching command paths. Use itasca_browse_commands for full documentation.

        When to use:
        - You have keywords but don't know exact command path
        - Example: "ball create", "contact property", "model solve"

        Related tools:
        - itasca_browse_commands: Get full documentation for a known command path
        - itasca_browse_reference: Browse reference docs (e.g., "contact-models linear")
        - itasca_query_python_api: Search Python SDK by keywords
        """
        sw = normalize_software_value(software)
        version_value = effective_doc_version(sw, normalize_command_doc_version(version))

        supported = supported_doc_versions(sw)
        if version_value not in supported:
            return build_error(
                code="unsupported_version",
                message=f"{sw} documentation covers versions: {', '.join(sorted(supported))}.",
                details={"input": {"software": sw, "version": version_value}},
            )

        results = CommandSearch.search_commands_only(query, top_k=limit, version=version_value, software=sw)
        matches: list[dict[str, Any]] = []
        for result in results:
            metadata = result.document.metadata or {}
            matches.append(
                {
                    "path": result.document.title,
                    "name": result.document.name,
                    "category": result.document.category,
                    "syntax": result.document.syntax,
                    "short_description": metadata.get("short_description"),
                    "score": round(result.score, 2),
                    "rank": result.rank,
                    "version": metadata.get("version", version_value),
                }
            )

        payload: dict[str, Any] = build_docs_data(
            source="commands",
            action="query",
            entries=matches,
            summary={
                "count": len(matches),
                "version": version_value,
                "software": sw,
            },
        )

        if not matches:
            categories = sorted(CommandLoader.load_index(software=sw).get("categories", {}).keys())
            payload["summary"]["hints"] = [
                "Try broader keywords (for example: create, property, solve).",
                "Try category + action (for example: ball create, contact property).",
            ]
            payload["summary"]["available_categories"] = categories

        return build_ok(payload)
