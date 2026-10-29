"""Generate the MassFlow Python SDK skeleton index.

MassFlow's engine-specific Python modules are hand-authored docs deferred to a
later pass. For now we ship a minimal skeleton so itasca_query_doc(source='python_api') /
itasca_browse_doc(source='python_api') answer software="massflow" without erroring: it exposes
only the shared `itasca` core module, which already lives once in _common/ and
is reused verbatim (same as FLAC/3DEC/MPoint skeletons do).

Usage:
    uv run python scripts/corpus/generate_massflow_python_skeleton.py
"""

import json
import shutil
from pathlib import Path

RESOURCES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
FLAC_PY = RESOURCES / "flac" / "python_sdk_docs"
OUT_PY = RESOURCES / "massflow" / "python_sdk_docs"


def main() -> None:
    flac_index = json.loads((FLAC_PY / "index.json").read_text(encoding="utf-8"))

    itasca_module = flac_index["modules"]["itasca"]
    assert str(itasca_module["file"]).startswith("_common/"), "itasca core module should live in _common/"

    quick_ref = {
        k: v
        for k, v in flac_index.get("quick_ref", {}).items()
        if k.startswith("itasca.") and str(v).startswith("_common/")
    }

    index = {
        "version": "1.0",
        "description": "MassFlow Python SDK documentation index (skeleton: shared itasca core only; engine-specific modules deferred)",
        "modules": {"itasca": itasca_module},
        "objects": {},
        "quick_ref": quick_ref,
    }

    OUT_PY.mkdir(parents=True, exist_ok=True)
    (OUT_PY / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    shutil.copyfile(FLAC_PY / "itasca_keywords.json", OUT_PY / "itasca_keywords.json")

    print(f"Wrote {OUT_PY / 'index.json'}")
    print(f"  itasca functions: {len(itasca_module.get('functions', []))}")
    print(f"  quick_ref itasca.* (shared): {len(quick_ref)}")
    print("Copied itasca_keywords.json")


if __name__ == "__main__":
    main()
