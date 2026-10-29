"""Integrity tests for vectorized Python array API documentation."""

import json
from pathlib import Path
from typing import Any

from itasca_mcp.knowledge.config import python_docs_root, resolve
from itasca_mcp.knowledge.python_api.loader import PythonAPILoader

ARRAY_MODULES = {
    "ballarray",
    "clumparray",
    "wallarray",
    "rblockarray",
    "ballballarray",
    "ballfacetarray",
    "ballpebblearray",
    "pebblepebblearray",
    "pebblefacetarray",
    "ballrblockarray",
    "cfdarray",
    "facetarray",
    "pebblearray",
    "pebblerblockarray",
    "rblockfacetarray",
    "rblockrblockarray",
    "vertexarray",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def setup_function() -> None:
    PythonAPILoader.clear_cache()


def test_array_modules_load_from_index() -> None:
    index = PythonAPILoader.load_index(software="pfc")

    for module in ARRAY_MODULES:
        assert module in index["modules"]
        doc = PythonAPILoader.load_module(module, software="pfc")
        assert doc is not None
        assert doc["module"] == f"itasca.{module}"
        assert any(func["name"] == "pos" for func in doc["functions"])


def test_ballarray_full_module_doc_loads_without_truncation_at_loader_layer() -> None:
    doc = PythonAPILoader.load_module("ballarray", software="pfc")

    assert doc is not None
    function_names = {func["name"] for func in doc["functions"]}
    assert "pos" in function_names
    assert "set_pos" in function_names


def test_array_quick_refs_resolve_to_existing_functions() -> None:
    index = PythonAPILoader.load_index(software="pfc")

    for api_path, ref in index["quick_ref"].items():
        if not any(api_path.startswith(f"itasca.{module}.") for module in ARRAY_MODULES):
            continue

        file_name, anchor = ref.split("#", 1)
        doc_path = resolve(file_name)
        assert doc_path.exists(), api_path

        doc = _load_json(doc_path)
        function_names = {func["name"] for func in doc.get("functions", [])}
        assert anchor in function_names, api_path


def test_array_keywords_point_to_quick_ref_entries() -> None:
    index = PythonAPILoader.load_index(software="pfc")
    quick_ref = index["quick_ref"]

    for module in ARRAY_MODULES:
        keywords_path = python_docs_root("pfc") / "modules" / module / "keywords.json"
        keywords = _load_json(keywords_path)["keywords"]
        for api_list in keywords.values():
            assert isinstance(api_list, list)
            for api_path in api_list:
                assert api_path in quick_ref, api_path


# Version gates measured on live 6.0 / 7.0 / 9.0 consoles: cfdarray group access exists only in 6.0.
VERSION_GATED = {
    ("cfdarray", "in_group"): ["6.0"],
    ("cfdarray", "set_group"): ["6.0"],
}


def test_array_modules_advertise_all_three_versions() -> None:
    for module in ARRAY_MODULES:
        doc = PythonAPILoader.load_module(module, software="pfc")
        assert doc is not None
        for func in doc["functions"]:
            expected = VERSION_GATED.get((module, func["name"]), ["6.0", "7.0", "9.0"])
            assert func["availability"]["versions"] == expected, f"{module}.{func['name']} version gate changed"
