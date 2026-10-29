"""Reference search: the ``source='reference'`` branch of ``itasca_query_doc``."""

from __future__ import annotations

from typing import Any

from itasca_mcp.knowledge.query.reference_search import ReferenceSearch
from itasca_mcp.knowledge.references import ReferenceLoader


def search(software: str, query: str, limit: int, version: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return ``(entries, summary extras)``; entries carry ``path`` for ``itasca_browse_doc``."""
    results = ReferenceSearch.search(query, top_k=limit, software=software, version=version)
    entries: list[dict[str, Any]] = []
    for result in results:
        doc = result.document
        meta = doc.metadata or {}
        entry: dict[str, Any] = {
            "path": doc.name,
            "category": meta.get("category"),
            "item": meta.get("item"),
            "description": doc.description,
            "score": round(result.score, 2),
            "rank": result.rank,
        }
        if meta.get("sub_item"):
            entry["sub_item"] = meta["sub_item"]
        if meta.get("full_name"):
            entry["full_name"] = meta["full_name"]
        entries.append(entry)

    extras: dict[str, Any] = {}
    if not entries:
        categories = sorted(ReferenceLoader.load_index(software=software).get("categories", {}).keys())
        extras["hints"] = ["Try a model, element or plot-item name (linear, mohr-coulomb, cylinder, contour)."]
        extras["available_categories"] = categories
    return entries, extras
