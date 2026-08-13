"""Multi-engine (software param) tests: FLAC coverage, _common sharing, isolation.

PR1 introduced the required ``software`` selector and a per-engine corpus laid out
as ``resources/{_common,pfc,flac}/``. These tests lock in:
- FLAC browse/query works through the tools and loaders
- the shared ``_common`` kernel resolves for every engine
- engine corpora stay isolated (PFC-only vs FLAC-only families)
- ``software`` is genuinely required (no default engine)
"""

import json

import pytest

from itasca_mcp.knowledge.commands.loader import CommandLoader
from itasca_mcp.knowledge.config import SUPPORTED_SOFTWARE, normalize_software
from itasca_mcp.knowledge.python_api.loader import DocumentationLoader
from itasca_mcp.knowledge.query import APISearch, CommandSearch
from itasca_mcp.knowledge.references.loader import ReferenceLoader
from itasca_mcp.server import mcp


def _parse_tool_payload(result) -> dict:
    assert result is not None
    assert len(result.content) > 0
    text = result.content[0].text
    assert text.startswith("{")
    return json.loads(text)


# --- config / required-ness -------------------------------------------------


def test_supported_software_set() -> None:
    assert set(SUPPORTED_SOFTWARE) == {"pfc", "flac", "3dec", "mpoint", "massflow"}


def test_normalize_software_validates() -> None:
    assert normalize_software("PFC") == "pfc"
    assert normalize_software("flac") == "flac"
    for bad in ("", "abaqus", "udec"):
        with pytest.raises(ValueError):
            normalize_software(bad)


@pytest.mark.asyncio
async def test_software_is_required_on_tools() -> None:
    """Omitting ``software`` is a validation error (there is no default engine)."""
    with pytest.raises(Exception, match="(?i)software"):
        await mcp.call_tool("itasca_browse_commands", {})


# --- FLAC coverage through the tools ----------------------------------------


@pytest.mark.asyncio
async def test_flac_browse_commands_root() -> None:
    result = await mcp.call_tool("itasca_browse_commands", {"software": "flac"})
    data = _parse_tool_payload(result)["data"]
    names = {e["name"] for e in data["entries"]}
    assert "zone" in names  # FLAC-only family
    assert "model" in names  # shared kernel family
    assert "ball" not in names  # PFC-only family must not leak
    assert data["summary"]["software"] == "flac"


@pytest.mark.asyncio
async def test_flac_browse_zone_command() -> None:
    result = await mcp.call_tool(
        "itasca_browse_commands", {"software": "flac", "command": "zone create", "version": "9.0"}
    )
    data = _parse_tool_payload(result)["data"]
    assert data["entries"][0]["doc"]["command"] == "zone create"


@pytest.mark.asyncio
async def test_flac_query_command_finds_zone() -> None:
    result = await mcp.call_tool("itasca_query_command", {"software": "flac", "query": "zone create"})
    data = _parse_tool_payload(result)["data"]
    assert data["summary"]["software"] == "flac"
    assert any("zone" in e["name"] for e in data["entries"])


@pytest.mark.asyncio
async def test_flac_browse_python_api_has_zone_not_ball() -> None:
    result = await mcp.call_tool("itasca_browse_python_api", {"software": "flac"})
    data = _parse_tool_payload(result)["data"]
    module_paths = {e.get("path") for e in data["entries"] if e.get("entry_type") == "module"}
    assert "itasca.zone" in module_paths
    assert "itasca.ball" not in module_paths


@pytest.mark.asyncio
async def test_flac_browse_reference_root() -> None:
    result = await mcp.call_tool("itasca_browse_reference", {"software": "flac"})
    data = _parse_tool_payload(result)["data"]
    names = {e["name"] for e in data["entries"]}
    assert "constitutive-models" in names


# --- _common sharing --------------------------------------------------------


def test_shared_model_solve_resolves_for_all_engines() -> None:
    # model solve points into _common/, which carries a 7.0 key for every engine.
    for sw in SUPPORTED_SOFTWARE:
        doc = CommandLoader.load_command_doc("model", "solve", "7.0", software=sw)
        assert doc is not None
        assert doc["command"] == "model solve"


def test_shared_itasca_module_resolves_for_all_engines() -> None:
    for sw in SUPPORTED_SOFTWARE:
        index = DocumentationLoader.load_index(software=sw)
        assert "itasca" in index["modules"]
        doc = DocumentationLoader.load_module("itasca", software=sw)
        assert doc is not None
        assert any(f["name"] == "command" for f in doc["functions"])


# --- isolation --------------------------------------------------------------


def test_command_families_are_engine_isolated() -> None:
    pfc = CommandLoader.load_index(software="pfc")["categories"]
    flac = CommandLoader.load_index(software="flac")["categories"]
    assert "ball" in pfc and "ball" not in flac
    assert "zone" in flac and "zone" not in pfc
    # shared kernel present in both
    assert "model" in pfc and "model" in flac


def test_search_is_engine_scoped() -> None:
    flac_hit = CommandSearch.search("zone create", top_k=3, software="flac")
    assert flac_hit and flac_hit[0].document.name == "zone create"
    api_hit = APISearch.search("zone gridpoint", top_k=3, software="flac")
    assert api_hit and "zone" in api_hit[0].document.name.lower() or "gridpoint" in api_hit[0].document.name.lower()


def test_reference_categories_are_engine_specific() -> None:
    pfc = set(ReferenceLoader.load_index(software="pfc").get("categories", {}))
    flac = set(ReferenceLoader.load_index(software="flac").get("categories", {}))
    assert "contact-models" in pfc
    assert "constitutive-models" in flac
    assert "contact-models" not in flac


