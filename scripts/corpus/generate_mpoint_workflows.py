"""Generate MPoint's ``workflows`` reference: complete model recipes, run end to end.

Batch 6 of the MPoint verification campaign. The other reference categories
document vocabulary -- which keywords exist, what they take, what they do. This
one documents *order*: the sequence of commands that produces a working model,
which is what someone actually needs and what no single command page states.

Every workflow here was executed on live MPoint3D 9.7 (2026-09-14) and its
result read back, not transcribed from a manual. Where a step exists only
because leaving it out breaks the model, that is recorded as ``why``, because a
recipe whose steps look optional invites people to drop them.

Usage:
    uv run python scripts/corpus/generate_mpoint_workflows.py
"""

import json
from pathlib import Path
from typing import Any

try:
    import mpoint_dimensions as dims
except ModuleNotFoundError:  # running as a package
    from . import mpoint_dimensions as dims  # type: ignore[no-redef]

RES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
OUT = RES / "mpoint/references"
CAT_DIR = OUT / "workflows"
CMD_INDEX = RES / "mpoint/command_docs/index.json"

WORKFLOWS: list[dict[str, Any]] = [
    {
        "name": "quickstart-zone-import",
        "full_name": "Build via zones, convert to material points (official QuickStart)",
        "description": (
            "The workflow the official MPoint QuickStart teaches: author the geometry with the FLAC3D "
            "'zone' family, give it a constitutive model and properties, then convert the whole thing to "
            "material points. Easiest route for primitive shapes, because 'zone create brick' has no "
            "material-point equivalent."
        ),
        "steps": [
            {"command": "model new", "note": "also resets any 'model configure' modes"},
            {
                "command": "model gravity 9.81",
                "why": "The scalar form is legal and means (0, 0, -9.81) -- magnitude, direction down.",
            },
            {
                "command": "model large-strain on",
                "why": (
                    "Not optional. MPM cycling refuses to start without an explicit strain mode: "
                    "'Strain calculation mode is not specified.' Large-strain is the mode MPM is for."
                ),
            },
            {"command": "model domain extent (-5 5) (-5 5) (0 2.5)"},
            {
                "command": "zone create brick point 0 (-1,-1,0) point 1 (1,-1,0) point 2 (-1,1,0) point 3 (-1,-1,2) size 10 10 10",
                "why": "1000 zones -- exactly the demo-mode ceiling. 1100 fails with a licence error.",
            },
            {"command": "zone cmodel assign mohr-coulomb"},
            {
                "command": "zone property density 1500 young 100e6 poisson 0.25 friction 35 cohesion 500 tension 500",
                "why": (
                    "The console echoes a confirmation line for young/poisson/friction/cohesion/tension "
                    "but NOT for density, though density is set (zone.density reads back 1500). Do not "
                    "audit this command by counting confirmation lines."
                ),
            },
            {"command": "zone initialize-stresses"},
            {"command": "mpoint node spacing 0.2"},
            {
                "command": "mpoint import from-zones",
                "why": (
                    "Converts and then DELETES the zones: 1000 zones -> 8000 material points, 0 zones "
                    "left. Pass 'keep' to retain them. Stress, properties and constitutive model all "
                    "carry across."
                ),
            },
            {
                "command": "mpoint node fix velocity range position-z 0",
                "why": (
                    "Grid-node fixity, not material-point fixity, is the mechanical boundary condition "
                    "in MPM. Fixed 2601 mesh points = the whole 51x51 z=0 plane."
                ),
            },
            {"command": "model cycle 30000"},
        ],
        "verified": {
            "engine": "MPoint3D 9.7",
            "date": "2026-09-14",
            "runtime_seconds": 429,
            "result": (
                "8000 material points, 0 zones. The 2x2x2 m block slumped from z 0..2 to z 0.038..1.381 "
                "-- 1.61 m of maximum displacement, which is the large-deformation regime MPM exists "
                "for. Maximum velocity fell to 5.4e-06, so the solution had settled."
            ),
        },
    },
    {
        "name": "zone-free-native",
        "full_name": "Build with material points only, no zones",
        "description": (
            "MPM does not need the zone family. This path uses only 'mpoint' commands and leaves "
            "zone.count() at zero throughout. Prefer it when the geometry can be described by a range, "
            "and reach for zones only when you need a primitive shape they can author and ranges cannot."
        ),
        "steps": [
            {"command": "model new"},
            {"command": "model large-strain on"},
            {"command": "model domain extent -1.2 1.2 -1.2 1.2 -1.2 1.2"},
            {"command": "mpoint node spacing 0.4"},
            {
                "command": "mpoint generate resolution 1 range position-x -0.4 0.4 position-y -0.4 0.4 position-z -0.4 0.4",
                "why": "'resolution' is material points per node spacing per axis; the default is 2, so 'resolution 1' is one point per cell.",
            },
            {
                "command": "mpoint cmodel assign elastic",
                "why": "Must precede 'mpoint property' -- without a model the engine answers 'There are no constitutive models in material points.'",
            },
            {
                "command": "mpoint property density 2500 young 1e8 poisson 0.25",
                "why": "'density' is a model property here. There is no 'mpoint density' command.",
            },
            {"command": "model gravity 0 0 -9.81"},
            {"command": "mpoint initialize-stresses"},
            {"command": "mpoint node fix velocity range position-z 0"},
            {"command": "model cycle 300"},
        ],
        "verified": {
            "engine": "MPoint3D 9.7",
            "date": "2026-09-14",
            "result": "Cycles and settles with zone.count() == 0 at every step.",
        },
    },
    {
        "name": "zone-mpoint-coupling",
        "full_name": "Coupled FLAC3D zones + MPM material points",
        "description": (
            "Zones and material points can live in one model and be solved together -- a continuum "
            "foundation carrying a large-deformation MPM body, say. The coupling is NOT automatic: "
            "'mpoint hybrid-points' registers the zone gridpoints as hybrid (coupled) points, and "
            "without it the two systems cycle side by side and exchange nothing."
        ),
        "steps": [
            {"command": "model new"},
            {"command": "model large-strain on"},
            {"command": "model domain extent (-1 5) (-1 2) (0 8)"},
            {
                "command": "zone create brick size 8 4 8 point 0 (0,0,0) point 1 (4,0,0) point 2 (0,1,0) point 3 (0,0,2)",
                "why": "The continuum part. Stays as zones.",
            },
            {"command": "zone cmodel assign elastic"},
            {"command": "zone property density 2000 young 2e7 poisson 0.25"},
            {
                "command": "zone create brick size 8 4 8 point 0 (0,0,2) point 1 (4,0,2) point 2 (0,1,2) point 3 (0,0,4) group 'mpm'",
                "why": "The part that becomes material points. Group it so the import can select it.",
            },
            {"command": "zone cmodel assign elastic range group 'mpm'"},
            {"command": "zone property density 2000 young 2e7 poisson 0.25 range group 'mpm'"},
            {"command": "mpoint node spacing 0.5"},
            {
                "command": "mpoint import from-zones range group 'mpm'",
                "why": "Ranged import: only the grouped zones are converted, the rest stay zones.",
            },
            {
                "command": "mpoint hybrid-points",
                "why": (
                    "THE coupling step. Without it the MPM body's weight does not reach the zones at "
                    "all -- measured settlement was identical to eight significant figures with the "
                    "body present and absent. With it, settlement went from -0.000797 to -0.00469."
                ),
            },
            {"command": "model gravity 0 0 -9.81"},
            {"command": "zone initialize-stresses"},
            {"command": "zone gridpoint fix velocity range position-z 0"},
            {"command": "mpoint node fix velocity range position-z 0"},
            {"command": "model cycle 400"},
        ],
        "verified": {
            "engine": "MPoint3D 9.7",
            "date": "2026-09-14",
            "result": (
                "Three-way comparison of the foundation's top settlement: bare foundation -0.000797; "
                "MPM body resting on it but uncoupled -0.000797 (identical); with 'mpoint hybrid-points' "
                "-0.00469. Both systems advance in one 'model cycle'."
            ),
        },
    },
]

