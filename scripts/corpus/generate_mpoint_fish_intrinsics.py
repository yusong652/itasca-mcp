"""Generate the MPoint (MPM) ``fish-intrinsics`` reference category.

FISH is MPoint's *only* scripted access to material points and background-grid
nodes -- neither is exposed to the Python API at all -- so this category carries
more weight for MPoint than for any other engine.

Provenance (MPoint verification campaign, Batch 4, 2026-09-14): the intrinsic set
and every signature below come from ``fish list intrinsics`` on a live MPoint3D
9.7, filtered to ``mpoint.*`` -- 100 intrinsics. The earlier version of this file
listed 55 names and no signatures; none of the 55 were wrong, but 45 were
missing, including ``mpoint.create`` / ``mpoint.delete`` (FISH can build and
destroy material points) and every per-component accessor.

Cross-checks:
- All 67 names in the installed ``out_fish.txt`` index are present live.
- ``mpoint.node.mass.mult`` is live-only: no doc page, no index entry.
- Argument kinds were verified by executing them both ways round (NODE_ARG_TRAP).

Output (MPoint-local, not a _common borrow):
    mpoint/references/fish-intrinsics/index.json     (category index)
    mpoint/references/fish-intrinsics/<item>.json    (one per entity)

Usage:
    uv run python scripts/corpus/generate_mpoint_fish_intrinsics.py
"""

import json
from pathlib import Path
from typing import Any

OUT = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/mpoint/references")
CAT_DIR = OUT / "fish-intrinsics"

# ---------------------------------------------------------------------------
# Live signatures: `fish list intrinsics` on MPoint3D 9.7 (2026-09-14),
# reproduced verbatim. A trailing ":= <type>" marks an assignable intrinsic.
# ---------------------------------------------------------------------------