# --- 3DEC coverage (9.0-only engine) ----------------------------------------
# 3DEC ships only the 9.x unified kernel, so commands are 9.0-only; queries must
# pass version="9.0" (the tool default 7.0 is a PFC-era leftover, same caveat as
# FLAC's 9.0-only families).


@pytest.mark.asyncio
async def test_3dec_browse_commands_root() -> None:
    result = await mcp.call_tool("itasca_browse_commands", {"software": "3dec", "version": "9.0"})
    data = _parse_tool_payload(result)["data"]
    names = {e["name"] for e in data["entries"]}
    assert "block" in names  # 3DEC-only family
    assert "model" in names  # shared kernel family
    assert "ball" not in names  # PFC-only family must not leak
    assert "zone" not in names  # FLAC-only top-level family (3DEC uses 'block zone ...')
    assert data["summary"]["software"] == "3dec"


@pytest.mark.asyncio
async def test_3dec_browse_block_zone_generate() -> None:
    result = await mcp.call_tool(
        "itasca_browse_commands", {"software": "3dec", "command": "block zone generate", "version": "9.0"}
    )
    data = _parse_tool_payload(result)["data"]
    assert data["entries"][0]["doc"]["command"] == "block zone generate"


@pytest.mark.asyncio
async def test_3dec_query_command_finds_block_create() -> None:
    result = await mcp.call_tool(
        "itasca_query_command", {"software": "3dec", "query": "create block", "version": "9.0"}
    )
    data = _parse_tool_payload(result)["data"]
    assert data["summary"]["software"] == "3dec"
    assert any(e["name"] == "block create" for e in data["entries"])


@pytest.mark.asyncio
async def test_3dec_python_api_exposes_itasca_core() -> None:
    result = await mcp.call_tool("itasca_query_python_api", {"software": "3dec", "query": "run command"})
    data = _parse_tool_payload(result)["data"]
    assert any(e.get("api_path") == "itasca.command" for e in data["entries"])


# --- 3DEC engine-specific Python API ----------------------------------------
# The full 3DEC proprietary namespace (block / flowknot / flowplane / structure /
# dfn / contact / history / fish) is parsed from the local 9.0 Sphinx python docs
# by scripts/corpus/parse_3dec_python.py. These modules are 3DEC-only (no PFC/FLAC
# equivalent) and must not leak across engines.


def test_3dec_block_module_and_class_resolve() -> None:
    # Module function.
    find = DocumentationLoader.load_api_doc("itasca.block.find", software="3dec")
    assert find is not None
    assert find["signature"].startswith("itasca.block.find(")
    # Class method via its full official path.
    vol = DocumentationLoader.load_api_doc("itasca.block.Block.vol", software="3dec")
    assert vol is not None
    assert vol["signature"] == "block.vol() -> float"


def test_3dec_block_submodule_class_resolves() -> None:
    # Sub-namespace class (itasca.block.subcontact.Subcontact) resolves end to end.
    fs = DocumentationLoader.load_api_doc("itasca.block.subcontact.Subcontact.force_shear", software="3dec")
    assert fs is not None
    assert "force_shear" in fs["signature"]


def test_3dec_block_objects_registered_in_index() -> None:
    index = DocumentationLoader.load_index(software="3dec")
    assert "block" in index["modules"]
    assert "Block" in index["objects"]
    # The Block module exposes exactly the six confirmed namespace functions.
    assert set(index["modules"]["block"]["functions"]) == {
        "containing",
        "count",
        "find",
        "list",
        "maxid",
        "near",
    }


def test_3dec_python_block_family_is_engine_isolated() -> None:
    # block family is 3DEC-only: it must not appear in PFC/FLAC python indices.
    for sw in ("pfc", "flac"):
        assert "block" not in DocumentationLoader.load_index(software=sw)["modules"]


def test_3dec_python_search_finds_block_method() -> None:
    # API-path style query (a documented use case) ranks the exact method first.
    hits = APISearch.search("Block.vol", top_k=5, software="3dec")
    assert hits and hits[0].document.name == "itasca.block.Block.vol"


def test_3dec_structure_exposes_all_element_classes() -> None:
    # itasca.structure carries six element classes directly (no PFC/FLAC analogue).
    index = DocumentationLoader.load_index(software="3dec")
    for cls in ("Beam", "Cable", "Geogrid", "Liner", "Pile", "Shell"):
        assert cls in index["objects"], cls
    pile = DocumentationLoader.load_api_doc("itasca.structure.Pile.force", software="3dec")
    assert pile is not None and pile["signature"].startswith("pile.force(")


def test_3dec_dfn_and_flow_modules_resolve() -> None:
    frac = DocumentationLoader.load_api_doc("itasca.dfn.DFN.create_fracture", software="3dec")
    assert frac is not None
    fk = DocumentationLoader.load_api_doc("itasca.flowknot.find", software="3dec")
    assert fk is not None and fk["signature"].startswith("itasca.flowknot.find(")


def test_3dec_colliding_class_names_disambiguate_by_full_path() -> None:
    # Zone exists in both block.zone and flowplane.zone; Vertex in flowplane.vertex
    # and dfn.vertex; Contact in contact and block.contact. The shallower/earlier
    # one keeps the bare object key, the other is registered under its full path.
    index = DocumentationLoader.load_index(software="3dec")
    objects = index["objects"]
    assert "Zone" in objects and "itasca.flowplane.zone.Zone" in objects
    assert "Vertex" in objects and "itasca.flowplane.vertex.Vertex" in objects
    # Bare Zone resolves to the block.zone variant; the flowplane variant is reachable
    # under its full path. Both keep correct, distinct method docs.
    bare = DocumentationLoader.load_object("Zone", software="3dec")
    flow = DocumentationLoader.load_object("itasca.flowplane.zone.Zone", software="3dec")
    assert bare is not None and "block.zone" in bare["note"]
    assert flow is not None and "flowplane.zone" in flow["note"]