DEMO_LIMITS = {
    "description": (
        "Measured on an unlicensed MPoint3D 9.7 (the host holds only a PFC3D licence, so MPoint runs in "
        "demo mode). Over the limit the engine reports 'Failed to find a valid license(s)!', which reads "
        "as a configuration problem rather than a size problem."
    ),
    "zones": {
        "limit": 1000,
        "evidence": "1000 created fine; 1100, 8000 and 18000 each failed. Same ceiling as FLAC3D demo.",
    },
    "material_points": {
        "limit": "about 8000",
        "evidence": (
            "8000 passed four times out of four and ran the full 30000-cycle QuickStart; 8400, 8800, "
            "9600, 10648 and above failed. The ceiling applies at 'mpoint cmodel assign', not at "
            "'mpoint generate' -- 125000 points generate without complaint and only fail when a model "
            "is assigned to them."
        ),
        "not_the_background_grid": (
            "8000 points passed with 9261, 68921 and 9801 background nodes, so the grid size is not what is counted."
        ),
        "caveat": (
            "Counts obtained by deleting points down from a larger generation behaved erratically "
            "(8100 alive passed while 8001 alive failed), so do not rely on 'mpoint delete' to bring a "
            "model back under the ceiling. Generate the size you want."
        ),
    },
    "note": (
        "Coupled zone + MPM analysis fits comfortably inside both limits: the verified coupling example "
        "uses 256 zones and 2048 material points."
    ),
    "by_dimension": dims.DEMO_LIMITS_BY_DIMENSION,
}


