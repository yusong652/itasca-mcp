"""``itasca_query_doc``: one keyword search over the four documentation trees."""

from __future__ import annotations

from collections import Counter
from typing import Any, cast

from fastmcp import FastMCP
from pydantic import Field

from itasca_mcp.contracts import DocsSource, build_docs_data, build_ok
from itasca_mcp.tools.docs import commands, fish, python_api, reference
from itasca_mcp.tools.docs._common import VERSION_DESCRIPTION, resolve_doc_version
from itasca_mcp.utils import (
    CommandDocVersion,
    DocQuery,
    DocSource,
    SearchLimit,
    SoftwareParam,
    normalize_doc_source,
    normalize_software_value,
)

_SEARCHERS = {
    "commands": commands.search,
    "python_api": python_api.search,
    "fish": fish.search,
    "reference": reference.search,
}

SOURCE_DESCRIPTION = (
    "Documentation tree to search: 'commands', 'python_api', 'fish' or 'reference'. Omit to search "
    "all four at once; each hit is then tagged with its source."
)


def register(mcp: FastMCP) -> None:
    """Register itasca_query_doc with the MCP server."""

    @mcp.tool()
    def itasca_query_doc(
        software: SoftwareParam,
        query: DocQuery,
        source: DocSource | None = Field(None, description=SOURCE_DESCRIPTION),
        version: CommandDocVersion = Field(CommandDocVersion.V9_0, description=VERSION_DESCRIPTION),
        limit: SearchLimit = 10,
    ) -> dict[str, Any]:
        """Search ITASCA documentation by keywords, like grep; every hit carries a path for itasca_browse_doc.

        Without source it searches commands, python_api, fish and reference together, so
        'ball pos' shows the FISH intrinsic and the Python method side by side. With source
        it searches one tree and adds that tree's hints (available categories or
        namespaces, SDK fallback hints) when nothing matches.
        """
        sw = normalize_software_value(software)
        version_value, error = resolve_doc_version(sw, version)
        if error is not None or version_value is None:
            return error or {}

        if source is not None:
            src = normalize_doc_source(source)
            entries, extras = _SEARCHERS[src](sw, query, limit, version_value)
            for entry in entries:
                entry["source"] = src
            summary: dict[str, Any] = {"count": len(entries), "version": version_value, "software": sw, **extras}
            return build_ok(
                build_docs_data(source=cast(DocsSource, src), action="query", entries=entries, summary=summary)
            )

        return build_ok(_search_all(sw, query, limit, version_value))


def _search_all(software: str, query: str, limit: int, version: str) -> dict[str, Any]:
    """Merge the four trees: scores are normalised per tree (each tree's best hit = 1.0).

    BM25 scores are not comparable across indexes, so the merge ranks hits by how
    strong they are within their own tree. The practical effect is that each tree's
    top hit lands near the front, which is the side-by-side view this mode exists for.
    """
    merged: list[dict[str, Any]] = []
    hints: list[str] = []
    for src, searcher in _SEARCHERS.items():
        entries, extras = searcher(software, query, limit, version)
        if src == "python_api":  # SDK fallback hints fire on query text, not on empty results
            hints.extend(extras.get("hints", []))
        best = max((float(e.get("score") or 0.0) for e in entries), default=0.0) or 1.0
        for entry in entries:
            entry["source"] = src
            entry["_norm"] = float(entry.get("score") or 0.0) / best
            merged.append(entry)

    merged.sort(key=lambda e: e["_norm"], reverse=True)
    merged = merged[:limit]
    for rank, entry in enumerate(merged, start=1):
        entry["rank"] = rank
        entry.pop("_norm", None)

    summary: dict[str, Any] = {
        "count": len(merged),
        "by_source": dict(Counter(e["source"] for e in merged)),
        "version": version,
        "software": software,
    }
    if hints:
        summary["hints"] = hints
    if not merged:
        summary["hints"] = [
            *hints,
            "No tree matched; try fewer or more generic keywords, or browse a tree from its top.",
        ]
    return build_docs_data(source="all", action="query", entries=merged, summary=summary)