SIGNATURES: dict[str, str] = {
    # --- material points ---
    "mpoint.containing": "MPM_POINT_pnt = mpoint.containing(vec3+,<index>)",
    "mpoint.create": "mpm_point_pnt := mpoint.create(flt,vec3+,<int>)",
    "mpoint.deformation": "flt := mpoint.deformation(mpm_point_pnt)",
    "mpoint.delete": "bool := mpoint.delete(mpm_point_pnt)",
    "mpoint.density": "flt := mpoint.density(mpm_point_pnt) := flt",
    "mpoint.disp": "vec3/flt := mpoint.disp(mpm_point_pnt,<int>) := vec3/flt",
    "mpoint.disp.x": "flt := mpoint.disp.x(mpm_point_pnt) := flt",
    "mpoint.disp.y": "flt := mpoint.disp.y(mpm_point_pnt) := flt",
    "mpoint.disp.z": "flt := mpoint.disp.z(mpm_point_pnt) := flt",
    "mpoint.extra": "any := mpoint.extra(mpm_point_pnt,<int>) := any",
    "mpoint.find": "MPM_POINT_pnt = mpoint.find(int)",
    "mpoint.fix": "bool := mpoint.fix(mpm_point_pnt,int) := bool",
    "mpoint.fluid.prop": "any := mpoint.fluid.prop(mpm_point_pnt,str) := any",
    "mpoint.force.app": "vec3/flt := mpoint.force.app(mpm_point_pnt,<int>) := vec3/flt",
    "mpoint.force.app.x": "flt := mpoint.force.app.x(mpm_point_pnt) := flt",
    "mpoint.force.app.y": "flt := mpoint.force.app.y(mpm_point_pnt) := flt",
    "mpoint.force.app.z": "flt := mpoint.force.app.z(mpm_point_pnt) := flt",
    "mpoint.group": "str := mpoint.group(mpm_point_pnt,<str/index>) := str/index",
    "mpoint.group.list": "list = mpoint.group.list(str/index,<str/index>)",
    "mpoint.group.remove": "bool := mpoint.group.remove(mpm_point_pnt,str/index,<str/index>)",
    "mpoint.groupmap": "map = mpoint.groupmap(str/index,<str/index>)",
    "mpoint.id": "int := mpoint.id(mpm_point_pnt)",
    "mpoint.inbox": "list = mpoint.inbox(vec3+,vec3+,<bool>)",
    "mpoint.isgroup": "bool := mpoint.isgroup(mpm_point_pnt,str/index,<str/index>)",
    "mpoint.list": "mpmpoint_list_pnt = mpoint.list()",
    "mpoint.mass.gravity": "flt := mpoint.mass.gravity(mpm_point_pnt)",
    "mpoint.maxid": "int = mpoint.maxid()",
    "mpoint.mech.ratio.avg": "flt = mpoint.mech.ratio.avg()",
    "mpoint.mech.ratio.local": "flt = mpoint.mech.ratio.local()",
    "mpoint.mech.ratio.max": "flt = mpoint.mech.ratio.max()",
    "mpoint.mech.unbal.max": "flt = mpoint.mech.unbal.max()",
    "mpoint.near": "MPM_POINT_pnt = mpoint.near(vec3+,<flt>)",
    "mpoint.num": "int = mpoint.num()",
    "mpoint.pos": "vec3/flt := mpoint.pos(mpm_point_pnt,<int>) := vec3/flt",
    "mpoint.pos.x": "flt := mpoint.pos.x(mpm_point_pnt) := flt",
    "mpoint.pos.y": "flt := mpoint.pos.y(mpm_point_pnt) := flt",
    "mpoint.pos.z": "flt := mpoint.pos.z(mpm_point_pnt) := flt",
    "mpoint.pp": "flt := mpoint.pp(mpm_point_pnt) := flt",
    "mpoint.pp.fix": "bool := mpoint.pp.fix(mpm_point_pnt) := bool",
    "mpoint.prop": "any := mpoint.prop(mpm_point_pnt,str/int) := any",
    "mpoint.prop.index": "int := mpoint.prop.index(mpm_point_pnt,str)",
    "mpoint.strain": "ten/flt := mpoint.strain(mpm_point_pnt,<int>,<int>) := ten/flt",
    "mpoint.strain.xx": "flt := mpoint.strain.xx(mpm_point_pnt) := flt",
    "mpoint.strain.xy": "flt := mpoint.strain.xy(mpm_point_pnt) := flt",
    "mpoint.strain.xz": "flt := mpoint.strain.xz(mpm_point_pnt) := flt",
    "mpoint.strain.yy": "flt := mpoint.strain.yy(mpm_point_pnt) := flt",
    "mpoint.strain.yz": "flt := mpoint.strain.yz(mpm_point_pnt) := flt",
    "mpoint.strain.zz": "flt := mpoint.strain.zz(mpm_point_pnt) := flt",
    "mpoint.stress": "ten/flt := mpoint.stress(mpm_point_pnt,<int>,<int>) := ten/flt",
    "mpoint.stress.xx": "flt := mpoint.stress.xx(mpm_point_pnt) := flt",
    "mpoint.stress.xy": "flt := mpoint.stress.xy(mpm_point_pnt) := flt",
    "mpoint.stress.xz": "flt := mpoint.stress.xz(mpm_point_pnt) := flt",
    "mpoint.stress.yy": "flt := mpoint.stress.yy(mpm_point_pnt) := flt",
    "mpoint.stress.yz": "flt := mpoint.stress.yz(mpm_point_pnt) := flt",
    "mpoint.stress.zz": "flt := mpoint.stress.zz(mpm_point_pnt) := flt",
    "mpoint.typeid": "int = mpoint.typeid()",
    "mpoint.vel": "vec3/flt := mpoint.vel(mpm_point_pnt,<int>) := vec3/flt",
    "mpoint.vel.x": "flt := mpoint.vel.x(mpm_point_pnt) := flt",
    "mpoint.vel.y": "flt := mpoint.vel.y(mpm_point_pnt) := flt",
    "mpoint.vel.z": "flt := mpoint.vel.z(mpm_point_pnt) := flt",
    "mpoint.vol": "flt := mpoint.vol(mpm_point_pnt)",
    # --- background-grid nodes ---
    "mpoint.node.disp": "vec3/flt := mpoint.node.disp(vec3,<int>)",
    "mpoint.node.disp.x": "flt := mpoint.node.disp.x(vec3)",
    "mpoint.node.disp.y": "flt := mpoint.node.disp.y(vec3)",
    "mpoint.node.disp.z": "flt := mpoint.node.disp.z(vec3)",
    "mpoint.node.find": "MESHPOINT_pnt = mpoint.node.find(int)",
    "mpoint.node.force.unbal": "vec3/flt := mpoint.node.force.unbal(MESHPOINT_pnt,<int>)",
    "mpoint.node.force.unbal.x": "flt := mpoint.node.force.unbal.x(MESHPOINT_pnt)",
    "mpoint.node.force.unbal.y": "flt := mpoint.node.force.unbal.y(MESHPOINT_pnt)",
    "mpoint.node.force.unbal.z": "flt := mpoint.node.force.unbal.z(MESHPOINT_pnt)",
    "mpoint.node.group": "str := mpoint.node.group(MESHPOINT_pnt,<str/index>) := str/index",
    "mpoint.node.group.list": "list = mpoint.node.group.list(str/index,<str/index>)",
    "mpoint.node.group.remove": "bool := mpoint.node.group.remove(MESHPOINT_pnt,str/index,<str/index>)",
    "mpoint.node.groupmap": "map = mpoint.node.groupmap(str/index,<str/index>)",
    "mpoint.node.id": "int := mpoint.node.id(MESHPOINT_pnt)",
    "mpoint.node.inbox": "list = mpoint.node.inbox(vec3+,vec3+,<bool>)",
    "mpoint.node.isgroup": "bool := mpoint.node.isgroup(MESHPOINT_pnt,str/index,<str/index>)",
    "mpoint.node.list": "list = mpoint.node.list()",
    "mpoint.node.mass.mult": "flt := mpoint.node.mass.mult(MESHPOINT_pnt)",
    "mpoint.node.maxid": "int = mpoint.node.maxid()",
    "mpoint.node.near": "MESHPOINT_pnt = mpoint.node.near(vec3+,<flt>)",
    "mpoint.node.num": "int = mpoint.node.num()",
    "mpoint.node.pos": "vec3/flt := mpoint.node.pos(MESHPOINT_pnt,<int>)",
    "mpoint.node.pos.x": "flt := mpoint.node.pos.x(MESHPOINT_pnt)",
    "mpoint.node.pos.y": "flt := mpoint.node.pos.y(MESHPOINT_pnt)",
    "mpoint.node.pos.z": "flt := mpoint.node.pos.z(MESHPOINT_pnt)",
    "mpoint.node.pp": "flt := mpoint.node.pp(vec3)",
    "mpoint.node.spacing": "flt := mpoint.node.spacing()",
    "mpoint.node.stress": "ten/flt := mpoint.node.stress(vec3,<int>,<int>)",
    "mpoint.node.stress.xx": "flt := mpoint.node.stress.xx(vec3)",
    "mpoint.node.stress.xy": "flt := mpoint.node.stress.xy(vec3)",
    "mpoint.node.stress.xz": "flt := mpoint.node.stress.xz(vec3)",
    "mpoint.node.stress.yy": "flt := mpoint.node.stress.yy(vec3)",
    "mpoint.node.stress.yz": "flt := mpoint.node.stress.yz(vec3)",
    "mpoint.node.stress.zz": "flt := mpoint.node.stress.zz(vec3)",
    "mpoint.node.typeid": "int = mpoint.node.typeid()",
    "mpoint.node.vel": "vec3/flt := mpoint.node.vel(MESHPOINT_pnt,<int>)",
    "mpoint.node.vel.x": "flt := mpoint.node.vel.x(MESHPOINT_pnt)",
    "mpoint.node.vel.y": "flt := mpoint.node.vel.y(MESHPOINT_pnt)",
    "mpoint.node.vel.z": "flt := mpoint.node.vel.z(MESHPOINT_pnt)",
}

