"""Wire MPoint's shared references (constitutive-models + range-elements) to _common.

MPoint (MPM) assigns the same 9.0-kernel zone constitutive models and uses the
same ``range ...`` filters as FLAC3D / 3DEC, so it borrows both from the shared
``_common`` pool created in the 3DEC references PR — no duplication.

- range-elements: all 22 kernel filters; MPoint has no engine-local range items,
  so the shared element docs are reused from _common. What is NOT reused is
  FLAC's evidence: the elements are kernel-level, but what they select on
  *material points* is a separate question from what they select on zones, and
  this now carries MPoint's own counts (see RANGE_SELECTION_COUNTS).
- constitutive-models: MPoint exposes 43 models (``mpoint cmodel assign``), and
  every one of them now has a shared _common doc. material-point properties ==
  the assigned cmodel's properties (``mpoint property`` requires an assigned
  model), so no separate properties category is needed.

Evidence grade: ``state`` for both categories. Every model was assigned to live material points on
MPoint3D 9.7 and its property vocabulary read back out of the engine's own
keyword table (``mpoint property zzbogus`` error enumeration), then compared
against the _common docs. See ``LIVE_PROPERTY_COUNTS`` below.

Historical note -- this script used to emit only 38 models plus a ``note``
saying the other five "do not yet have a shared _common doc". That was true when
it was first run (2026-06-20), and went stale on 2026-08-13 when PR #78 added
those five docs to _common and lifted FLAC's index 38 -> 43. Nobody re-ran this
script, so MPoint advertised a non-existent gap for two months. _common doc
*files* are shared, but the per-engine indexes that list them are snapshots:
adding to _common does not reach an engine until its index is regenerated.
``_assert_every_model_documented`` now fails the build instead of quietly
emitting a note, so the same drift cannot recur silently.

Usage:
    uv run python scripts/corpus/wire_mpoint_common_references.py
"""

import json
from pathlib import Path
from typing import Any

try:
    import mpoint_dimensions as dims
except ModuleNotFoundError:  # running as a package
    from . import mpoint_dimensions as dims  # type: ignore[no-redef]

RES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
COMMON_CM_REL = "_common/references/constitutive-models"
COMMON_CM_DIR = RES / COMMON_CM_REL
FLAC_CM = RES / "flac/references/constitutive-models/index.json"
FLAC_RE = RES / "flac/references/range-elements/index.json"
MP_REFS = RES / "mpoint/references"

# The 43 models MPoint exposes (mpoint cmodel assign ?, MPoint 3D 9).
MPOINT_CMODELS = [
    "anisotropic",
    "burgers",
    "burgers-mohr",
    "cap-yield",
    "cap-yield-simplified",
    "cavehoek",
    "clay-and-sand",
    "columnar-basalt",
    "concrete",
    "curved-mohr-coulomb",
    "double-yield",
    "drucker-prager",
    "elastic",
    "finn",
    "hoek-brown",
    "hoek-brown-pac",
    "hydration-drucker-prager",
    "imass",
    "jones-wilkins-lee",
    "maxwell",
    "modified-cam-clay",
    "mohr-coulomb",
    "mohr-coulomb-tension",
    "munson-dawson",
    "norsand",
    "null",
    "orthotropic",
    "p2psand",
    "plastic-hardening",
    "power",
    "power-mohr",
    "power-ubiquitous",
    "soft-soil",
    "soft-soil-creep",
    "softening-ubiquitous",
    "strain-softening",
    "swell",
    "ubiquitous-anisotropic",
    "ubiquitous-joint",
    "von-mises",
    "wipp",
    "wipp-drucker",
    "wipp-salt",
]

