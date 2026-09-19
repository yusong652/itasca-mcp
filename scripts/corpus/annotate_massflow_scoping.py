"""Make the MassFlow corpus say what is *not* reachable, and from where.

Two scoping facts were true but unstated, and both are the kind of thing a user
loses an afternoon to:

1. **The MassFlow Python API cannot see any model object.** `itasca` on the
   massflow binary is a flat module (not a package) with three kernel
   submodules — contact, fish, history — and no zone, gridpoint, ball, block,
   structure or dfn. Mine blocks, drawpoints, markers and draw periods have no
   Python binding at all; FISH is the only route. Verified live on 9.7.47:
   `hasattr(itasca, 'zone')` is False and `import itasca.zone` raises
   "'itasca' is not a package".

2. **`constitutive-models` is FLAC3D zone vocabulary, not mine-block material
   properties.** MassFlow runs the FLAC3D zone engine in-process, so
   `zone cmodel assign` and its 43 models are real — but they only bite in a
   coupled analysis. Mine-block material behaviour comes from the columns of
   the block-model import file (SolidsDen / InSituPor / MaxPor / FricAng /
   PriFragA / PriFragB / TenStrA / TenStrB / UCS / PercK1 / PercK2 / PercVMR),
   which is a different reference topic entirely.

The `zone` command family stays unborrowed. A MassFlow model is fully
buildable without a single `zone` command — the vendor's own tutorial is — so
by the engine-isolation rule it is not MassFlow's. `zone` docs remain reachable
under `software="flac"`.

Usage:
    uv run python scripts/corpus/annotate_massflow_scoping.py
"""

from __future__ import annotations

import json
from pathlib import Path

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"
PY_INDEX = RESOURCES / "massflow" / "python_sdk_docs" / "index.json"
PY_MODULES = RESOURCES / "massflow" / "python_sdk_docs" / "modules"
REF_INDEX = RESOURCES / "massflow" / "references" / "index.json"

FISH_MODULE_DESCRIPTION = (
    "Call FISH functions and read/write FISH symbols from Python. On the massflow "
    "binary this is the only Python route to model objects: mine blocks, drawpoints, "
    "markers, extracted markers and draw periods have no Python binding — see the "
    "fish-intrinsics reference for the 175 massflow.* intrinsics that do reach them."
)

HISTORY_MODULE_DESCRIPTION = (
    "Read recorded histories. Shared 9.0 kernel module; MassFlow adds no history types of its own."
)

CONTACT_MODULE_DESCRIPTION = (
    "Shared 9.0 kernel contact module. MassFlow creates no contacts of its own — "
    "this is only populated in a coupled FLAC3D analysis."
)

PY_INDEX_DESCRIPTION = (
    "MassFlow Python SDK index. The massflow binary exposes `itasca` as a flat module "
    "(not a package) with 49 core functions and three kernel submodules — contact, "
    "fish, history. There is no MassFlow Python module and no zone/gridpoint module: "
    "every model object is reached through FISH."
)

CONSTITUTIVE_DESCRIPTION = (
    "FLAC3D zone constitutive models, for coupled mechanical analysis only. MassFlow "
    "runs the FLAC3D zone engine in-process, so `zone cmodel assign` and `zone "
    "property` are available and these 43 models are real — but they do not describe "
    "mine-block material behaviour. Mine-block properties (SolidsDen, InSituPor, "
    "MaxPor, FricAng, PriFragA/B, TenStrA/B, UCS, PercK1/K2/VMR) arrive as columns of "
    "the block-model import file; see the file-formats reference. Docs shared via "
    "_common."
)

CONSTITUTIVE_USAGE = (
    "Coupled analysis only: zone cmodel assign <name> ; zone property <prop> <value> "
    "[range ...]. For mine-block material properties see 'file-formats block-model'."
)


def _patch(path: Path, fn) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    def py_index(data: dict) -> None:
        data["description"] = PY_INDEX_DESCRIPTION
        data["modules"]["fish"]["description"] = FISH_MODULE_DESCRIPTION
        data["modules"]["history"]["description"] = HISTORY_MODULE_DESCRIPTION
        data["modules"]["contact"]["description"] = CONTACT_MODULE_DESCRIPTION

    _patch(PY_INDEX, py_index)

    for module, description in (
        ("fish", FISH_MODULE_DESCRIPTION),
        ("history", HISTORY_MODULE_DESCRIPTION),
        ("contact", CONTACT_MODULE_DESCRIPTION),
    ):
        _patch(PY_MODULES / module / "module.json", lambda d, t=description: d.update(description=t))

    def ref_index(data: dict) -> None:
        cat = data["categories"]["constitutive-models"]
        cat["name"] = "Constitutive Models (Zone, coupled analysis)"
        cat["description"] = CONSTITUTIVE_DESCRIPTION
        cat["usage"] = CONSTITUTIVE_USAGE
        cat["summary"] = (
            "43 FLAC3D zone material models reachable in a coupled analysis "
            "(38 documented via _common, 5 disclosed without docs); NOT mine-block properties"
        )

    _patch(REF_INDEX, ref_index)

    print("annotated MassFlow Python index + 3 kernel modules, and constitutive-models scope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