def test_3dec_python_proprietary_modules_isolated_from_pfc_flac() -> None:
    threedec = set(DocumentationLoader.load_index(software="3dec")["modules"])
    for sw in ("pfc", "flac"):
        other = set(DocumentationLoader.load_index(software=sw)["modules"])
        # None of the 3DEC-only families leak into the other engines.
        assert not ({"block", "flowknot", "flowplane", "structure", "dfn"} & other)
    assert {"block", "flowknot", "flowplane", "structure", "dfn", "contact"} <= threedec


def test_3dec_command_families_are_isolated() -> None:
    threedec = CommandLoader.load_index(software="3dec")["categories"]
    pfc = CommandLoader.load_index(software="pfc")["categories"]
    flac = CommandLoader.load_index(software="flac")["categories"]
    assert "block" in threedec and "block" not in pfc and "block" not in flac
    assert "model" in threedec  # shared kernel present
    assert "ball" not in threedec and "zone" not in threedec


# --- MPoint / MPM coverage (9.0-only engine) --------------------------------
# MPoint is the Material Point Method product; like 3DEC/FLAC it ships only the
# 9.x unified kernel, so commands are 9.0-only (queries pass version="9.0").


@pytest.mark.asyncio
async def test_mpoint_browse_commands_root() -> None:
    result = await mcp.call_tool("itasca_browse_commands", {"software": "mpoint", "version": "9.0"})
    data = _parse_tool_payload(result)["data"]
    names = {e["name"] for e in data["entries"]}
    assert "mpoint" in names  # MPoint-only family
    assert "model" in names  # shared kernel family
    assert "ball" not in names  # PFC-only family must not leak
    assert "block" not in names  # 3DEC-only family must not leak
    assert "zone" not in names  # FLAC-only top-level family
    assert data["summary"]["software"] == "mpoint"


@pytest.mark.asyncio
async def test_mpoint_browse_mpoint_create() -> None:
    result = await mcp.call_tool(
        "itasca_browse_commands", {"software": "mpoint", "command": "mpoint create", "version": "9.0"}
    )
    data = _parse_tool_payload(result)["data"]
    assert data["entries"][0]["doc"]["command"] == "mpoint create"


@pytest.mark.asyncio
async def test_mpoint_browse_node_subcommand() -> None:
    # 'mpoint node fix' is keyed as node-fix.json but addressed with spaces.
    result = await mcp.call_tool(
        "itasca_browse_commands", {"software": "mpoint", "command": "mpoint node fix", "version": "9.0"}
    )
    data = _parse_tool_payload(result)["data"]
    assert data["entries"][0]["doc"]["command"] == "mpoint node fix"


@pytest.mark.asyncio
async def test_mpoint_query_command_finds_mpoint_create() -> None:
    result = await mcp.call_tool(
        "itasca_query_command", {"software": "mpoint", "query": "create material point", "version": "9.0"}
    )
    data = _parse_tool_payload(result)["data"]
    assert data["summary"]["software"] == "mpoint"
    assert any(e["name"] == "mpoint create" for e in data["entries"])


@pytest.mark.asyncio
async def test_mpoint_python_api_exposes_itasca_core() -> None:
    result = await mcp.call_tool("itasca_query_python_api", {"software": "mpoint", "query": "run command"})
    data = _parse_tool_payload(result)["data"]
    assert any(e.get("api_path") == "itasca.command" for e in data["entries"])


def test_mpoint_command_families_are_isolated() -> None:
    mpoint = CommandLoader.load_index(software="mpoint")["categories"]
    assert "mpoint" in mpoint  # proprietary family
    assert "model" in mpoint and "fish" in mpoint  # shared kernel borrowed
    # other engines' proprietary families must not leak in
    assert "ball" not in mpoint and "block" not in mpoint and "zone" not in mpoint


def test_mpoint_borrows_common_kernel_verbatim() -> None:
    mpoint = CommandLoader.load_index(software="mpoint")["categories"]
    # every borrowed kernel command points back into _common/ (single source)
    for fam in ("data", "fish", "geometry", "history", "model", "plot", "table"):
        cmds = mpoint[fam]["commands"]
        assert cmds and all(str(c["file"]).startswith("_common/") for c in cmds)


def test_mpoint_plot_items_are_engine_specific() -> None:
    cat = ReferenceLoader.load_category_index("plot-items", software="mpoint")
    assert cat is not None
    names = {i["name"] for i in cat["items"]}
    # MPoint's distinctive plottable entities (material points + background grid).
    assert {"mpoint", "mpoint-vector", "mpoint-tensor", "meshpoint"} <= names
    # 'mpoint' is a directory item with a color-by sub-item (contour vs label).
    assert ReferenceLoader.is_directory_item("plot-items", "mpoint", software="mpoint")
    cb = ReferenceLoader.load_sub_item_doc("plot-items", "mpoint", "color-by", software="mpoint")
    assert {m["mode"] for m in cb["modes"]} == {"contour", "label"}
    # mpoint-vector documents the live-probed vector value set.
    vec = ReferenceLoader.load_item_doc("plot-items", "mpoint-vector", software="mpoint")
    assert "meshnode-vector" in vec["item_types"]  # shares the keyword set


