"""Generate resources/mpoint/python_sdk_docs/index.json.

MPoint ships no product-specific Python package: the MPM doc tree contains zero
Python API pages, and there is no ``itasca.mpoint`` module. What the binary does
expose is the shared Itasca 9.0 kernel -- the same ``itasca.zone`` /
``itasca.gridpoint`` surface FLAC3D has, because Itasca 9 is one binary.

Those modules are NOT copied into this index. Every engine layer in this corpus
documents only its own product (see generate_mpoint_index.py), and the continuum
Python API belongs to FLAC; it is reachable under ``software="flac"``. This index
therefore carries the ``itasca`` core from ``_common`` and nothing else.

What it does add is the part that is genuinely MPoint's: the boundary. Material
points and background-grid nodes have no Python binding at all. After
``mpoint import from-zones`` every ``itasca`` module reports a count of zero
while FISH sees every point. That is the single most likely thing for a new
MPoint user to get wrong, so it is stated in the index description and, more
importantly, in ``fallback_hints`` -- which ``itasca_query_python_api`` surfaces
whenever a query mentions material points, by text match rather than only on an
empty result set.

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
    "package. IMPORTANT: material points and background-grid nodes are NOT exposed to Python -- "
    "there is no itasca.mpoint module and no itasca module reports them; read material-point "
    "state from FISH (mpoint.list, mpoint.pos, mpoint.node.num, ...). The shared continuum "
    "modules (itasca.zone, itasca.gridpoint, ...) do run on the MPoint binary but belong to "
    "FLAC and are documented under software='flac'."
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
    "itasca.zone": (
        "itasca.zone and itasca.gridpoint run on the MPoint binary -- all 236 documented functions "
        "are present -- but they are FLAC's continuum API and are documented under software='flac'. "
        "Note they only see the pre-conversion grid: 'mpoint import' deletes the zones."
    ),
    "itasca.gridpoint": (
        "itasca.gridpoint is FLAC's zone-gridpoint API, documented under software='flac'. It is NOT "
        "the MPM background grid -- read grid nodes from FISH (mpoint.node.*)."
    ),
}

LIVE_VERIFICATION = (
    "Material points are not exposed to Python: after a 512-point 'mpoint import from-zones', "
    "count()/maxid() were swept across all 46 itasca submodules on live MPoint3D 9.7 (2026-09-14) "
    "and every one reported zero, while FISH reported all 512. Separately, FLAC's 14 documented "
    "Python module units (236 functions) were diffed against the same binary and matched exactly "
    "(0 missing, 0 extras) -- that surface is real here, but it is FLAC's API and is documented "
    "under software='flac'."
)


def main() -> None:
    flac_index = json.loads((FLAC_PY / "index.json").read_text(encoding="utf-8"))

    itasca_module = flac_index["modules"]["itasca"]
    assert str(itasca_module["file"]).startswith("_common/"), "itasca core should live in _common/"

    # Only the shared core travels; the continuum modules stay under software="flac".
    quick_ref = {
        k: v
        for k, v in flac_index.get("quick_ref", {}).items()
        if k.startswith("itasca.") and str(v).startswith("_common/")
    }

    index = {
        "version": "1.0",
        "description": DESCRIPTION,
        "modules": {"itasca": itasca_module},
        "objects": {},
        "quick_ref": quick_ref,
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
