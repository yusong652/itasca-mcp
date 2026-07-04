"""ITASCA Reference Browse Tool - Navigate syntax elements and model properties."""

from typing import Any, cast

from fastmcp import FastMCP
from pydantic import Field

from itasca_mcp.contracts import build_docs_data, build_error, build_ok
from itasca_mcp.knowledge.references import ReferenceLoader
from itasca_mcp.utils import (
    CommandDocVersion,
    SoftwareParam,
    effective_doc_version,
    normalize_command_doc_version,
    normalize_input,
    normalize_software_value,
    supported_doc_versions,
)


def register(mcp: FastMCP) -> None:
    """Register itasca_browse_reference tool with the MCP server."""

    @mcp.tool()
    def itasca_browse_reference(
        software: SoftwareParam,
        topic: str | None = Field(
            None,
            description=(
                "Reference topic to browse (space-separated path). Categories vary by engine — "
                "call with no topic first to discover them. Examples (by engine):\n"
                "- None or '': List all reference categories for the chosen engine\n"
                "- PFC 'contact-models' / 'contact-models linear': contact model + its properties\n"
                "- FLAC 'constitutive-models' / 'constitutive-models mohr-coulomb': zone model + properties\n"
                "- 3DEC 'joint-models' / 'joint-models mohr': joint (sub-contact) model + properties\n"
                "- 'range-elements' / 'range-elements cylinder': range filter syntax (all engines)\n"
                "- 'plot-items' / 'plot-items <type>' / 'plot-items <type> <sub>': plot item keywords"
            ),
        ),
        version: CommandDocVersion = Field(
            CommandDocVersion.V7_0,
            description=(
                "Documentation version (PFC: 6.0/7.0/9.0, FLAC: 7.0/9.0). Only gates "
                "version-specific items (e.g. PFC contact models by availability). "
                "range-elements, plot-items, and the FLAC/3DEC reference sets are "
                "version-agnostic, so the value is ignored for them. "
                "9.0-only engines (3DEC, MPoint, MassFlow) always resolve at 9.0."
            ),
        ),
    ) -> dict[str, Any]:
        """Browse ITASCA reference documentation (syntax elements, model properties).

        Works across engines via the required ``software`` selector (pfc/flac/3dec).
        References are language elements used within commands, not standalone commands.

        Navigation levels:
        - No topic: All reference categories for the engine
        - Category (e.g., "constitutive-models"): List items in category
        - Full path (e.g., "constitutive-models mohr-coulomb"): Full documentation
        - Sub-item path (e.g., "plot-items zone contour"): Sub-item details

        When to use:
        - Need material/contact/joint model property names (kn, ks, fric, cohesion, friction, ...)
        - Need range filtering syntax (position, cylinder, group, id)
        - Need plot item configuration (contour, label, color-by, cut, transparency, legend)
        - Setting up model-assignment commands (e.g. "... cmodel assign ... property ...")
        - Using range filters in any command
        - Configuring "plot item create" commands

        Related tools:
        - itasca_browse_commands: Command syntax (e.g., "zone create")
        - itasca_query_command: Search commands by keywords
        """
        topic_str = normalize_input(topic, lowercase=True)
        sw = normalize_software_value(software)
        version_value = effective_doc_version(sw, normalize_command_doc_version(version))

        supported = supported_doc_versions(sw)
        if version_value not in supported:
            return build_error(
                code="unsupported_version",
                message=f"{sw} documentation covers versions: {', '.join(sorted(supported))}.",
                details={"input": {"software": sw, "version": version_value}},
            )

        if not topic_str:
            return build_ok(_browse_references_root(version_value, sw))

        parts = topic_str.split()
        category = parts[0]

        if len(parts) == 1:
            payload = _browse_category(category, version_value, sw)
        elif len(parts) == 2:
            payload = _browse_item(category, parts[1], version_value, sw)
        else:
            # 3+ parts: category + item + sub-item (remaining parts joined)
            payload = _browse_sub_item(category, parts[1], " ".join(parts[2:]), version_value, sw)
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
                "hint": f"Use itasca_browse_reference('{category} {item} <sub_item>') for details",
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
    return build_docs_data(
        source="reference",
        action="browse",
        entries=[entry],
        summary=summary,
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
        return {
            "source": "reference",
            "action": "browse",
            "error": {
                "code": "no_sub_items",
                "message": f"Item '{item}' in '{category}' does not have sub-items.",
            },
            "input": {
                "category": category,
                "item": item,
                "sub_item": sub_item,
                "version": version,
                "software": software,
            },
        }

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
