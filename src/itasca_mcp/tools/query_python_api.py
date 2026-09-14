"""Itasca Python API Query Tool - Keyword search for SDK documentation."""

from typing import Any

from fastmcp import FastMCP

from itasca_mcp.contracts import build_docs_data, build_ok
from itasca_mcp.knowledge.python_api import APIDocFormatter, DocumentationLoader
from itasca_mcp.knowledge.query import APISearch
from itasca_mcp.utils import PythonAPISearchQuery, SearchLimit, SoftwareParam, normalize_software_value


def register(mcp: FastMCP) -> None:
    """Register itasca_query_python_api tool with the MCP server."""

    @mcp.tool()
    def itasca_query_python_api(
        query: PythonAPISearchQuery,
        software: SoftwareParam,
        limit: SearchLimit = 10,
    ) -> dict[str, Any]:
        """Search Itasca Python SDK documentation by keywords (like grep).

        Returns matching API paths with signatures. Use itasca_browse_python_api for full documentation.

        When to use:
        - You have keywords but don't know exact API path
        - Example: "ball velocity", "create", "contact force"

        Related tools:
        - itasca_browse_python_api: Get full documentation for a known API path
        - itasca_query_command: Search Itasca commands by keywords
        """
        sw = normalize_software_value(software)
        matches = APISearch.search(query, top_k=limit, software=sw)
        results_payload: list[dict[str, Any]] = []
        for result in matches:
            api_path = result.document.name
            sig = APIDocFormatter.format_signature(api_path, result.document.metadata, software=sw)
            results_payload.append(
                {
                    "api_path": api_path,
                    "signature": sig,
                    "category": result.document.category,
                    "description": result.document.description,
                    "score": round(result.score, 2),
                    "rank": result.rank,
                    "metadata": result.document.metadata,
                }
            )

        payload: dict[str, Any] = build_docs_data(
            source="python_api",
            action="query",
            entries=results_payload,
            summary={
                "count": len(results_payload),
                "software": sw,
            },
        )

        # Fallback hints fire on a query-text match, not only on an empty result
        # set. A hint key names something the SDK does not cover (material points
        # in MPoint, "model solve"), and for those the fuzzy matcher does return
        # results -- just misleading ones. Suppressing the hint exactly when the
        # search looks successful is the wrong way round.
        index = DocumentationLoader.load_index(software=sw)
        hints = [msg for key, msg in index.get("fallback_hints", {}).items() if key in query.lower()]
        if hints:
            payload["summary"]["hints"] = hints

        return build_ok(payload)
