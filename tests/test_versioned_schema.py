"""Unit tests for the versioned command doc schema and loader."""

import pytest

from itasca_mcp.knowledge.commands.loader import CommandLoader


class TestLoadCommandDocVersioned:
    """Tests for CommandLoader.load_command_doc with versioned JSON schema."""

    def setup_method(self):
        CommandLoader.clear_cache()

    def test_version_specific_fields_merged_to_top_level(self):
        doc = CommandLoader.load_command_doc("ball", "create", "7.0", software="pfc")
        assert doc is not None
        assert "command" in doc
        assert "syntax" in doc
        assert "keywords" in doc
        assert "examples" in doc

    def test_version_field_values_are_correct(self):
        doc = CommandLoader.load_command_doc("ball", "create", "7.0", software="pfc")
        assert doc["command"] == "ball create"
        assert "ball create" in doc["syntax"]
        assert isinstance(doc["keywords"], list)
        assert len(doc["keywords"]) > 0
        assert isinstance(doc["examples"], list)
        assert len(doc["examples"]) > 0

    def test_shared_fields_remain_at_top_level(self):
        doc = CommandLoader.load_command_doc("ball", "create", "7.0", software="pfc")
        assert "description" in doc
        assert "search_keywords" in doc
        assert "category" in doc
        assert isinstance(doc["search_keywords"], list)

    def test_versions_collapsed_to_list(self):
        doc = CommandLoader.load_command_doc("ball", "create", "7.0", software="pfc")
        assert "versions" in doc
        assert isinstance(doc["versions"], list)
        assert "7.0" in doc["versions"]

    def test_unknown_version_raises_key_error(self):
        with pytest.raises(KeyError, match="5.0"):
            CommandLoader.load_command_doc("ball", "create", "5.0", software="pfc")

    def test_version_6_0_loads_correctly(self):
        doc = CommandLoader.load_command_doc("ball", "create", "6.0", software="pfc")
        assert doc is not None
        assert doc["command"] == "ball create"
        assert "syntax" in doc
        assert isinstance(doc["keywords"], list)
        assert len(doc["keywords"]) > 0
        assert "6.0" in doc["versions"]

    def test_version_6_0_unavailable_command(self):
        """A command absent from 6.0 is not in availability.versions and 6.0 raises."""
        import json

        import pytest

        from itasca_mcp.knowledge.config import resolve

        path = resolve("pfc/command_docs/commands/ball/accumulate-stress.json")
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert "6.0" not in raw["availability"]["versions"]
        with pytest.raises(KeyError):
            CommandLoader.load_command_doc("ball", "accumulate-stress", "6.0", software="pfc")

    def test_unknown_command_returns_none(self):
        result = CommandLoader.load_command_doc("ball", "nonexistent_cmd", "7.0", software="pfc")
        assert result is None

    def test_unknown_category_returns_none(self):
        result = CommandLoader.load_command_doc("nonexistent_cat", "create", "7.0", software="pfc")
        assert result is None

    def test_default_version_is_7_0(self):
        doc_default = CommandLoader.load_command_doc("ball", "create", software="pfc")
        doc_explicit = CommandLoader.load_command_doc("ball", "create", "7.0", software="pfc")
        assert doc_default["command"] == doc_explicit["command"]
        assert doc_default["syntax"] == doc_explicit["syntax"]

    def test_model_category_versioned(self):
        """Model commands are the primary target for multi-version support."""
        doc = CommandLoader.load_command_doc("model", "new", "7.0", software="pfc")
        assert doc is not None
        assert "command" in doc
        assert "syntax" in doc

    def test_keywords_list_contains_name_and_syntax(self):
        doc = CommandLoader.load_command_doc("ball", "create", "7.0", software="pfc")
        kw = doc["keywords"][0]
        assert "name" in kw
        assert "syntax" in kw

    def test_examples_list_contains_command_field(self):
        doc = CommandLoader.load_command_doc("ball", "create", "7.0", software="pfc")
        ex = doc["examples"][0]
        assert "command" in ex
