"""Itasca Python API Browse Tool - Navigate and retrieve Python SDK documentation."""

from typing import Any

from fastmcp import FastMCP
from pydantic import Field

from itasca_mcp.contracts import build_docs_data, build_error, build_ok
from itasca_mcp.knowledge.python_api import APILoader
from itasca_mcp.knowledge.python_api.types.mappings import CLASS_TO_MODULE
from itasca_mcp.utils import SoftwareParam, normalize_software_value


def register(mcp: FastMCP) -> None:
    """Register itasca_browse_python_api tool with the MCP server."""

    @mcp.tool()
    def itasca_browse_python_api(
        software: SoftwareParam,
        api: str | None = Field(
            None,
            description=(
                "Itasca Python API path to browse (dot-separated, starting from itasca). Examples:\n"
                "- None or '': Root overview - all modules and objects\n"
                "- 'itasca': Core module functions (command, cycle, gravity, etc.)\n"
                "- 'itasca.ball': Ball module functions (create, find, list, etc.)\n"
                "- 'itasca.ball.create': Specific function documentation\n"
                "- 'itasca.ball.Ball': Ball object method groups\n"
                "- 'itasca.ball.Ball.pos': Specific method documentation\n"
                "- 'itasca.wall.facet': Nested submodule\n"
                "- 'itasca.wall.facet.Facet': Facet object in wall.facet module"
            ),
        ),
    ) -> dict[str, Any]:
        """Browse Itasca Python SDK documentation by path (like glob + cat)."""
        normalized = _normalize_api_path(api)
        sw = normalize_software_value(software)

        if not normalized:
            return build_ok(_browse_root(sw))

        if normalized == "itasca":
            return _wrap_payload(_browse_module("itasca", sw))

        parsed = _parse_api_path(normalized, sw)

        if parsed["type"] == "error":
            return _wrap_payload(_browse_with_fallback(parsed, normalized, sw))

        if parsed["type"] == "module":
            payload = _browse_module(parsed["module_path"], sw)
            return _wrap_payload(payload)
        if parsed["type"] == "function":
            payload = _browse_function(parsed["module_path"], parsed["name"], sw)
            return _wrap_payload(payload)
        if parsed["type"] == "object":
            payload = _browse_object(
                parsed["module_path"],
                parsed["name"],
                parsed.get("display_name"),
                software=sw,
            )
            return _wrap_payload(payload)
        if parsed["type"] == "method":
            payload = _browse_method(
                parsed["module_path"],
                parsed["object_name"],
                parsed["name"],
                parsed.get("display_name"),
                software=sw,
            )
            return _wrap_payload(payload)

        return build_error(
            code="unknown_parse_type",
            message=f"Unknown parse result type: {parsed['type']}",
            details={"path": normalized},
        )


def _normalize_api_path(api: str | None) -> str:
    if api is None:
        return ""
    return api.strip()


def _parse_api_path(api: str, software: str) -> dict[str, Any]:
    if not api.startswith("itasca"):
        return {
            "type": "error",
            "error": f"Path must start with 'itasca', got: {api}",
            "fallback_path": "",
        }

    parts = api.split(".")
    index = APILoader.load_index(software=software)
    modules = index.get("modules", {})
    objects = index.get("objects", {})

    object_index = None
    for i, part in enumerate(parts):
        if i > 0 and part[0].isupper():
            object_index = i
            break

    if object_index is not None:
        module_parts = parts[:object_index]
        module_path = ".".join(module_parts)
        object_name = parts[object_index]

        actual_object_name = _resolve_object(module_path, object_name, objects)
        if actual_object_name is None:
            return {
                "type": "error",
                "error": f"Object '{object_name}' not found in {module_path}",
                "fallback_path": _nearest_module(module_parts, modules),
            }

        if len(parts) == object_index + 1:
            return {
                "type": "object",
                "module_path": module_path,
                "name": actual_object_name,
                "display_name": object_name,
            }

        method_name = parts[object_index + 1]
        return {
            "type": "method",
            "module_path": module_path,
            "object_name": actual_object_name,
            "display_name": object_name,
            "name": method_name,
        }

    for length in range(len(parts), 0, -1):
        candidate = ".".join(parts[:length])
        index_key = _path_to_index_key(candidate)

        if index_key in modules:
            if length == len(parts):
                return {
                    "type": "module",
                    "module_path": candidate,
                }

            func_name = parts[length]
            return {
                "type": "function",
                "module_path": candidate,
                "name": func_name,
            }

    return {
        "type": "error",
        "error": f"Module path not found: {api}",
        "fallback_path": _nearest_module(parts[:-1], modules),
    }


