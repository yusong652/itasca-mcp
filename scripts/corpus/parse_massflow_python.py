"""Parse MassFlow engine-exposed Python SDK HTML docs into the corpus JSON layout.

MassFlow has no proprietary Python package: its ``itasca`` is a flat module whose
only documentable sub-modules (confirmed live against the running massflow bridge
via ``dir(itasca)`` -> ModuleType filter) are the generic 9.0-kernel modules
``contact``, ``history``, ``fish`` and ``table``. ``util`` is interop-only (FLAC3D/PFC/UDEC
*_Connection bridges) and is skipped, exactly as the 3DEC parser skips it.

Source: the unified Sphinx Python API pages shipped with the Itasca Software
Subscription at ``<DOC>/itasca.<module>.html`` (the same pages
docs.itascacg.com mirrors and the same format the FLAC/3DEC python_sdk_docs were
derived from). Output matches ``3dec/python_sdk_docs/modules/<m>/{module.json,
<Class>.json}`` field-for-field; the shared ``itasca`` core skeleton (written by
generate_massflow_python_skeleton.py) is preserved.

Usage:
    uv run python scripts/corpus/parse_massflow_python.py
"""

import json
from pathlib import Path
from typing import Any

try:
    from parse_3dec_python import (
        _first_paragraph,
        _functions,
        _method_groups,
        _methods,
    )
except ModuleNotFoundError:
    from .parse_3dec_python import (  # type: ignore[no-redef]
        _first_paragraph,
        _functions,
        _method_groups,
        _methods,
    )

DOC = Path(
    "C:/Program Files/Itasca/Itasca Software Subscription/exe64/doc"
    "/common/docproject/source/manual/scripting/python/doc"
)
RESOURCES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
OUT_PY = RESOURCES / "massflow" / "python_sdk_docs"
SRC_BASE = "https://docs.itascacg.com/itasca900/common/docproject/source/manual/scripting/python/doc"
ENGINE = "massflow"

# MassFlow's engine-exposed Python modules (beyond the shared itasca core),
# confirmed against the running bridge. ``util`` is deliberately excluded.
MODULES = [
    "contact",
    "history",
    "fish",
    "table",
]


def _class_names(dotted: str) -> list[str]:
    """Class pages for a module: ``itasca.<dotted>.<Cap>.html`` (single segment)."""
    prefix = f"itasca.{dotted}."
    names = []
    for f in DOC.glob(f"itasca.{dotted}.*.html"):
        rest = f.name[len(prefix) : -len(".html")]
        if "." not in rest and rest[:1].isupper():
            names.append(rest)
    return sorted(names)


def _preserve_core() -> dict[str, Any]:
    """Reset to just the shared itasca core skeleton (so re-runs drop stale entries)."""
    existing = json.loads((OUT_PY / "index.json").read_text(encoding="utf-8"))
    core_modules = {"itasca": existing["modules"]["itasca"]}
    core_quick_ref = {k: v for k, v in existing.get("quick_ref", {}).items() if str(v).startswith("_common/")}
    return {
        "version": existing.get("version", "1.0"),
        "description": "MassFlow Python SDK documentation index for quick lookup and LLM-assisted API discovery",
        "modules": core_modules,
        "objects": {},
        "quick_ref": core_quick_ref,
    }


def main() -> None:
    index = _preserve_core()
    modules = index["modules"]
    objects = index["objects"]
    quick_ref = index["quick_ref"]

    counts = {"mod": 0, "cls": 0}
    for dotted in sorted(MODULES, key=lambda m: (m.count("."), m)):
        mod_html = (DOC / f"itasca.{dotted}.html").read_text(encoding="utf-8")
        rel_dir = Path("modules") / dotted.replace(".", "/")
        out_dir = OUT_PY / rel_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        mod_desc = _first_paragraph(mod_html)
        funcs = _functions(mod_html, dotted)
        module_doc = {
            "module": f"itasca.{dotted}",
            "description": mod_desc,
            "import_statement": "import itasca",
            "source_url": f"{SRC_BASE}/itasca.{dotted}.html",
            "functions": funcs,
        }
        (out_dir / "module.json").write_text(json.dumps(module_doc, indent=2, ensure_ascii=False) + "\n", "utf-8")

        module_file = f"{ENGINE}/python_sdk_docs/{rel_dir.as_posix()}/module.json"
        modules[dotted] = {"description": mod_desc, "file": module_file, "functions": [f["name"] for f in funcs]}
        for f in funcs:
            quick_ref[f"itasca.{dotted}.{f['name']}"] = f"{module_file}#{f['name']}"
        counts["mod"] += 1

        class_notes = []
        for class_name in _class_names(dotted):
            cls_html = (DOC / f"itasca.{dotted}.{class_name}.html").read_text(encoding="utf-8")
            methods = _methods(cls_html, class_name.lower())
            cls_desc = _first_paragraph(cls_html) or f"{class_name} object instance in itasca.{dotted}."
            note = f"Do not instantiate directly; use itasca.{dotted} module functions."
            class_doc = {
                "class": class_name,
                "description": cls_desc,
                "source_url": f"{SRC_BASE}/itasca.{dotted}.{class_name}.html",
                "note": note,
                "method_groups": _method_groups(methods),
                "methods": methods,
            }
            (out_dir / f"{class_name}.json").write_text(
                json.dumps(class_doc, indent=2, ensure_ascii=False) + "\n", "utf-8"
            )

            class_file = f"{ENGINE}/python_sdk_docs/{rel_dir.as_posix()}/{class_name}.json"
            obj_entry = {
                "description": cls_desc,
                "file": class_file,
                "note": note,
                "method_groups": class_doc["method_groups"],
            }
            bare_taken = class_name in objects and objects[class_name]["file"] != class_file
            obj_key = f"itasca.{dotted}.{class_name}" if bare_taken else class_name
            objects[obj_key] = obj_entry
            for m in methods:
                quick_ref[f"itasca.{dotted}.{class_name}.{m['name']}"] = f"{class_file}#{m['name']}"
            counts["cls"] += 1
            class_notes.append(f"{class_name}({len(methods)}){'*' if bare_taken else ''}")

        suffix = "  +  " + ", ".join(class_notes) if class_notes else ""
        print(f"  {dotted:<26} {len(funcs):>3} funcs{suffix}")

    index["modules"] = {k: modules[k] for k in sorted(modules)}
    index["objects"] = {k: objects[k] for k in sorted(objects)}
    index["quick_ref"] = {k: quick_ref[k] for k in sorted(quick_ref)}
    (OUT_PY / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", "utf-8")

    print(f"\nWrote {OUT_PY / 'index.json'}")
    print(f"  modules: {counts['mod']} (+itasca core)   object classes: {counts['cls']}   quick_ref: {len(quick_ref)}")


if __name__ == "__main__":
    main()
