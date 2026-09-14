"""Wire MPoint's shared references (constitutive-models + range-elements) to _common.

MPoint (MPM) assigns the same 9.0-kernel zone constitutive models and uses the
same ``range ...`` filters as FLAC3D / 3DEC, so it borrows both from the shared
``_common`` pool created in the 3DEC references PR — no duplication.

- range-elements: all 22 kernel filters; MPoint has no engine-local range items,
  so it clones FLAC's (already _common-pointing) index verbatim.
- constitutive-models: MPoint exposes 43 models (``mpoint cmodel assign``), and
  every one of them now has a shared _common doc. material-point properties ==
  the assigned cmodel's properties (``mpoint property`` requires an assigned
  model), so no separate properties category is needed.

Evidence grade: ``state``. Every model was assigned to live material points on
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
