"""Markdown formatter for Itasca reference documentation.

This module formats reference documentation (contact models, range elements)
as markdown for LLM consumption.

Formatting Goals:
- Clear structure with headers
- Concise but complete information
- Highlight key syntax and examples
"""

from typing import Any


class ReferenceFormatter:
    """Format Itasca reference documentation as markdown.

    This class provides static methods for formatting contact models and
    range elements in a consistent, LLM-friendly markdown format.
    """

    @staticmethod
    def format_with_error(error_msg: str, fallback_content: str) -> str:
        """Prepend error message to fallback content.

        Used when a requested path doesn't exist but we can show the parent level.
        Format matches itasca_browse_doc(source='python_api') for consistency.

        Args:
            error_msg: Error message describing what wasn't found
            fallback_content: Content from parent level to display

        Returns:
            Formatted markdown with error notice and fallback content
        """
        return f"Error: {error_msg}\n\n{fallback_content}"

    @staticmethod
    def format_root(categories: dict[str, Any]) -> str:
        """Format reference categories overview as markdown.

        Args:
            categories: Dict of category data from index

        Returns:
            Formatted markdown string
        """
        parts = []

        parts.append("## Itasca Reference Documentation")
        parts.append("")
        parts.append(f"Total: {len(categories)} categories")
        parts.append("")

        for cat_name, cat_data in categories.items():
            desc = cat_data.get("description", "")
            summary = cat_data.get("summary", "")
            if len(desc) > 50:
                desc = desc[:47] + "..."
            parts.append(f"- {cat_name}: {desc}")
            if summary:
                parts.append(f"  ({summary})")

        return "\n".join(parts)

    @staticmethod
    def format_index(category: str, index: dict[str, Any]) -> str:
        """Format a reference category index as markdown.

        Unified formatter for both contact-models and range-elements indexes.

        Args:
            category: Category name (e.g., "contact-models", "range-elements")
            index: Category index dict (contains "models" or "elements" list)

        Returns:
            Formatted markdown string
        """
        parts = []

        # Detect index type and get items
        if "models" in index:
            items = index["models"]
            item_type = "model"
            title = "Contact Models"
            intro = "Contact models define mechanical behavior at contact points."
        elif "elements" in index:
            items = index["elements"]
            item_type = "element"
            title = "Range Elements"
            intro = "Range elements filter objects by geometric regions, attributes, or logical conditions."
        else:
            return "Unknown reference index format."

        # Header
        parts.append(f"## {title}")
        parts.append("")
        parts.append(intro)
        parts.append(f"Total: {len(items)} {item_type}s")
        parts.append("")

        # Item list - check if grouped by categories
        categories_info = index.get("categories", {})
        if categories_info and item_type == "element":
            # Grouped display for range-elements
            for cat_key, cat_data in categories_info.items():
                cat_name = cat_data.get("name", cat_key)
                cat_elements = cat_data.get("elements", [])
                parts.append(f"**{cat_name}**: {', '.join(cat_elements)}")
            parts.append("")
        else:
            # Simple list display for contact-models
            for item in items:
                name = item.get("name", "")
                # Handle different field names
                full_name = item.get("full_name", "")
                desc = item.get("description", "") or item.get("short_description", "")
                if len(desc) > 50:
                    desc = desc[:47] + "..."

                if full_name:
                    parts.append(f"- {name} ({full_name}): {desc}")
                else:
                    parts.append(f"- {name}: {desc}")
            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def format_contact_model(doc: dict[str, Any]) -> str:
        """Format a complete contact model documentation as markdown.

        Args:
            doc: Model documentation dict with all properties

        Returns:
            Formatted markdown string
        """
        parts = []

        model_name = doc.get("model", "unknown")
        model_full_name = doc.get("full_name", model_name)

        # Header
        parts.append(f"# {model_full_name}")
        parts.append(f"*Model name: `{model_name}`*")
        availability = doc.get("availability")
        if isinstance(availability, dict):
            avail_in = [v for v, ok in availability.items() if ok]
            parts.append(f"*Available in versions: {', '.join(avail_in) or 'none'}*")
        parts.append("")

        # Description
        description = doc.get("description", "")
        if description:
            parts.append("## Description")
            parts.append(description)
            parts.append("")

        # Typical Applications
        typical_apps = doc.get("typical_applications", [])
        if typical_apps:
            parts.append("## Typical Applications")
            for app in typical_apps:
                parts.append(f"- {app}")
            parts.append("")

        # Property Groups
        property_groups = doc.get("property_groups", [])
        if property_groups:
            parts.append("## Properties")
            parts.append("")

            for group in property_groups:
                group_name = group.get("name", "Properties")
                group_desc = group.get("description", "")

                parts.append(f"### {group_name}")
                if group_desc:
                    parts.append(f"*{group_desc}*")
                    parts.append("")

                properties = group.get("properties", [])
                if properties:
                    has_since = any(p.get("since") for p in properties)
                    if has_since:
                        parts.append("| Property | Symbol | Description | Type | Default | Since |")
                        parts.append("|----------|--------|-------------|------|---------|-------|")
                    else:
                        parts.append("| Property | Symbol | Description | Type | Default |")
                        parts.append("|----------|--------|-------------|------|---------|")

                    for prop in properties:
                        keyword = prop.get("keyword", "")
                        symbol = prop.get("symbol", "-")
                        desc = prop.get("description", "")
                        prop_type = prop.get("type", "")
                        default = prop.get("default", "-")

                        # Truncate description for table
                        if len(desc) > 60:
                            desc = desc[:57] + "..."

                        if has_since:
                            since = prop.get("since", "")
                            parts.append(f"| `{keyword}` | {symbol} | {desc} | {prop_type} | {default} | {since} |")
                        else:
                            parts.append(f"| `{keyword}` | {symbol} | {desc} | {prop_type} | {default} |")

                    parts.append("")

        # Usage Examples
        parts.append("## Usage")
        parts.append("Set properties for this model using:")
        parts.append(f"- Command: `contact cmat add model {model_name} property <prop> <value>`")
        parts.append("- Command: `contact property <prop> <value> range ...`")
        parts.append("- Python: `contact.set_prop('<prop>', value)`")
        parts.append("")

        return "\n".join(parts)

    @staticmethod
    def format_range_element(doc: dict[str, Any]) -> str:
        """Format a range element documentation as markdown.

        Args:
            doc: Range element documentation dict

        Returns:
            Formatted markdown string
        """
        parts = []

        elem_name = doc.get("name", "")
        category_name = doc.get("category_name", doc.get("category", ""))
        elem_syntax = doc.get("syntax", "")
        alt_syntax = doc.get("alt_syntax", "")
        elem_desc = doc.get("description", "")
        elem_examples = doc.get("examples", [])
        parameters = doc.get("parameters", [])
        supports_extent = doc.get("supports_extent", False)
        notes = doc.get("notes", [])
        related = doc.get("related", [])

        # Header
        parts.append(f"# range {elem_name}")
        parts.append(f"*Category: {category_name}*")
        parts.append("")

        # Syntax
        if elem_syntax:
            parts.append("## Syntax")
            parts.append("```")
            parts.append(f"range {elem_syntax}")
            parts.append("```")
            if alt_syntax:
                parts.append(f"**Alternative**: `range {alt_syntax}`")
            parts.append("")

        # Description
        if elem_desc:
            parts.append("## Description")
            parts.append(elem_desc)
            parts.append("")

        # Parameters
        if parameters:
            parts.append("## Parameters")
            parts.append("| Parameter | Type | Description |")
            parts.append("|-----------|------|-------------|")
            for param in parameters:
                p_name = param.get("name", "")
                p_type = param.get("type", "")
                p_desc = param.get("description", "")
                parts.append(f"| `{p_name}` | {p_type} | {p_desc} |")
            parts.append("")

        # Modifiers
        if supports_extent:
            parts.append("## Modifiers")
            parts.append("- Supports `extent` modifier (require entire object inside region)")
            parts.append("")

        # Examples
        if elem_examples:
            parts.append("## Examples")
            parts.append("```")
            for ex in elem_examples:
                parts.append(ex)
            parts.append("```")
            parts.append("")

        # Notes
        if notes:
            parts.append("## Notes")
            for note in notes:
                parts.append(f"- {note}")
            parts.append("")

        # Related
        if related:
            parts.append("## Related")
            for rel in related:
                parts.append(f"- `{rel}`")
            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def format_model_property(doc: dict[str, Any], property_keyword: str) -> str:
        """Format a contact model property documentation as markdown.

        Args:
            doc: Model documentation dict (full model with property_groups)
            property_keyword: Specific property keyword (e.g., "kn", "pb_kn")

        Returns:
            Formatted markdown string
        """
        parts = []

        model_name = doc.get("model", "unknown")
        model_full_name = doc.get("full_name", model_name)

        # Find the specific property
        target_property = None
        for group in doc.get("property_groups", []):
            for prop in group.get("properties", []):
                if prop.get("keyword") == property_keyword:
                    target_property = prop
                    break
            if target_property:
                break

        if not target_property:
            return f"# Property {property_keyword} not found in {model_name}"

        # Header
        parts.append(f"# {model_name}.{property_keyword}")
        parts.append(f"*{model_full_name}*")
        parts.append("")

        # Property details
        symbol = target_property.get("symbol", "")
        if symbol:
            parts.append(f"**Symbol**: {symbol}")

        prop_type = target_property.get("type", "")
        if prop_type:
            parts.append(f"**Type**: {prop_type}")

        description = target_property.get("description", "")
        if description:
            parts.append(f"**Description**: {description}")
            parts.append("")

        # Range and default
        prop_range = target_property.get("range", "")
        default = target_property.get("default", "")
        if prop_range or default:
            parts.append("## Value Constraints")
            if prop_range:
                parts.append(f"- **Range**: {prop_range}")
            if default:
                parts.append(f"- **Default**: {default}")
            parts.append("")

        # Flags
        modifiable = target_property.get("modifiable", True)
        inheritable = target_property.get("inheritable", False)
        parts.append("## Property Flags")
        parts.append(f"- **Modifiable**: {'Yes' if modifiable else 'No'}")
        parts.append(f"- **Inheritable**: {'Yes' if inheritable else 'No'}")
        since = target_property.get("since")
        if since:
            parts.append(f"- **Since**: version {since}")
        parts.append("")

        # Notes
        notes = target_property.get("notes", "")
        if notes:
            parts.append("## Notes")
            parts.append(notes)
            parts.append("")

        # Usage context
        parts.append("## Usage")
        parts.append("Set this property using:")
        parts.append(f"- Command: `contact cmat add ... property {property_keyword} <value>`")
        parts.append(f"- Command: `contact property {property_keyword} <value> range ...`")
        parts.append(f"- Python: `contact.set_prop('{property_keyword}', value)`")
        parts.append("")

        # Model context
        typical_apps = doc.get("typical_applications", [])
        if typical_apps:
            parts.append(f"## {model_full_name} - Typical Applications")
            for app in typical_apps:
                parts.append(f"- {app}")
            parts.append("")

        return "\n".join(parts)