# Size of each model's live keyword table, read back off MPoint3D 9.7 by assigning
# the model to 8 material points and enumerating `mpoint property zzbogus`.
# 'null' is absent on purpose: assigning it removes the constitutive model, so the
# engine answers "There are no constitutive models in material points."
LIVE_PROPERTY_COUNTS: dict[str, int] = {
    "anisotropic": 13,
    "burgers": 12,
    "burgers-mohr": 18,
    "cap-yield": 42,
    "cap-yield-simplified": 28,
    "cavehoek": 76,
    "clay-and-sand": 20,
    "columnar-basalt": 96,
    "concrete": 25,
    "curved-mohr-coulomb": 22,
    "double-yield": 22,
    "drucker-prager": 9,
    "elastic": 5,
    "finn": 24,
    "hoek-brown": 34,
    "hoek-brown-pac": 20,
    "hydration-drucker-prager": 18,
    "imass": 68,
    "jones-wilkins-lee": 15,
    "maxwell": 6,
    "modified-cam-clay": 15,
    "mohr-coulomb": 11,
    "mohr-coulomb-tension": 16,
    "munson-dawson": 39,
    "norsand": 38,
    "orthotropic": 18,
    "p2psand": 53,
    "plastic-hardening": 34,
    "power": 11,
    "power-mohr": 16,
    "power-ubiquitous": 29,
    "soft-soil": 25,
    "soft-soil-creep": 26,
    "softening-ubiquitous": 50,
    "strain-softening": 18,
    "swell": 35,
    "ubiquitous-anisotropic": 23,
    "ubiquitous-joint": 23,
    "von-mises": 7,
    "wipp": 15,
    "wipp-drucker": 21,
    "wipp-salt": 23,
}

# Models the keyword table lists but `mpoint cmodel assign` refuses until the
# model is configured for them ("Not configured for model X. See the MODEL CONFIG
# command."). Both are IMASS-family caving models behind one config keyword.
CONFIG_GATED = {"cavehoek": "model configure imass", "imass": "model configure imass"}

# Models whose property names are snake_case rather than the kebab-case every
# other model uses -- they carry their original research-code vocabulary.
SNAKE_CASE_MODELS = ["cavehoek", "imass"]

LIVE_VERIFICATION = {
    "grade": "state",
    "engine": "MPoint3D 9.7 (Itasca Software Subscription)",
    "date": "2026-09-14",
    "method": (
        "For each model: 'mpoint cmodel assign <model>' onto 8 generated material points, then "
        "'mpoint property zzbogus 1.0' to make the engine enumerate that model's legal property "
        "keywords. The returned sets were diffed against the _common docs."
    ),
    "result": (
        "All 43 models assign successfully (2 of them only after 'model configure imass'). "
        "Every property name in the _common docs is accepted by the engine. The diff reduced to "
        "three facts, all now reflected in the docs: 'density' is universal and was missing "
        "everywhere; double-yield spells it 'strain-tension-plastic' (not 'tensile'); and "
        "columnar-basalt's '-i' keywords expand to 1..4."
    ),
    "traps": [
        "The enumerated keyword table under-reports: 'strain-volume-plastic' is accepted by both "
        "cap-yield and double-yield but is listed by neither. Absence from the table is not proof "
        "a keyword is rejected -- only a rejection is.",
        "'tensile' vs 'tension' is not a doc typo to normalise away: cap-yield and "
        "cap-yield-simplified accept only 'strain-tensile-plastic', double-yield accepts only "
        "'strain-tension-plastic'. The engine itself is inconsistent, and each official page "
        "happens to print both spellings in different blocks.",
    ],
}

# Every model additionally accepts these, on top of its own property table.
UNIVERSAL_PROPERTIES = [
    {
        "keyword": "density",
        "description": (
            "Mass density of the material points. Present in every model's live keyword table but "
            "absent from every _common model doc, because the official per-model pages document it "
            "separately from the property table. There is no 'mpoint density' command -- unlike some "
            "other Itasca families, density on material points is set only as a model property."
        ),
        "usage": "mpoint property density <value> [range ...]",
        "verified": "state -- accepted on all 42 assignable models, MPoint3D 9.7",
    }
]


# ---------------------------------------------------------------------------
# range-elements: live evidence, measured on material points (not inherited).
# ---------------------------------------------------------------------------

