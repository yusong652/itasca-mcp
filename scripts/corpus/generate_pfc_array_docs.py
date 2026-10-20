"""Generate the PFC vectorized array modules that were missing from the corpus.

The PFC ``python_sdk_docs`` carried nine ``*array`` modules; a live ``dir(itasca)`` on
PFC 7.0 shows eight more PFC-family array modules that every shipped version
documents (6.0 / 7.0 / 9.0 Sphinx pages):

    ballrblockarray, cfdarray, facetarray, pebblearray, pebblerblockarray,
    rblockfacetarray, rblockrblockarray, vertexarray

Engine-family array modules that the PFC binary also exposes (``zonearray``,
``gridpointarray``, ``blockarray``, ``interface*array``, ``flow*array``) belong to
other products and are deliberately not added (engine isolation).

Source pages: ``<install>/exe64/doc/common/docproject/source/manual/scripting/python/doc/
itasca.<module>.html`` for each version. 6.0/7.0 use the old Sphinx markup
(``<dl class="function">`` with bare ``<em>`` params) and 9.0 the new one
(``<dl class="py function">`` with ``sig-param``). Both split a parameter at the
comma inside its shape braces (``data: array float{facet`` + ``dim}``); fragments
are re-joined until the braces balance. Content comes from the 7.0 page; a
function's ``availability.versions`` lists every version whose page has it.

``--live <json>`` takes ``{module: [function, ...]}`` from ``dir(itasca.<module>)``
on a running PFC 7.0 and fails if the 7.0 page disagrees with the engine.

Usage:
    uv run python scripts/corpus/generate_pfc_array_docs.py [--live pfc700_arrays.json]
"""

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

DOC_SUFFIX = "exe64/doc/common/docproject/source/manual/scripting/python/doc"
VERSION_ROOTS = {
    "6.0": Path("C:/Program Files/Itasca/PFC600") / DOC_SUFFIX,
    "7.0": Path("C:/Program Files/Itasca/PFC700") / DOC_SUFFIX,
    "9.0": Path("C:/Program Files/Itasca/ItascaSoftware900") / DOC_SUFFIX,
}
CONTENT_VERSION = "7.0"
OUT = Path(__file__).resolve().parents[2] / "src/itasca_mcp/knowledge/resources/pfc/python_sdk_docs"
REL = "pfc/python_sdk_docs/modules"

# module -> (object noun used in descriptions, module description)
MODULES = {
    "ballrblockarray": ("contact", "Vectorized NumPy array access for ball-rigid block contact attributes."),
    "cfdarray": ("cfd element", "Vectorized NumPy array access for CFD coupling elements (fluid mesh cells)."),
    "facetarray": ("facet", "Vectorized NumPy array access for wall facet attributes."),
    "pebblearray": ("pebble", "Vectorized NumPy array access for clump pebble attributes."),
    "pebblerblockarray": ("contact", "Vectorized NumPy array access for pebble-rigid block contact attributes."),
    "rblockfacetarray": ("contact", "Vectorized NumPy array access for rigid block-facet contact attributes."),
    "rblockrblockarray": ("contact", "Vectorized NumPy array access for rigid block-rigid block contact attributes."),
    "vertexarray": ("vertex", "Vectorized NumPy array access for wall vertex attributes."),
}

BASE_NOTE = (
    "Array APIs operate on all current objects of this type and return or accept NumPy "
    "arrays with the shape shown in the signature."
)
FILL_NOTE = "The destination array must already have the correct shape and dtype."
SETTER_NOTE = "Setter functions modify model state immediately."
EXTRA_NOTE = "Array extra variables must be float or vector values in the selected slot."

