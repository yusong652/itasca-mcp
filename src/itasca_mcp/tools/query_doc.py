"""``itasca_query_doc``: one keyword search over the four documentation trees."""

from __future__ import annotations

import re
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
    """Merge the four trees: per-tree normalised score, weighted by how much of the query the hit's name spells.

    BM25 scores are not comparable across indexes, so each tree's best hit is 1.0 and every
    tree's top hit lands near the front - the side-by-side view this mode exists for. Those
    1.0s tie, though, and a tie used to go to whichever tree was searched first, so a weak
    command outranked the FISH intrinsic the query named ('version code major' put
    geometry refine above version.code.major). The share of query words found in the hit's
    own path breaks that tie, and a path that is the query outright goes first.

    The merged entries carry that rank key as their ``score`` (so score is monotone with
    rank); a single-tree query keeps the tree's raw BM25 score.
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
            norm = float(entry.get("score") or 0.0) / best
            entry["_rank_key"] = norm * (1.0 + _name_coverage(query, _path_of(entry))) + _exact_bonus(query, entry)
            merged.append(entry)

    merged.sort(key=lambda e: e["_rank_key"], reverse=True)
    merged = merged[:limit]
    for rank, entry in enumerate(merged, start=1):
        entry["rank"] = rank
        entry["score"] = round(entry.pop("_rank_key"), 2)

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


_WORDS = re.compile(r"[a-z0-9]+")


def _path_of(entry: dict[str, Any]) -> str:
    return str(entry.get("path") or entry.get("name") or "")


def _name_coverage(query: str, path: str) -> float:
    """Share of the query's words found in the hit's own path (0.0-1.0).

    A word counts when it and a path token of 3+ characters are prefixes of one another,
    so abbreviated names still match spelled-out queries ('position' / pos, 'balls' / ball).
    """
    words = set(_WORDS.findall(query.lower()))
    if not words:
        return 0.0
    tokens = set(_WORDS.findall(path.lower()))
    stems = [t for t in tokens if len(t) >= 3]
    covered = {
        w for w in words if w in tokens or (len(w) >= 3 and any(w.startswith(t) or t.startswith(w) for t in stems))
    }
    return len(covered) / len(words)


def _exact_bonus(query: str, entry: dict[str, Any]) -> float:
    """1.0 when the hit's path is the query, or ends with it and the query is itself a name.

    A bare word ('fragment') ends many paths (Ball.fragment, Wall.fragment...); letting it
    count would bury the command or namespace the word usually means.
    """
    key = " ".join(query.lower().split())
    path = _path_of(entry).lower()
    if path == key:
        return 1.0
    looks_like_name = any(sep in key for sep in "._ ")
    return 1.0 if looks_like_name and path.endswith(("." + key, " " + key)) else 0.0