# A 216-point lattice: domain -1.2..1.2 cubed, `mpoint node spacing 0.4`,
# `mpoint generate resolution 1`. One point per cell, so coordinates are exactly
# {-1.0, -0.6, -0.2, 0.2, 0.6, 1.0} in each direction and every count below is
# hand-checkable. Counts were read off `mpoint cmodel assign elastic range ...`,
# which reports how many points it matched.
RANGE_LATTICE = {
    "setup": [
        "model domain extent -1.2 1.2 -1.2 1.2 -1.2 1.2",
        "mpoint node spacing 0.4",
        "mpoint generate resolution 1",
    ],
    "points": 216,
    "coordinates_per_axis": [-1.0, -0.6, -0.2, 0.2, 0.6, 1.0],
    "point_volume": 0.064,
}

RANGE_SELECTION_COUNTS = {
    "lattice": RANGE_LATTICE,
    "counts": [
        {"range": "range position (0,0,0) (10,10,10)", "selected": 27, "expected": "3x3x3 positive octant"},
        {"range": "range position-x 0 10", "selected": 108, "expected": "half the lattice"},
        {"range": "range sphere center (0,0,0) radius 0.5", "selected": 8, "expected": "the 8 points at |p|=0.346"},
        {
            "range": "range sphere center (0,0,0) radius 0.7",
            "selected": 32,
            "expected": "8 at 0.346 + 24 at 0.663",
        },
        {
            "range": "range cylinder end-1 0 0 0 end-2 0 0 10 radius 5",
            "selected": 108,
            "expected": "z>0 half (radius covers all)",
        },
        {"range": "range plane origin (0,0,0) normal (0,0,1) above", "selected": 108, "expected": "z>0 half"},
        {
            "range": "range polygon vertices (0,0,0) (10,0,0) (10,10,0) (0,10,0)",
            "selected": 54,
            "expected": "x>0 and y>0, all z",
        },
        {
            "range": "range ellipse vertices (0,0,0) (10,0,0) (10,5,0) (0,5,0)",
            "selected": 6,
            "expected": "one (x,y) on the boundary exactly, all z -- boundary is inclusive",
        },
        {"range": "range id 42", "selected": 1, "expected": "single id"},
        {"range": "range id-list 1 5 10 15 20", "selected": 5, "expected": "five ids"},
        {"range": "range position-z 0 20 not", "selected": 108, "expected": "complement of the z>0 half"},
        {
            "range": "range position-x 0 20 position-y 0 20 union",
            "selected": 162,
            "expected": "108 + 108 - 54 overlap",
        },
        {"range": "range volume 0.06 0.07", "selected": 216, "expected": "every point's volume is 0.4^3"},
    ],
}

# Elements the engine accepts on material points that the shared docs do not list.
RANGE_EXTRA_ELEMENTS = [
    {
        "name": "volume",
        "syntax": "volume <low> <high>",
        "description": "Filter by material-point volume. Verified discriminating: 0..0.05 matched 0 "
        "points, 0.06..0.07 matched all 216, 0.07..1 matched 0, on a lattice whose point volume is "
        "exactly 0.4^3 = 0.064.",
    },
    {
        "name": "velocity",
        "syntax": "velocity <low> <high>",
        "description": "Filter by velocity magnitude. Verified discriminating at a 1e-12 threshold.",
    },
    {
        "name": "displacement",
        "syntax": "displacement <low> <high>",
        "description": "Filter by displacement magnitude. Verified discriminating at a 1e-12 threshold.",
    },
    {
        "name": "selected / deselected",
        "syntax": "selected | deselected",
        "description": "Filter by GUI selection state. Both parse and evaluate, but there is no "
        "'mpoint select' command, so selection can only be driven from the GUI.",
    },
]

