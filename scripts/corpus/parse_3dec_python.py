"""Parse 3DEC engine-specific Python SDK HTML docs into the corpus JSON layout.

Source: the local Sphinx Python API pages shipped with ITASCA Software 9.0 at
``<DOC>/common/docproject/source/manual/scripting/python/doc/itasca.<module>.html``.
These are the same pages docs.itascacg.com mirrors online, and the same format
the FLAC ``python_sdk_docs`` were derived from, so the output matches
``flac/python_sdk_docs/modules/zone/{module.json,Zone.json}`` field-for-field.

For each module (dotted, e.g. ``block`` or ``block.contact``):
  - ``itasca.<dotted>.html``         -> ``modules/<path>/module.json``  (functions)
  - ``itasca.<dotted>.<Class>.html`` -> ``modules/<path>/<Class>.json`` (methods)

A module may expose several classes (``structure`` -> Beam/Cable/Geogrid/Liner/
Pile/Shell); class pages are discovered by filename (``itasca.<dotted>.<Cap>.html``,
which naturally excludes the page-less ``*Iter`` helpers). Array modules carry
functions only. ``<path>`` is the dotted name with dots turned into directory
separators (matching how FLAC lays out ``interface.element``).

Module functions and class methods are both registered in the engine index's
``quick_ref`` as full dotted paths (``itasca.block.Block.area``), which is how the
loader/search consume them. The shared ``itasca`` core skeleton is preserved.

Some bare class names collide across sub-modules (``Contact`` in both
``itasca.contact`` and ``itasca.block.contact``; ``Zone`` in ``block.zone`` and
``flowplane.zone``; ``Vertex`` in ``flowplane.vertex`` and ``dfn.vertex``).
Modules are processed shallowest-first, so the most top-level class keeps the bare
``objects`` key and the deeper one is registered under its full path key
(``itasca.flowplane.zone.Zone``). browse_python_api resolves the full-path key
when present (see _parse_api_path), so every class is reachable; quick_ref always
uses unambiguous full paths regardless.

The MODULES list is the 3DEC-specific namespace confirmed against the running
bridge (``dir(itasca)`` and recursively ``dir(itasca.<mod>)``); ``util`` is
intentionally skipped (interop *_Connection bridges, not modelling API).

Usage:
    uv run python scripts/corpus/parse_3dec_python.py
"""

import html
import json
import re
from pathlib import Path
from typing import Any

DOC = Path("C:/Program Files/Itasca/ItascaSoftware900/exe64/doc/common/docproject/source/manual/scripting/python/doc")
RESOURCES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
OUT_PY = RESOURCES / "3dec" / "python_sdk_docs"
SRC_BASE = "https://docs.itascacg.com/itasca900/common/docproject/source/manual/scripting/python/doc"

# 3DEC engine-specific Python modules (dotted), confirmed against the running
# bridge namespace. ``util`` is deliberately excluded.
MODULES = [
    # block family
    "block",
    "block.contact",
    "block.contactarray",
    "block.face",
    "block.facearray",
    "block.gridpoint",
    "block.gridpointarray",
    "block.subcontact",
    "block.subcontactarray",
    "block.zone",
    "block.zonearray",
    "blockarray",
    # flow knots / flow planes (hydro-mechanical coupling)
    "flowknot",
    "flowknotarray",
    "flowplane",
    "flowplane.vertex",
    "flowplane.vertexarray",
    "flowplane.zone",
    "flowplane.zonearray",
    "flowplanearray",
    # structural elements
    "structure",
    "structure.link",
    "structure.node",
    # discrete fracture network
    "dfn",
    "dfn.fracture",
    "dfn.inter",
    "dfn.setinter",
    "dfn.template",
    "dfn.vertex",
    # misc engine modules
    "contact",
    "history",
    "fish",
]


