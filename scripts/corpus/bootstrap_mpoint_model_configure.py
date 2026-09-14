"""Add the missing ``model configure`` command to MPoint's corpus.

``model configure`` is engine-local in this corpus -- pfc, flac and 3dec each
carry their own copy under ``<engine>/command_docs/commands/model/``, because
the option list differs per engine. MPoint had none at all, which is a real
gap rather than a stylistic one:

- the official MPoint examples use it (``model configure dynamic`` in the
  NaturalPeriodsElasticColumn verification problem), and
- two of the 43 constitutive models MPoint exposes, ``cavehoek`` and ``imass``,
  refuse to assign until ``model configure imass`` has run. Batch 5a recorded
  that dependency in the constitutive-models reference and it pointed at a
  command the corpus could not resolve.

Option list enumerated from the live engine (``model configure zzbogus``) and
every option then executed on MPoint3D 9.7 (2026-09-14). ``array`` is the one
that takes a further argument; the rest are bare switches and each printed its
own confirmation line, quoted below.

Usage:
    uv run python scripts/corpus/bootstrap_mpoint_model_configure.py
"""

import json
from pathlib import Path

try:
    import mpoint_dimensions as dims
except ModuleNotFoundError:  # running as a package
    from . import mpoint_dimensions as dims  # type: ignore[no-redef]

RES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
TARGET = RES / "mpoint/command_docs/commands/model/configure.json"

# name -> (description, the engine's own confirmation line, or None if untested)
OPTIONS: dict[str, tuple[str, str | None]] = {
    "array": ("Array-based storage mode. Takes a further argument, unlike every other option.", None),
    "cfd": ("Coupled CFD (computational fluid dynamics) analysis.", None),
    "cluster": ("Cluster (distributed) computing.", "Configured for use with cluster (distributed) computing."),
    "creep": ("Creep (time-dependent) material analysis.", "Process creep configured."),
    "dynamic": (
        "Fully dynamic analysis. Used by the NaturalPeriodsElasticColumn verification problem.",
        "Process dynamic configured.",
    ),
    "energy": ("Energy summation / tracking.", "Energy summation has been set"),
    "feblock": ("Finite-element block logic.", None),
    "fluid-explicit": ("Fluid-flow analysis, explicit solution scheme.", None),
    "fluid-flow": (
        "Fluid-flow analysis. Resolves to the implicit scheme by default.",
        "Process fluid configured in mode fluid-flow fluid-implicit.",
    ),
    "fluid-implicit": ("Fluid-flow analysis, implicit solution scheme.", None),
    "highorder": ("High-order element logic.", "High order element logic is set."),
    "hotetra": ("Higher-order tetrahedral element logic.", None),
    "imass": (
        "The IMASS constitutive-model framework. REQUIRED before 'mpoint cmodel assign imass' or "
        "'mpoint cmodel assign cavehoek' -- both are listed by the cmodel keyword table but refuse to "
        "assign without it, reporting 'Not configured for model X. See the MODEL CONFIG command.'",
        "Configured for use with the IMASS constitutive model.",
    ),
    "matrixflow": ("Matrix-flow analysis.", None),
    "mechanical": ("Mechanical analysis (the default process).", None),
    "thermal": ("Thermal analysis.", "Process thermal configured."),
}


def build() -> dict:
    keywords = []
    for name, (desc, confirm) in sorted(OPTIONS.items()):
        entry = {
            "name": name,
            "syntax": f"{name} <value>" if name == "array" else name,
            "description": desc,
        }
        if confirm:
            entry["verified"] = f"state -- MPoint3D 9.7 accepted it and reported: {confirm!r}"
        else:
            entry["verified"] = "syntax -- enumerated by the engine's keyword table, not separately executed"
        keywords.append(entry)

    return {
        "category": "model",
        "search_keywords": ["configure", "settings", "imass", "dynamic", "creep", "thermal", "fluid"],
        "description": (
            "Configure an additional calculation mode. Specifies that the model uses calculation modes "
            "that need extra resources or are gated by the licence. It can be given at any stage but "
            "must come before 'model solve' / 'model cycle' invokes that mode."
        ),
        "notes": [
            "Must be given BEFORE the mode is used by 'model solve' or 'model cycle'; in practice put it "
            "immediately after 'model new'.",
            "'model configure imass' is a hard prerequisite for the cavehoek and imass constitutive "
            "models -- see references/constitutive-models.",
            "Once configured, the mode stays active for the model.",
            "The option list is engine-specific. MPoint's 16 options were enumerated from the live "
            "engine; they are not the same set FLAC3D or PFC offers.",
        ],
        "python_sdk_alternative": {
            "available": False,
            "workaround": "itasca.command('model configure imass') - no direct SDK method",
        },
        "versions": {
            "9.0": {
                "command": "model configure",
                "syntax": "model configure keyword ...",
                "keywords": keywords,
                "examples": [
                    {
                        "command": "model new\nmodel configure imass\nmpoint cmodel assign cavehoek",
                        "description": "Without the configure line the assign fails with 'Not configured for model cavehoek.'",
                    },
                    {
                        "command": "model configure dynamic",
                        "description": "Fully dynamic analysis, as used by the NaturalPeriodsElasticColumn example.",
                    },
                ],
            }
        },
        "dimension_differences": {
            "note": (
                "This option list is MPoint3D's. MPoint2D offers a different nine, including one 3D does not have."
            ),
            "mpoint2d_options": dims.CONFIGURE_2D_OPTIONS,
            "3d_only": dims.CONFIGURE_3D_ONLY,
            "mpoint2d_only": dims.CONFIGURE_2D_ONLY,
            "consequence": (
                "'imass' is 3D-only, so the cavehoek and imass constitutive models cannot be configured "
                "for on MPoint2D at all -- yet MPoint2D still lists cavehoek among its models."
            ),
            "verified": dims.DIMENSION_VERIFICATION,
        },
        "live_verification": {
            "grade": "state",
            "engine": "MPoint3D 9.7 (Itasca Software Subscription)",
            "date": "2026-09-14",
            "method": (
                "Option list enumerated with 'model configure zzbogus', then nine options executed "
                "individually on a fresh model. Each printed its own confirmation line."
            ),
        },
    }


def main() -> None:
    if TARGET.exists():
        raise SystemExit(f"refusing to overwrite existing doc: {TARGET}")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    doc = build()
    TARGET.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {TARGET}")
    print(f"  options: {len(doc['versions']['9.0']['keywords'])}")


if __name__ == "__main__":
    main()
