"""Regression tests for the rblock Python SDK docs integration."""

from itasca_mcp.knowledge.python_api.formatter import PythonAPIFormatter
from itasca_mcp.knowledge.python_api.loader import PythonAPILoader


class TestRBlockPythonApiDocs:
    def setup_method(self) -> None:
        PythonAPILoader.clear_cache()

    def test_rblock_module_loads(self) -> None:
        doc = PythonAPILoader.load_module("rblock", software="pfc")

        assert doc is not None
        assert doc["module"] == "itasca.rblock"
        function_names = [func["name"] for func in doc["functions"]]
        assert "count" in function_names
        assert "near" in function_names

    def test_rblock_template_module_loads(self) -> None:
        doc = PythonAPILoader.load_module("rblock.template", software="pfc")

        assert doc is not None
        assert doc["module"] == "itasca.rblock.template"
        function_names = [func["name"] for func in doc["functions"]]
        assert "find" in function_names
        assert "maxid" in function_names

    def test_rblock_object_loads(self) -> None:
        doc = PythonAPILoader.load_object("RBlock", software="pfc")

        assert doc is not None
        assert doc["class"] == "RBlock"
        assert any(method["name"] == "id" for method in doc["methods"])
        assert any(method["name"] == "vol" for method in doc["methods"])

    def test_rblock_template_object_loads(self) -> None:
        doc = PythonAPILoader.load_object("RBlockTemplate", software="pfc")

        assert doc is not None
        assert doc["class"] == "Template"
        assert any(method["name"] == "name" for method in doc["methods"])
        assert any(method["name"] == "vol" for method in doc["methods"])

    def test_rblock_object_method_loads(self) -> None:
        doc = PythonAPILoader.load_method("RBlock", "id", software="pfc")

        assert doc is not None
        assert doc["name"] == "id"
        assert doc["signature"].startswith("rblock.id()")

    def test_formatter_root_includes_rblock_paths(self) -> None:
        index = PythonAPILoader.load_index(software="pfc")
        text = PythonAPIFormatter.format_root(index["modules"], index["objects"])

        assert "itasca.rblock" in text
        assert "itasca.rblock.template" in text
        assert "itasca.rblock.RBlock" in text
        assert "itasca.rblock.template.RBlockTemplate" in text
