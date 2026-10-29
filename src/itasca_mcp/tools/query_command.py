"""Itasca Command Query Tool - Keyword search for command documentation."""

from typing import Any

from itasca_mcp.knowledge.commands import CommandLoader
from itasca_mcp.knowledge.query import CommandSearch


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
                "short_description": metadata.get("short_description"),
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