def test_mpoint_borrows_constitutive_models_from_common() -> None:
    cats = ReferenceLoader.load_index(software="mpoint").get("categories", {})
    assert "constitutive-models" in cats
    cat = ReferenceLoader.load_category_index("constitutive-models", software="mpoint")
    # MPoint shares zone models with FLAC3D/3DEC; the docs live once in _common.
    entry = next(m for m in cat["models"] if m["name"] == "mohr-coulomb")
    assert entry["file"].startswith("_common/references/constitutive-models/")
    # Resolving the borrowed item returns the shared _common doc (same as FLAC's).
    doc = ReferenceLoader.load_item_doc("constitutive-models", "mohr-coulomb", software="mpoint")
    assert doc == ReferenceLoader.load_item_doc("constitutive-models", "mohr-coulomb", software="flac")
    # The 5 MPoint-only models without a _common doc are disclosed, not fabricated.
    assert "jones-wilkins-lee" in cat["note"]


def test_mpoint_range_elements_shared_via_common() -> None:
    cats = ReferenceLoader.load_index(software="mpoint").get("categories", {})
    assert "range-elements" in cats
    # Same _common cylinder doc as the other engines.
    mp = ReferenceLoader.load_item_doc("range-elements", "cylinder", software="mpoint")
    flac = ReferenceLoader.load_item_doc("range-elements", "cylinder", software="flac")
    assert mp is not None and mp == flac


def test_mpoint_fish_intrinsics_engine_specific() -> None:
    cats = ReferenceLoader.load_index(software="mpoint").get("categories", {})
    assert "fish-intrinsics" in cats
    cat = ReferenceLoader.load_category_index("fish-intrinsics", software="mpoint")
    names = {i["name"] for i in cat["items"]}
    # MPoint's FISH is built around material points + background-grid nodes.
    assert names == {"material-point", "background-node"}
    mp = ReferenceLoader.load_item_doc("fish-intrinsics", "material-point", software="mpoint")
    examples = {ex for fam in mp["intrinsic_families"] for ex in fam["examples"]}
    assert "mpoint.stress" in examples and "mpoint.mech.ratio.max" in examples
    node = ReferenceLoader.load_item_doc("fish-intrinsics", "background-node", software="mpoint")
    node_ex = {ex for fam in node["intrinsic_families"] for ex in fam["examples"]}
    assert "mpoint.node.force.unbal" in node_ex


def test_mpoint_boundary_conditions_use_mpoint_syntax() -> None:
    cat = ReferenceLoader.load_category_index("boundary-conditions", software="mpoint")
    assert cat is not None
    assert {i["name"] for i in cat["items"]} == {"material-point-fixity", "grid-node-fixity"}
    node = ReferenceLoader.load_item_doc("boundary-conditions", "grid-node-fixity", software="mpoint")
    # MPM grid-node fixity, not FLAC's 'zone gridpoint fix'.
    assert "mpoint node fix" in node["primary_commands"]
    fams = {f["family"] for f in node["condition_families"]}
    assert "prescribed fluid velocity" in fams


def test_mpoint_initial_conditions_field_and_gravity() -> None:
    cat = ReferenceLoader.load_category_index("initial-conditions", software="mpoint")
    assert cat is not None
    assert {i["name"] for i in cat["items"]} == {"field-initialization", "gravitational-stress"}
    grav = ReferenceLoader.load_item_doc("initial-conditions", "gravitational-stress", software="mpoint")
    assert "mpoint initialize-stresses" in grav["primary_commands"]
    field = ReferenceLoader.load_item_doc("initial-conditions", "field-initialization", software="mpoint")
    all_fields = {f for g in field["field_groups"] for f in g["fields"]}
    assert {"stress", "pore-pressure", "biot-modulus"} <= all_fields


# --- MassFlow (gravity flow / caving) coverage (9.0-only engine) ------------
# MassFlow is the caving / gravity-flow product. Its one proprietary family is
# ``massflow`` (initialize/compute, drawpoints, markers, mine-blocks, fines
# migration); everything else is the shared 9.0 kernel. The FLAC3D ``zone``
# family is reachable on the binary for coupled analysis but is documented under
# software="flac" (MassFlow3D's zone set diverges, e.g. no zone create2d).


@pytest.mark.asyncio
async def test_massflow_browse_commands_root() -> None:
    result = await mcp.call_tool("itasca_browse_commands", {"software": "massflow", "version": "9.0"})
    data = _parse_tool_payload(result)["data"]
    names = {e["name"] for e in data["entries"]}
    assert "massflow" in names  # MassFlow-only family
    assert "model" in names  # shared kernel family
    assert "ball" not in names  # PFC-only family must not leak
    assert "block" not in names  # 3DEC-only family must not leak
    assert "mpoint" not in names  # MPoint-only family must not leak
    assert "zone" not in names  # FLAC3D zone family documented under software="flac"
    assert data["summary"]["software"] == "massflow"


@pytest.mark.asyncio
async def test_massflow_browse_compute_command() -> None:
    result = await mcp.call_tool(
        "itasca_browse_commands", {"software": "massflow", "command": "massflow compute", "version": "9.0"}
    )
    data = _parse_tool_payload(result)["data"]
    assert data["entries"][0]["doc"]["command"] == "massflow compute"


