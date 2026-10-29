"""Reference documentation (models, range elements, plot items): browse by path, search by keywords.

Exposes ``browse(software, path, version)`` and ``search(software, query, limit, version)``
for the ``reference`` source of itasca_browse_doc / itasca_query_doc.
"""

from __future__ import annotations

from itertools import chain
from typing import Any, cast

from itasca_mcp.contracts import build_docs_data, build_error, build_ok
from itasca_mcp.knowledge.query.reference_search import ReferenceSearch
from itasca_mcp.knowledge.references import ReferenceLoader
from itasca_mcp.tools.docs._common import compact_field, omit_largest, trim_to_response
from itasca_mcp.utils import (
    normalize_input,
)


def browse(software: str, path: str | None, version: str) -> dict[str, Any]:
    """'' -> categories; 'contact-models' -> items; 'contact-models linear' -> doc; 3 parts -> sub-item or section."""
    topic_str = normalize_input(path, lowercase=True)
    if not topic_str:
        return build_ok(_browse_references_root(version, software))

    parts = topic_str.split()
    category = parts[0]
    if len(parts) == 1:
        payload = _browse_category(category, version, software)
    elif len(parts) == 2:
        payload = _browse_item(category, parts[1], version, software)
    else:
        payload = _browse_sub_item(category, parts[1], " ".join(parts[2:]), version, software)
    return _wrap_payload(payload)


def _browse_references_root(version: str, software: str) -> dict[str, Any]:
    refs_index = ReferenceLoader.load_index(software=software)
    categories = refs_index.get("categories", {})
    category_items: list[dict[str, Any]] = []

    for category_name, category_data in categories.items():
        items = ReferenceLoader.get_item_list(category_name, version, software=software)
        category_items.append(
            {
                "name": category_name,
                "description": category_data.get("description", ""),
                "item_count": len(items),
            }
        )

    return build_docs_data(
        source="reference",
        action="browse",
        entries=category_items,
        summary={"count": len(category_items), "version": version, "software": software},
    )


def _browse_category(category: str, version: str, software: str) -> dict[str, Any]:
    refs_index = ReferenceLoader.load_index(software=software)
    categories = refs_index.get("categories", {})

    if category not in categories:
        return {
            "source": "reference",
            "action": "browse",
            "error": {
                "code": "category_not_found",
                "message": f"Category '{category}' not found.",
            },
            "input": {"category": category, "version": version, "software": software},
            "available_categories": sorted(categories.keys()),
        }

    cat_index = cast(dict[str, Any], ReferenceLoader.load_category_index(category, software=software))
    if not cat_index:
        return {
            "source": "reference",
            "action": "browse",
            "error": {
                "code": "category_index_not_found",
                "message": f"Category index not found for '{category}'.",
            },
            "input": {"category": category, "version": version, "software": software},
        }
    raw_items = ReferenceLoader.get_item_list(category, version, software=software)
    items = []
    for item in raw_items:
        entry: dict[str, Any] = {
            "name": item.get("name", ""),
            "description": item.get("description", ""),
        }
        if "full_name" in item:
            entry["full_name"] = item["full_name"]
        if "category" in item:
            entry["category"] = item["category"]
        if "common_use" in item:
            entry["common_use"] = item["common_use"]
        if "availability" in item:
            entry["availability"] = item["availability"]
        items.append(entry)

    return build_docs_data(
        source="reference",
        action="browse",
        entries=items,
        summary={
            "count": len(items),
            "category": category,
            "version": version,
            "software": software,
        },
    )


def _browse_item(category: str, item: str, version: str, software: str) -> dict[str, Any]:
    refs_index = ReferenceLoader.load_index(software=software)
    categories = refs_index.get("categories", {})
    if category not in categories:
        return {
            "source": "reference",
            "action": "browse",
            "error": {
                "code": "category_not_found",
                "message": f"Category '{category}' not found.",
            },
            "input": {"category": category, "item": item, "version": version, "software": software},
            "available_categories": sorted(categories.keys()),
        }

    item_doc = ReferenceLoader.load_item_doc(category, item, software=software)

    if not item_doc:
        items = ReferenceLoader.get_item_list(category, version, software=software)
        available = [i.get("name", "") for i in items]
        return {
            "source": "reference",
            "action": "browse",
            "error": {
                "code": "item_not_found",
                "message": f"Item '{item}' not found in '{category}'.",
            },
            "input": {"category": category, "item": item, "version": version, "software": software},
            "available_items": available,
        }

    availability = item_doc.get("availability")
    if isinstance(availability, dict) and not availability.get(version, False):
        supported = [v for v, ok in availability.items() if ok]
        return {
            "source": "reference",
            "action": "browse",
            "error": {
                "code": "item_unavailable_for_version",
                "message": (
                    f"'{item}' is not available in {software} {version} (available in: {', '.join(supported) or 'none'})."
                ),
            },
            "input": {"category": category, "item": item, "version": version, "software": software},
            "available_versions": supported,
        }

    # Directory-based item: return overview with sub-item list instead of full doc
    if ReferenceLoader.is_directory_item(category, item, software=software):
        sub_items = item_doc.get("sub_items", [])
        overview: dict[str, Any] = {
            "category": category,
            "item": item,
            "description": item_doc.get("description", ""),
            "base_syntax": item_doc.get("base_syntax", ""),
        }
        if "basic_keywords" in item_doc:
            overview["basic_keywords"] = item_doc["basic_keywords"]
        if "common_usage_patterns" in item_doc:
            overview["common_usage_patterns"] = item_doc["common_usage_patterns"]
        overview["sub_items"] = [{"name": s["name"], "description": s.get("description", "")} for s in sub_items]
        return build_docs_data(
            source="reference",
            action="browse",
            entries=[overview],
            summary={
                "count": 1,
                "sub_item_count": len(sub_items),
                "version": version,
                "hint": f"Browse '{category} {item} <sub_item>' (source='reference') for details",
            },
        )

    entry: dict[str, Any] = {
        "category": category,
        "item": item,
        "doc": item_doc,
    }
    summary: dict[str, Any] = {"count": 1, "version": version}
    if isinstance(item_doc.get("availability"), dict):
        summary["available_in"] = [v for v, ok in item_doc["availability"].items() if ok]
    payload = build_docs_data(
        source="reference",
        action="browse",
        entries=[entry],
        summary=summary,
    )
    doc = payload["entries"][0]["doc"]  # model_dump copy: safe to trim
    trim_to_response(
        payload,
        chain(
            omit_largest(doc, keep=_ITEM_CORE_FIELDS),
            compact_field(doc, "property_groups", _property_keywords),
            omit_largest(doc, keep=_ITEM_IDENTITY_FIELDS),
        ),
        hint=(
            f"Trimmed to fit one response: browse '{category} {item} <name>' for an omitted section or one property."
        ),
    )
    return payload


