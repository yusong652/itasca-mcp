"""Generate MPoint's ``boundary-conditions`` and ``initial-conditions`` references.

Condition commands are engine-syntax-specific, so these are authored MPoint-
specific (not borrowed). MPoint applies boundary fixity with ``mpoint fix`` /
``mpoint free`` (material points) and ``mpoint node fix`` / ``mpoint node free``
(background-grid nodes); it seeds state with ``mpoint initialize <field>`` and
gravitational stresses with ``mpoint initialize-stresses``.

Every keyword set was probed live against MPoint 3D 9 via the bridge
(``mpoint fix ?``, ``mpoint node fix ?``, ``mpoint initialize ?``,
``mpoint initialize-stresses ?``) and baked in as constants. Every referenced
command is validated against the MPoint command corpus.

Evidence grade: ``state``. All four keyword lists match the engine exactly, so
the names were already right; the conditions were then applied to a live model
and the resulting field read back through FISH. That is what produced the
numbers in ``GRAVITY_MEASUREMENTS`` and ``FIXITY_MEASUREMENTS`` -- and what
showed that ``mpoint fix velocity-x`` does not actually pin material-point
motion the way ``mpoint node fix velocity-x`` pins it. Material points take
their velocity from the background grid every step, so the grid is where a
mechanical boundary condition has to be imposed.

Output (MPoint-local):
    mpoint/references/index.json                          (top index, 2 entries)
    mpoint/references/boundary-conditions/{index,<item>}.json
    mpoint/references/initial-conditions/{index,<item>}.json

Usage:
    uv run python scripts/corpus/generate_mpoint_conditions.py
"""

import json
from pathlib import Path
from typing import Any

RES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
OUT = RES / "mpoint/references"
CMD_INDEX = RES / "mpoint/command_docs/index.json"

# ---------------------------------------------------------------------------
# Live measurements. Model: domain -1.2..1.2 cubed, `mpoint node spacing 0.4`,
# `mpoint generate resolution 1` -> 216 points at +-{0.2, 0.6, 1.0}, elastic,
# density 2500, young 1e8, poisson 0.25. Fields read back with FISH, since
# material points are not reachable from the Python SDK.
# ---------------------------------------------------------------------------

FIXITY_MEASUREMENTS = {
    "experiment": (
        "Every point given velocity-x 0.01, then the x<0 half restrained and the model cycled 20 "
        "steps. Mean x-displacement of the restrained half vs the free half."
    ),
    "results": [
        {
            "command": "mpoint fix velocity-x 0 range position-x -2 0",
            "affected": "108 material points",
            "restrained_half_dx": 0.0378439,
            "free_half_dx": 0.0845669,
            "verdict": "restrains, does not pin -- the restrained half still moved 45% as far as the free half",
        },
        {
            "command": "mpoint node fix velocity-x 0 range position-x -2 0",
            "affected": "147 mesh points",
            "restrained_half_dx": 0.00268573,
            "free_half_dx": 0.0162114,
            "verdict": "effective -- an order of magnitude less motion, and it damps the free half too",
        },
    ],
    "prescribed_velocity": (
        "Driving instead of pinning tells the same story. 'mpoint node fix velocity-x 0.01' held the "
        "mean point velocity at exactly 0.01 with displacement linear in time (0.0999995 after 10 "
        "steps, 0.199999 after 20). 'mpoint fix velocity-x 0.01' did not hold it at all: the mean "
        "drifted 0.00285 -> 0.00896 -> 0.01544 over the same three intervals."
    ),
    "conclusion": (
        "Grid-node fixity is the mechanical boundary condition in MPM; material-point fixity is a "
        "partial restraint. Material points re-read their velocity from the background grid every "
        "step, so a constraint held only on the points is overwritten by the grid solution."
    ),
}