# Elements that enumerate on the unified binary but never match a material point.
RANGE_INAPPLICABLE = [
    {
        "name": "by",
        "reason": "Its object-type list (ball, zone, clump, structure, ...) has no 'mpoint' entry, and "
        "'by zone' / 'by ball' on an mpoint command parse but change the result by nothing. The shared "
        "doc's example 'range position-z 0 10 by zone' is a no-op here.",
    },
    {"name": "cmodel", "reason": "Matched 0 points even with every point assigned 'elastic'; it filters zone models."},
    {"name": "radius", "reason": "Material points have no radius (a ball/pebble attribute). Always 0."},
    {"name": "name", "reason": "Always 0 on material points."},
    {"name": "group-intersection", "reason": "Always 0 on material points."},
    {"name": "index-list", "reason": "Always 0 on material points."},
]

RANGE_LIVE_VERIFICATION = {
    "grade": "state",
    "engine": "MPoint3D 9.7 (Itasca Software Subscription)",
    "date": "2026-09-14",
    "method": (
        "Every documented example was executed against a 216-point lattice with hand-checkable "
        "coordinates, and the number of material points each range matched was compared with the "
        "count computed by hand. This category had been inherited from FLAC by assumption -- the "
        "elements are kernel-level, but nothing had confirmed what they select on material points, "
        "which are not zones."
    ),
    "result": (
        "All 22 documented elements parse, and every geometric and attribute element selects exactly "
        "the predicted set. One documented example is rejected by the engine ('range fish' quoting), "
        "one is a no-op on material points ('by'), and four useful elements were undocumented."
    ),
    "notes": [
        "'range' may appear only once in a command: 'range position-x 0 20 range position-y 0 20' is "
        "rejected. Multiple elements go inside the single range phrase.",
        "'extent' is meaningful on material points rather than a no-op -- they carry a volume, so "
        "'sphere center (0,0,0) radius 0.7 extent' matched 0 where the same sphere without 'extent' "
        "matched 32.",
        "Group slots hold ONE group per point. Assigning a second group in the same slot silently "
        "replaces the first, and the replaced group then matches nothing -- the original "
        "'Group X assigned to 108 MPoints' message gives no hint that it will be superseded. "
        "Groups in different slots coexist.",
        "Group names must be quoted: 'range group sample' is rejected, 'range group \\'sample\\'' works.",
    ],
}


def _assert_every_model_documented(common_pool: set[str], by_name: dict[str, Any]) -> None:
    """Fail loudly rather than emitting a 'not documented yet' note.

    The note this replaces was correct when written and rotted silently for two
    months (see module docstring). A build failure is recoverable; a shipped doc
    that tells users a model is undocumented when it is not, is not.
    """
    missing_doc = [k for k in MPOINT_CMODELS if k not in common_pool]
    missing_idx = [k for k in MPOINT_CMODELS if k not in by_name]
    if missing_doc or missing_idx:
        raise SystemExit(
            "MPoint exposes models this corpus cannot wire:\n"
            f"  no _common doc file : {missing_doc}\n"
            f"  not in FLAC's index : {missing_idx}\n"
            "Add the doc to _common/references/constitutive-models/ (and regenerate FLAC's\n"
            "index) before re-running, or drop the model from MPOINT_CMODELS with a reason."
        )


def _doc_property_count(path: Path) -> int:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return sum(len(g.get("properties", [])) for g in doc.get("property_groups", []))


def _assert_live_matches_docs(models: list[dict[str, Any]]) -> None:
    """Every live keyword table must be the documented set plus 'density'.

    columnar-basalt is the one model documented with the manual's generic '-i'
    joint-set placeholder, so its live table is the expansion instead. Anything
    else drifting means a doc and the engine have diverged and the diff needs to
    be looked at, not silently re-baselined.
    """
    bad = []
    for m in models:
        live, doc = m.get("live_property_count"), m["documented_property_count"]
        if live is None:  # 'null' removes the model; it has no table
            continue
        if m["name"] == "columnar-basalt":
            expansion = json.loads((COMMON_CM_DIR / "columnar-basalt.json").read_text(encoding="utf-8"))
            indexed = len(expansion["index_expansion"]["indexed_keywords"])
            expected = (doc - indexed) + indexed * len(expansion["index_expansion"]["values"]) + 1
        else:
            expected = doc + 1  # 'density'
        if live != expected:
            bad.append(f"  {m['name']}: live={live} documented={doc} expected={expected}")
    if bad:
        raise SystemExit("live property tables disagree with the _common docs:\n" + "\n".join(bad))


