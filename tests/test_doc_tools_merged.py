"""Contracts of the merged documentation tools and the ``fish`` source.

``itasca_browse_doc`` / ``itasca_query_doc`` replaced the five per-source tools;
these tests pin the envelope shapes a client depends on: the source selector,
the 9.0 default version, the FISH tree semantics (a node can be both a function
and a prefix), engine isolation of FISH namespaces, and the cross-source query.
"""

import json

import pytest

from itasca_mcp.knowledge.fish import FishLoader
from itasca_mcp.server import mcp

DOC_SOURCES = {"commands", "python_api", "fish", "reference"}


def _payload(result) -> dict:
    assert result is not None and result.content
    text = result.content[0].text
    assert text.startswith("{")
    return json.loads(text)


@pytest.mark.asyncio
async def test_two_documentation_tools_only() -> None:
    names = {tool.name for tool in await mcp.list_tools()}
    assert {"itasca_browse_doc", "itasca_query_doc"} <= names
    stale = {n for n in names if n.startswith(("itasca_browse_", "itasca_query_"))} - {
        "itasca_browse_doc",
        "itasca_query_doc",
    }
    assert not stale
    assert len(names) == 7


@pytest.mark.asyncio
async def test_default_version_is_9_0_for_every_source() -> None:
    for source in DOC_SOURCES:
        data = _payload(await mcp.call_tool("itasca_browse_doc", {"software": "pfc", "source": source}))["data"]
        assert data["source"] == source
        assert data["action"] == "browse"
        assert data["summary"]["version"] == "9.0"
        assert data["summary"]["software"] == "pfc"


@pytest.mark.asyncio
async def test_browse_fish_root_contract() -> None:
    data = _payload(await mcp.call_tool("itasca_browse_doc", {"software": "pfc", "source": "fish"}))["data"]
    names = {e["name"] for e in data["entries"]}
    assert {"ball", "wall", "contact", "math", "list"} <= names
    assert "block" not in names and "zone" not in names  # other engines' families stay out
    assert all({"name", "scope", "count"} <= set(e) for e in data["entries"])
    assert "system" in data["summary"]["excluded_namespaces"]
    assert data["summary"]["count"] == len(data["entries"])


@pytest.mark.asyncio
async def test_browse_fish_node_that_is_function_and_prefix() -> None:
    result = await mcp.call_tool("itasca_browse_doc", {"software": "pfc", "source": "fish", "path": "ball.pos"})
    data = _payload(result)["data"]
    head, *children = data["entries"]
    assert head["name"] == "ball.pos"
    assert head["settable"] is True
    assert head["returns"] == "vec3/flt"
    assert "6.0" in head["available_in"]
    assert [c["name"] for c in children] == ["ball.pos.x", "ball.pos.y", "ball.pos.z"]
    assert all("signature" in c for c in children)
    assert data["summary"]["is_function"] is True
    assert data["summary"]["child_count"] == 3


@pytest.mark.asyncio
async def test_browse_fish_namespace_lists_children() -> None:
    data = _payload(await mcp.call_tool("itasca_browse_doc", {"software": "pfc", "source": "fish", "path": "ball"}))[
        "data"
    ]
    assert data["summary"]["is_function"] is False
    assert data["summary"]["child_count"] == len(data["entries"]) > 20
    by_name = {e["name"]: e for e in data["entries"]}
    assert by_name["ball.pos"]["children"] == 3  # function with component children
    assert "signature" not in by_name["ball.thermal"]  # pure namespace
    assert by_name["ball.thermal"]["children"] > 0


@pytest.mark.asyncio
async def test_browse_fish_not_found_suggests_siblings() -> None:
    payload = _payload(
        await mcp.call_tool("itasca_browse_doc", {"software": "pfc", "source": "fish", "path": "ball.rotation"})
    )
    assert payload["ok"] is False
    assert payload["error"]["code"] == "intrinsic_not_found"
    details = payload["error"]["details"]
    assert details["source"] == "fish"
    assert details["input"]["path"] == "ball.rotation"
    assert any(s.startswith("ball.") for s in details["suggestions"])


