"""Documentation formatters for LLM consumption.

This module provides formatters that convert API documentation into
LLM-friendly markdown format. It handles:
- Brief signature formatting for quick reference
- Full documentation with examples and best practices
- Special formatting for Contact types
- Official API path generation
- Search result responses (no results, low confidence)
"""

from typing import Any

from itasca_mcp.knowledge.python_api.loader import DocumentationLoader
from itasca_mcp.knowledge.python_api.types.mappings import CLASS_TO_MODULE


class APIDocFormatter:
    """Formats API documentation as LLM-friendly markdown.

    This class provides static methods for formatting API documentation
    in various styles, optimized for LLM consumption and understanding.
    """

    @staticmethod
    def format_with_error(error_msg: str, fallback_content: str) -> str:
        """Prepend error message to fallback content.

        Used when a requested path doesn't exist but we can show the parent level.

        Args:
            error_msg: Error message describing what wasn't found
            fallback_content: Content from parent level to display

        Returns:
            Formatted markdown with error notice and fallback content
        """
        return f"Error: {error_msg}\n\n{fallback_content}"

    @staticmethod
    def _index_key_to_path(index_key: str) -> str:
        """Convert index key to full path.

        Examples:
        - "itasca" -> "itasca"
        - "ball" -> "itasca.ball"
        - "wall.facet" -> "itasca.wall.facet"
        """
        if index_key == "itasca":
            return "itasca"
        return f"itasca.{index_key}"

    @staticmethod
    def format_root(modules: dict[str, Any], objects: dict[str, Any]) -> str:
        """Format root overview of all modules and objects.

        Args:
            modules: Dict of module data from index
            objects: Dict of object data from index

        Returns:
            Formatted markdown string
        """
        parts = []

        # Build modules list
        module_lines = []
        for key, data in modules.items():
            full_path = APIDocFormatter._index_key_to_path(key)
            func_count = len(data.get("functions", []))
            desc = data.get("description", "")
            if len(desc) > 50:
                desc = desc[:47] + "..."
            module_lines.append(f"- {full_path} ({func_count} funcs): {desc}")

        # Build objects list
        object_lines = []
        for name, data in objects.items():
            desc = data.get("description", "")
            if len(desc) > 50:
                desc = desc[:47] + "..."

            # Find which module contains this object
            file_path = data.get("file", "")
            if "ball" in file_path:
                obj_path = f"itasca.ball.{name}"
            elif "clump/pebble" in file_path:
                obj_path = f"itasca.clump.pebble.{name}"
            elif "clump/template" in file_path:
                obj_path = f"itasca.clump.template.{name}"
            elif "clump" in file_path:
                obj_path = f"itasca.clump.{name}"
            elif "rblock/template" in file_path:
                obj_path = f"itasca.rblock.template.{name}"
            elif "rblock" in file_path:
                obj_path = f"itasca.rblock.{name}"
            elif "wall/facet" in file_path:
                obj_path = f"itasca.wall.facet.{name}"
            elif "wall/vertex" in file_path:
                obj_path = f"itasca.wall.vertex.{name}"
            elif "wall" in file_path:
                obj_path = f"itasca.wall.{name}"
            elif "measure" in file_path:
                obj_path = f"itasca.measure.{name}"
            else:
                obj_path = name

            # Handle Contact interface aliases - concrete contact types are in the itasca root namespace.
            contact_types = data.get("types", [])
            if contact_types:
                for ct in contact_types:
                    object_lines.append(f"- itasca.{ct}: {desc}")
                continue

            object_lines.append(f"- {obj_path}: {desc}")

        parts.append("## Itasca Python SDK Documentation")
        parts.append("")
        parts.append(f"Modules ({len(modules)}):")
        parts.append("\n".join(module_lines))
        parts.append("")
        parts.append(f"Objects ({len(object_lines)}):")
        parts.append("\n".join(object_lines))
        return "\n".join(parts)

    @staticmethod
    def format_module(module_path: str, module_data: dict[str, Any], related_objects: list[str] | None = None) -> str:
        """Format module overview with its functions.

        Args:
            module_path: Full module path (e.g., "itasca.ball")
            module_data: Module data dict
            related_objects: Optional list of related object names

        Returns:
            Formatted markdown string
        """
        parts = []

        functions = module_data.get("functions", [])
        description = module_data.get("description", "")

        # Build function list
        func_lines = []
        for func in functions:
            if isinstance(func, dict):
                name = func.get("name", "")
                desc = func.get("description", "")
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                func_lines.append(f"- {name}: {desc}")
            else:
                func_lines.append(f"- {func}")

        parts.append(f"## {module_path}")
        parts.append("")
        if description:
            parts.append(description)
            parts.append("")
        parts.append(f"Functions ({len(func_lines)}):")
        parts.append("\n".join(func_lines))

        if related_objects:
            obj_paths = [f"{module_path}.{obj}" for obj in related_objects]
            parts.append("")
            parts.append(f"Related Objects: {', '.join(obj_paths)}")

        return "\n".join(parts)

    @staticmethod
    def format_object(
        module_path: str, object_name: str, object_doc: dict[str, Any], display_name: str | None = None
    ) -> str:
        """Format object overview with its method groups.

        Args:
            module_path: Full module path (e.g., "itasca.ball")
            object_name: Object name (e.g., "Ball")
            object_doc: Object documentation dict
            display_name: Optional display name for Contact types

        Returns:
            Formatted markdown string
        """
        parts = []

        shown_name = display_name or object_name
        description = object_doc.get("description", "")
        note = object_doc.get("note", "")
        method_groups = object_doc.get("method_groups", {})
        methods = object_doc.get("methods", [])

        full_path = f"{module_path}.{shown_name}"

        # Build method groups or list
        method_lines = []
        if method_groups:
            for group_name, group_methods in method_groups.items():
                if isinstance(group_methods, list):
                    method_list = ", ".join(group_methods[:5])
                    if len(group_methods) > 5:
                        method_list += f", ... (+{len(group_methods) - 5})"
                    method_lines.append(f"- {group_name}: {method_list}")
                else:
                    method_lines.append(f"- {group_name}: {group_methods}")
        elif methods:
            method_names = []
            for m in methods:
                if isinstance(m, dict):
                    method_names.append(m.get("name", str(m)))
                else:
                    method_names.append(str(m))
            for i in range(0, len(method_names), 5):
                chunk = method_names[i : i + 5]
                method_lines.append(f"  {', '.join(chunk)}")

        parts.append(f"## {full_path}")
        parts.append("")
        if description:
            parts.append(description)
        if note:
            parts.append("")
            parts.append(f"Note: {note}")
        parts.append("")
        parts.append("Method Groups:")
        parts.append("\n".join(method_lines))
        return "\n".join(parts)

    @staticmethod
    def _detect_component_methods(object_name: str, method_name: str, *, software: str) -> list[str]:
        """Detect if a method has component alternatives (_x, _y, _z).

        Checks the object's method_groups or methods list to see if component
        methods exist for the given base method.

        Args:
            object_name: Object class name (e.g., "Ball", "Wall")
            method_name: Base method name (e.g., "vel", "pos")

        Returns:
            List of component suffixes (['x', 'y', 'z']) if components exist,
            empty list otherwise.

        Example:
            >>> APIDocFormatter._detect_component_methods("Ball", "vel")
            ['x', 'y', 'z']  # If vel_x, vel_y, vel_z exist
            >>> APIDocFormatter._detect_component_methods("Ball", "id")
            []  # No component methods for id()
        """
        try:
            object_doc = DocumentationLoader.load_object(object_name, software=software)
            if not object_doc:
                return []

            # Collect all method names from both method_groups and methods list
            all_method_names = set()

            # Strategy 1: Check method_groups (Ball, Clump, etc.)
            method_groups = object_doc.get("method_groups", {})
            for group_methods in method_groups.values():
                if isinstance(group_methods, list):
                    all_method_names.update(group_methods)

            # Strategy 2: Check flat methods list (Wall, Contact, etc.)
            methods = object_doc.get("methods", [])
            for method in methods:
                if isinstance(method, dict):
                    all_method_names.add(method.get("name", ""))
                elif isinstance(method, str):
                    all_method_names.add(method)

            # Check if base method and component methods exist
            has_base = method_name in all_method_names
            has_x = f"{method_name}_x" in all_method_names
            has_y = f"{method_name}_y" in all_method_names
            has_z = f"{method_name}_z" in all_method_names

            # If base method exists and at least one component exists, return components
            if has_base:
                components = []
                if has_x:
                    components.append("x")
                if has_y:
                    components.append("y")
                if has_z:
                    components.append("z")

                return components

            return []

        except Exception:
            # If any error occurs during detection, fail silently
            return []

    @staticmethod
    def format_signature(api_name: str, metadata: dict[str, Any] | None = None, *, software: str) -> str | None:
        """Format brief one-liner signature for quick reference.

        Args:
            api_name: Full API name (e.g., "itasca.ball.create")
            metadata: Optional metadata from SearchResult (for Contact type info)

        Returns:
            Brief signature string with return type and description
            Format: "`signature` -> return_type - brief description"
            For Contact APIs: includes supported contact types
            Returns None if API not found

        Example:
            >>> APIDocFormatter.format_signature("Ball.vel")
            "`ball.vel() -> vec` - Get ball velocity vector"

            >>> APIDocFormatter.format_signature(
            ...     "itasca.BallBallContact.force_global",
            ...     {"all_contact_types": ["BallBallContact", "BallFacetContact", ...]}
            ... )
            "`contact.force_global() -> vec` - Get contact force (supports: BallBallContact, BallFacetContact, ...)"
        """
        api_doc = DocumentationLoader.load_api_doc(api_name, software=software)
        if not api_doc:
            return None

        # Extract first line of description (usually the summary)
        description_lines = api_doc["description"].strip().split("\n")
        brief_desc = description_lines[0].strip()

        # Build signature - check if return type already in signature string
        signature = api_doc["signature"]
        if "->" not in signature and api_doc.get("returns"):
            return_type = api_doc["returns"]["type"]
            signature = f"{signature} -> {return_type}"

        # Add Contact type support information if available
        contact_suffix = ""
        if metadata and "all_contact_types" in metadata:
            contact_types = metadata["all_contact_types"]
            contact_suffix = f" (supports: {', '.join(contact_types)})"

        # Add component access information if available
        component_suffix = ""
        if metadata and "has_components" in metadata:
            components = metadata["has_components"]
            component_suffix = f" [has _{', _'.join(components)} components]"

        return f"`{signature}` - {brief_desc}{contact_suffix}{component_suffix}"

    @staticmethod
    def format_full_doc(api_doc: dict[str, Any], api_name: str, metadata: dict[str, Any] | None = None) -> str:
        """Format complete API documentation with Contact type support.

        Generates structured markdown with clear sections for LLM consumption:
        - Official API path (with Contact type mapping if applicable)
        - Signature and return type
        - Detailed description
        - Parameters with types and descriptions
        - Usage examples with code
        - Limitations and fallback commands
        - Best practices and notes

        Args:
            api_doc: Documentation dict from DocumentationLoader.load_api_doc()
            api_name: API name (e.g., "Ball.vel", "itasca.ball.create")
            metadata: Optional metadata dict (for Contact type info, etc.)

        Returns:
            Formatted markdown string

        Example output for Contact type:
            # itasca.BallBallContact.gap

            **Available for**: BallBallContact, BallFacetContact, ...

            **Signature**: `contact.gap() -> float`

            Get the gap between contact entities...

        Example output for regular API:
            # itasca.ball.create

            **Signature**: `ball.create(radius, pos=None)`

            Creates a new ball in the simulation...
        """
        lines = []

        # Generate official API path for display
        display_path = APIDocFormatter._get_display_path(api_name, metadata)

        # Header
        lines.append(f"# {display_path}")
        lines.append("")

        # Add Contact type availability info
        if metadata and "all_contact_types" in metadata:
            all_types = metadata["all_contact_types"]
            lines.append(f"**Available for**: {', '.join(all_types)}")
            lines.append("")

        # Add component access info if available
        if metadata and "has_components" in metadata:
            components = metadata["has_components"]
            method_name = api_name.split(".")[-1]
            component_list = ", ".join([f"`{method_name}_{c}()`" for c in components])
            lines.append(f"**Component Access**: {component_list}")
            lines.append("")
            lines.append("This method returns a vector. Individual components can be accessed via:")
            for c in components:
                lines.append(f"- `{method_name}_{c}()` - Get {c}-component only")
            lines.append("")

        # Signature
        lines.append(f"**Signature**: `{api_doc['signature']}`")
        lines.append("")

        # Description
        lines.append(api_doc["description"])
        lines.append("")

        # Parameters
        if api_doc.get("parameters"):
            lines.append("## Parameters")
            for param in api_doc["parameters"]:
                required = "**required**" if param["required"] else "*optional*"
                lines.append(f"- **`{param['name']}`** ({param['type']}, {required}): {param['description']}")
            lines.append("")

        # Returns
        if api_doc.get("returns"):
            ret = api_doc["returns"]
            lines.append("## Returns")
            lines.append(f"**`{ret['type']}`**: {ret['description']}")
            lines.append("")

        # Examples
        if api_doc.get("examples"):
            lines.append("## Examples")
            for i, ex in enumerate(api_doc["examples"], 1):
                lines.append(f"### Example {i}: {ex['description']}")
                lines.append("```python")
                lines.append(ex["code"])
                lines.append("```")
                lines.append("")

        # Limitations (IMPORTANT - guides LLM to command fallback)
        if api_doc.get("limitations"):
            lines.append("## Limitations")
            lines.append(api_doc["limitations"])
            lines.append("")

            if api_doc.get("fallback_commands"):
                lines.append(f"**When to use commands instead**: {', '.join(api_doc['fallback_commands'])}")
                lines.append("")

        # Best Practices
        if api_doc.get("best_practices"):
            lines.append("## Best Practices")
            for bp in api_doc["best_practices"]:
                lines.append(f"- {bp}")
            lines.append("")

        # Notes
        if api_doc.get("notes"):
            lines.append("## Notes")
            for note in api_doc["notes"]:
                lines.append(f"- {note}")
            lines.append("")

        # See Also
        if api_doc.get("see_also"):
            lines.append(f"**See Also**: {', '.join(api_doc['see_also'])}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _get_display_path(api_name: str, metadata: dict[str, Any] | None) -> str:
        """Generate official API path for display.

        Handles three cases:
        1. Contact types: itasca.{ContactType}.{method}
        2. Object methods: itasca.{module}.{Class}.{method}
        3. Module functions: itasca.{module}.{function}

        Args:
            api_name: Internal API name
            metadata: Optional metadata dict with contact_type info

        Returns:
            Official API path string

        Example:
            >>> _get_display_path("Contact.gap", {"contact_type": "BallBallContact"})
            "itasca.BallBallContact.gap"
            >>> _get_display_path("Ball.vel", None)
            "itasca.ball.Ball.vel"
            >>> _get_display_path("itasca.ball.create", None)
            "itasca.ball.create"
        """
        # Case 1: Contact types
        if metadata and "contact_type" in metadata:
            contact_type = metadata["contact_type"]
            method_name = api_name.split(".")[-1]  # Extract method from "Contact.gap"
            return f"itasca.{contact_type}.{method_name}"

        # Case 2: Object methods (e.g., "Ball.vel", "Wall.vel")
        if "." in api_name and not api_name.startswith("itasca."):
            class_name = api_name.split(".")[0]
            if class_name in CLASS_TO_MODULE:
                module_name = CLASS_TO_MODULE[class_name]
                return f"itasca.{module_name}.{api_name}"

        # Case 3: Module functions (already has full path)
        return api_name

    @staticmethod
    def format_no_results_response(query: str, hints: list[str] | None = None) -> str:
        """Format LLM content when no Python SDK API found.

        Args:
            query: Original search query
            hints: Optional list of hint messages from fallback_hints

        Returns:
            Formatted markdown string for LLM consumption

        Example output:
            **Python SDK**: Not available for this operation

            **Next Step**: Use itasca_query_doc(source='commands') tool to search for Itasca commands instead
        """
        hint_text = f"\nNote: {hints[0]}" if hints else ""

        return f"**Python SDK**: Not available for '{query}'{hint_text}"

    @staticmethod
    def format_function(func_doc: dict[str, Any], module_path: str) -> str:
        """Format function documentation for browse tool.

        Args:
            func_doc: Function documentation dict
            module_path: Full module path (e.g., "itasca.ball")

        Returns:
            LLM-friendly formatted markdown
        """
        lines = []

        name = func_doc.get("name", "")
        signature = func_doc.get("signature", f"{module_path}.{name}()")
        description = func_doc.get("description", "")

        lines.append(f"## {module_path}.{name}")
        lines.append("")
        lines.append(f"Signature: `{signature}`")
        lines.append("")
        lines.append(description)
        lines.append("")

        # Parameters
        params = func_doc.get("parameters", [])
        if params:
            lines.append("Parameters:")
            for param in params:
                pname = param.get("name", "")
                ptype = param.get("type", "")
                required = param.get("required", False)
                pdesc = param.get("description", "")
                req_str = "required" if required else "optional"
                lines.append(f"- {pname} ({ptype}, {req_str}): {pdesc}")
            lines.append("")

        # Returns
        returns = func_doc.get("returns", {})
        if returns:
            rtype = returns.get("type", "")
            rdesc = returns.get("description", "")
            lines.append(f"Returns: {rtype} - {rdesc}")
            lines.append("")

        # Limitations
        limitations = func_doc.get("limitations")
        if limitations:
            lines.append(f"Limitations: {limitations}")
            lines.append("")

        # Examples
        examples = func_doc.get("examples", [])
        if examples:
            lines.append("Example:")
            lines.append("```python")
            lines.append(examples[0].get("code", ""))
            lines.append("```")

        return "\n".join(lines)

    @staticmethod
    def format_method(
        method_doc: dict[str, Any], object_name: str, actual_object_name: str | None = None, *, software: str
    ) -> str:
        """Format method documentation for browse tool.

        Args:
            method_doc: Method documentation dict
            object_name: Display object name (e.g., "Ball", "BallBallContact")
            actual_object_name: Actual object name for loading documentation
                               (e.g., "Contact" when object_name is "BallBallContact")

        Returns:
            LLM-friendly formatted markdown
        """
        lines = []

        name = method_doc.get("name", "")
        signature = method_doc.get("signature", f"{object_name.lower()}.{name}()")
        description = method_doc.get("description", "")

        lines.append(f"## {object_name}.{name}")
        lines.append("")
        lines.append(f"Signature: `{signature}`")
        lines.append("")
        lines.append(description)
        lines.append("")

        # Parameters
        params = method_doc.get("parameters", [])
        if params:
            lines.append("Parameters:")
            for param in params:
                pname = param.get("name", "")
                ptype = param.get("type", "")
                required = param.get("required", False)
                pdesc = param.get("description", "")
                req_str = "required" if required else "optional"
                lines.append(f"- {pname} ({ptype}, {req_str}): {pdesc}")
            lines.append("")

        # Returns (with enhanced vec type information)
        returns = method_doc.get("returns", {})
        if returns:
            rtype = returns.get("type", "")
            rdesc = returns.get("description", "")

            # Enhance vec type description with indexing info
            if rtype == "vec":
                rdesc_enhanced = f"{rdesc} (indexable: [0]=x, [1]=y, [2]=z)"
                lines.append(f"Returns: {rtype} - {rdesc_enhanced}")
            else:
                lines.append(f"Returns: {rtype} - {rdesc}")
            lines.append("")

        # Component method detection and hints
        # Detect if this method has component alternatives (_x, _y, _z)
        # Use actual_object_name if provided (for Contact type aliases)
        lookup_name = actual_object_name or object_name
        components = APIDocFormatter._detect_component_methods(lookup_name, name, software=software)
        if components:
            component_list = ", ".join([f"`{name}_{c}()`" for c in components])
            lines.append(f"Component Access: {component_list}")
            lines.append("")
            lines.append("This method returns a vector. Individual components can be accessed via:")
            for c in components:
                lines.append(f"- `{name}_{c}()` - Get {c}-component only")
            lines.append("")

        # Examples
        examples = method_doc.get("examples", [])
        if examples:
            lines.append("Example:")
            lines.append("```python")
            lines.append(examples[0].get("code", ""))
            lines.append("```")

        return "\n".join(lines)