@pytest.mark.asyncio
async def test_massflow_browse_subnamespace_command() -> None:
    # 'massflow drawpoint import' is keyed as drawpoint-import.json but addressed with spaces.
    result = await mcp.call_tool(
        "itasca_browse_commands", {"software": "massflow", "command": "massflow drawpoint import", "version": "9.0"}
    )
    data = _parse_tool_payload(result)["data"]
    assert data["entries"][0]["doc"]["command"] == "massflow drawpoint import"


@pytest.mark.asyncio
async def test_massflow_query_command_finds_compute() -> None:
    result = await mcp.call_tool(
        "itasca_query_command", {"software": "massflow", "query": "compute flow solution", "version": "9.0"}
    )
    data = _parse_tool_payload(result)["data"]
    assert data["summary"]["software"] == "massflow"
    assert any(e["name"] == "massflow compute" for e in data["entries"])


@pytest.mark.asyncio
async def test_massflow_python_api_exposes_itasca_core() -> None:
    result = await mcp.call_tool("itasca_query_python_api", {"software": "massflow", "query": "run command"})
    data = _parse_tool_payload(result)["data"]
    assert any(e.get("api_path") == "itasca.command" for e in data["entries"])


def test_massflow_python_exposes_kernel_modules_only() -> None:
    # MassFlow has no proprietary Python package; itasca is flat and exposes only
    # the generic 9.0-kernel sub-modules (contact/history/fish) beyond the core.
    index = DocumentationLoader.load_index(software="massflow")
    mods = set(index["modules"])
    assert {"itasca", "contact", "history", "fish"} <= mods
    # No zone-family / other-engine / fabricated 'massflow' python modules.
    assert not ({"zone", "block", "ball", "structure", "massflow", "dfn"} & mods)


def test_massflow_python_contact_module_resolves() -> None:
    doc = DocumentationLoader.load_api_doc("itasca.contact.find", software="massflow")
    assert doc is not None
    assert doc["signature"].startswith("itasca.contact.find(")
    # Generic kernel module: identical content to the same 3DEC module.
    assert doc == DocumentationLoader.load_api_doc("itasca.contact.find", software="3dec")


def test_massflow_python_search_finds_fish_intrinsic_api() -> None:
    hits = APISearch.search("call fish function", top_k=5, software="massflow")
    assert hits and any("fish" in h.document.name.lower() for h in hits)


def test_massflow_command_families_are_isolated() -> None:
    massflow = CommandLoader.load_index(software="massflow")["categories"]
    assert "massflow" in massflow  # proprietary family
    assert "model" in massflow and "fish" in massflow  # shared kernel borrowed
    # other engines' proprietary families must not leak in
    assert "ball" not in massflow
    assert "block" not in massflow
    assert "mpoint" not in massflow
    assert "zone" not in massflow  # FLAC3D zone not borrowed (diverges on massflow3d)


def test_massflow_borrows_common_kernel_verbatim() -> None:
    massflow = CommandLoader.load_index(software="massflow")["categories"]
    for fam in ("data", "fish", "geometry", "history", "model", "plot", "table"):
        cmds = massflow[fam]["commands"]
        assert cmds and all(str(c["file"]).startswith("_common/") for c in cmds)


def test_massflow_compute_resolves_with_keywords() -> None:
    doc = CommandLoader.load_command_doc("massflow", "compute", "9.0", software="massflow")
    assert doc is not None
    assert doc["command"] == "massflow compute"
    kw = {k["name"] for k in doc.get("keywords", [])}
    assert {"days", "periods"} <= kw  # live-probed keyword set


def test_massflow_constitutive_models_shared_via_common() -> None:
    cats = ReferenceLoader.load_index(software="massflow").get("categories", {})
    assert "constitutive-models" in cats
    cat = ReferenceLoader.load_category_index("constitutive-models", software="massflow")
    # MassFlow's coupled analysis shares the FLAC3D zone models; docs live in _common.
    entry = next(m for m in cat["models"] if m["name"] == "mohr-coulomb")
    assert entry["file"].startswith("_common/references/constitutive-models/")
    doc = ReferenceLoader.load_item_doc("constitutive-models", "mohr-coulomb", software="massflow")
    assert doc == ReferenceLoader.load_item_doc("constitutive-models", "mohr-coulomb", software="flac")
    # The 5 superset models without a _common doc are disclosed, not fabricated.
    assert "jones-wilkins-lee" in cat["note"]


def test_massflow_range_elements_shared_via_common() -> None:
    cats = ReferenceLoader.load_index(software="massflow").get("categories", {})
    assert "range-elements" in cats
    mf = ReferenceLoader.load_item_doc("range-elements", "cylinder", software="massflow")
    flac = ReferenceLoader.load_item_doc("range-elements", "cylinder", software="flac")
    assert mf is not None and mf == flac


def test_massflow_plot_items_are_engine_specific() -> None:
    cat = ReferenceLoader.load_category_index("plot-items", software="massflow")
    assert cat is not None
    names = {i["name"] for i in cat["items"]}
    # MassFlow's caving / gravity-flow plottable entities (not PFC ball / FLAC zone).
    assert {
        "drawpoint",
        "mineblock",
        "imz",
        "marker",
        "flow-vector",
        "particle-trace",
        "history-locations",
    } <= names
    # drawpoint is a directory item: color-by sub-item = categorical 'colorby' + 'contour'.
    assert ReferenceLoader.is_directory_item("plot-items", "drawpoint", software="massflow")
    cb = ReferenceLoader.load_sub_item_doc("plot-items", "drawpoint", "color-by", software="massflow")
    assert {m["mode"] for m in cb["modes"]} == {"colorby", "contour"}
    # mineblock's colorby exposes the rich grade/state vocabulary.
    mb = ReferenceLoader.load_sub_item_doc("plot-items", "mineblock", "color-by", software="massflow")
    mb_attrs = next(m["attributes"] for m in mb["modes"] if m["mode"] == "colorby")
    assert {"ucs", "caved", "meandiameter"} <= set(mb_attrs)
    # marker merges marker-extracted and carries the size-by vocabulary.
    marker = ReferenceLoader.load_item_doc("plot-items", "marker", software="massflow")
    assert "marker-extracted" in marker["item_types"]
    mcb = ReferenceLoader.load_sub_item_doc("plot-items", "marker", "color-by", software="massflow")
    assert "meanDiameter" in mcb["size_by"]