@pytest.mark.asyncio
async def test_browse_fish_version_gate() -> None:
    gated = _payload(
        await mcp.call_tool(
            "itasca_browse_doc", {"software": "pfc", "source": "fish", "path": "ball.fluid", "version": "6.0"}
        )
    )
    assert gated["ok"] is False
    assert gated["error"]["code"] == "item_unavailable_for_version"
    assert gated["error"]["details"]["available_versions"] == ["9.0"]

    kernel = _payload(
        await mcp.call_tool(
            "itasca_browse_doc", {"software": "pfc", "source": "fish", "path": "math.sqrt", "version": "6.0"}
        )
    )
    assert kernel["ok"] is True
    assert kernel["data"]["entries"][0]["name"] == "math.sqrt"


@pytest.mark.asyncio
async def test_fish_namespaces_are_engine_isolated() -> None:
    roots = {}
    for software in ("pfc", "flac", "3dec", "mpoint", "massflow"):
        data = _payload(await mcp.call_tool("itasca_browse_doc", {"software": software, "source": "fish"}))["data"]
        roots[software] = {e["name"] for e in data["entries"]}
    assert "ball" in roots["pfc"] and "ball" not in roots["flac"] and "ball" not in roots["3dec"]
    assert "zone" in roots["flac"] and "zone" not in roots["pfc"] and "zone" not in roots["3dec"]
    assert "block" in roots["3dec"] and "block" not in roots["flac"]
    assert "mpoint" in roots["mpoint"] and "massflow" in roots["massflow"]
    assert "struct" in roots["flac"] and "struct" in roots["3dec"] and "struct" not in roots["pfc"]
    for names in roots.values():
        assert "math" in names  # kernel namespace everywhere


@pytest.mark.asyncio
async def test_query_fish_contract() -> None:
    result = await mcp.call_tool(
        "itasca_query_doc", {"software": "pfc", "query": "ball position", "source": "fish", "limit": 5}
    )
    data = _payload(result)["data"]
    assert data["source"] == "fish" and data["action"] == "query"
    top = data["entries"][0]
    assert top["path"] == "ball.pos"
    assert top["source"] == "fish"
    assert top["signature"].startswith("vec3/flt := ball.pos(")
    assert "6.0" in top["available_in"]


@pytest.mark.asyncio
async def test_query_fish_respects_version() -> None:
    result = await mcp.call_tool(
        "itasca_query_doc", {"software": "pfc", "query": "ball fluid find", "source": "fish", "version": "6.0"}
    )
    names = {e["path"] for e in _payload(result)["data"]["entries"]}
    assert "ball.fluid.find" not in names  # 9.x-only


@pytest.mark.asyncio
async def test_query_reference_contract() -> None:
    result = await mcp.call_tool(
        "itasca_query_doc", {"software": "flac", "query": "mohr coulomb", "source": "reference", "limit": 3}
    )
    data = _payload(result)["data"]
    assert data["source"] == "reference"
    top = data["entries"][0]
    assert top["path"] == "constitutive-models mohr-coulomb"
    assert top["category"] == "constitutive-models" and top["item"] == "mohr-coulomb"


@pytest.mark.asyncio
async def test_query_all_sources_tags_entries() -> None:
    data = _payload(await mcp.call_tool("itasca_query_doc", {"software": "pfc", "query": "ball pos"}))["data"]
    assert data["source"] == "all"
    assert data["summary"]["count"] == len(data["entries"]) == 10
    assert set(data["summary"]["by_source"]) <= DOC_SOURCES
    assert len(data["summary"]["by_source"]) >= 2
    assert [e["rank"] for e in data["entries"]] == list(range(1, 11))
    assert all(e["source"] in DOC_SOURCES and e["path"] for e in data["entries"])
    assert {"ball.pos", "itasca.ball.Ball.pos"} <= {e["path"] for e in data["entries"]}


