"""Python API added from the live console sweeps (reconcile_python_api_live.py; 2026-10-24 and the 9.8 sweep of 2026-10-28).

Each family was missing from the corpus although the engine exposes it; the
notes pinned here come from state-readback probes, not from the docstrings.
"""

import json

import pytest

from itasca_mcp.knowledge.python_api import PythonAPILoader
from itasca_mcp.server import mcp


def _payload(result) -> dict:
    return json.loads(result.content[0].text)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("software", "api"),
    [
        ("flac", "itasca.structure.Beam.length"),
        ("flac", "itasca.structure.beamarray.length"),
        ("flac", "itasca.dfn.fracture.Fracture.dip"),
        ("flac", "itasca.data.scalar.Scalar.value"),
        ("flac", "itasca.geometry.Set.poly_count"),
        ("flac", "itasca.history.get"),
        ("pfc", "itasca.ball.thermal.ThermalBall.temp"),
        ("pfc", "itasca.wall.thermal.facet.ThermalFacet.temp"),
        ("pfc", "itasca.ball.cfd.CFDBall.force"),
        ("pfc", "itasca.element.cfd.CFDElement.vel"),
        ("pfc", "itasca.ballarray.rotation"),
        ("mpoint", "itasca.fish.get"),
        ("mpoint", "itasca.dfn.fracture.Fracture.dip"),
        ("3dec", "itasca.structure.beamarray.length"),
        ("3dec", "itasca.data.vector.Vector.value"),
        ("mpoint", "itasca.mpoint.MPMPoint.stress"),
        ("mpoint", "itasca.mpoint.mpmpointarray.pos"),
        ("mpoint", "itasca.mpoint.node.MeshPoint.velocity"),
        ("flac", "itasca.table.Table.value"),
        ("flac", "itasca.zonearray.face_normal"),
    ],
)
async def test_live_families_are_browsable(software: str, api: str) -> None:
    result = await mcp.call_tool("itasca_browse_doc", {"source": "python_api", "path": api, "software": software})
    payload = _payload(result)

    assert payload["ok"] is True, payload


def test_flac_interface_dimension_and_version_entries() -> None:
    node = {m["name"]: m for m in PythonAPILoader.load_object("Node", software="flac")["methods"]}

    assert "2D builds only." in node["length"]["notes"]
    assert any("reads 0.0 before the first cycle" in n for n in node["length"]["notes"])
    assert node["has_prop"]["availability"] == {"versions": ["7.0"]}
    assert any("not usable" in n for n in node["has_prop"]["notes"])


def test_pfc_2d_rotation_is_documented_in_degrees_and_euler_is_3d_only() -> None:
    funcs = {f["name"]: f for f in PythonAPILoader.load_module("ballarray", software="pfc")["functions"]}

    assert "2D builds only." in funcs["rotation"]["notes"]
    assert any("Angle in degrees" in n for n in funcs["rotation"]["notes"])
    assert any("2D builds expose rotation" in n for n in funcs["euler"]["notes"])


@pytest.mark.parametrize("software", ["pfc", "flac", "3dec", "mpoint", "massflow"])
def test_fish_call_function_takes_a_tuple(software: str) -> None:
    func = PythonAPILoader.load_function("fish", "call_function", software=software)

    assert func is not None
    assert [p["name"] for p in func["parameters"]] == ["func", "args"]
    assert any("must be passed as a tuple" in n for n in func["notes"])


def test_9x_only_modules_carry_the_9_marker_and_no_point_release_note() -> None:
    # The "9.0" label stands for the current 9.x release (9.8); point builds are not tracked.
    module = PythonAPILoader.load_module("structure.beamarray", software="3dec")

    assert module["availability"] == {"versions": ["9.0"]}
    assert not any("9.7" in n for n in module.get("notes", []))


def test_flac_7_attach_names_and_9_renames_are_both_marked() -> None:
    attach = {m["name"]: m for m in PythonAPILoader.load_object("Attach", software="flac")["methods"]}

    assert attach["master"]["availability"] == {"versions": ["7.0"]}
    assert attach["leader"]["availability"] == {"versions": ["9.0"]}
