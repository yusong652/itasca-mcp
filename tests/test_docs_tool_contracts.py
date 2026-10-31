"""Contract tests for documentation tool response structures."""

import json

import pytest

from itasca_mcp.server import mcp


def _parse_tool_payload(result) -> dict:
    assert result is not None
    assert len(result.content) > 0
    text = result.content[0].text
    assert text.startswith("{")
    return json.loads(text)


@pytest.mark.asyncio
async def test_browse_commands_root_contract() -> None:
    result = await mcp.call_tool("itasca_browse_doc", {"source": "commands", "software": "pfc"})
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload.get("error") is None
    assert data["source"] == "commands"
    assert data["action"] == "browse"
    assert isinstance(data["entries"], list)
    assert data["summary"]["count"] >= 1
    assert data["summary"]["total_commands"] >= 1
    assert data["summary"]["version"] == "9.0"


@pytest.mark.asyncio
async def test_browse_commands_not_found_contract() -> None:
    result = await mcp.call_tool(
        "itasca_browse_doc",
        {"source": "commands", "path": "ball not_a_real_command", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "command_not_found"
    details = payload["error"].get("details") or {}
    assert details["source"] == "commands"
    assert details["input"]["category"] == "ball"
    assert details["input"]["command"] == "not_a_real_command"
    assert isinstance(details.get("available_commands"), list)


@pytest.mark.asyncio
async def test_query_command_contract() -> None:
    result = await mcp.call_tool(
        "itasca_query_doc",
        {"source": "commands", "query": "ball create", "limit": 5, "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["source"] == "commands"
    assert data["action"] == "query"
    assert data["summary"]["count"] >= 1
    assert data["summary"]["version"] == "9.0"
    assert isinstance(data["entries"], list)
    assert len(data["entries"]) >= 1


@pytest.mark.asyncio
async def test_browse_commands_versioned_contract() -> None:
    result = await mcp.call_tool(
        "itasca_browse_doc",
        {"source": "commands", "path": "brick assemble", "version": "6.0", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["summary"]["version"] == "6.0"
    doc = data["entries"][0]["doc"]
    assert doc["syntax"] == "brick assemble keyword [range]"


@pytest.mark.asyncio
async def test_browse_commands_accepts_mixed_case_paths() -> None:
    result = await mcp.call_tool(
        "itasca_browse_doc",
        {"source": "commands", "path": "Ball Create", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["summary"]["count"] == 1
    assert data["entries"][0]["category"] == "ball"
    assert data["entries"][0]["command"] == "ball create"


@pytest.mark.asyncio
async def test_browse_category_filters_unavailable_commands_by_version() -> None:
    result = await mcp.call_tool(
        "itasca_browse_doc",
        {"source": "commands", "path": "ball", "version": "6.0", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]
    names = {entry["name"] for entry in data["entries"]}

    assert payload["ok"] is True
    assert data["summary"]["version"] == "6.0"
    assert "ball create" in names
    assert "ball accumulate-stress" not in names


@pytest.mark.asyncio
async def test_browse_command_not_found_suggestions_are_version_filtered() -> None:
    result = await mcp.call_tool(
        "itasca_browse_doc",
        {"source": "commands", "path": "ball not_a_real_command", "version": "6.0", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    details = payload["error"].get("details") or {}

    assert payload["ok"] is False
    assert payload["error"]["code"] == "command_not_found"
    assert "ball create" in details["available_commands"]
    assert "ball accumulate-stress" not in details["available_commands"]


@pytest.mark.parametrize(
    ("prefix", "key", "command", "name", "group"),
    [
        # the doc's command field spells the key: trusted
        ("block", "contact-generate-subcontacts", "block contact generate-subcontacts", None, "block contact"),
        ("block", "merge-start", "block merge-start", None, None),
        ("building-blocks", "block-create", "building-blocks block create", None, "building-blocks block"),
        ("ball", "create", "ball create", None, None),
        # the field wins over the key: a live spelling, or a command filed under a category
        # whose word it does not carry
        ("wall", "velocity-conveyor", "wall conveyor", None, None),
        ("brick", "inlet-create", "inlet create", None, None),
        # no field: fall back to the key
        ("model", "solve", "", "model solve", None),
    ],
)
def test_command_full_name_follows_engine_spelling(
    prefix: str, key: str, command: str, name: str | None, group: str | None
) -> None:
    from itasca_mcp.knowledge.commands.naming import full_name, group_of

    resolved = full_name(prefix, key, {"command": command})
    assert resolved == (name or command)
    assert group_of(resolved) == group


@pytest.mark.asyncio
async def test_browse_command_heading_lists_its_commands() -> None:
    result = await mcp.call_tool(
        "itasca_browse_doc", {"source": "commands", "path": "block contact", "software": "3dec"}
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["summary"]["group"] == "block contact"
    assert data["summary"]["count"] >= 20
    assert all(entry["name"].startswith("block contact ") for entry in data["entries"])
    assert all(entry["syntax"].startswith("block contact ") for entry in data["entries"])

    category = _parse_tool_payload(
        await mcp.call_tool("itasca_browse_doc", {"source": "commands", "path": "block", "software": "3dec"})
    )
    assert category["data"]["summary"]["groups"]["block contact"] == data["summary"]["count"]

    # The engine word reaches a category whose index key differs, and a search hit's path browses.
    body = _parse_tool_payload(
        await mcp.call_tool(
            "itasca_browse_doc", {"source": "commands", "path": "building-blocks block create", "software": "flac"}
        )
    )
    assert body["ok"] is True
    assert body["data"]["entries"][0]["command"] == "building-blocks block create"
    assert body["data"]["entries"][0]["category"] == "building-blocks"

    root = _parse_tool_payload(await mcp.call_tool("itasca_browse_doc", {"source": "commands", "software": "flac"}))
    names = {entry["name"] for entry in root["data"]["entries"]}
    assert {"building-blocks", "sketch", "zone"} <= names and not names & {"body", "extruder", "domain"}
    # 'model domain ...' is a heading under model, not a category of its own
    model = _parse_tool_payload(
        await mcp.call_tool("itasca_browse_doc", {"source": "commands", "software": "flac", "path": "model"})
    )
    assert model["data"]["summary"]["groups"]["model domain"] == 3
    old = _parse_tool_payload(
        await mcp.call_tool("itasca_browse_doc", {"source": "commands", "software": "flac", "version": "7.0"})
    )
    assert "extrude" in {entry["name"] for entry in old["data"]["entries"]}

    # 'block merge-start' is one hyphenated command, not a 'merge' group.
    hyphenated = _parse_tool_payload(
        await mcp.call_tool("itasca_browse_doc", {"source": "commands", "path": "block merge", "software": "3dec"})
    )
    assert hyphenated["ok"] is False
    assert hyphenated["error"]["code"] == "command_not_found"


@pytest.mark.asyncio
async def test_query_command_versioned_contract() -> None:
    result = await mcp.call_tool(
        "itasca_query_doc",
        {"source": "commands", "query": "brick assemble", "limit": 5, "version": "6.0", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["summary"]["version"] == "6.0"
    assert len(data["entries"]) >= 1
    assert data["entries"][0]["syntax"] == "brick assemble keyword [range]"


@pytest.mark.asyncio
async def test_browse_python_api_root_contract() -> None:
    result = await mcp.call_tool("itasca_browse_doc", {"source": "python_api", "software": "pfc"})
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["source"] == "python_api"
    assert data["action"] == "browse"
    assert isinstance(data["entries"], list)
    assert data["summary"]["total_modules"] >= 1
    assert data["summary"]["total_objects"] >= 1


@pytest.mark.asyncio
async def test_browse_python_api_array_module_contract() -> None:
    result = await mcp.call_tool(
        "itasca_browse_doc", {"source": "python_api", "path": "itasca.ballarray", "software": "pfc"}
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["source"] == "python_api"
    assert data["action"] == "browse"
    assert data["summary"]["module_path"] == "itasca.ballarray"
    names = {entry["name"] for entry in data["entries"]}
    assert "pos" in names
    assert "set_pos" in names


@pytest.mark.asyncio
async def test_browse_python_api_array_function_contract() -> None:
    result = await mcp.call_tool(
        "itasca_browse_doc", {"source": "python_api", "path": "itasca.ballarray.pos", "software": "pfc"}
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    doc = data["entries"][0]["doc"]
    assert doc["name"] == "pos"
    assert doc["signature"].startswith("itasca.ballarray.pos")
    assert "centroid" in doc["description"]
    assert doc["availability"]["versions"] == ["6.0", "7.0", "9.0"]


@pytest.mark.asyncio
async def test_browse_python_api_does_not_resolve_class_from_another_module() -> None:
    # FLAC documents a Node class in several modules (interface, structure,
    # geometry); a bare name under a module that has none must not resolve.
    result = await mcp.call_tool(
        "itasca_browse_doc",
        {"source": "python_api", "path": "itasca.zone.Node.pos", "software": "flac"},
    )
    payload = _parse_tool_payload(result)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_path"

    # Same-named classes resolve to their own module's docs.
    structure = await mcp.call_tool(
        "itasca_browse_doc",
        {"source": "python_api", "path": "itasca.structure.node.Node.pos", "software": "flac"},
    )
    interface = await mcp.call_tool(
        "itasca_browse_doc",
        {"source": "python_api", "path": "itasca.interface.node.Node.pos", "software": "flac"},
    )
    structure_obj = _parse_tool_payload(structure)["data"]["entries"][0]["actual_object"]
    interface_obj = _parse_tool_payload(interface)["data"]["entries"][0]["actual_object"]
    assert structure_obj != interface_obj


@pytest.mark.asyncio
async def test_browse_python_api_resolves_colliding_class_by_module() -> None:
    # Live PFC exposes both clump.template.Template and rblock.template.Template.
    result = await mcp.call_tool(
        "itasca_browse_doc",
        {"source": "python_api", "path": "itasca.rblock.template.Template", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)

    assert payload["ok"] is True
    assert payload["data"]["entries"][0]["actual_object"] == "RBlockTemplate"


@pytest.mark.asyncio
async def test_browse_python_api_fallback_path_is_a_documented_module() -> None:
    result = await mcp.call_tool(
        "itasca_browse_doc",
        {"source": "python_api", "path": "itasca.ball.nosuchmodule.ThermalBall.temp", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)

    assert payload["ok"] is False
    assert payload["error"]["details"]["fallback_path"] == "itasca.ball"


@pytest.mark.parametrize("software", ["pfc", "flac", "3dec", "mpoint", "massflow"])
def test_every_searchable_python_api_path_is_browsable(software: str) -> None:
    from itasca_mcp.knowledge.python_api import PythonAPILoader
    from itasca_mcp.tools.docs.python_api import _parse_api_path

    # Search results come from both the index and the keyword files.
    paths = set(PythonAPILoader.load_index(software=software)["quick_ref"])
    paths.update(p for apis in PythonAPILoader.load_all_keywords(software=software).values() for p in apis)
    unresolved = sorted(path for path in paths if _parse_api_path(path, software)["type"] == "error")

    assert unresolved == []


def test_pfc_facet_and_pebble_paths_match_live_modules() -> None:
    # Live PFC has itasca.wall.facet.Facet / itasca.clump.pebble.Pebble;
    # itasca.wall.Facet and itasca.clump.Pebble raise AttributeError.
    from itasca_mcp.knowledge.python_api import PythonAPILoader

    quick_ref = PythonAPILoader.load_index(software="pfc")["quick_ref"]

    assert "itasca.wall.facet.Facet.pos" in quick_ref
    assert "itasca.clump.pebble.Pebble.pos" in quick_ref
    assert not any(p.startswith(("itasca.wall.Facet.", "itasca.clump.Pebble.")) for p in quick_ref)


def test_corpus_does_not_reference_nonexistent_fish_get() -> None:
    # itasca.fish_get() does not exist on any engine build; the API is itasca.fish.get().
    from pathlib import Path

    resources = Path(__file__).resolve().parents[1] / "src" / "itasca_mcp" / "knowledge" / "resources"
    offenders = [str(p) for p in resources.rglob("*.json") if "itasca.fish_get" in p.read_text(encoding="utf-8")]

    assert offenders == []


@pytest.mark.asyncio
async def test_query_python_api_array_position_contract() -> None:
    result = await mcp.call_tool(
        "itasca_query_doc",
        {"source": "python_api", "query": "array position", "limit": 10, "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert any(entry["api_path"].endswith("array.pos") for entry in data["entries"])


@pytest.mark.asyncio
async def test_query_python_api_no_results_contract() -> None:
    result = await mcp.call_tool(
        "itasca_query_doc",
        {"source": "python_api", "query": "definitelynonexistentkeyword", "limit": 5, "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["source"] == "python_api"
    assert data["action"] == "query"
    assert data["summary"]["count"] == 0
    assert data["entries"] == []


@pytest.mark.asyncio
async def test_browse_reference_root_contract() -> None:
    result = await mcp.call_tool("itasca_browse_doc", {"source": "reference", "software": "pfc"})
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["source"] == "reference"
    assert data["action"] == "browse"
    assert data["summary"]["count"] >= 1
    assert isinstance(data["entries"], list)


@pytest.mark.asyncio
async def test_browse_command_unavailable_error_lists_only_versions_that_have_it() -> None:
    # pfc 'ball accumulate-stress' carries a 6.0 entry marked available: false.
    payload = _parse_tool_payload(
        await mcp.call_tool(
            "itasca_browse_doc",
            {"source": "commands", "path": "ball accumulate-stress", "software": "pfc", "version": "6.0"},
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "command_unavailable_for_version"
    assert "6.0" not in payload["error"]["details"]["available_versions"]
    assert {"7.0", "9.0"} <= set(payload["error"]["details"]["available_versions"])

    full = _parse_tool_payload(
        await mcp.call_tool(
            "itasca_browse_doc", {"source": "commands", "path": "ball accumulate-stress", "software": "pfc"}
        )
    )
    assert "6.0" not in full["data"]["entries"][0]["doc"]["versions"]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["itasca.", "itasca..ball", "itasca.ball.", ".itasca.ball.Ball.pos"])
async def test_browse_python_api_tolerates_empty_dotted_segments(path: str) -> None:
    payload = _parse_tool_payload(
        await mcp.call_tool("itasca_browse_doc", {"source": "python_api", "path": path, "software": "pfc"})
    )

    assert payload["ok"] is True
    assert payload["data"]["source"] == "python_api"
    assert payload["data"]["action"] == "browse"


@pytest.mark.asyncio
async def test_query_reference_finds_a_model_property_by_its_keyword() -> None:
    # Properties live in property_groups, not sub_items; each gets its own document
    # named by its browse path so an exact keyword such as 'pb_ten' ranks first.
    payload = _parse_tool_payload(
        await mcp.call_tool("itasca_query_doc", {"software": "pfc", "query": "pb_ten", "source": "reference"})
    )
    top = payload["data"]["entries"][0]

    assert payload["ok"] is True
    assert top["path"] == "contact-models linearpbond pb_ten"
    assert top["property"] == "pb_ten"

    merged = _parse_tool_payload(await mcp.call_tool("itasca_query_doc", {"software": "pfc", "query": "pb_ten"}))
    assert merged["data"]["entries"][0]["path"] == "contact-models linearpbond pb_ten"
    assert merged["data"]["entries"][0]["source"] == "reference"


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["ball.pos.", "BALL.POS.", ".ball.pos", "ball..pos"])
async def test_browse_fish_tolerates_empty_dotted_segments(path: str) -> None:
    payload = _parse_tool_payload(
        await mcp.call_tool("itasca_browse_doc", {"source": "fish", "path": path, "software": "pfc"})
    )

    assert payload["ok"] is True
    assert payload["data"]["summary"]["path"] == "ball.pos"
    assert payload["data"]["entries"][0]["name"] == "ball.pos"