# Behaviour verified live on PFC 7.0 (2026-10-18, facet-membrane probe): kept to what was measured.
MODULE_NOTES = {
    "vertexarray": [
        "Rows follow the order of ids(). A corner shared by facets of the same wall is one vertex "
        "(wall create vertices stitches coincident corners); separate walls keep separate vertices "
        "(wall generate box: 6 walls, 12 facets, 24 vertices).",
    ],
    "facetarray": [
        "Rows follow the order of ids(); use vertexarray to move the facet corners.",
    ],
}
FUNCTION_NOTES = {
    ("vertexarray", "set_vel"): [
        "Vertex velocities are integrated by the engine every cycle (pos += vel * dt), persist "
        "across cycles until changed, and enter ball-facet contact kinematics; one call drives "
        "a whole deformable wall.",
        "Conveyor velocity cannot be used on a wall while its vertex velocities are active (see wall attribute).",
    ],
    ("facetarray", "set_conveyor"): [
        "Each conveyor velocity must lie in its facet's plane. A velocity with a normal "
        "component stops the script with the engine error 'The conveyor velocity must be "
        "parallel to the facet.'; this is not a Python exception that try/except can catch, "
        "and the GUI shows it as a blocking error dialog.",
    ],
    ("cfdarray", "set_porosity"): [
        "Porosity must lie in (2.2e-16, 1]; other values raise ValueError and nothing is set.",
    ],
}

# Corrections to the Itasca pages, measured on PFC 7.0 (2026-10-20, console probe): (module, function) ->
# replacement return type / parameter types, with a note saying what the page claims.
SHAPE_3_ELEMENT = "The Itasca page lists the shape as {3,element}; the arrays are (element, 3) (measured on PFC 7.0)."
VERIFIED = {
    ("cfdarray", "drag"): dict(returns="array float{element,3}", note=SHAPE_3_ELEMENT),
    ("cfdarray", "velocity"): dict(returns="array float{element,3}", note=SHAPE_3_ELEMENT),
    ("cfdarray", "pressure_gradient"): dict(returns="array float{element,3}", note=SHAPE_3_ELEMENT),
    ("cfdarray", "set_drag"): dict(params={"data": "array float{element, 3}"}, note=SHAPE_3_ELEMENT),
    ("cfdarray", "set_velocity"): dict(params={"data": "array float{element, 3}"}, note=SHAPE_3_ELEMENT),
    ("cfdarray", "set_pressure_gradient"): dict(params={"data": "array float{element, 3}"}, note=SHAPE_3_ELEMENT),
    ("pebblearray", "radius"): dict(
        returns="array float{pebble}", note="One value per pebble (the Itasca page writes {ball})."
    ),
    ("pebblearray", "fill_radius"): dict(
        params={"data": "array float{pebble}"}, note="One value per pebble (the Itasca page writes {ball})."
    ),
    ("pebblearray", "set_radius"): dict(
        params={"data": "array float{pebble}"}, note="One value per pebble (the Itasca page writes {ball})."
    ),
    ("rblockrblockarray", "indices"): dict(
        returns="array uint64{contact,2}",
        note="Returned dtype is uint64 (measured on PFC 7.0; the Itasca page writes int64).",
    ),
}

TOPICS = {
    "position": ("pos",),
    "velocity": ("vel", "velocity"),
    "force": ("force",),
    "moment": ("moment",),
    "group": ("group",),
    "extra": ("extra",),
    "id": ("ids", "indices"),
    "radius": ("radius",),
    "normal": ("normal",),
    "conveyor": ("conveyor",),
    "pressure": ("pressure",),
    "porosity": ("porosity",),
    "drag": ("drag",),
}


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _join_fragments(raw: list[str]) -> list[str]:
    """Re-join parameters Sphinx split at the comma inside ``{...}`` shapes."""
    out: list[str] = []
    for frag in raw:
        if out and out[-1].count("{") > out[-1].count("}"):
            out[-1] = f"{out[-1]}, {frag}"
        else:
            out.append(frag)
    return out


def _parse_param(p: str) -> dict[str, Any]:
    default = None
    left = p
    if "=" in p and "{" not in p.split("=", 1)[0]:
        left, default = (s.strip() for s in p.split("=", 1))
    out: dict[str, Any] = {}
    if ":" in left:
        name, typ = left.split(":", 1)
        out["name"], out["type"] = name.strip(), typ.strip()
    else:
        out["name"], out["type"] = left.strip(), "Any"
    out["required"] = default is None
    if default is not None:
        out["default"] = default
    return out