def _nearest_module(parts: list[str], modules: dict[str, Any]) -> str:
    """Longest prefix of `parts` that is a documented module (never an unknown path)."""
    for length in range(len(parts), 1, -1):
        candidate = ".".join(parts[:length])
        if _path_to_index_key(candidate) in modules:
            return candidate
    return "itasca"


def _object_home(object_info: dict[str, Any]) -> tuple[str, str] | None:
    """(module index key, class name) an object's doc file lives under.

    ``pfc/python_sdk_docs/modules/wall/facet/Facet.json`` -> ``("wall.facet", "Facet")``.
    """
    file_path = object_info.get("file") or ""
    _, sep, rel = file_path.partition("/modules/")
    if not sep:
        return None
    module_dir, _, file_name = rel.rpartition("/")
    return module_dir.replace("/", "."), file_name.removesuffix(".json")


def _resolve_object(module_path: str, object_name: str, objects: dict[str, Any]) -> str | None:
    """Index key of the object documented at ``module_path.object_name``, or None.

    The module path must match where the object is documented: a bare class name
    alone is ambiguous across modules (FLAC interface Node vs structure Node,
    clump Template vs rblock Template), and resolving it anyway returns another
    module's documentation for an undocumented class.
    """
    module_key = _path_to_index_key(module_path)
    for key, info in objects.items():
        home = _object_home(info)
        if home is None or home[0] != module_key:
            continue
        if object_name in (key.rsplit(".", 1)[-1], home[1]):
            return key

    # Legacy paths still emitted by search results (e.g. itasca.wall.Facet).
    if object_name in objects and CLASS_TO_MODULE.get(object_name) == module_key:
        return object_name

    # Concrete contact types (BallBallContact, ...) live in the itasca root namespace.
    if module_key == "itasca" and _is_documented_object_type(object_name, objects):
        return object_name

    return None


def _path_to_index_key(full_path: str) -> str:
    if full_path == "itasca":
        return "itasca"
    if full_path.startswith("itasca."):
        return full_path[7:]
    return full_path


def _format_module_path(index_key: str) -> str:
    if index_key == "itasca":
        return "itasca"
    return f"itasca.{index_key}"


def _is_documented_object_type(object_name: str, objects: dict[str, Any]) -> bool:
    return any(object_name in object_info.get("types", []) for object_info in objects.values())


def _extract_function_names(functions: list[Any]) -> list[str]:
    names: list[str] = []
    for func in functions:
        if isinstance(func, dict):
            name = func.get("name")
            if name:
                names.append(name)
        elif isinstance(func, str):
            names.append(func)
    return names


def _browse_root(software: str) -> dict[str, Any]:
    index = APILoader.load_index(software=software)
    modules = index.get("modules", {})
    objects = index.get("objects", {})

    module_items: list[dict[str, Any]] = []
    for module_key, module_info in modules.items():
        module_items.append(
            {
                "entry_type": "module",
                "path": _format_module_path(module_key),
                "description": module_info.get("description", ""),
                "function_count": len(module_info.get("functions", [])),
            }
        )

    object_items: list[dict[str, Any]] = []
    for object_name, object_info in objects.items():
        object_items.append(
            {
                "entry_type": "object",
                "name": object_name,
                "description": object_info.get("description", ""),
                "file": object_info.get("file"),
                "types": object_info.get("types"),
            }
        )

    entries = module_items + object_items
    return build_docs_data(
        source="python_api",
        action="browse",
        entries=entries,
        summary={
            "count": len(entries),
            "total_modules": len(module_items),
            "total_objects": len(object_items),
            "software": software,
        },
    )


