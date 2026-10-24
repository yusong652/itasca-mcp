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
    result = await mcp.call_tool("itasca_browse_commands", {"software": "pfc"})
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload.get("error") is None
    assert data["source"] == "commands"
    assert data["action"] == "browse"
    assert isinstance(data["entries"], list)
    assert data["summary"]["count"] >= 1
    assert data["summary"]["total_commands"] >= 1
    assert data["summary"]["version"] == "7.0"


@pytest.mark.asyncio
async def test_browse_commands_not_found_contract() -> None:
    result = await mcp.call_tool(
        "itasca_browse_commands",
        {"command": "ball not_a_real_command", "software": "pfc"},
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
        "itasca_query_command",
        {"query": "ball create", "limit": 5, "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["source"] == "commands"
    assert data["action"] == "query"
    assert data["summary"]["count"] >= 1
    assert data["summary"]["version"] == "7.0"
    assert isinstance(data["entries"], list)
    assert len(data["entries"]) >= 1


@pytest.mark.asyncio
async def test_browse_commands_versioned_contract() -> None:
    result = await mcp.call_tool(
        "itasca_browse_commands",
        {"command": "brick assemble", "version": "6.0", "software": "pfc"},
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
        "itasca_browse_commands",
        {"command": "Ball Create", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["summary"]["count"] == 1
    assert data["entries"][0]["category"] == "ball"
    assert data["entries"][0]["command"] == "create"


@pytest.mark.asyncio
async def test_browse_category_filters_unavailable_commands_by_version() -> None:
    result = await mcp.call_tool(
        "itasca_browse_commands",
        {"command": "ball", "version": "6.0", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]
    names = {entry["name"] for entry in data["entries"]}

    assert payload["ok"] is True
    assert data["summary"]["version"] == "6.0"
    assert "accumulate-stress" not in names


@pytest.mark.asyncio
async def test_browse_command_not_found_suggestions_are_version_filtered() -> None:
    result = await mcp.call_tool(
        "itasca_browse_commands",
        {"command": "ball not_a_real_command", "version": "6.0", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    details = payload["error"].get("details") or {}

    assert payload["ok"] is False
    assert payload["error"]["code"] == "command_not_found"
    assert "accumulate-stress" not in details["available_commands"]


@pytest.mark.asyncio
async def test_query_command_versioned_contract() -> None:
    result = await mcp.call_tool(
        "itasca_query_command",
        {"query": "brick assemble", "limit": 5, "version": "6.0", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["summary"]["version"] == "6.0"
    assert len(data["entries"]) >= 1
    assert data["entries"][0]["syntax"] == "brick assemble keyword [range]"


@pytest.mark.asyncio
async def test_browse_python_api_root_contract() -> None:
    result = await mcp.call_tool("itasca_browse_python_api", {"software": "pfc"})
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
    result = await mcp.call_tool("itasca_browse_python_api", {"api": "itasca.ballarray", "software": "pfc"})
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
    result = await mcp.call_tool("itasca_browse_python_api", {"api": "itasca.ballarray.pos", "software": "pfc"})
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
    # FLAC documents interface Node but not structure Node; the bare name must
    # not hand back the interface docs for the structural-element class.
    result = await mcp.call_tool(
        "itasca_browse_python_api",
        {"api": "itasca.structure.node.Node.pos", "software": "flac"},
    )
    payload = _parse_tool_payload(result)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_path"


@pytest.mark.asyncio
async def test_browse_python_api_resolves_colliding_class_by_module() -> None:
    # Live PFC exposes both clump.template.Template and rblock.template.Template.
    result = await mcp.call_tool(
        "itasca_browse_python_api",
        {"api": "itasca.rblock.template.Template", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)

    assert payload["ok"] is True
    assert payload["data"]["entries"][0]["actual_object"] == "RBlockTemplate"


@pytest.mark.asyncio
async def test_browse_python_api_fallback_path_is_a_documented_module() -> None:
    result = await mcp.call_tool(
        "itasca_browse_python_api",
        {"api": "itasca.ball.thermal.ThermalBall.temp", "software": "pfc"},
    )
    payload = _parse_tool_payload(result)

    assert payload["ok"] is False
    assert payload["error"]["details"]["fallback_path"] == "itasca.ball"


@pytest.mark.parametrize("software", ["pfc", "flac", "3dec", "mpoint", "massflow"])
def test_every_searchable_python_api_path_is_browsable(software: str) -> None:
    from itasca_mcp.knowledge.python_api import APILoader
    from itasca_mcp.tools.browse_python_api import _parse_api_path

    quick_ref = APILoader.load_index(software=software)["quick_ref"]
    unresolved = [path for path in quick_ref if _parse_api_path(path, software)["type"] == "error"]

    assert unresolved == []


def test_corpus_does_not_reference_nonexistent_fish_get() -> None:
    # itasca.fish_get() does not exist on any engine build; the API is itasca.fish.get().
    from pathlib import Path

    resources = Path(__file__).resolve().parents[1] / "src" / "itasca_mcp" / "knowledge" / "resources"
    offenders = [str(p) for p in resources.rglob("*.json") if "itasca.fish_get" in p.read_text(encoding="utf-8")]

    assert offenders == []


@pytest.mark.asyncio
async def test_query_python_api_array_position_contract() -> None:
    result = await mcp.call_tool(
        "itasca_query_python_api",
        {"query": "array position", "limit": 10, "software": "pfc"},
    )
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert any(entry["api_path"].endswith("array.pos") for entry in data["entries"])


@pytest.mark.asyncio
async def test_query_python_api_no_results_contract() -> None:
    result = await mcp.call_tool(
        "itasca_query_python_api",
        {"query": "definitelynonexistentkeyword", "limit": 5, "software": "pfc"},
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
    result = await mcp.call_tool("itasca_browse_reference", {"software": "pfc"})
    payload = _parse_tool_payload(result)
    data = payload["data"]

    assert payload["ok"] is True
    assert data["source"] == "reference"
    assert data["action"] == "browse"
    assert data["summary"]["count"] >= 1
    assert isinstance(data["entries"], list)