def parse_page(path: Path) -> tuple[str, dict[str, dict[str, Any]]]:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"<h1>.*?</h1>\s*<p[^>]*>(.*?)</p>", text, re.S)
    summary = _norm(_text(m.group(1))) if m else ""
    funcs: dict[str, dict[str, Any]] = {}
    for block in re.findall(r'<dl class="(?:py )?function">.*?</dl>', text, re.S):
        dt = re.search(r"<dt[^>]*>(.*?)</dt>", block, re.S)
        name_m = dt and re.search(r'class="(?:sig-name )?descname">(.*?)</', dt.group(1), re.S)
        if not name_m:
            continue
        name = _text(name_m.group(1)).strip()
        # lstrip: the 6.0/7.0 facetarray.set_conveyor page has a stray "(" before the parameter
        raw = [
            _norm(_text(p)).lstrip("(")
            for p in re.findall(r"<em(?: class=\"sig-param\")?>(.*?)</em>", dt.group(1), re.S)
        ]
        params = [_parse_param(p) for p in _join_fragments([r for r in raw if r])]
        full = _norm(_text(dt.group(1))).replace("→", "->").rstrip(".").rstrip()
        ret = full.split("->", 1)[1].strip() if "->" in full else "None"
        dd = re.search(r"<dd[^>]*>(.*?)</dd>", block, re.S)
        funcs[name] = dict(name=name, params=params, returns=ret, description=_norm(_text(dd.group(1))) if dd else "")
    return summary, funcs


def _signature(module: str, f: dict[str, Any]) -> str:
    parts = []
    for p in f["params"]:
        s = p["name"] if p["type"] == "Any" else f"{p['name']}: {p['type']}"
        parts.append(f"{s}={p['default']}" if "default" in p else s)
    return f"itasca.{module}.{f['name']}({', '.join(parts)}) -> {f['returns']}"


def _getter_for(name: str, names: set[str]) -> str | None:
    base = name.split("_", 1)[1] if "_" in name else ""
    return base if base in names else None


def _example(module: str, f: dict[str, Any], names: set[str]) -> dict[str, str]:
    name, mod = f["name"], f"it.{module}"
    if name == "create_mesh":
        return dict(
            code="import numpy as np\nimport itasca as it\n"
            "nodes = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],\n"
            "                  [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], dtype=float)\n"
            "elements = np.array([[0, 1, 2, 3, 4, 5, 6, 7]], dtype=np.int64)\n"
            "it.cfdarray.create_mesh(nodes, elements)",
            description="Create a one-element hexahedral CFD mesh (requires model configure cfd).",
        )
    if name == "set_conveyor":
        return dict(
            code="import numpy as np\nimport itasca as it\nn = it.facetarray.normal()\n"
            "t = np.cross(n, [0.0, 0.0, 1.0])  # in-plane direction (zero on facets normal to z)\n"
            "it.facetarray.set_conveyor(0.01 * t)",
            description="Set an in-plane conveyor velocity on every facet; a normal component is an engine error.",
        )
    if name == "extra":
        return dict(
            code=f"import itasca as it\nvalues = {mod}.extra(1)", description="Read extra slot 1 for every object."
        )
    if name == "set_extra":
        return dict(
            code=f"import numpy as np\nimport itasca as it\n{mod}.set_extra(1, np.zeros(len({mod}.ids())))",
            description="Write a float into extra slot 1 for every object.",
        )
    if name == "in_group":
        return dict(
            code=f"import itasca as it\nmask = {mod}.in_group('mygroup')",
            description="Boolean mask of the objects in group 'mygroup' (slot 1).",
        )
    if name == "set_group":
        return dict(
            code=f"import itasca as it\nmask = {mod}.pos()[:, 2] > 0.0\n{mod}.set_group(mask, 'upper')",
            description="Put the objects above z = 0 into group 'upper'.",
        )
    getter = _getter_for(name, names)
    if name.startswith("fill_") and getter:
        return dict(
            code=f"import numpy as np\nimport itasca as it\ndata = np.empty_like({mod}.{getter}())\n{mod}.{name}(data)",
            description="Fill a preallocated NumPy array to avoid allocating a new result array.",
        )
    if name.startswith("set_") and getter:
        return dict(
            code=f"import itasca as it\ndata = {mod}.{getter}()\n# modify data in place, then write it back\n{mod}.{name}(data)",
            description=f"Read, modify and write back {getter} for every object.",
        )
    if not f["params"]:
        return dict(code=f"import itasca as it\nvalues = {mod}.{name}()", description=f"Call {module}.{name}.")
    args = ", ".join(p["name"] for p in f["params"] if p["required"])
    return dict(code=f"import itasca as it\n{mod}.{name}({args})", description=f"Call {module}.{name}.")


