"""Generate resources/mpoint/python_sdk_docs/index.json.

Replaces the earlier skeleton, which shipped only the shared ``itasca`` core and
deferred everything else. MPoint has no product-specific Python package -- the
MPM doc tree contains zero Python API pages -- but the engine does expose the
full 9.0 continuum kernel, and that is what an MPoint model is authored on:
``zone create`` / ``cmodel`` / ``property`` build the geometry and
``mpoint import from-zones`` converts it.

So the module set is borrowed from FLAC, by pointer, exactly as the zone command
family is. The borrow is not assumed -- every documented FLAC Python name was
checked against live MPoint3D 9.7 introspection (2026-09-14):

    14 module units, 236 documented functions -> 0 missing, 0 live-only extras.

The 7 upstream-documented names FLAC3D 9.7 does not expose (flagged
``available_in_flac3d_97=false`` in their files) are absent from MPoint too, so
the borrowed files are accurate including their exclusions.

The one thing this index must say loudly is what the API does *not* cover:
material points and background-grid nodes have no Python binding at all. After
``mpoint import from-zones`` every Python module reports a count of zero while
FISH sees the points perfectly. That boundary is the single most likely thing
for a new MPoint user to get wrong, so it is stated in the index description and
in the fallback hints.

Usage:
    uv run python scripts/corpus/generate_mpoint_python_index.py
"""

import json
import shutil
from pathlib import Path

RESOURCES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
FLAC_PY = RESOURCES / "flac" / "python_sdk_docs"
OUT_PY = RESOURCES / "mpoint" / "python_sdk_docs"

DESCRIPTION = (
    "MPoint (MPM) Python SDK documentation index. MPoint ships no product-specific Python "
    "package; it exposes the shared Itasca 9.0 continuum kernel, which is what MPoint models "
    "are built on before conversion. IMPORTANT: material points and background-grid nodes are "
    "NOT exposed to Python -- there is no itasca.mpoint module and no module reports them. "
    "The Python API covers the pre-conversion zone/gridpoint phase; read material-point state "
    "from FISH (mpoint.list, mpoint.pos, mpoint.node.num, ...)."
)

# Hint keys are matched as substrings of the user's query, so they are written the
# way someone would actually phrase the question -- singular, and without the
# "itasca." prefix -- and kept short enough to match inside a longer sentence.
MPOINT_HINTS = {
    "material point": (
        "Material points have no Python binding. After 'mpoint import from-zones' every itasca "
        "module reports a count of zero even though the points exist -- verified on MPoint3D 9.7 "
        "by sweeping count()/maxid() across all 46 submodules while FISH reported 512 points. "
        "Read them from FISH instead: loop foreach local mp mpoint.list / mpoint.pos(mp)."
    ),
    "mpoint": (
        "There is no itasca.mpoint module. MPoint's engine-specific scripting surface is FISH, not "
        "Python: drive it with itasca.command('mpoint ...') and read results back through FISH. "
        "The Python API covers the shared continuum kernel (zone, gridpoint, ...) only."
    ),
    "background node": (
        "Background-grid nodes are not itasca.gridpoint objects. itasca.gridpoint covers zone "
        "gridpoints, which exist only until 'mpoint import' deletes them. Read grid nodes from "
        "FISH (mpoint.node.num and the mpoint.node.* intrinsics)."
    ),
    "grid node": (
        "Background-grid nodes are not itasca.gridpoint objects. itasca.gridpoint covers zone "
        "gridpoints, which exist only until 'mpoint import' deletes them. Read grid nodes from "
        "FISH (mpoint.node.num and the mpoint.node.* intrinsics)."
    ),
    "from-zones": (
        "'mpoint import from-zones' deletes the zones and their gridpoints, so itasca.zone.count() "
        "and itasca.gridpoint.count() both drop to 0 afterwards. Read zone state before converting."
    ),
}

LIVE_VERIFICATION = (
    "All 14 module units (236 documented functions) diffed against live MPoint3D 9.7 "
    "introspection (2026-09-14): exact match, 0 missing and 0 live-only extras. The 7 names "
    "flagged available_in_flac3d_97=false are absent from MPoint as well. Functional spot-checks "
    "at state grade: itasca.zone/gridpoint/zonearray/gridpointarray read back geometry, density, "
    "gravity-initialized stress and displacement on an 8-zone brick. Material points are not "
    "exposed to Python (swept count()/maxid() across all 46 submodules after a 512-point import: "
    "every one reported zero)."
)


def main() -> None:
    flac_index = json.loads((FLAC_PY / "index.json").read_text(encoding="utf-8"))

    modules = dict(flac_index["modules"])
    assert str(modules["itasca"]["file"]).startswith("_common/"), "itasca core should live in _common/"

    index = {
        "version": "1.0",
        "description": DESCRIPTION,
        "modules": modules,
        "objects": dict(flac_index.get("objects", {})),
        "quick_ref": dict(flac_index.get("quick_ref", {})),
        "fallback_hints": {**flac_index.get("fallback_hints", {}), **MPOINT_HINTS},
        "live_verification_mpoint3d_97": LIVE_VERIFICATION,
    }

    OUT_PY.mkdir(parents=True, exist_ok=True)
    (OUT_PY / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.copyfile(FLAC_PY / "itasca_keywords.json", OUT_PY / "itasca_keywords.json")

    print(f"Wrote {OUT_PY / 'index.json'}")
    print(f"  modules: {len(index['modules'])}  objects: {len(index['objects'])}  quick_ref: {len(index['quick_ref'])}")
    print(f"  fallback hints: {len(index['fallback_hints'])} ({len(MPOINT_HINTS)} MPoint-specific)")


if __name__ == "__main__":
    main()
