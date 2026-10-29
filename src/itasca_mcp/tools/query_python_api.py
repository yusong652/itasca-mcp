"""Itasca Python API Query Tool - Keyword search for SDK documentation."""

from typing import Any

from itasca_mcp.knowledge.python_api import APIDocFormatter, DocumentationLoader
from itasca_mcp.knowledge.query import APISearch


def search(software: str, query: str, limit: int, version: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return ``(entries, summary extras)``; entries carry ``path`` for ``itasca_browse_doc``.

    The SDK corpus is a single 9.8 baseline, so ``version`` does not filter here.
    """
    del version
    matches = APISearch.search(query, top_k=limit, software=software)
    entries: list[dict[str, Any]] = []
    for result in matches:
        api_path = result.document.name
        entries.append(
            {
                "path": api_path,
                "api_path": api_path,
                "signature": APIDocFormatter.format_signature(api_path, result.document.metadata, software=software),
                "category": result.document.category,
                "description": result.document.description,
                "score": round(result.score, 2),
                "rank": result.rank,
                "metadata": result.document.metadata,
            }
        )

    # Fallback hints fire on a query-text match, not only on an empty result
    # set. A hint key names something the SDK does not cover (material points
    # in MPoint, "model solve"), and for those the fuzzy matcher does return
    # results -- just misleading ones. Suppressing the hint exactly when the
    # search looks successful is the wrong way round.
    extras: dict[str, Any] = {}
    index = DocumentationLoader.load_index(software=software)
    hints = [msg for key, msg in index.get("fallback_hints", {}).items() if key in query.lower()]
    if hints:
        extras["hints"] = hints
    return entries, extras