def _valid_commands() -> set[str]:
    idx = json.loads(CMD_INDEX.read_text(encoding="utf-8"))
    out: set[str] = set()
    for fam, info in idx["categories"].items():
        prefix = info.get("command_prefix", fam)
        for c in info["commands"]:
            out.add(f"{prefix} {c['name']}".strip())
            out.add(f"{prefix} {str(c['name']).replace('-', ' ')}".strip())
    return out


def _check_mpoint_steps(valid: set[str]) -> None:
    """Every 'mpoint ...' / 'model ...' step must resolve in MPoint's own corpus.

    'zone ...' steps deliberately do not: the zone family belongs to FLAC and is
    documented under software='flac'. The workflows say so rather than smuggling
    another engine's family into this one.
    """
    missing = []
    for wf in WORKFLOWS:
        for step in wf["steps"]:
            toks = str(step["command"]).split()
            if toks[0] not in ("mpoint", "model"):
                continue
            if not any(" ".join(toks[:n]) in valid for n in range(min(3, len(toks)), 0, -1)):
                missing.append(f"{wf['name']}: {step['command']}")
    if missing:
        raise SystemExit("workflow steps not resolvable in the MPoint corpus:\n  " + "\n  ".join(missing))


def main() -> None:
    valid = _valid_commands()
    _check_mpoint_steps(valid)
    CAT_DIR.mkdir(parents=True, exist_ok=True)

    catalog = []
    for wf in WORKFLOWS:
        doc = {"dimension": "3D", **wf}
        (CAT_DIR / f"{wf['name']}.json").write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        catalog.append(
            {
                "name": wf["name"],
                "file": f"{wf['name']}.json",
                "full_name": wf["full_name"],
                "steps": len(wf["steps"]),
            }
        )
        print(f"  workflows/{wf['name']:<24} {len(wf['steps'])} steps")

    (CAT_DIR / "index.json").write_text(
        json.dumps(
            {
                "type": "workflows",
                "description": (
                    "Complete MPoint model recipes, each executed end to end on a live engine. Command "
                    "pages give vocabulary; these give order, and record the steps that only look "
                    "optional."
                ),
                "usage_context": "Follow a workflow top to bottom; every step was run in this sequence.",
                "items": catalog,
                "demo_mode_limits": DEMO_LIMITS,
                "notes": [
                    "The 'zone ...' steps in these workflows belong to the FLAC3D zone family, which "
                    "runs on the MPoint binary but is documented under software='flac'.",
                    "'model large-strain on' is required before any MPM cycling; without an explicit "
                    "strain mode the engine refuses to cycle.",
                    "Grid-node fixity ('mpoint node fix') is the mechanical boundary condition in MPM; "
                    "material-point fixity restrains but does not pin.",
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    top_path = OUT / "index.json"
    top = json.loads(top_path.read_text(encoding="utf-8"))
    top.setdefault("categories", {})["workflows"] = {
        "name": "Workflows",
        "description": (
            "End-to-end MPoint model recipes verified on a live engine: the official zone-import "
            "QuickStart, the zone-free native path, and coupled zone + MPM analysis."
        ),
        "directory": "workflows",
        "index_file": "workflows/index.json",
        "summary": f"{len(catalog)} verified end-to-end workflows, plus measured demo-mode limits",
        "usage": "Follow a workflow's steps in order; each was executed in this sequence.",
    }
    top_path.write_text(json.dumps(top, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote workflows ({len(catalog)}) + registered in the references index")


if __name__ == "__main__":
    main()
