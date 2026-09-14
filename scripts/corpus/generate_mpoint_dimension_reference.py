"""Generate MPoint's ``dimension-differences`` reference from mpoint_dimensions.

The per-category flags added by the other generators answer "is this thing
available in 2D" at the point of use, which is where the question usually comes
up. This category answers the other one -- "what changes if I move this model to
2D" -- in a single place, because that answer is spread across five categories
otherwise.

Usage:
    uv run python scripts/corpus/generate_mpoint_dimension_reference.py
"""

import json
from pathlib import Path

try:
    import mpoint_dimensions as dims
except ModuleNotFoundError:  # running as a package
    from . import mpoint_dimensions as dims  # type: ignore[no-redef]

RES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
OUT = RES / "mpoint/references"
CAT_DIR = OUT / "dimension-differences"


def main() -> None:
    CAT_DIR.mkdir(parents=True, exist_ok=True)
    doc = {
        "type": "dimension_differences",
        "description": (
            "What differs between MPoint3D and MPoint2D, measured on both binaries. Everything else in "
            "this reference was probed on the 3D binary, so its 'absent' verdicts described that binary "
            "rather than the product; this category is the correction and the general answer."
        ),
        "plane": dims.PLANE,
        "identical": {
            "command_family": (
                "The 'mpoint' family is the same on both: 28 subcommands, letter for letter. The "
                "command docs therefore carry no dimension gating."
            ),
            "initialize_fields": "'mpoint initialize' offers the same 25 keywords in both.",
            "plot_item_types": "All six MPoint plot item types exist on both binaries.",
        },
        "differences": [
            {
                "category": "constitutive-models",
                "3d_only": dims.CMODELS_3D_ONLY,
                "counts": {"mpoint3d": 43, "mpoint2d": 43 - len(dims.CMODELS_3D_ONLY)},
                "listed_but_unreachable_in_2d": dims.CMODELS_LISTED_BUT_UNREACHABLE_2D,
            },
            {
                "category": "model configure",
                "3d_only": dims.CONFIGURE_3D_ONLY,
                "mpoint2d_only": dims.CONFIGURE_2D_ONLY,
                "mpoint2d_options": dims.CONFIGURE_2D_OPTIONS,
                "note": (
                    "'axisymmetry' is the 2D-only one and has no 3D counterpart. 'imass' being 3D-only "
                    "is what strands cavehoek in 2D."
                ),
            },
            {
                "category": "range-elements",
                "3d_only": dims.RANGE_3D_ONLY,
                "mpoint2d_only": dims.RANGE_2D_ONLY,
                "note": "'circle' replaces 'sphere'; there is no 2D counterpart to 'cylinder'.",
            },
            {
                "category": "plot-items",
                "3d_only_keywords": dims.PLOT_KEYWORDS_3D_ONLY,
                "mpoint2d_only_keywords": dims.PLOT_KEYWORDS_2D_ONLY,
                "mpoint2d_only_applies_to": dims.PLOT_2D_ONLY_APPLIES_TO,
                "note": dims.PLOT_KEYWORD_NOTE,
            },
            {
                "category": "boundary-conditions",
                "note": (
                    "Per-axis keywords lose their z variant: 'mpoint fix' and 'mpoint node fix' offer "
                    "velocity-x / velocity-y (and fluid-velocity-x / -y) only."
                ),
            },
        ],
        "corrections": [
            {
                "was": "'zone create2d' is absent from MPoint.",
                "is": (
                    "It is absent from MPoint3D and present on MPoint2D, which enumerates it as "
                    "'create2D'. The original verdict was about the binary, not the product."
                ),
                "recorded_in": "Batch 1, corrected by this pass",
            }
        ],
        "live_verification": dims.DIMENSION_VERIFICATION,
    }
    (CAT_DIR / "index.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    top_path = OUT / "index.json"
    top = json.loads(top_path.read_text(encoding="utf-8"))
    top.setdefault("categories", {})["dimension-differences"] = {
        "name": "MPoint3D vs MPoint2D",
        "description": (
            "Measured differences between the two MPoint binaries: constitutive models, "
            "'model configure' options, range elements, plot keywords and per-axis boundary keywords."
        ),
        "directory": "dimension-differences",
        "index_file": "dimension-differences/index.json",
        "summary": "What changes between MPoint3D and MPoint2D, probed on both",
        "usage": "Check before porting a model between the two, or when a keyword is rejected unexpectedly.",
    }
    top_path.write_text(json.dumps(top, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {CAT_DIR / 'index.json'}")
    print(f"  differences across {len(doc['differences'])} categories, {len(doc['corrections'])} correction(s)")


if __name__ == "__main__":
    main()
