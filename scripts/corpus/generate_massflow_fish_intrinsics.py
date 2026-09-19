"""Generate the MassFlow ``fish-intrinsics`` reference category.

MassFlow ships **no** engine-specific Python API — ``itasca`` on the massflow
binary is the bare shared kernel — so FISH is the only scripted access to
drawpoints, draw periods, mine blocks and markers. The corpus had no MassFlow
FISH reference at all.

Provenance (MassFlow verification campaign, Batch 4, 2026-09-19):

* signatures: ``fish list intrinsics`` on live MassFlow 9.7.47, filtered to
  ``massflow.*`` — **175** intrinsics (1328 in total across the kernel);
* descriptions: the **96** ``fish_massflow.*`` pages of the 9.7 doc tree.

The two do not line up, and the gaps are recorded rather than papered over:

* **81** live intrinsics have no page — among them the entire
  ``massflow.drawperiod.*`` family (14 functions, the scripted view of the draw
  schedule), every ``.pos.x`` / ``.y`` / ``.z``-style component accessor, the
  writable ``massflow.mineblock.*.dyn`` twins of the imported block properties,
  ``massflow.marker.moved-day`` / ``moved-cycle`` / ``column``,
  ``massflow.markerfraglimit.*``, ``massflow.massbalance.*``,
  ``massflow.solveOutput*`` and ``massflow.write``;
* **2** documented names are gone from the binary and are listed as renames, not
  as usable intrinsics: ``massflow.mass.extracted`` (now
  ``massflow.mass.total``) and ``massflow.mineblock.friction`` (now
  ``massflow.mineblock.fric``). Both were evaluated in FISH and answered
  "is not recognized as a library function".

``massflow.mass.dpday``'s page is an orphan (its breadcrumb is "Temp Toctree
Material", not the FISH toctree) and spells the name in lower case; FISH is
case-insensitive, so it resolves to the live ``massflow.mass.DpDay``.

Data lives beside this script in ``massflow_fish_data.json`` so the captured
signatures and descriptions stay reviewable as data.

Output (MassFlow-local, not a _common borrow):
    massflow/references/fish-intrinsics/index.json
    massflow/references/fish-intrinsics/<family>.json

Usage:
    uv run python scripts/corpus/generate_massflow_fish_intrinsics.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESOURCES = HERE.parents[1] / "src" / "itasca_mcp" / "knowledge" / "resources"
CAT_DIR = RESOURCES / "massflow" / "references" / "fish-intrinsics"
REF_INDEX = RESOURCES / "massflow" / "references" / "index.json"
DATA = HERE / "massflow_fish_data.json"

LIVE_SOURCE = "fish list intrinsics on live MassFlow 9.7.47 (build 6bc705b1eb), massflow.* only"
DOC_SOURCE = "Itasca 9.7 MassFlow manual, FISH Functions (96 fish_massflow.* pages)"

# Documented names that no longer exist in the binary.
RETIRED: dict[str, str] = {
    "massflow.mass.extracted": "massflow.mass.total",
    "massflow.mineblock.friction": "massflow.mineblock.fric",
}

FAMILIES: list[dict[str, Any]] = [
    {
        "name": "mineblock",
        "prefix": "massflow.mineblock.",
        "full_name": "Mine Block FISH Intrinsics",
        "description": (
            "Pointer-based access to mine blocks — the orebody cells that carry material "
            "properties, ore grades, caving state and fragmentation. Imported block "
            "columns are read through here, and the `.dyn` variants are the writable "
            "twins that let a script override an imported value mid-run."
        ),
        "notes": [
            "`massflow.mineblock.state` returns an integer. The manual lists -1 solid, "
            "1 caved, 2 mobilized active, 3 mobilized inactive, 4 air, 5 extracted — but "
            "block 1 of the tutorial model reads back **0**, which the manual does not "
            "list, and the vendor's own unittests.dat asserts that same 0.",
            "Pairs like `frag.primary.a` / `frag.primary.a.dyn` are the imported value "
            "and its user-writable override; when they differ, the dynamic one is used.",
            "Iterate with `loop foreach local mb massflow.mineblock.list` rather than assuming contiguous IDs.",
        ],
    },
    {
        "name": "marker",
        "prefix": "massflow.marker.",
        "full_name": "Marker FISH Intrinsics",
        "description": (
            "Pointer-based access to markers — the moving carriers that track where "
            "caved material came from and where it went. Markers are created lazily as "
            "caving proceeds, so the set grows during `massflow compute`."
        ),
        "notes": [
            "`massflow.marker.type` returns an integer: -2 unbulked for IMZ growth, "
            "-1 unbulked for collapse, 0 unbulked for rilling, 1 partially bulked, "
            "2 fully bulked, 3 air.",
            "`massflow.marker.active.tolerance` is a global setting, readable and writable, not a per-marker value.",
            "An intrinsic whose signature ends in `:= <type>` can be assigned to, not just read.",
            "`massflow.marker.moved-day` and `massflow.marker.moved-cycle` cannot be "
            "written in a FISH expression: the parser reads the hyphen as subtraction "
            "and fails with `massflow.marker.moved is not recognized as a library "
            "function`. They are listed by `fish list intrinsics` all the same.",
        ],
    },
    {
        "name": "drawpoint",
        "prefix": "massflow.drawpoint.",
        "full_name": "Draw Point FISH Intrinsics",
        "description": (
            "Pointer-based access to drawpoints — position, drawbell, the IMZ slice "
            "geometry above them, and the requested versus actual extracted mass per "
            "day and per period."
        ),
        "notes": [
            "`massflow.drawpoint.radius(dp, i)` and `height(dp, i)` index the IMZ slices "
            "listed by `massflow.drawpoint.slices(dp)`.",
            "`mass.requested` works by day; `mass.actual`, `mass.actual.cum` and "
            "`mass.actual.period` report what was really drawn.",
        ],
    },
    {
        "name": "extracted-marker",
        "prefix": "massflow.extractedmarker.",
        "full_name": "Extracted Marker FISH Intrinsics",
        "description": (
            "Markers that have left through a drawpoint. They form their own list with "
            "their own IDs — a marker does not stay in `massflow.marker.list` after "
            "extraction — and carry the birth day, origin, mass and fragment size that "
            "recovery accounting is built from."
        ),
        "notes": [
            "Iterate with `loop foreach local m massflow.extractedmarker.list`.",
            "`massflow.extractedmarker.mineblock` gives the block the material came "
            "from, which is what origin/destination reporting keys on.",
        ],
    },
    {
        "name": "draw-period",
        "prefix": "massflow.drawperiod.",
        "full_name": "Draw Period FISH Intrinsics",
        "description": (
            "Draw-period objects: the scripted view of the draw schedule. "
            "`massflow.drawperiod.num` matches the number of periods imported, and "
            "`massflow.period.days(i)` returns the period length in days."
        ),
        "notes": [
            "This whole family is undocumented: there is no `fish_massflow.drawperiod.*` "
            "page in the 9.7 manual. The signatures come from live enumeration and only "
            "`num` has been confirmed against a known model (59 imported periods -> 59).",
            "Semantics of the per-period accessors are NOT established. On a model with "
            "7-day periods computed to day 20, `massflow.drawperiod.find(1)` returned "
            "day.start 1 and day.end 1, and `drawpoints()` returned an empty list — "
            "neither matches the imported schedule, so do not read these as "
            "'period 1 spans days 1-7'.",
            "`massflow.drawperiod.drawrate` carries a `= flt` assignment form in its "
            "signature, but assigning to it on that model neither changed the value it "
            "returns nor raised. Treat it as unverified.",
            "Use `massflow.period`, `massflow.period.days(i)` and the drawpoint mass "
            "intrinsics for schedule accounting that has been checked.",
        ],
    },
    {
        "name": "model",
        "prefix": None,
        "full_name": "Model-Level FISH Intrinsics",
        "description": (
            "Where the solution is (day, period, period length), the mass accounting "
            "(total, per period, per drawpoint-day), the global fragmentation and "
            "mass-balance limits, and the solve-output objects."
        ),
        "notes": [
            "`massflow.markerfraglimit.lower/upper` and `massflow.massbalance.lower/upper` "
            "are the FISH side of the `massflow initialize markerfraglimit-*` and "
            "`massbalance-*` keywords; both are readable and writable.",
            "`massflow.mass.DpDay` is spelled in mixed case by the binary. FISH is "
            "case-insensitive, so the manual's `massflow.mass.dpday` resolves to it.",
        ],
    },
]


def family_of(name: str) -> str:
    for fam in FAMILIES:
        prefix = fam["prefix"]
        if prefix and name.startswith(prefix):
            return str(fam["name"])
    return "model"


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    signatures: dict[str, str] = data["signatures"]
    descriptions: dict[str, str] = data["descriptions"]

    CAT_DIR.mkdir(parents=True, exist_ok=True)

    index_items = []
    for fam in FAMILIES:
        names = sorted((n for n in signatures if family_of(n) == fam["name"]), key=str.lower)
        intrinsics = []
        for name in names:
            entry: dict[str, Any] = {"name": name, "signature": signatures[name]}
            if name in descriptions:
                entry["description"] = descriptions[name]
            else:
                entry["documented"] = False
            intrinsics.append(entry)
        undocumented = [i["name"] for i in intrinsics if i.get("documented") is False]

        doc: dict[str, Any] = {
            "name": fam["name"],
            "full_name": fam["full_name"],
            "description": fam["description"],
            "notes": fam["notes"],
            "intrinsic_count": len(intrinsics),
            "undocumented_count": len(undocumented),
            "intrinsics": intrinsics,
            "live_verification": LIVE_SOURCE,
        }
        if undocumented:
            doc["undocumented"] = undocumented
        (CAT_DIR / f"{fam['name']}.json").write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        index_items.append(
            {
                "name": fam["name"],
                "file": f"{fam['name']}.json",
                "full_name": fam["full_name"],
                "intrinsic_count": len(intrinsics),
                "undocumented_count": len(undocumented),
            }
        )

    total = len(signatures)
    undoc_total = total - len(descriptions)
    index = {
        "type": "fish_intrinsics",
        "description": (
            "MassFlow FISH intrinsic families — mine blocks, markers, extracted markers, "
            "drawpoints, draw periods, and model-level state. FISH is the only scripted "
            "access to any of them: the massflow binary exposes no MassFlow-specific "
            "Python module."
        ),
        "items": index_items,
        "usage_pattern": {
            "invocation": "fish define <name> ... end  then  [<name>]",
            "iteration": "loop foreach local mb massflow.mineblock.list ... end_loop",
            "assignment": "an intrinsic whose signature ends in ':= <type>' can be written, e.g. massflow.mineblock.frag.primary.a(mb) = 1.0",
            "examples": [
                "[massflow.mineblock.num]",
                "[massflow.drawpoint.mass.actual(massflow.drawpoint.find(1), 50)]",
                "[massflow.mass.total]",
            ],
        },
        "live_verification": (
            f"{total} massflow.* intrinsics captured from `fish list intrinsics` on live "
            f"MassFlow 9.7.47; {undoc_total} of them have no page in the 9.7 manual and "
            "are marked `documented: false`. State-grade spot checks on the tutorial "
            "model: massflow.mass.total, massflow.day, massflow.period, "
            "massflow.mineblock.fric, massflow.marker.type, "
            "massflow.extractedmarker.num, massflow.drawperiod.num (59 imported "
            "periods) and massflow.period.days(1) (7-day period) all returned values "
            "consistent with the model that produced them. The per-period "
            "massflow.drawperiod.* accessors did not, and their family file says so."
        ),
        "retired": [
            {
                "name": old,
                "replacement": new,
                "note": (
                    f"Has a page in the 9.7 manual but is gone from the binary: "
                    f"evaluating it answers '{old} is not recognized as a library "
                    f"function'. Use {new}."
                ),
            }
            for old, new in sorted(RETIRED.items())
        ],
        "official_documentation": DOC_SOURCE,
    }
    (CAT_DIR / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ref_index = json.loads(REF_INDEX.read_text(encoding="utf-8"))
    ref_index["categories"]["fish-intrinsics"] = {
        "name": "FISH Intrinsics",
        "description": (
            "MassFlow's FISH intrinsic functions, by entity: mine blocks, markers, "
            "extracted markers, drawpoints, draw periods and model-level state. The "
            "massflow binary has no MassFlow-specific Python module, so this is the only "
            "scripted access to model objects."
        ),
        "directory": "fish-intrinsics",
        "index_file": "fish-intrinsics/index.json",
        "summary": f"{total} MassFlow FISH intrinsics across 6 entity families ({undoc_total} undocumented by the vendor)",
        "usage": "fish define <name> ... end ; [<name>]",
    }
    REF_INDEX.write_text(json.dumps(ref_index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"wrote {len(FAMILIES)} families, {total} intrinsics ({undoc_total} undocumented)")
    for item in index_items:
        print(f"  {item['name']:18s} {item['intrinsic_count']:3d}  ({item['undocumented_count']} undocumented)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