# Fields every item page keeps when trimmed; the rest (workflows, callback events...) are extra sections.
_ITEM_IDENTITY_FIELDS = (
    "name",
    "model",
    "full_name",
    "category",
    "category_name",
    "description",
    "syntax",
    "availability",
    "property_groups",
    "parameters",
)
_ITEM_CORE_FIELDS = (*_ITEM_IDENTITY_FIELDS, "alt_syntax", "dimension", "usage", "examples", "notes")


def _property_keywords(groups: list[Any]) -> list[Any]:
    return [
        {**group, "properties": [p.get("keyword") for p in group.get("properties", []) if isinstance(p, dict)]}
        if isinstance(group, dict)
        else group
        for group in groups
    ]


def _properties(item_doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        prop
        for group in item_doc.get("property_groups") or []
        if isinstance(group, dict)
        for prop in group.get("properties", [])
        if isinstance(prop, dict)
    ]


def _browse_item_part(category: str, item: str, part: str, version: str, software: str) -> dict[str, Any]:
    """One section ('callback_events') or property ('pb_ten') of a single-file item doc."""
    item_payload = _browse_item(category, item, version, software)
    if "error" in item_payload:  # unknown category/item or unavailable in this version
        return item_payload
    item_doc = ReferenceLoader.load_item_doc(category, item, software=software) or {}

    entry: dict[str, Any] = {"category": category, "item": item}
    prop = next((p for p in _properties(item_doc) if str(p.get("keyword", "")).lower() == part), None)
    if part in item_doc:
        entry["section"] = part
        entry["content"] = item_doc[part]
    elif prop is not None:
        entry["property"] = prop
    else:
        return {
            "source": "reference",
            "action": "browse",
            "error": {
                "code": "section_not_found",
                "message": f"'{category} {item}' has no section or property '{part}'.",
            },
            "input": {"category": category, "item": item, "part": part, "version": version, "software": software},
            "available_sections": sorted(item_doc),
            "available_properties": [p.get("keyword") for p in _properties(item_doc)],
        }
    return build_docs_data(
        source="reference",
        action="browse",
        entries=[entry],
        summary={"count": 1, "version": version},
    )


def _browse_sub_item(category: str, item: str, sub_item: str, version: str, software: str) -> dict[str, Any]:
    refs_index = ReferenceLoader.load_index(software=software)
    categories = refs_index.get("categories", {})
    if category not in categories:
        return {
            "source": "reference",
            "action": "browse",
            "error": {
                "code": "category_not_found",
                "message": f"Category '{category}' not found.",
            },
            "input": {
                "category": category,
                "item": item,
                "sub_item": sub_item,
                "version": version,
                "software": software,
            },
            "available_categories": sorted(categories.keys()),
        }

    if not ReferenceLoader.is_directory_item(category, item, software=software):
        return _browse_item_part(category, item, sub_item, version, software)

    sub_doc = ReferenceLoader.load_sub_item_doc(category, item, sub_item, software=software)
    if not sub_doc:
        item_doc = ReferenceLoader.load_item_doc(category, item, software=software)
        available = [s["name"] for s in (item_doc or {}).get("sub_items", [])]
        return {
            "source": "reference",
            "action": "browse",
            "error": {
                "code": "sub_item_not_found",
                "message": f"Sub-item '{sub_item}' not found in '{category} {item}'.",
            },
            "input": {
                "category": category,
                "item": item,
                "sub_item": sub_item,
                "version": version,
                "software": software,
            },
            "available_sub_items": available,
        }

    return build_docs_data(
        source="reference",
        action="browse",
        entries=[
            {
                "category": category,
                "item": item,
                "sub_item": sub_item,
                "doc": sub_doc,
            }
        ],
        summary={"count": 1, "version": version},
    )


def _wrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if "error" in payload:
        err = payload.get("error") or {}
        details = {k: v for k, v in payload.items() if k != "error"}
        return build_error(
            code=str(err.get("code") or "browse_error"),
            message=str(err.get("message") or "Browse failed"),
            details=details or None,
        )
    return build_ok(payload)


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