# --- 9.0-only engines: version selector coerces to 9.0 ----------------------
# 3DEC/MPoint/MassFlow ship a single 9.0 doc key. The tools' version default is
# 7.0 (a PFC-era leftover); without coercion every 9.0-only command would resolve
# as "unavailable for 7.0". effective_doc_version() forces 9.0 for these engines.


def test_effective_doc_version_coerces_nine_zero_only() -> None:
    from itasca_mcp.utils import effective_doc_version

    for sw in ("3dec", "mpoint", "massflow"):
        assert effective_doc_version(sw, "7.0") == "9.0"
        assert effective_doc_version(sw, "6.0") == "9.0"
        assert effective_doc_version(sw, "9.0") == "9.0"
    # Multi-version engines keep the requested version.
    assert effective_doc_version("pfc", "7.0") == "7.0"
    assert effective_doc_version("flac", "7.0") == "7.0"


@pytest.mark.asyncio
async def test_nine_zero_only_browse_without_version_resolves() -> None:
    # No version passed -> must NOT fail with "unavailable for 7.0".
    for sw, cmd in (("3dec", "block create"), ("mpoint", "mpoint create"), ("massflow", "massflow compute")):
        result = await mcp.call_tool("itasca_browse_commands", {"software": sw, "command": cmd})
        payload = _parse_tool_payload(result)
        assert payload["ok"] is True, (sw, payload)
        assert payload["data"]["entries"][0]["doc"]["command"] == cmd


@pytest.mark.asyncio
async def test_nine_zero_only_reference_summary_reports_9_0() -> None:
    for sw in ("3dec", "mpoint", "massflow"):
        result = await mcp.call_tool("itasca_browse_reference", {"software": sw})
        data = _parse_tool_payload(result)["data"]
        assert data["summary"]["version"] == "9.0", sw


# --- FLAC: the 9.x series is represented by a single 9.0 key -----------------
# FLAC is multi-version (7.0/9.0). The only command that had granular 9.1/9.3
# keys (model configure) folds the current 9.x content into 9.0.


def test_flac_model_configure_single_9x_key() -> None:
    doc = CommandLoader.load_command_doc("model", "configure", "9.0", software="flac")
    assert doc is not None
    assert set(doc["versions"]) == {"7.0", "9.0"}  # 9.1/9.3 folded away
    kw = {k["name"] for k in doc["keywords"]}
    # Current 9.x syntax (fluid-flow) folded into 9.0; the old 'fluid' is gone.
    assert "fluid-flow" in kw and "fluid" not in kw


# --- per-engine doc versions: FLAC covers 7.0/9.0, PFC keeps 6.0 --------------


@pytest.mark.asyncio
async def test_flac_6_0_rejected_across_doc_tools() -> None:
    for tool, extra in (
        ("itasca_browse_commands", {"command": "zone create"}),
        ("itasca_query_command", {"query": "zone create"}),
        ("itasca_browse_reference", {}),
    ):
        result = await mcp.call_tool(tool, {"software": "flac", "version": "6.0", **extra})
        payload = _parse_tool_payload(result)
        assert payload["ok"] is False, (tool, payload)
        assert payload["error"]["code"] == "unsupported_version", tool


@pytest.mark.asyncio
async def test_pfc_6_0_docs_still_supported() -> None:
    result = await mcp.call_tool(
        "itasca_browse_commands", {"software": "pfc", "command": "ball create", "version": "6.0"}
    )
    payload = _parse_tool_payload(result)
    assert payload["ok"] is True, payload
    assert payload["data"]["summary"]["version"] == "6.0"


def test_flac_common_doc_versions_exclude_6_0() -> None:
    # _common docs keep their 6.0 key for PFC; the FLAC view must not advertise it.
    doc = CommandLoader.load_command_doc("plot", "active", "7.0", software="flac")
    assert doc is not None
    assert "6.0" not in doc["versions"]
    pfc_doc = CommandLoader.load_command_doc("plot", "active", "6.0", software="pfc")
    assert pfc_doc is not None
    assert "6.0" in pfc_doc["versions"]


# --- 3DEC references (joint constitutive models) ----------------------------
# Joint (sub-contact) constitutive models are 3DEC's defining reference and have
# no FLAC/PFC equivalent. Generated by scripts/corpus/generate_3dec_joint_models.py.


def test_3dec_joint_models_reference_category() -> None:
    cats = ReferenceLoader.load_index(software="3dec").get("categories", {})
    assert "joint-models" in cats
    # PFC contact-models (ball/clump contacts) is a different physics and stays out.
    assert "contact-models" not in cats


def test_3dec_joint_models_lists_all_nine() -> None:
    cat = ReferenceLoader.load_category_index("joint-models", software="3dec")
    assert cat is not None
    names = {m["name"] for m in cat["models"]}
    # The nine jmodels enumerated by live 3DEC 9.7 'block contact jmodel assign'.
    assert names == {
        "elastic",
        "mohr",
        "bilinear-mohr",
        "softening-mohr",
        "cyjm",
        "nonlinear",
        "power",
        "ratestate",
        "velocity-weakening",
    }