def _wire_constitutive_models() -> int:
    flac = json.loads(FLAC_CM.read_text(encoding="utf-8"))
    by_name = {m["name"]: m for m in flac["models"]}
    common_pool = {p.stem for p in COMMON_CM_DIR.glob("*.json") if p.stem != "index"}
    _assert_every_model_documented(common_pool, by_name)

    models = []
    for key in MPOINT_CMODELS:
        m = dict(by_name[key])
        m["file"] = f"{COMMON_CM_REL}/{Path(m['file']).name}"  # ensure _common pointer
        # FLAC's index carries its own 'property_count' that does not always match
        # the doc it points at (mohr-coulomb: index 9, doc 10), so recount from the
        # _common file rather than inherit a number we cannot explain. MPoint's
        # live number is kept under a separate name: it is larger on every model,
        # by exactly the undocumented 'density'.
        m.pop("property_count", None)
        m["documented_property_count"] = _doc_property_count(COMMON_CM_DIR / f"{key}.json")
        if key in LIVE_PROPERTY_COUNTS:
            m["live_property_count"] = LIVE_PROPERTY_COUNTS[key]
        if key in CONFIG_GATED:
            m["requires"] = CONFIG_GATED[key]
        if key in SNAKE_CASE_MODELS:
            m["property_naming"] = "snake_case"
        if key in dims.CMODELS_3D_ONLY:
            m["dimension"] = "3D only -- not offered by MPoint2D"
        if key in dims.CMODELS_LISTED_BUT_UNREACHABLE_2D:
            m["dimension_caveat"] = dims.CMODELS_LISTED_BUT_UNREACHABLE_2D[key]
        models.append(m)
    _assert_live_matches_docs(models)

    cat = {
        "type": "constitutive_model_properties",
        "description": (
            "MPoint (MPM) material-point constitutive model properties — the property vocabulary for "
            "'mpoint cmodel assign' + 'mpoint property'. Shared 9.0 kernel with FLAC3D/3DEC (docs live in "
            "_common). All 43 models MPoint exposes are documented; each model's 'property_count' is the "
            "size of its keyword table as read back off the live engine."
        ),
        "usage_contexts": [
            "mpoint cmodel assign <name> [range ...]",
            "mpoint property <prop> <value> [range ...]",
        ],
        "universal_properties": UNIVERSAL_PROPERTIES,
        "models": models,
        "notes": [
            "'mpoint property' operates on whatever model is currently assigned, so assign first. "
            "Assigning 'null' removes the constitutive model entirely and any following "
            "'mpoint property' fails with 'There are no constitutive models in material points.'",
            "cavehoek and imass are listed by 'mpoint cmodel assign' but refuse to assign until the "
            "model is configured: run 'model configure imass' right after 'model new'. Their "
            "properties are snake_case (in_stren_gsi, hb_cohesion, ...), not the kebab-case every "
            "other model uses.",
            "Property availability is per-model, not global: 'mpoint property <name>' is rejected "
            "unless <name> belongs to the assigned model's table.",
        ],
        "live_verification": LIVE_VERIFICATION,
        "dimension_differences": {
            "3d_only": dims.CMODELS_3D_ONLY,
            "mpoint2d_count": len(MPOINT_CMODELS) - len(dims.CMODELS_3D_ONLY),
            "listed_but_unreachable_in_2d": dims.CMODELS_LISTED_BUT_UNREACHABLE_2D,
            "verified": dims.DIMENSION_VERIFICATION,
        },
    }
    (MP_REFS / "constitutive-models").mkdir(parents=True, exist_ok=True)
    (MP_REFS / "constitutive-models/index.json").write_text(
        json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return len(models)


def _wire_range_elements() -> int:
    flac = json.loads(FLAC_RE.read_text(encoding="utf-8"))
    # sanity: FLAC's index already points into _common (post 3DEC PR).
    common_pool = {p.stem for p in (RES / "_common/references/range-elements").glob("*.json") if p.stem != "index"}
    missing = [e["name"] for e in flac["elements"] if e["name"] not in common_pool]
    if missing:
        raise SystemExit(f"range elements missing from _common: {missing}")
    # FLAC's index carries blocks of its own live-probe evidence (keys naming
    # flac3d/the FLAC engine). Cloning those into MPoint would assert, in MPoint's
    # namespace, results that were only ever measured on FLAC3D. The 22 shared
    # element docs travel; another engine's evidence does not.
    foreign = [k for k in flac if "flac" in k.lower()]
    for key in foreign:
        del flac[key]
    if foreign:
        print(f"  dropped FLAC-only evidence blocks from MPoint's copy: {foreign}")
    # ... and replaced with MPoint's own, measured on material points.
    flac["live_verification"] = RANGE_LIVE_VERIFICATION
    flac["mpoint_selection_counts"] = RANGE_SELECTION_COUNTS
    flac["mpoint_additional_elements"] = RANGE_EXTRA_ELEMENTS
    flac["mpoint_inapplicable_elements"] = RANGE_INAPPLICABLE
    for e in flac["elements"]:
        if e["name"] in dims.RANGE_3D_ONLY:
            e["dimension"] = "3D only -- MPoint2D has no such element"
    flac["mpoint2d_only_elements"] = dims.RANGE_2D_ONLY
    flac["dimension_note"] = (
        "MPoint2D drops " + ", ".join(dims.RANGE_3D_ONLY) + " and adds 'circle'. " + dims.PLANE["note"]
    )
    (MP_REFS / "range-elements").mkdir(parents=True, exist_ok=True)
    (MP_REFS / "range-elements/index.json").write_text(
        json.dumps(flac, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return len(flac["elements"])


def main() -> None:
    n_cm = _wire_constitutive_models()
    n_re = _wire_range_elements()

    top_path = MP_REFS / "index.json"
    top = json.loads(top_path.read_text(encoding="utf-8"))
    cats = top.setdefault("categories", {})
    cats["constitutive-models"] = {
        "name": "Constitutive Models (Material Point)",
        "description": (
            "MPoint material-point constitutive material model properties — mohr-coulomb, drucker-prager, "
            "hoek-brown, cam-clay, creep models, etc. Property vocabulary for 'mpoint cmodel assign' + "
            "'mpoint property'. Shared 9.0 kernel with FLAC3D (docs via _common). Every model and its "
            "property table was read back off a live MPoint3D 9.7 engine."
        ),
        "directory": "constitutive-models",
        "index_file": "constitutive-models/index.json",
        "summary": f"{n_cm} material-point material models (shared with FLAC3D via _common; all verified live)",
        "usage": "mpoint cmodel assign <name> ; mpoint property <prop> <value> [range ...]",
    }
    cats["range-elements"] = {
        "name": "Range Elements",
        "description": (
            "Geometric and logical 'range ...' filters (cylinder, sphere, plane, position, group, id, "
            "polygon, union, not, ...) used to scope any MPoint command. Shared 9.0 kernel."
        ),
        "directory": "range-elements",
        "index_file": "range-elements/index.json",
        "summary": f"{n_re} range filter elements (shared 9.0 kernel via _common)",
        "usage": "<any command> ... range <element> <args> [union|intersect|not ...]",
    }
    top_path.write_text(json.dumps(top, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"MPoint constitutive-models registered: {n_cm} from _common (all live-verified)")
    print(f"  config-gated: {sorted(CONFIG_GATED)}  snake_case: {SNAKE_CASE_MODELS}")
    print(f"MPoint range-elements registered: {n_re} (shared _common)")


if __name__ == "__main__":
    main()