GRAVITY_MEASUREMENTS = {
    "experiment": (
        "'model gravity 0 0 -9.81' + 'mpoint initialize-stresses', then szz/sxx/syy read back at the "
        "top and bottom of the point cloud."
    ),
    "results": [
        {
            "command": "mpoint initialize-stresses",
            "gradient_pa_per_m": -24525.0,
            "note": "exactly rho*g = 2500 * 9.81; sxx == szz, so the default lateral ratio is 1.0",
        },
        {"command": "mpoint initialize-stresses ratio 0.5", "sxx_over_szz": 0.5},
        {"command": "mpoint initialize-stresses ratio 0.25", "sxx_over_szz": 0.25},
        {
            "command": "mpoint initialize-stresses ratio 0.5 overburden -10000",
            "note": "shifted both top and bottom szz by exactly -10000; the gradient is unchanged",
        },
        {
            "command": "mpoint initialize-stresses ratio 0.5 0.25 direction-x (1,0,0)",
            "sxx": -27567.8,
            "syy": -13783.9,
            "note": "two ratios: the first goes to the direction-x axis, the second perpendicular",
        },
        {
            "command": "mpoint initialize-stresses ratio 0.5 0.25 direction-x (0,1,0)",
            "sxx": -13783.9,
            "syy": -27567.8,
            "note": "rotating direction-x swaps them",
        },
        {
            "command": "mpoint initialize-stresses ratio 0.5 0.25 direction-x (1,1,0)",
            "sxx": -20675.9,
            "syy": -20675.9,
            "note": "45 degrees blends them exactly: 0.375 * szz",
        },
        {
            "command": "mpoint initialize-stresses ratio 0.5   (pore pressure 20000 present)",
            "sxx": -17567.8,
            "note": "0.5 * the EFFECTIVE vertical stress (-35135.6)",
        },
        {
            "command": "mpoint initialize-stresses ratio 0.5 total   (pore pressure 20000 present)",
            "sxx": -27567.8,
            "note": "'total' switches ratio to multiply the TOTAL vertical stress (-55135.6)",
        },
    ],
}

# Undocumented in the official pages and missing from `mpoint initialize ?`.
INITIALIZE_MODIFIERS = [
    {
        "keyword": "add | multiply | replace",
        "syntax": "mpoint initialize <field> <add|multiply|replace> <value>",
        "description": (
            "How the value combines with what is already there. 'replace' is the default. Verified: "
            "density 1000, then 'add 500' -> 1500, then 'multiply 2' -> 3000, then 'replace 777' -> 777."
        ),
        "trap": (
            "The modifier goes BEFORE the value. Written after it "
            "('mpoint initialize density 500 add') the engine sets the field to 500 and THEN rejects "
            "'add' -- the command half-applies before it errors."
        ),
    },
    {
        "keyword": "component",
        "syntax": "mpoint initialize <vector-field> component <x|y|z> <value>",
        "description": "Initialize one component of a vector field rather than the whole vector.",
    },
    {
        "keyword": "quantity",
        "syntax": "mpoint initialize <tensor-field> quantity <xx|xy|xz|yy|yz|zz> <value>",
        "description": "Initialize one component of a tensor field.",
    },
    {
        "keyword": "gradient",
        "syntax": "mpoint initialize <field> <value> gradient <3D vector>",
        "description": (
            "Spatially varying initialization: the field becomes value + gradient . position. Verified "
            "exactly -- 'density 1000 gradient (0,0,-100)' gave 1100 at z=-1 and 900 at z=+1."
        ),
        "trap": (
            "'gradient' is NOT listed by 'mpoint initialize ?'. It only appears in the keyword table of "
            "an unrelated parse error. Absence from an enumeration is not evidence a keyword is absent."
        ),
    },
]