UNDOCUMENTED = {"mpoint.node.mass.mult"}

NODE_ARG_TRAP = (
    "Background-node intrinsics take two different kinds of first argument and the engine will not "
    "convert between them. pos / vel / id / group / isgroup / force.unbal / mass.mult take a node "
    "POINTER (MESHPOINT_pnt, from mpoint.node.find or mpoint.node.list). disp / pp / stress take a "
    "POSITION (vec3) and interpolate the field there. Verified by executing both the correct and the "
    "swapped form: mpoint.node.vel(<vec3>) and mpoint.node.pp(<ptr>) both fail. (state)"
)

ITEMS: list[dict[str, Any]] = [
    {
        "name": "material-point",
        "full_name": "Material Point FISH Intrinsics",
        "description": (
            "Pointer-based FISH access to material points -- the MPM carriers of mass, stress and "
            "history. This is the ONLY scripted access to material points: they have no Python "
            "binding. MPoint3D is 3D."
        ),
        "notes": [
            "Material points are not exposed to the Python API. itasca.* reports a count of zero "
            "after 'mpoint import from-zones' even though the points exist -- use these intrinsics.",
            "Iterate with 'loop foreach local mp mpoint.list' rather than assuming contiguous IDs.",
            "An intrinsic whose signature ends in ':= <type>' can be assigned to, not just read "
            "(for example mpoint.vel(mp) = vector(0,0,0)).",
            "Properties are constitutive-model-specific: mpoint.prop(mp,'young') works only if the "
            "assigned model has that property. See references/constitutive-models.",
        ],
        "families": [
            (
                "iteration & identity",
                [
                    "mpoint.list",
                    "mpoint.num",
                    "mpoint.maxid",
                    "mpoint.find",
                    "mpoint.id",
                    "mpoint.typeid",
                    "mpoint.near",
                    "mpoint.containing",
                    "mpoint.inbox",
                ],
                [
                    "mpoint.containing(pos) finds the point occupying a position, mpoint.near(pos,<radius>) "
                    "the closest one, and mpoint.inbox(lo,hi) every point in a box.",
                ],
            ),
            (
                "creation & deletion",
                ["mpoint.create", "mpoint.delete"],
                [
                    "FISH can build and destroy material points directly -- mpoint.create(volume,position) "
                    "-- which is the scripted alternative to 'mpoint create' / 'mpoint generate'.",
                ],
            ),
            (
                "geometry & motion",
                [
                    "mpoint.pos",
                    "mpoint.pos.x",
                    "mpoint.pos.y",
                    "mpoint.pos.z",
                    "mpoint.disp",
                    "mpoint.disp.x",
                    "mpoint.disp.y",
                    "mpoint.disp.z",
                    "mpoint.vel",
                    "mpoint.vel.x",
                    "mpoint.vel.y",
                    "mpoint.vel.z",
                    "mpoint.vol",
                    "mpoint.deformation",
                ],
                [
                    "mpoint.vol is the current point volume; mpoint.deformation is the determinant of the "
                    "deformation gradient (1.0 in the undeformed state).",
                    "The vector forms take an optional component index, so mpoint.pos(mp,3) and "
                    "mpoint.pos.z(mp) are the same value.",
                ],
            ),
            (
                "stress & strain",
                [
                    "mpoint.stress",
                    "mpoint.stress.xx",
                    "mpoint.stress.xy",
                    "mpoint.stress.xz",
                    "mpoint.stress.yy",
                    "mpoint.stress.yz",
                    "mpoint.stress.zz",
                    "mpoint.strain",
                    "mpoint.strain.xx",
                    "mpoint.strain.xy",
                    "mpoint.strain.xz",
                    "mpoint.strain.yy",
                    "mpoint.strain.yz",
                    "mpoint.strain.zz",
                ],
                [
                    "Stress initialized on zones survives the conversion: after 'zone initialize-stresses' "
                    "then 'mpoint import from-zones', mpoint.stress.zz matches the zone value it came "
                    "from. (state)",
                ],
            ),
            (
                "constitutive model & properties",
                ["mpoint.prop", "mpoint.prop.index", "mpoint.density", "mpoint.extra"],
                [],
            ),
            ("fluid", ["mpoint.fluid.prop", "mpoint.pp", "mpoint.pp.fix"], []),
            (
                "fixity & loading",
                [
                    "mpoint.fix",
                    "mpoint.force.app",
                    "mpoint.force.app.x",
                    "mpoint.force.app.y",
                    "mpoint.force.app.z",
                    "mpoint.mass.gravity",
                ],
                [
                    "mpoint.fix(mp,dof) reads or sets the fixity flag for one degree of freedom; the "
                    "command form is 'mpoint fix velocity-x ... range ...'.",
                ],
            ),
            (
                "groups",
                [
                    "mpoint.group",
                    "mpoint.group.list",
                    "mpoint.group.remove",
                    "mpoint.groupmap",
                    "mpoint.isgroup",
                ],
                [],
            ),
            (
                "convergence (unbalance)",
                [
                    "mpoint.mech.ratio.avg",
                    "mpoint.mech.ratio.local",
                    "mpoint.mech.ratio.max",
                    "mpoint.mech.unbal.max",
                ],
                ["Model-level rather than per-point: these take no arguments."],
            ),
        ],
    },
    {
        "name": "background-node",
        "full_name": "Background-Grid Node FISH Intrinsics",
        "description": (
            "FISH access to the background-grid nodes -- the fixed computational mesh the material "
            "points move through. Like material points, these have no Python binding."
        ),
        "notes": [
            NODE_ARG_TRAP,
            "The grid spans the whole 'model domain extent', not the material-point bounding box, and "
            "is built lazily at 'mpoint import' time. mpoint.node.pos of the first node is the domain "
            "corner. Keep the domain tight. (state)",
            "mpoint.node.spacing() reports the value set by 'mpoint node spacing'.",
            "mpoint.node.mass.mult is undocumented -- no doc page and no entry in out_fish.txt -- but "
            "the engine exposes it and it returns 1.0 on an untouched grid. (state)",
        ],
        "families": [
            (
                "iteration & identity",
                [
                    "mpoint.node.list",
                    "mpoint.node.num",
                    "mpoint.node.maxid",
                    "mpoint.node.find",
                    "mpoint.node.id",
                    "mpoint.node.typeid",
                    "mpoint.node.near",
                    "mpoint.node.inbox",
                ],
                [],
            ),
            (
                "grid geometry",
                [
                    "mpoint.node.pos",
                    "mpoint.node.pos.x",
                    "mpoint.node.pos.y",
                    "mpoint.node.pos.z",
                    "mpoint.node.spacing",
                ],
                ["Pointer-taking, except spacing, which takes no argument."],
            ),
            (
                "field queries at a position",
                [
                    "mpoint.node.disp",
                    "mpoint.node.disp.x",
                    "mpoint.node.disp.y",
                    "mpoint.node.disp.z",
                    "mpoint.node.pp",
                    "mpoint.node.stress",
                    "mpoint.node.stress.xx",
                    "mpoint.node.stress.xy",
                    "mpoint.node.stress.xz",
                    "mpoint.node.stress.yy",
                    "mpoint.node.stress.yz",
                    "mpoint.node.stress.zz",
                ],
                [
                    "These take a vec3 POSITION, not a node pointer -- they interpolate the field at "
                    "that point. Passing a pointer fails. (state)",
                ],
            ),
            (
                "motion, mass & convergence",
                [
                    "mpoint.node.vel",
                    "mpoint.node.vel.x",
                    "mpoint.node.vel.y",
                    "mpoint.node.vel.z",
                    "mpoint.node.force.unbal",
                    "mpoint.node.force.unbal.x",
                    "mpoint.node.force.unbal.y",
                    "mpoint.node.force.unbal.z",
                    "mpoint.node.mass.mult",
                ],
                ["Pointer-taking."],
            ),
            (
                "groups",
                [
                    "mpoint.node.group",
                    "mpoint.node.group.list",
                    "mpoint.node.group.remove",
                    "mpoint.node.groupmap",
                    "mpoint.node.isgroup",
                ],
                [],
            ),
        ],
    },
]

