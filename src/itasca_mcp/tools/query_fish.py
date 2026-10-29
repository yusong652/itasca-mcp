"""FISH intrinsic search: the ``source='fish'`` branch of ``itasca_query_doc``."""

from __future__ import annotations

from typing import Any

from itasca_mcp.knowledge.fish import FishLoader
from itasca_mcp.knowledge.query import FishSearch


def search(software: str, query: str, limit: int, version: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return ``(entries, summary extras)``; entries carry ``path`` for ``itasca_browse_doc``."""
    results = FishSearch.search(query, top_k=limit, software=software, version=version)
    entries: list[dict[str, Any]] = []
    for result in results:
        doc = result.document
        meta = doc.metadata or {}
        entries.append(
            {
                "path": doc.name,
                "name": doc.name,
                "signature": doc.syntax,
                "namespace": doc.category,
                "returns": meta.get("returns"),
                "settable": meta.get("settable"),
                "available_in": [v for v, ok in (meta.get("versions") or {}).items() if ok],
                "doc": meta.get("doc"),
                "score": round(result.score, 2),
                "rank": result.rank,
            }
        )

    extras: dict[str, Any] = {}
    if not entries:
        extras["hints"] = [
            "FISH names are dotted: try the namespace alone (ball, zone, block, math) or a fragment (pos, vel).",
            "Browse with source='fish' and no path to list the namespaces this engine exposes.",
        ]
        extras["available_namespaces"] = [
            ns["name"] for ns in FishLoader.namespaces(software=software, version=version)
        ]
    return entries, extras