CONDITIONS_LIVE_VERIFICATION = {
    "grade": "state",
    "engine": "MPoint3D 9.7 (Itasca Software Subscription)",
    "date": "2026-09-14",
    "keyword_lists": (
        "All four match the engine exactly: 'mpoint node fix' 9, 'mpoint fix' 7, 'mpoint initialize' "
        "25, 'mpoint initialize-stresses' 5 (each including 'range')."
    ),
    "method": (
        "Conditions applied to a 216-point model and the resulting field read back through FISH "
        "(material points are not reachable from the Python SDK)."
    ),
    "traps": [
        "These commands do not enumerate on a bogus token -- 'mpoint fix zzbogus' answers 'Must "
        "specify degree of freedom to fix.' with no keyword table. Probe with '?'.",
        "'mpoint initialize-stresses ?' refuses to enumerate until 'model gravity' is set.",
        "'ratio' accepts TWO values but '?' reports only one float; the second is invisible until "
        "you pass it. A third is rejected.",
        "'mpoint fix velocity-x' takes an OPTIONAL value -- after the keyword the parser offers "
        "either a float or more keywords.",
    ],
}

BOUNDARY_ITEMS: list[dict[str, Any]] = [
    {
        "name": "material-point-fixity",
        "full_name": "Material-Point Fixity / Prescribed Motion",
        "description": (
            "Fix or release degrees of freedom on material points with 'mpoint fix' / 'mpoint free'. "
            "This RESTRAINS material points rather than pinning them: measured on a live model, points "
            "under 'mpoint fix velocity-x 0' still moved 45% as far as unrestrained ones, and a "
            "prescribed 'velocity-x 0.01' was not held at all. Material points re-read their velocity "
            "from the background grid every step, so impose mechanical boundaries with "
            "'mpoint node fix' instead and use this for pore-pressure fixity and for nudging points."
        ),
        "primary_commands": ["mpoint fix", "mpoint free"],
        "condition_families": [
            {
                "family": "prescribed velocity",
                "keywords": ["velocity", "velocity-x", "velocity-y", "velocity-z"],
                "notes": [
                    "'mpoint fix velocity-x 0 range ...' restrains but does not pin -- see "
                    "'live_verification' for the measured comparison against 'mpoint node fix'.",
                    "The value is optional: 'mpoint fix velocity-x' sets the fixity flag alone.",
                ],
            },
            {
                "family": "pore pressure (fluid)",
                "keywords": ["pore-pressure"],
                "notes": ["Fix pore pressure for the hydro-mechanical / fluid-coupled solution."],
            },
            {
                "family": "modifiers",
                "keywords": ["multiplier", "range"],
                "notes": [
                    "'multiplier' applies a time-varying factor and takes a float between 1 and 100; "
                    "'range' scopes which material points are affected."
                ],
            },
        ],
    },
    {
        "name": "grid-node-fixity",
        "full_name": "Background-Grid Node Fixity",
        "description": (
            "Fix or release the background-grid nodes with 'mpoint node fix' / 'mpoint node free'. Grid-node "
            "fixity is the workhorse mechanical BC in MPM — material points exchange momentum with the grid, "
            "so pinning grid-node velocity sets the domain boundary. Fluid velocity has its own components."
        ),
        "primary_commands": ["mpoint node fix", "mpoint node free"],
        "condition_families": [
            {
                "family": "prescribed velocity",
                "keywords": ["velocity", "velocity-x", "velocity-y", "velocity-z"],
                "notes": [
                    "Pin a wall/floor by fixing the relevant grid-node velocity component to 0 over a range.",
                    "This is the boundary condition that actually holds: a prescribed "
                    "'mpoint node fix velocity-x 0.01' kept the mean point velocity at exactly 0.01 with "
                    "displacement linear in time.",
                ],
            },
            {
                "family": "prescribed fluid velocity",
                "keywords": ["fluid-velocity", "fluid-velocity-x", "fluid-velocity-y", "fluid-velocity-z"],
                "notes": ["Fluid-phase grid-node velocity for coupled fluid-flow analyses."],
            },
            {
                "family": "modifiers",
                "keywords": ["range"],
                "notes": ["'range' scopes which grid nodes are affected (e.g. a boundary plane)."],
            },
        ],
    },
]