LIVE_VERIFICATION = (
    "Intrinsic set and signatures captured from 'fish list intrinsics' on live MPoint3D 9.7 "
    "(2026-09-14): 100 mpoint.* intrinsics. Every one of the 67 names in the installed out_fish.txt "
    "index is present; mpoint.node.mass.mult is live-only. State-grade spot-checks on a 512-point "
    "model: mpoint.pos/vol/density/stress.zz/prop and mpoint.node.pos/spacing/stress.zz/mass.mult all "
    "returned values consistent with the model that produced them."
)


def build_item(item: dict[str, Any]) -> dict[str, Any]:
    families = []
    for family, names, notes in item["families"]:
        families.append(
            {
                "family": family,
                "intrinsics": [
                    {
                        "name": name,
                        "signature": SIGNATURES[name],
                        **({"undocumented": True} if name in UNDOCUMENTED else {}),
                    }
                    for name in names
                ],
                "notes": notes,
            }
        )
    count = sum(len(f["intrinsics"]) for f in families)
    return {
        "name": item["name"],
        "dimension": "3D",
        "full_name": item["full_name"],
        "description": item["description"],
        "notes": item["notes"],
        "intrinsic_count": count,
        "intrinsic_families": families,
        "live_verification": LIVE_VERIFICATION,
    }


