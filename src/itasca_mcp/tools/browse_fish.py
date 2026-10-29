"""FISH intrinsic browsing: the ``source='fish'`` tree of ``itasca_browse_doc``.

FISH intrinsics are a lexical tree. ``ball`` is a namespace, ``ball.pos`` is a
function that is also the parent of ``ball.pos.x/y/z``; browsing a node shows
the node itself (when it is a function) followed by its direct children.
"""

from __future__ import annotations

from typing import Any

from itasca_mcp.contracts import build_docs_data, build_error, build_ok
from itasca_mcp.knowledge.fish import FishLoader
from itasca_mcp.utils import normalize_input

_ENTRY_FIELDS = (
    "name",
    "signature",
    "signature_7.0",
    "signature_source",
    "returns",
    "args",
    "settable",
    "dimension",
    "note",
    "family",
    "doc",
    "namespace",
    "scope",
)


def browse(software: str, path: str | None, version: str) -> dict[str, Any]:
    """'' -> namespaces; 'ball' -> children; 'ball.pos' -> its signature plus ball.pos.x/y/z."""
    node = normalize_input(path, lowercase=True)
    if not node:
        return build_ok(_browse_root(software, version))

    if not FishLoader.is_node(node, software=software):
        return build_error(
            code="intrinsic_not_found",
            message=f"No FISH intrinsic or namespace '{node}' in {software}.",
            details={
                "source": "fish",
                "input": {"path": node, "version": version, "software": software},
                "suggestions": FishLoader.suggest(node, software=software),
            },
        )

    entry = FishLoader.get(node, software=software)
    self_available = entry is not None and FishLoader.available(entry, version)
    children = [
        child
        for child in FishLoader.children(node, software=software)
        if FishLoader.has_available_descendant(child, version, software=software)
    ]

    if not self_available and not children:
        available_in = FishLoader.available_in(entry) if entry else _namespace_versions(node, software)
        return build_error(
            code="item_unavailable_for_version",
            message=f"'{node}' is not available in {software} {version} (available in: {', '.join(available_in) or 'none'}).",
            details={
                "source": "fish",
                "input": {"path": node, "version": version, "software": software},
                "available_versions": available_in,
            },
        )

    entries: list[dict[str, Any]] = []
    if entry is not None and self_available:
        entries.append(_entry_record(entry))
    for child in children:
        item: dict[str, Any] = {"name": child}
        child_entry = FishLoader.get(child, software=software)
        if child_entry is not None and FishLoader.available(child_entry, version):
            item["signature"] = child_entry.get("signature")
        grandchildren = FishLoader.children(child, software=software)
        if grandchildren:
            item["children"] = len(grandchildren)
        entries.append(item)

    summary: dict[str, Any] = {
        "count": len(entries),
        "path": node,
        "is_function": self_available,
        "child_count": len(children),
        "version": version,
        "software": software,
    }
    if "." not in node:
        notes = FishLoader.namespace_notes(node, software=software)
        if notes:
            summary["notes"] = notes
    return build_ok(build_docs_data(source="fish", action="browse", entries=entries, summary=summary))


def _browse_root(software: str, version: str) -> dict[str, Any]:
    index = FishLoader.load_index(software=software)
    namespaces = FishLoader.namespaces(software=software, version=version)
    excluded = {name: meta.get("count") for name, meta in index.get("excluded_namespaces", {}).items()}
    return build_docs_data(
        source="fish",
        action="browse",
        entries=namespaces,
        summary={
            "count": len(namespaces),
            "total_intrinsics": sum(ns["count"] for ns in namespaces),
            "kernel_verified": index.get("kernel_verified"),
            "excluded_namespaces": excluded,
            "version": version,
            "software": software,
        },
    )


def _entry_record(entry: dict[str, Any]) -> dict[str, Any]:
    record = {key: entry[key] for key in _ENTRY_FIELDS if key in entry}
    record["available_in"] = FishLoader.available_in(entry)
    return record


def _namespace_versions(prefix: str, software: str) -> list[str]:
    """Versions in which anything below ``prefix`` exists."""
    versions: set[str] = set()
    stack = [prefix]
    while stack:
        node = stack.pop()
        entry = FishLoader.get(node, software=software)
        if entry is not None:
            versions.update(FishLoader.available_in(entry))
        stack.extend(FishLoader.children(node, software=software))
    return sorted(versions)