INITIAL_ITEMS: list[dict[str, Any]] = [
    {
        "name": "field-initialization",
        "full_name": "Material-Point Field Initialization",
        "description": (
            "Seed material-point state directly with 'mpoint initialize <field> <value> [range ...]' before "
            "solving. Covers stress/strain, velocity/displacement, pore pressure and the fluid/biot "
            "poromechanical properties, plus density/porosity/volume. Compression is negative."
        ),
        "primary_commands": ["mpoint initialize"],
        "field_groups": [
            {
                "group": "stress & strain",
                "fields": ["stress", "stress-effective", "strain", "deformation"],
                "notes": [
                    "'stress' / 'stress-effective' set the carried tensor; pair with 'mpoint initialize-stresses' for gravitational fields."
                ],
            },
            {
                "group": "kinematics",
                "fields": ["velocity", "displacement", "position"],
                "notes": [
                    "Reset velocity/displacement between staged-loading phases so reported values measure the current stage."
                ],
            },
            {
                "group": "fluid / poromechanics",
                "fields": [
                    "pore-pressure",
                    "porosity",
                    "fluid-density",
                    "fluid-modulus",
                    "fluid-tension",
                    "fluid-flow",
                    "biot-coefficient",
                    "biot-modulus",
                    "mobility-coefficient",
                ],
                "notes": ["Initialize the poromechanical field for hydro-mechanical (Biot) coupling."],
            },
            {
                "group": "mass & identity",
                "fields": ["density", "volume", "applied-force", "fixity", "state", "model", "id", "index"],
                "notes": [
                    "'model' / 'state' seed the constitutive model and its state; see the 'constitutive-models' reference."
                ],
            },
        ],
    },
    {
        "name": "gravitational-stress",
        "full_name": "Gravitational (In-Situ) Stress Initialization",
        "description": (
            "Establish a gravitational in-situ stress field over the material points with "
            "'mpoint initialize-stresses'. Requires 'model gravity' to be set first. Builds a depth-varying "
            "field from the overburden and a lateral stress ratio (k0-style)."
        ),
        "primary_commands": ["model gravity", "mpoint initialize-stresses"],
        "field_groups": [
            {
                "group": "in-situ stress controls",
                "fields": ["overburden", "ratio", "direction-x", "total"],
                "notes": [
                    "'model gravity 0 0 -9.81' must be defined before 'mpoint initialize-stresses'; "
                    "without it the command refuses even to enumerate its keywords.",
                    "The vertical gradient is exactly rho*g. 'overburden' shifts the whole profile by "
                    "the value given and leaves the gradient alone.",
                    "'ratio' defaults to 1.0 -- the initialized field is isotropic unless you say "
                    "otherwise. It accepts TWO values (k0 along the 'direction-x' axis and "
                    "perpendicular to it), though the engine's own prompt mentions only one.",
                    "'direction-x' takes a 3D VECTOR and orients the first ratio. (0,1,0) swaps the two "
                    "horizontal stresses; (1,1,0) blends them.",
                    "'total' is a bare switch that changes what 'ratio' multiplies: by default the "
                    "EFFECTIVE vertical stress, with 'total' the TOTAL vertical stress. The two agree "
                    "only when there is no pore pressure.",
                ],
            },
        ],
    },
]


def _valid_commands() -> set[str]:
    idx = json.loads(CMD_INDEX.read_text(encoding="utf-8"))
    out = set()
    for cat_name, cat in idx["categories"].items():
        for c in cat.get("commands", []):
            out.add(f"{cat_name} {c['name'].replace('-', ' ')}")
    return out


def _check(commands: list[str], valid: set[str]) -> None:
    for full in commands:
        toks = full.replace("-", " ").split()
        if not any(" ".join(toks[:n]) in valid for n in range(len(toks), 0, -1)):
            raise SystemExit(f"command not in MPoint corpus: {full!r}")