def test_3dec_joint_model_item_has_property_vocabulary() -> None:
    mohr = ReferenceLoader.load_item_doc("joint-models", "mohr", software="3dec")
    assert mohr is not None
    keywords = {p["keyword"] for grp in mohr["property_groups"] for p in grp["properties"]}
    # Core Coulomb-slip joint property keywords parsed from the theory page.
    assert {"stiffness-normal", "stiffness-shear", "friction", "cohesion", "tension"} <= keywords


@pytest.mark.asyncio
async def test_3dec_browse_reference_joint_models() -> None:
    result = await mcp.call_tool("itasca_browse_reference", {"software": "3dec", "topic": "joint-models"})
    data = _parse_tool_payload(result)["data"]
    assert {e.get("name") for e in data["entries"]} >= {"mohr", "cyjm", "nonlinear"}


def test_3dec_references_isolated_from_flac() -> None:
    # joint-models is 3DEC-only; it must not appear in the FLAC reference index.
    flac = set(ReferenceLoader.load_index(software="flac").get("categories", {}))
    assert "joint-models" not in flac


# --- shared (_common) zone constitutive-models borrow -----------------------
# Zone (continuum / deformable-block) constitutive models are a 9.0 kernel shared
# by FLAC3D and 3DEC; the per-model docs live once in _common and each engine
# borrows them via RESOURCES-root-relative file pointers (same as command _common).


def test_zone_constitutive_models_shared_via_common() -> None:
    flac = ReferenceLoader.load_item_doc("constitutive-models", "mohr-coulomb", software="flac")
    tdec = ReferenceLoader.load_item_doc("constitutive-models", "mohr-coulomb", software="3dec")
    assert flac is not None and tdec is not None
    # Both engines resolve the very same _common document.
    assert flac == tdec
    assert flac["full_name"] == "Mohr-Coulomb Model"


def test_3dec_zone_models_are_engine_filtered_subset() -> None:
    flac_names = {
        m["name"] for m in ReferenceLoader.load_category_index("constitutive-models", software="flac")["models"]
    }
    tdec_names = {
        m["name"] for m in ReferenceLoader.load_category_index("constitutive-models", software="3dec")["models"]
    }
    # 3DEC exposes a strict subset of FLAC's zone models (block zone cmodel list).
    assert tdec_names < flac_names
    assert len(tdec_names) == 26
    # 3DEC-supported model present; FLAC-only models (no 3DEC support) excluded.
    assert "columnar-basalt" in tdec_names
    assert {"plastic-hardening", "norsand", "soft-soil"}.isdisjoint(tdec_names)


def test_pfc_has_no_zone_constitutive_models() -> None:
    # PFC has no zones; it must not carry the zone constitutive-models category.
    assert "constitutive-models" not in ReferenceLoader.load_index(software="pfc").get("categories", {})


def test_common_borrowed_item_pointer_resolves_to_common_path() -> None:
    # The 3DEC catalog entry points into _common (no duplicated item file under 3dec/).
    cat = ReferenceLoader.load_category_index("constitutive-models", software="3dec")
    entry = next(m for m in cat["models"] if m["name"] == "drucker-prager")
    assert entry["file"].startswith("_common/references/constitutive-models/")


# --- shared (_common) range-elements borrow ---------------------------------
# Range filters are 9.0 kernel shared by every engine; the docs live once in
# _common, with per-engine locals preserved (PFC's ball-contact range + its
# "ball"-keyworded sphere).


def test_range_elements_shared_across_all_engines() -> None:
    for sw in SUPPORTED_SOFTWARE:
        cyl = ReferenceLoader.load_item_doc("range-elements", "cylinder", software=sw)
        assert cyl is not None and cyl["name"] == "cylinder"
    # The same _common document backs cylinder for every engine.
    docs = [ReferenceLoader.load_item_doc("range-elements", "cylinder", software=sw) for sw in SUPPORTED_SOFTWARE]
    assert all(d == docs[0] for d in docs)


def test_range_elements_engine_specific_locals_preserved() -> None:
    # PFC keeps a ball-contact range filter; FLAC/3DEC (no ball contacts) do not.
    assert ReferenceLoader.load_item_doc("range-elements", "contact", software="pfc") is not None
    assert ReferenceLoader.load_item_doc("range-elements", "contact", software="3dec") is None
    # PFC's sphere stays local with its "ball" search keyword; the shared one is neutral.
    pfc_sphere = ReferenceLoader.load_item_doc("range-elements", "sphere", software="pfc")
    common_sphere = ReferenceLoader.load_item_doc("range-elements", "sphere", software="3dec")
    assert "ball" in pfc_sphere.get("search_keywords", [])
    assert "ball" not in common_sphere.get("search_keywords", [])


def test_3dec_range_elements_registered() -> None:
    cats = ReferenceLoader.load_index(software="3dec").get("categories", {})
    assert "range-elements" in cats
    assert len(ReferenceLoader.load_category_index("range-elements", software="3dec")["elements"]) == 22


# --- 3DEC FISH intrinsics (engine-specific, authored not borrowed) ----------
# FLAC's fish-intrinsics are zone/structure-specific, so 3DEC's are authored
# around blocks/joints/zones/flow (validated against the real 9.0 FISH docs).


def test_3dec_fish_intrinsics_category() -> None:
    cat = ReferenceLoader.load_category_index("fish-intrinsics", software="3dec")
    assert cat is not None
    assert {i["name"] for i in cat["items"]} == {"block-and-joints", "block-zone-gridpoint", "fluid-flow"}