def main() -> None:
    used: list[str] = []
    for item in ITEMS:
        for _, names, _ in item["families"]:
            used.extend(names)

    unknown = [n for n in used if n not in SIGNATURES]
    duplicated = sorted({n for n in used if used.count(n) > 1})
    unplaced = sorted(set(SIGNATURES) - set(used))
    if unknown or duplicated or unplaced:
        raise SystemExit(
            f"family/signature mismatch -- unknown: {unknown}; duplicated: {duplicated}; "
            f"not placed in any family: {unplaced}"
        )

    CAT_DIR.mkdir(parents=True, exist_ok=True)
    index_items = []
    for item in ITEMS:
        built = build_item(item)
        (CAT_DIR / f"{built['name']}.json").write_text(
            json.dumps(built, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        index_items.append(
            {
                "name": built["name"],
                "file": f"{built['name']}.json",
                "full_name": built["full_name"],
                "intrinsic_count": built["intrinsic_count"],
            }
        )
        print(f"  {built['name']}.json  {built['intrinsic_count']} intrinsics")

    index = {
        "type": "fish_intrinsics",
        "description": (
            "MPoint (MPM) FISH intrinsic families -- material points and the background-grid nodes. "
            "FISH is the only scripted access to either: neither is exposed to the Python API."
        ),
        "items": index_items,
        "live_verification": LIVE_VERIFICATION,
        "official_sources": ["https://docs.itascacg.com/itasca900/mpm/mpm/doc/source/manual/fish/fish.html"],
    }
    (CAT_DIR / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    total = sum(i["intrinsic_count"] for i in index_items)
    print(f"total: {total} intrinsics (signature table has {len(SIGNATURES)})")


if __name__ == "__main__":
    main()