def _browse_module(module_path: str, software: str) -> dict[str, Any]:
    index_key = _path_to_index_key(module_path)
    module_data = APILoader.load_module(index_key, software=software)

    if not module_data:
        return {
            "source": "python_api",
            "action": "browse",
            "error": {
                "code": "module_not_found",
                "message": f"Module not found: {module_path}",
            },
            "input": {"module_path": module_path, "software": software},
        }

    index = APILoader.load_index(software=software)
    objects = index.get("objects", {})
    related_objects = []
    for obj_name, obj_data in objects.items():
        file_path = obj_data.get("file", "")
        if index_key in file_path or (index_key == "itasca" and "/" not in file_path):
            related_objects.append(obj_name)

    functions = module_data.get("functions", [])
    function_names = _extract_function_names(functions)

    return build_docs_data(
        source="python_api",
        action="browse",
        entries=[{"entry_type": "function", "name": name} for name in function_names],
        summary={
            "count": len(function_names),
            "module_path": module_path,
            "module": {key: value for key, value in module_data.items() if key != "functions"},
            "related_objects": sorted(related_objects),
        },
    )


def _browse_function(module_path: str, func_name: str, software: str) -> dict[str, Any]:
    index_key = _path_to_index_key(module_path)
    func_doc = APILoader.load_function(index_key, func_name, software=software)

    if not func_doc:
        module_data = APILoader.load_module(index_key, software=software) or {}
        available_functions = _extract_function_names(module_data.get("functions", []))
        return {
            "source": "python_api",
            "action": "browse",
            "error": {
                "code": "function_not_found",
                "message": f"Function '{func_name}' not found in {module_path}",
            },
            "input": {"module_path": module_path, "function": func_name, "software": software},
            "available_functions": available_functions,
        }

    return build_docs_data(
        source="python_api",
        action="browse",
        entries=[
            {
                "module_path": module_path,
                "function": func_name,
                "doc": func_doc,
            }
        ],
        summary={"count": 1},
    )


def _browse_object(
    module_path: str, object_name: str, display_name: str | None = None, *, software: str
) -> dict[str, Any]:
    object_doc = APILoader.load_object(object_name, software=software)
    shown_name = display_name or object_name

    if not object_doc:
        index = APILoader.load_index(software=software)
        available_objects = sorted(index.get("objects", {}).keys())
        return {
            "source": "python_api",
            "action": "browse",
            "error": {
                "code": "object_not_found",
                "message": f"Object not found: {shown_name}",
            },
            "input": {"module_path": module_path, "object": shown_name, "software": software},
            "available_objects": available_objects,
        }

    return build_docs_data(
        source="python_api",
        action="browse",
        entries=[
            {
                "module_path": module_path,
                "object": shown_name,
                "actual_object": object_name,
                "doc": object_doc,
            }
        ],
        summary={"count": 1},
    )


def _browse_method(
    module_path: str,
    object_name: str,
    method_name: str,
    display_name: str | None = None,
    *,
    software: str,
) -> dict[str, Any]:
    method_doc = APILoader.load_method(object_name, method_name, software=software)
    shown_name = display_name or object_name

    if not method_doc:
        object_doc = APILoader.load_object(object_name, software=software) or {}
        method_names = _extract_function_names(object_doc.get("methods", []))
        return {
            "source": "python_api",
            "action": "browse",
            "error": {
                "code": "method_not_found",
                "message": f"Method '{method_name}' not found in {shown_name}",
            },
            "input": {
                "module_path": module_path,
                "object": shown_name,
                "actual_object": object_name,
                "method": method_name,
                "software": software,
            },
            "available_methods": method_names,
        }

    return build_docs_data(
        source="python_api",
        action="browse",
        entries=[
            {
                "module_path": module_path,
                "object": shown_name,
                "actual_object": object_name,
                "method": method_name,
                "doc": method_doc,
            }
        ],
        summary={"count": 1},
    )


def _browse_with_fallback(parsed: dict[str, Any], requested_api: str, software: str) -> dict[str, Any]:
    error_msg = parsed.get("error", "Unknown error")
    fallback_path = parsed.get("fallback_path", "")

    index = APILoader.load_index(software=software)
    modules = index.get("modules", {})
    available_modules = sorted(_format_module_path(module_key) for module_key in modules)

    return {
        "source": "python_api",
        "action": "browse",
        "error": {
            "code": "invalid_path",
            "message": error_msg,
        },
        "input": {"api": requested_api, "software": software},
        "fallback_path": fallback_path or "itasca",
        "available_modules": available_modules,
    }


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