@pytest.mark.asyncio
async def test_command_hits_summarise_in_description() -> None:
    """Command hits carry 'description' like the other trees, a whole first sentence ('etc.)' is no end)."""
    data = _payload(await mcp.call_tool("itasca_query_doc", {"software": "flac", "query": "create brick zones"}))[
        "data"
    ]
    hit = next(e for e in data["entries"] if e["path"] == "zone create")
    assert "short_description" not in hit
    assert hit["description"] == (
        "Create 3D zone-filled primitive shapes ( brick , cylinder , etc.) with a predefined grid pattern."
    )


@pytest.mark.asyncio
async def test_query_no_results_hints() -> None:
    data = _payload(await mcp.call_tool("itasca_query_doc", {"software": "pfc", "query": "zzzqqq", "source": "fish"}))[
        "data"
    ]
    assert data["entries"] == []
    assert data["summary"]["hints"]
    assert "ball" in data["summary"]["available_namespaces"]


def test_fish_loader_tree_shape() -> None:
    assert FishLoader.is_node("ball", software="pfc")
    assert FishLoader.get("ball", software="pfc") is None  # namespace, not a symbol
    assert FishLoader.children("ball.pos", software="pfc") == ["ball.pos.x", "ball.pos.y", "ball.pos.z"]
    assert FishLoader.get("ball.pos", software="pfc")["namespace"] == "ball"
    assert FishLoader.get("math.sqrt", software="3dec")["scope"] == "common"
    assert not FishLoader.is_node("ball", software="3dec")


async def _top_paths(query: str, source: str | None = None, limit: int = 5) -> list[str]:
    args = {"software": "pfc", "query": query, "limit": limit}
    if source:
        args["source"] = source
    data = _payload(await mcp.call_tool("itasca_query_doc", args))["data"]
    return [e["path"] for e in data["entries"]]


@pytest.mark.asyncio
async def test_query_names_win_over_per_tree_ties() -> None:
    """Each tree's best hit normalises to 1.0; the hit whose name the query spells must win the tie."""
    assert (await _top_paths("version code major"))[0] == "version.code.major"
    assert (await _top_paths("contact.force.normal"))[0] == "contact.force.normal"
    assert (await _top_paths("ball position"))[0] != "table position"
    # a bare word still means the command, not every method that happens to end with it
    assert (await _top_paths("fragment"))[0] == "fragment compute"


@pytest.mark.asyncio
async def test_query_exact_python_name_with_stopword_or_short_rival() -> None:
    """'in' is a stopword and itasca.contact.count outscores Ball.contact_count on tokens alone."""
    assert (await _top_paths("itasca.ball.Ball.in_group", "python_api"))[0] == "itasca.ball.Ball.in_group"
    assert (await _top_paths("Ball.contact_count", "python_api"))[0] == "itasca.ball.Ball.contact_count"
    assert all(p.endswith(".in_group") for p in await _top_paths("in_group", "python_api", limit=3))


@pytest.mark.asyncio
async def test_fish_entries_carry_manual_descriptions() -> None:
    """FISH names are abbreviations; the manual's one-liner is what prose queries match."""
    data = _payload(
        await mcp.call_tool("itasca_browse_doc", {"software": "pfc", "source": "fish", "path": "tensor.prin"})
    )["data"]
    assert "principal" in data["entries"][0]["description"]
    assert "tensor.prin" in await _top_paths("principal values tensor")


def test_fish_suggestions_rank_by_closeness() -> None:
    assert FishLoader.suggest("ball.position", software="pfc")[0] == "ball.pos"
    assert FishLoader.suggest("tensor.principal", software="pfc")[:2] == ["tensor", "tensor.prin"]