def test_3dec_fish_intrinsics_item_lists_real_families() -> None:
    item = ReferenceLoader.load_item_doc("fish-intrinsics", "block-and-joints", software="3dec")
    assert item is not None
    examples = {ex for fam in item["intrinsic_families"] for ex in fam["examples"]}
    # 3DEC joint behavior lives on sub-contacts.
    assert "block.subcontact.model" in examples
    assert "block.subcontact.force.shear" in examples


def test_3dec_fish_intrinsics_is_engine_local_not_flac() -> None:
    # 3DEC's set is its own (block/joint/flow), not FLAC's (zone/gridpoint/structure).
    flac = ReferenceLoader.load_category_index("fish-intrinsics", software="flac")
    flac_names = {i["name"] for i in flac["items"]}
    assert "block-and-joints" not in flac_names


def test_3dec_initial_conditions_uses_block_syntax() -> None:
    cat = ReferenceLoader.load_category_index("initial-conditions", software="3dec")
    assert cat is not None
    assert {i["name"] for i in cat["items"]} == {
        "stress-initialization",
        "velocity-and-state-reset",
        "fluid-thermal",
    }
    si = ReferenceLoader.load_item_doc("initial-conditions", "stress-initialization", software="3dec")
    cmds = " ".join(si["primary_commands"])
    # 3DEC syntax (block ...), not FLAC's bare 'zone initialize'.
    assert "block zone initialize" in cmds and "block insitu" in cmds


def test_3dec_boundary_conditions_uses_block_syntax() -> None:
    cat = ReferenceLoader.load_category_index("boundary-conditions", software="3dec")
    assert cat is not None
    names = {i["name"] for i in cat["items"]}
    assert {"mechanical-face", "gridpoint-and-block-fixity", "apply-modifiers"} <= names
    mf = ReferenceLoader.load_item_doc("boundary-conditions", "mechanical-face", software="3dec")
    assert "block face apply" in mf["primary_commands"]  # 3DEC, not FLAC's 'zone face apply'


def test_3dec_geometry_data_table_topics() -> None:
    cat = ReferenceLoader.load_category_index("geometry-data-table", software="3dec")
    assert cat is not None
    assert {i["name"] for i in cat["items"]} == {"geometry-workflow", "data-sets", "table-curves"}
    geo = ReferenceLoader.load_item_doc("geometry-data-table", "geometry-workflow", software="3dec")
    # 3DEC geometry guides block cutting (not FLAC zone meshing).
    assert "block cut" in geo["primary_commands"]


def test_3dec_structural_properties_all_sel_types() -> None:
    cat = ReferenceLoader.load_category_index("structural-properties", software="3dec")
    assert cat is not None
    # 3DEC's six SEL types (more than FLAC's set — geogrid/shell included).
    assert {m["name"] for m in cat["models"]} == {"beam", "cable", "geogrid", "liner", "pile", "shell"}
    beam = ReferenceLoader.load_item_doc("structural-properties", "beam", software="3dec")
    kws = {p["keyword"] for p in beam["property_groups"][0]["properties"]}
    assert "cross-sectional-area" in kws
    # 3DEC is 3D: 2D-only keywords are omitted.
    assert "moi" not in kws and "shear-coefficient" not in kws


def test_3dec_plot_items_are_engine_specific() -> None:
    cat = ReferenceLoader.load_category_index("plot-items", software="3dec")
    assert cat is not None
    names = {i["name"] for i in cat["items"]}
    # 3DEC's distinctive plottable entities (not PFC's ball/clump, not FLAC's zone-only).
    assert {"block", "bzone", "subcontact", "joint", "fracture", "flow"} <= names
    # subcontact is where joint mechanics live: colorby exposes state / model.
    assert ReferenceLoader.is_directory_item("plot-items", "subcontact", software="3dec")
    cb = ReferenceLoader.load_sub_item_doc("plot-items", "subcontact", "colorby", software="3dec")
    assert {"state", "model"} <= set(cb["attributes"])
    # bzone field contour carries the continuum stress/displacement vocabulary.
    contour = ReferenceLoader.load_sub_item_doc("plot-items", "bzone", "contour", software="3dec")
    assert {"stress-zz", "displacement", "pore-pressure"} <= set(contour["attributes"])
    # 3DEC's structure item covers all six SEL types as one plot group.
    assert "structure-shell" in {
        i for it in cat["items"] if it["name"] == "structure" for i in it.get("common_use", "").split(", ")
    }


def test_3dec_histories_and_results_sampling_is_engine_specific() -> None:
    cat = ReferenceLoader.load_category_index("histories-and-results", software="3dec")
    assert cat is not None
    assert {i["name"] for i in cat["items"]} == {"history-workflow", "results-export"}
    wf = ReferenceLoader.load_item_doc("histories-and-results", "history-workflow", software="3dec")
    cmds = wf["primary_commands"]
    # 3DEC samples blocks / joints, not FLAC's 'zone history' / 'gridpoint history'.
    assert "block history" in cmds and "block contact history" in cmds
    assert "zone history" not in cmds


def test_3dec_now_has_ten_reference_categories() -> None:
    cats = set(ReferenceLoader.load_index(software="3dec").get("categories", {}))
    assert {
        "joint-models",
        "constitutive-models",
        "range-elements",
        "fish-intrinsics",
        "initial-conditions",
        "boundary-conditions",
        "geometry-data-table",
        "structural-properties",
        "plot-items",
        "histories-and-results",
    } <= cats