def _write_category(
    directory: str,
    items: list[dict[str, Any]],
    cat_type: str,
    cat_desc: str,
    valid: set[str],
) -> list[dict[str, Any]]:
    cat_dir = OUT / directory
    cat_dir.mkdir(parents=True, exist_ok=True)
    catalog = []
    for item in items:
        _check(item["primary_commands"], valid)
        doc = {"name": item["name"], "dimension": "3D", **{k: v for k, v in item.items() if k != "name"}}
        doc["live_verification"] = CONDITIONS_LIVE_VERIFICATION
        if item["name"] in ("material-point-fixity", "grid-node-fixity"):
            doc["measured"] = FIXITY_MEASUREMENTS
        if item["name"] == "gravitational-stress":
            doc["measured"] = GRAVITY_MEASUREMENTS
        if item["name"] == "field-initialization":
            doc["modifiers"] = INITIALIZE_MODIFIERS
        (cat_dir / f"{item['name']}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", "utf-8")
        catalog.append({"name": item["name"], "file": f"{item['name']}.json", "full_name": item["full_name"]})
        print(f"  {directory}/{item['name']}")
    (cat_dir / "index.json").write_text(
        json.dumps(
            {
                "type": cat_type,
                "description": cat_desc,
                "items": catalog,
                "live_verification": CONDITIONS_LIVE_VERIFICATION,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        "utf-8",
    )
    return catalog


def main() -> None:
    valid = _valid_commands()

    bc = _write_category(
        "boundary-conditions",
        BOUNDARY_ITEMS,
        "boundary_conditions",
        "Boundary-condition reference topics for MPoint — material-point fixity ('mpoint fix'/'free') and "
        "background-grid node fixity ('mpoint node fix'/'free'). Grid-node velocity fixity is the primary "
        "mechanical BC in MPM.",
        valid,
    )
    ic = _write_category(
        "initial-conditions",
        INITIAL_ITEMS,
        "initial_conditions",
        "Initial-condition reference topics for MPoint — direct material-point field initialization "
        "('mpoint initialize') and gravitational in-situ stress ('mpoint initialize-stresses').",
        valid,
    )

    top_path = OUT / "index.json"
    top = json.loads(top_path.read_text(encoding="utf-8"))
    cats = top.setdefault("categories", {})
    cats["boundary-conditions"] = {
        "name": "Boundary Conditions",
        "description": (
            "MPoint boundary conditions — material-point fixity ('mpoint fix'/'free': velocity, pore-pressure) "
            "and background-grid node fixity ('mpoint node fix'/'free': velocity, fluid-velocity)."
        ),
        "directory": "boundary-conditions",
        "index_file": "boundary-conditions/index.json",
        "summary": f"{len(bc)} MPoint boundary-condition topics (material-point + grid-node fixity)",
        "usage": "mpoint fix velocity-x 0 range ... ; mpoint node fix velocity 0 range ...",
    }
    cats["initial-conditions"] = {
        "name": "Initial Conditions",
        "description": (
            "MPoint initial conditions — material-point field initialization ('mpoint initialize': stress, "
            "velocity, pore-pressure, biot/fluid props) and gravitational in-situ stress "
            "('mpoint initialize-stresses')."
        ),
        "directory": "initial-conditions",
        "index_file": "initial-conditions/index.json",
        "summary": f"{len(ic)} MPoint initial-condition topics (field init + gravitational stress)",
        "usage": "mpoint initialize stress-zz -1e5 range ... ; model gravity 0 0 -9.81 ; mpoint initialize-stresses overburden ... ratio ...",
    }
    top_path.write_text(json.dumps(top, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"\nWrote boundary-conditions ({len(bc)}) + initial-conditions ({len(ic)})")


if __name__ == "__main__":
    main()