def _entry(module: str, f: dict[str, Any], names: set[str], versions: list[str]) -> dict[str, Any]:
    notes = [BASE_NOTE]
    if f["name"].startswith("fill_"):
        notes.append(FILL_NOTE)
    if f["name"].startswith("set_"):
        notes.append(SETTER_NOTE)
    if "extra" in f["name"]:
        notes.append(EXTRA_NOTE)
    notes += FUNCTION_NOTES.get((module, f["name"]), [])
    fix = VERIFIED.get((module, f["name"]), {})
    if fix:
        f = dict(
            f,
            returns=fix.get("returns", f["returns"]),
            params=[dict(p, type=fix.get("params", {}).get(p["name"], p["type"])) for p in f["params"]],
        )
        notes.append(fix["note"])
    params = []
    for p in f["params"]:
        q = dict(name=p["name"], type=p["type"], required=p["required"])
        if "default" in p:
            q["default"] = p["default"]
        params.append(q)
    return {
        "name": f["name"],
        "signature": _signature(module, f),
        "description": f["description"],
        "parameters": params,
        "returns": {"type": f["returns"], "description": f["returns"]},
        "examples": [_example(module, f, names)],
        "availability": {"versions": versions},
        "notes": notes,
    }


def _keywords(module: str, names: list[str]) -> dict[str, Any]:
    paths = [f"itasca.{module}.{n}" for n in names]
    kw: dict[str, list[str]] = {f"{module} array": paths, "array api": paths}
    for topic, tokens in TOPICS.items():
        hits = [p for p, n in zip(paths, names) if any(t in n.split("_") or n == t for t in tokens)]
        if hits:
            kw[f"array {topic}"] = hits
            kw[f"{module} {topic}"] = hits
    for p, n in zip(paths, names):
        kw[f"{module} {n.replace('_', ' ')}"] = [p]
    return {
        "module": module,
        "description": f"Natural language keywords for {module} vectorized array API search",
        "keywords": kw,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", type=Path, help="dir() dump from a running PFC 7.0 to cross-check")
    args = ap.parse_args()
    live = json.loads(args.live.read_text(encoding="utf-8")) if args.live else None

    index_path = OUT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for module, (_noun, description) in MODULES.items():
        pages = {v: parse_page(root / f"itasca.{module}.html") for v, root in VERSION_ROOTS.items()}
        content = pages[CONTENT_VERSION][1]
        if live is not None and set(live[module]) != set(content):
            raise SystemExit(f"{module}: 7.0 page {sorted(set(content) ^ set(live[module]))} disagrees with the engine")
        # Union over versions: 6.0 cfdarray still has in_group/set_group, dropped from 7.0 on
        # (present in the 6.0 page and in a live 6.0 console, absent from both on 7.0 and 9.0).
        names = sorted(set().union(*(funcs for _s, funcs in pages.values())))
        entries = []
        module_versions: set[str] = set()
        for n in names:
            versions = [v for v in VERSION_ROOTS if n in pages[v][1]]
            module_versions.update(versions)
            source = pages[CONTENT_VERSION if n in content else versions[0]][1]
            entries.append(_entry(module, source[n], set(names), versions))
        versions_all = [v for v in VERSION_ROOTS if v in module_versions]
        doc: dict[str, Any] = {
            "module": f"itasca.{module}",
            "description": description,
            "import_statement": "import itasca as it",
            "versions": versions_all,
        }
        if module in MODULE_NOTES:
            doc["notes"] = MODULE_NOTES[module]
        doc["functions"] = entries
        mod_dir = OUT / "modules" / module
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / "module.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (mod_dir / "keywords.json").write_text(
            json.dumps(_keywords(module, names), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        index["modules"][module] = {
            "description": description,
            "file": f"{REL}/{module}/module.json",
            "functions": names,
            "versions": versions_all,
        }
        for n in names:
            index["quick_ref"][f"itasca.{module}.{n}"] = f"{REL}/{module}/module.json#{n}"
        print(f"{module}: {len(names)} functions, versions {versions_all}")
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