def _text(fragment: str) -> str:
    """Strip tags and unescape entities from an HTML fragment."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _first_paragraph(html_text: str) -> str:
    """The first <p> following the <h1> (the module/class summary line)."""
    m = re.search(r"<h1>.*?</h1>\s*<p[^>]*>(.*?)</p>", html_text, re.S)
    return _norm(_text(m.group(1))) if m else ""


def _parse_param(raw: str) -> dict[str, Any]:
    """Parse one ``sig-param`` like ``point: vec3`` or ``search_start=None``."""
    p = _norm(raw)
    out: dict[str, Any] = {}
    default = None
    if "=" in p:
        left, default = p.split("=", 1)
        default = default.strip()
    else:
        left = p
    if ":" in left:
        name, typ = left.split(":", 1)
        out["name"] = name.strip()
        out["type"] = typ.strip()
    else:
        out["name"] = left.strip()
    out["required"] = default is None
    if default is not None:
        out["default"] = default
    return out


def mark_bracketed_optional(signature: str, params: list[dict[str, Any]]) -> None:
    """Params the signature writes inside [...] ('group([slot: str or int])') are optional.

    Neither the Sphinx sig-param markup nor a split on commas sees the brackets, so
    such params came out ``required: true``.
    """
    for p in params:
        name = p.get("name")
        if name and p.get("required") and re.search(r"\[[^\]]*\b" + re.escape(name) + r"\b", signature):
            p["required"] = False


def _parse_sig_block(block: str) -> dict[str, Any] | None:
    """Parse one ``<dl class="py function|method">`` block into an entry dict."""
    dt = re.search(r"<dt[^>]*>(.*?)</dt>", block, re.S)
    if not dt:
        return None
    dt_inner = dt.group(1)

    name_m = re.search(r'sig-name descname">(.*?)</span>\s*<span class="sig-paren"', dt_inner, re.S)
    if not name_m:
        return None
    name = _text(name_m.group(1)).strip()

    params = [_parse_param(_text(p)) for p in re.findall(r'<em class="sig-param">(.*?)</em>', dt_inner, re.S)]
    params = [p for p in params if p.get("name")]

    full = _norm(_text(dt_inner)).replace("→", "->")
    # 3DEC's Sphinx return typehints carry a trailing period ("int.", "Block
    # object."); drop it so signatures/return types match the FLAC corpus style.
    if full.endswith("."):
        full = full[:-1].rstrip()
    mark_bracketed_optional(full, params)
    ret = ""
    if "->" in full:
        ret = full.split("->", 1)[1].strip()

    dd = re.search(r"<dd[^>]*>(.*?)</dd>", block, re.S)
    description = _norm(_text(dd.group(1))) if dd else ""

    entry: dict[str, Any] = {"name": name, "_sig_text": full, "description": description}
    if params:
        entry["parameters"] = params
    if ret:
        entry["returns"] = {"type": ret}
    return entry


def _ordered(entry: dict[str, Any]) -> dict[str, Any]:
    """Reorder keys to match the FLAC corpus: name, signature, description, ..."""
    ordered: dict[str, Any] = {"name": entry["name"], "signature": entry["signature"]}
    if entry.get("description"):
        ordered["description"] = entry["description"]
    if "parameters" in entry:
        ordered["parameters"] = entry["parameters"]
    if "returns" in entry:
        ordered["returns"] = entry["returns"]
    return ordered


def _functions(html_text: str, dotted: str) -> list[dict[str, Any]]:
    out = []
    for block in re.findall(r'<dl class="py function">.*?</dl>', html_text, re.S):
        entry = _parse_sig_block(block)
        if not entry:
            continue
        sig = entry.pop("_sig_text")
        if not sig.startswith("itasca."):  # dt text already carries the module prefix
            sig = f"itasca.{dotted}.{sig}"
        entry["signature"] = sig
        out.append(_ordered(entry))
    return out


def _methods(html_text: str, inst: str) -> list[dict[str, Any]]:
    out = []
    for block in re.findall(r'<dl class="py method">.*?</dl>', html_text, re.S):
        entry = _parse_sig_block(block)
        if not entry:
            continue
        entry["signature"] = f"{inst}.{entry.pop('_sig_text')}"
        out.append(_ordered(entry))
    return out


def _group_key(name: str) -> str:
    """Semantic group: drop a leading ``set_``, then the prefix before ``_``."""
    n = name[4:] if name.startswith("set_") else name
    return n.split("_")[0]


def _method_groups(methods: list[dict[str, Any]]) -> dict[str, str]:
    groups: dict[str, list[str]] = {}
    for m in methods:
        groups.setdefault(_group_key(m["name"]), []).append(m["name"])
    return {k: ", ".join(sorted(v)) for k, v in sorted(groups.items())}


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
        "description": "3DEC Python SDK documentation index for quick lookup and LLM-assisted API discovery",
        "modules": core_modules,
        "objects": {},
        "quick_ref": core_quick_ref,
    }


def main() -> None:
    index = _preserve_core()
    modules = index["modules"]
    objects = index["objects"]
    quick_ref = index["quick_ref"]

    # Shallowest-first: a top-level class keeps the bare ``objects`` key; deeper
    # collisions fall back to a full-path key.
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

        module_file = f"3dec/python_sdk_docs/{rel_dir.as_posix()}/module.json"
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

            class_file = f"3dec/python_sdk_docs/{rel_dir.as_posix()}/{class_name}.json"
            obj_entry = {
                "description": cls_desc,
                "file": class_file,
                "note": note,
                "method_groups": class_doc["method_groups"],
            }
            # First (shallowest) wins the bare key; later collisions go full-path.
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
    print("  ('*' = bare class-name collision, registered under its full-path key)")


if __name__ == "__main__":
    main()
