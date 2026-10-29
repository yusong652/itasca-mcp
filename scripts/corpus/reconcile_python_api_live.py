"""Reconcile the Python SDK corpus against live engine introspection.

A sweep of 20 console builds (PFC/FLAC/3DEC/MPoint, 6.0 - 9.7, 2D and 3D) found
own-product Python API the corpus did not document. Each build dumped
``itasca.*`` recursively (modules, functions, classes, methods and their
``__doc__``) to ``api_<tag>.json``; this script reads those dumps and, per engine:

  A. adds modules that are live but undocumented (``structure``, ``dfn``,
     ``ball.thermal``, ``data`` ...), with their classes;
  B. adds members that are live but missing from an already documented module or
     object (FLAC 2D interface ``length``, PFC 2D ``rotation``, 7.0-only names);
  C. adds ``availability.versions`` to existing entries that are absent from
     some of the engine's versions and carry no availability marker yet.

Content comes from the ITASCA Sphinx page (newest install that has it, parsed
with the 3DEC parser) and falls back to the live ``__doc__`` (2D-only and
version-only members have no Sphinx page: the shipped docs are built from 3D
9.x). Entries the engine does not expose are never added.

Only each engine's own families are touched (engine isolation): the single 9.x
binary exposes every product's modules, which is not a reason to document them.
``itasca.util`` (socket bridges to other codes, not modelling API) is skipped as
in parse_3dec_python. ``_common`` docs are shared across engines and are left
alone. Re-runs are idempotent: existing modules, members and markers are kept.

Usage:
    uv run python scripts/corpus/reconcile_python_api_live.py --dumps <dir with api_*.json>
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_3dec_python import (  # noqa: E402
    _first_paragraph,
    _functions,
    _group_key,
    _method_groups,
    _methods,
    mark_bracketed_optional,
)

RESOURCES = Path(__file__).resolve().parents[2] / "src/itasca_mcp/knowledge/resources"
DOC_SUFFIX = "exe64/doc/common/docproject/source/manual/scripting/python/doc"
# Newest first; the 3DEC parser reads the 9.x Sphinx markup only.
SPHINX_ROOTS = [
    Path("C:/Program Files/Itasca/Itasca Software Subscription") / DOC_SUFFIX,
    Path("C:/Program Files/Itasca/ItascaSoftware900") / DOC_SUFFIX,
]
SRC_BASE = "https://docs.itascacg.com/itasca900/common/docproject/source/manual/scripting/python/doc"
SWEEP_DATE = "2026-10-28"
# The "9.0" label stands for the current official 9.x release, 9.8 (2026-10-26). The
# 9.0 and 9.7 point builds are no longer a reference: dumps tagged 900/97 are ignored.
LABEL_BUILDS = {"6.0": {"6.0"}, "7.0": {"7.0"}, "9.0": {"9.8"}}
# Notes an earlier sweep wrote while 9.7 was tracked as a build of its own; stripped.
LEGACY_97_NOTES = (
    "Present from 9.7; absent from 9.0 builds (live introspection, 2026-10-24).",
    "Absent from 9.7 builds (live introspection, 2026-10-24).",
)

SHARED = ("data", "fish", "geometry", "history", "dfn", "table")
ENGINES: dict[str, dict[str, Any]] = {
    "flac": {
        "dump_prefixes": ("flac2d", "flac3d"),
        "versions": ["7.0", "9.0"],
        "families": SHARED + ("zone", "gridpoint", "attach", "interface", "structure"),
    },
    "3dec": {
        "dump_prefixes": ("3dec",),
        "versions": ["7.0", "9.0"],
        "families": SHARED + ("block", "sel", "structure", "flowknot", "flowplane", "contact"),
    },
    "mpoint": {
        "dump_prefixes": ("mpoint",),
        "versions": ["9.0"],
        "families": SHARED + ("mpoint",),
    },
    "pfc": {
        "dump_prefixes": ("pfc",),
        "versions": ["6.0", "7.0", "9.0"],
        "families": SHARED
        + ("ball", "clump", "contact", "wall", "rblock", "measure", "element", "cfdarray", "facetarray")
        + ("vertexarray", "pebblearray", "pebble"),
    },
}
SKIP_MODULES = ("util", "_test")

# Behaviour measured in state-readback probes (probe_interface.py, 2026-10-24), which
# the docstrings do not say. Keyed by (engine, live path); appended to the entry notes.
_LENGTH_AFTER_CYCLE = (
    "The effective length is assigned when the model cycles: it reads 0.0 before the first "
    "cycle. Measured on a 4-unit straight interface after one cycle: node lengths "
    "[1, 0.5, 1, 1, 0.5] (end nodes get half), summing to 4.0."
)
_BROKEN_70_SURFACE_PROP = (
    "Exposed on FLAC3D 7.0 interface nodes but not usable there: every call raises "
    "ValueError('There was a problem with the property cast.'), whatever the arguments. "
    "Use prop() / prop_set(), which work. Removed in 9.0."
)
# Notes for existing entries matched by name (pass C). PFC orientation is euler in 3D and a
# scalar rotation in 2D; the corpus came from 3D Sphinx pages, so 2D users found only euler.
NAME_NOTES: dict[str, list[tuple[re.Pattern[str], str]]] = {
    "pfc": [(re.compile(r"(^|_)euler(_[xyz])?$"), "3D builds only; 2D builds expose rotation / set_rotation instead.")],
}

_ROTATION_DEGREES = (
    "Angle in degrees. It only advances with the spin when orientation tracking is on "
    "(model orientation-tracking on; off by default): with tracking off it keeps the last set "
    "value. Measured on PFC2D 7.0 (probe_families.py, 2026-10-24): spin 0.01 rad/s for 10 s "
    "reads 5.7296 (= 0.1 rad in degrees)."
)

VERIFIED_NOTES: dict[tuple[str, str], list[str]] = {
    ("pfc", "itasca.ball.Ball.rotation"): [_ROTATION_DEGREES],
    ("pfc", "itasca.ballarray.rotation"): [_ROTATION_DEGREES],
    ("flac", "itasca.interface.node.Node.length"): [_LENGTH_AFTER_CYCLE],
    ("flac", "itasca.interfacenodearray.length"): [_LENGTH_AFTER_CYCLE],
    ("flac", "itasca.interface.element.Element.length"): [
        "Valid immediately after the interface is created (each element of a unit-zone interface reads 1.0)."
    ],
    ("flac", "itasca.interface.node.Node.has_prop"): [_BROKEN_70_SURFACE_PROP],
    ("flac", "itasca.interface.node.Node.props"): [_BROKEN_70_SURFACE_PROP],
    ("flac", "itasca.interface.node.Node.set_prop"): [_BROKEN_70_SURFACE_PROP],
}


def build_version(tag: str) -> tuple[str, str]:
    """``flac2d97`` -> (corpus version label "9.0", build "9.7")."""
    num = re.search(r"(600|700|900|97|98)$", tag)
    assert num, tag
    return {
        "600": ("6.0", "6.0"),
        "700": ("7.0", "7.0"),
        "900": ("9.0", "9.0"),
        "97": ("9.0", "9.7"),
        "98": ("9.0", "9.8"),
    }[num.group(1)]


def dimension(tag: str) -> str:
    return "2D" if "2d" in tag else "3D"


class Live:
    """Union of one engine's dumps: where every module/function/method exists, and its __doc__."""

    def __init__(self, dump_dir: Path, engine: str) -> None:
        cfg = ENGINES[engine]
        self.engine = engine
        self.versions = cfg["versions"]
        self.seen: dict[str, set[tuple[str, str, str]]] = {}  # path -> {(label, build, dim)}
        self.docs: dict[str, str] = {}
        self.classes: dict[str, set[str]] = {}  # module -> class names
        self.modules: set[str] = set()
        self.builds: set[tuple[str, str, str]] = set()
        for path in sorted(dump_dir.glob("api_*.json")):
            tag = path.stem[4:]
            if not tag.startswith(cfg["dump_prefixes"]):
                continue
            label, build = build_version(tag)
            if label not in self.versions or build not in LABEL_BUILDS[label]:
                continue
            key = (label, build, dimension(tag))
            self.builds.add(key)
            for mod, entry in json.loads(path.read_text(encoding="utf-8"))["modules"].items():
                self.modules.add(mod)
                self._mark(mod, key, entry.get("doc", ""))
                for name, kind in entry["members"].items():
                    if name.startswith("_") or kind == "module":
                        continue
                    if kind == "class":
                        if not name.endswith("Iter"):
                            self.classes.setdefault(mod, set()).add(name)
                        continue
                    self._mark(f"{mod}.{name}", key, entry.get("docs", {}).get(name, ""))
                for cls, members in entry["classes"].items():
                    if cls.startswith("_") or cls.endswith("Iter"):
                        continue
                    self._mark(f"{mod}.{cls}", key, entry.get("docs", {}).get(cls, ""))
                    for m in members:
                        if not m.startswith("_"):
                            self._mark(f"{mod}.{cls}.{m}", key, entry.get("class_docs", {}).get(cls, {}).get(m, ""))

    def _mark(self, path: str, key: tuple[str, str, str], doc: str) -> None:
        self.seen.setdefault(path, set()).add(key)
        if doc and not self.docs.get(path):
            self.docs[path] = doc

    def has(self, path: str) -> bool:
        return path in self.seen

    def members(self, prefix: str) -> list[str]:
        """Direct function/method names under a module or class path."""
        depth = prefix.count(".") + 1
        names = set()
        for p in self.seen:
            if p.startswith(prefix + ".") and p.count(".") == depth and p not in self.modules:
                tail = p.rsplit(".", 1)[1]
                if tail[:1].islower():
                    names.add(tail)
        return sorted(names)

    def availability(self, path: str) -> tuple[dict[str, Any] | None, list[str]]:
        """(availability marker or None when in every version, notes on build/dimension limits)."""
        seen = self.seen.get(path, set())
        labels = sorted({s[0] for s in seen})
        notes = []
        dims = {s[2] for s in seen}
        if len({b[2] for b in self.builds}) > 1 and len(dims) == 1:
            notes.append(f"{next(iter(dims))} builds only.")
        marker = None if labels == self.versions else {"versions": labels}
        return marker, notes


# Field replacements for module functions whose Sphinx signature does not parse into
# usable parameters. Applied to every engine documenting the path (3DEC and MassFlow
# carried the same broken entry), including ones without dumps.
OVERRIDES: dict[str, dict[str, Any]] = {
    "itasca.fish.call_function": {
        "signature": "itasca.fish.call_function(func: str, args: tuple = ()) -> Any",
        "description": "Call the FISH function func and return its result.",
        "parameters": [
            {"name": "func", "type": "str", "required": True},
            {"name": "args", "type": "tuple", "required": False, "default": "()"},
        ],
        "notes": [
            "Arguments must be passed as a tuple: call_function('twice', (4,)) returns 8, while "
            "call_function('twice', 4) raises ValueError('FISH function arguments must be given as "
            "a tuple.'). Measured on FLAC3D 9.7 (probe_families.py, 2026-10-24)."
        ],
    },
}


# Misspellings in the engine's own docstrings and Sphinx pages (9.8 itasca.mpoint). They
# are repeated verbatim into the corpus by the passes above; BM25 matches whole words,
# so "veolcity" never answers a "velocity" query. Applied to description and signature
# of every entry, every engine; idempotent.
TEXT_FIXES = {
    "veolcity": "velocity",
    "appliad": "applied",
    "unbalance force": "unbalanced force",
    "mpoint mpoint ": "mpoint ",
    "mesh point mesh point ": "mesh point ",
}


def apply_text_fixes() -> list[str]:
    fixed = []
    for doc_path in sorted(RESOURCES.glob("*/python_sdk_docs/modules/**/*.json")):
        if doc_path.name == "keywords.json":
            continue
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
        changed = False
        for e in doc.get("functions", []) + doc.get("methods", []):
            if not isinstance(e, dict):
                continue
            for field in ("description", "signature"):
                text = e.get(field)
                if not isinstance(text, str):
                    continue
                new = text
                for wrong, right in TEXT_FIXES.items():
                    new = new.replace(wrong, right)
                if new != text:
                    e[field] = new
                    changed = True
        if changed:
            _write(doc_path, doc)
            fixed.append(str(doc_path.relative_to(RESOURCES)))
    return fixed


def apply_overrides() -> list[str]:
    patched = []
    for path, fields in OVERRIDES.items():
        mod, _, func = path[len("itasca.") :].rpartition(".")
        for doc_path in sorted(RESOURCES.glob(f"*/python_sdk_docs/modules/{mod.replace('.', '/')}/module.json")):
            doc = json.loads(doc_path.read_text(encoding="utf-8"))
            for e in doc.get("functions", []):
                if isinstance(e, dict) and e.get("name") == func and any(e.get(k) != v for k, v in fields.items()):
                    e.update(fields)
                    _write(doc_path, doc)
                    patched.append(f"{doc_path.relative_to(RESOURCES).as_posix()}#{func}")
    return patched


def _sphinx_page(name: str) -> str | None:
    for root in SPHINX_ROOTS:
        page = root / f"itasca.{name}.html"
        if page.exists():
            return page.read_text(encoding="utf-8")
    return None


_DOC_RE = re.compile(r"^\s*(\([^)]*\))\s*->\s*(.*?)\.(?:\s+(.*))?$", re.S)


def _parse_params(args: str) -> list[dict[str, Any]]:
    out = []
    for raw in [a.strip() for a in args.strip("()").split(",") if a.strip()]:
        default = None
        if "=" in raw:
            raw, default = (s.strip() for s in raw.split("=", 1))
        if ":" in raw:  # annotated: "property_name: str"
            name, typ = (s.strip() for s in raw.split(":", 1))
            param: dict[str, Any] = {"name": name, "type": typ}
        else:  # C-style: "string name"
            bits = raw.split()
            param = {"name": bits[-1]}
            if len(bits) > 1:
                param["type"] = " ".join(bits[:-1])
        param["required"] = default is None
        if default is not None:
            param["default"] = default
        out.append(param)
    return out


def entry_from_doc(name: str, doc: str, sig_prefix: str) -> dict[str, Any]:
    """Corpus entry from a live ``(args) -> ret. description`` docstring."""
    text = re.sub(r"\s+", " ", doc).strip()
    m = _DOC_RE.match(text)
    if not m:
        return {"name": name, "signature": f"{sig_prefix}{name}()", "description": text}
    args, ret, desc = m.group(1), m.group(2).strip(), (m.group(3) or "").strip()
    entry: dict[str, Any] = {"name": name, "signature": f"{sig_prefix}{name}{args} -> {ret}"}
    if desc:
        entry["description"] = desc
    params = _parse_params(args)
    mark_bracketed_optional(args, params)
    if params:
        entry["parameters"] = params
    if ret:
        entry["returns"] = {"type": ret}
    return entry


def _with_markers(entry: dict[str, Any], live: Live, path: str, container: str | None = None) -> dict[str, Any]:
    """Attach availability/notes, omitting what the enclosing module or class already says."""
    marker, notes = live.availability(path)
    notes = notes + VERIFIED_NOTES.get((live.engine, path), [])
    if container is not None:
        outer_marker, outer_notes = live.availability(container)
        marker = None if marker == outer_marker else marker
        notes = [n for n in notes if n not in outer_notes]
    if marker:
        entry["availability"] = marker
    if notes:
        entry["notes"] = entry.get("notes", []) + notes
    return entry


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", "utf-8")


def _entries(live: Live, prefix: str, sphinx: list[dict[str, Any]], sig_prefix: str) -> list[dict[str, Any]]:
    """Sphinx entries the engine exposes, plus live-only members from __doc__."""
    by_name = {e["name"]: e for e in sphinx}
    out = []
    for name in live.members(prefix):
        entry = by_name.get(name) or entry_from_doc(name, live.docs.get(f"{prefix}.{name}", ""), sig_prefix)
        out.append(_with_markers(dict(entry), live, f"{prefix}.{name}", container=prefix))
    return out


def add_modules(engine: str, live: Live, index: dict[str, Any]) -> list[str]:
    """Pass A: live own-family modules missing from the index."""
    families = ENGINES[engine]["families"]
    added = []
    candidates = [m[len("itasca.") :] for m in live.modules if m.startswith("itasca.")]
    for dotted in sorted(candidates, key=lambda d: (d.count("."), d)):
        if dotted.split(".")[0] in SKIP_MODULES or not dotted.startswith(families):
            continue
        if dotted in index["modules"]:
            continue
        page = _sphinx_page(dotted) or ""
        funcs = _entries(live, f"itasca.{dotted}", _functions(page, dotted) if page else [], f"itasca.{dotted}.")
        rel = f"{engine}/python_sdk_docs/modules/{dotted.replace('.', '/')}"
        desc = _first_paragraph(page) if page else _first_line(live.docs.get(f"itasca.{dotted}", ""))
        module_doc: dict[str, Any] = {
            "module": f"itasca.{dotted}",
            "description": desc or f"itasca.{dotted} module.",
            "import_statement": "import itasca",
            "source_url": f"{SRC_BASE}/itasca.{dotted}.html" if page else "",
        }
        _with_markers(module_doc, live, f"itasca.{dotted}")
        module_doc["functions"] = funcs
        _write(RESOURCES / rel / "module.json", module_doc)
        index["modules"][dotted] = {
            "description": module_doc["description"],
            "file": f"{rel}/module.json",
            "functions": [f["name"] for f in funcs],
        }
        if "availability" in module_doc:
            index["modules"][dotted]["availability"] = module_doc["availability"]
        for f in funcs:
            index["quick_ref"][f"itasca.{dotted}.{f['name']}"] = f"{rel}/module.json#{f['name']}"
        classes = sorted(live.classes.get(f"itasca.{dotted}", ()))
        for cls in classes:
            add_class(engine, live, index, dotted, cls, rel)
        added.append(f"{dotted} ({len(funcs)} funcs{', ' + ', '.join(classes) if classes else ''})")
    return added


def _first_line(doc: str) -> str:
    return re.sub(r"\s+", " ", doc).strip().split(". ")[0]


def add_class(engine: str, live: Live, index: dict[str, Any], dotted: str, cls: str, rel: str) -> None:
    page = _sphinx_page(f"{dotted}.{cls}") or ""
    prefix = f"itasca.{dotted}.{cls}"
    inst = cls.lower()
    methods = _entries(live, prefix, _methods(page, inst) if page else [], f"{inst}.")
    desc = (_first_paragraph(page) if page else _first_line(live.docs.get(prefix, ""))) or (
        f"{cls} object instance in itasca.{dotted}."
    )
    note = f"Do not instantiate directly; use itasca.{dotted} module functions."
    class_doc: dict[str, Any] = {
        "class": cls,
        "description": desc,
        "source_url": f"{SRC_BASE}/itasca.{dotted}.{cls}.html" if page else "",
        "note": note,
    }
    _with_markers(class_doc, live, prefix, container=f"itasca.{dotted}")
    class_doc["method_groups"] = _method_groups(methods)
    class_doc["methods"] = methods
    _write(RESOURCES / rel / f"{cls}.json", class_doc)
    file_ref = f"{rel}/{cls}.json"
    key = cls if cls not in index["objects"] else f"itasca.{dotted}.{cls}"
    index["objects"][key] = {
        "description": desc,
        "file": file_ref,
        "note": note,
        "method_groups": class_doc["method_groups"],
    }
    if "availability" in class_doc:
        index["objects"][key]["availability"] = class_doc["availability"]
    for m in methods:
        index["quick_ref"][f"{prefix}.{m['name']}"] = f"{file_ref}#{m['name']}"


def _doc_targets(engine: str, index: dict[str, Any]) -> list[tuple[str, Path, str, str]]:
    """(live path prefix, doc file, list key, signature prefix) for every engine-owned doc."""
    out = []
    for key, info in index["modules"].items():
        file_ref = info.get("file", "")
        if key == "itasca" or not file_ref.startswith(f"{engine}/"):
            continue
        out.append((f"itasca.{key}", RESOURCES / file_ref, "functions", f"itasca.{key}."))
    for info in index["objects"].values():
        file_ref = info.get("file", "")
        if info.get("types") or not file_ref.startswith(f"{engine}/"):
            continue
        module_dir, _, file_name = file_ref.partition("/modules/")[2].rpartition("/")
        cls = file_name.removesuffix(".json")
        out.append((f"itasca.{module_dir.replace('/', '.')}.{cls}", RESOURCES / file_ref, "methods", f"{cls.lower()}."))
    return out


GROUP_HINTS = {"rotation": "orientation"}


def _extend_groups(groups: dict[str, Any], new_names: list[str]) -> None:
    """Add names to existing method groups without regrouping hand-curated ones.

    Groups are either lists (PFC) or comma-joined strings (FLAC/3DEC). A name joins
    the group named by its stem, else the group of a sibling with the same stem,
    else "other". GROUP_HINTS sends PFC 2D rotation to the 3D orientation group.
    """
    for name in new_names:
        stem = _group_key(name)
        hinted = GROUP_HINTS.get(stem)
        target = (
            hinted
            if hinted in groups
            else stem
            if stem in groups
            else next((g for g, v in groups.items() if any(_group_key(m) == stem for m in _group_list(v))), "other")
        )
        current = _group_list(groups.get(target, []))
        if name in current:
            continue
        current.append(name)
        groups[target] = current if isinstance(groups.get(target, []), list) else ", ".join(current)


def _group_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return list(value)
    return [s.strip() for s in str(value).split(",") if s.strip()]


def _strip_legacy_notes(entry: dict[str, Any]) -> bool:
    """Drop the 9.7-era notes; True if any was present."""
    notes = entry.get("notes")
    if not notes:
        return False
    kept = [n for n in notes if n not in LEGACY_97_NOTES]
    if len(kept) == len(notes):
        return False
    if kept:
        entry["notes"] = kept
    else:
        del entry["notes"]
    return True


def add_members_and_markers(engine: str, live: Live, index: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Passes B, C and D over the engine's existing module/object docs."""
    added, marked, removed = [], [], []
    for prefix, path, list_key, sig_prefix in _doc_targets(engine, index):
        if not path.exists() or not live.has(prefix):
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        entries = doc.setdefault(list_key, [])
        names = {e.get("name") for e in entries if isinstance(e, dict)}
        changed = False
        dropped: list[str] = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            for pattern, note in NAME_NOTES.get(engine, []):
                if pattern.search(e["name"]) and note not in e.get("notes", []):
                    e["notes"] = e.get("notes", []) + [note]
                    marked.append(f"{prefix}.{e['name']} note")
                    changed = True
            if _strip_legacy_notes(e):
                marked.append(f"{prefix}.{e['name']} 9.7 note stripped")
                changed = True
            if not live.has(f"{prefix}.{e['name']}"):
                dropped.append(f"{prefix}.{e['name']}")
                continue
            marker, _ = live.availability(f"{prefix}.{e['name']}")
            # A marker from the 9.7-era sweep may name a label the entry is no longer
            # seen in; recompute it from the builds that count now.
            if "availability" in e and marker is not None and e["availability"] != marker:
                e["availability"] = marker
                marked.append(f"{prefix}.{e['name']} {marker['versions']} (was stale)")
                changed = True
            # Legacy available_in_* flags are read by nothing; they do not count as a marker.
            if "availability" in e:
                continue
            if marker and marker != live.availability(prefix)[0]:
                e["availability"] = marker
                marked.append(f"{prefix}.{e['name']} {marker['versions']}")
                changed = True
        for name in live.members(prefix):
            if name in names:
                continue
            entry = _with_markers(
                entry_from_doc(name, live.docs.get(f"{prefix}.{name}", ""), sig_prefix),
                live,
                f"{prefix}.{name}",
                container=prefix,
            )
            # Docs that mark every entry (e.g. the PFC arrays) stay uniformly marked.
            if "availability" not in entry and any(isinstance(e, dict) and "availability" in e for e in entries):
                entry["availability"] = {"versions": list(live.versions)}
            entries.append(entry)
            index["quick_ref"][f"{prefix}.{name}"] = f"{path.relative_to(RESOURCES).as_posix()}#{name}"
            added.append(f"{prefix}.{name}")
            changed = True
        if dropped:
            # Documented but exposed by no build that counts (9.7-only, or dropped by 9.8).
            doc[list_key] = [e for e in entries if not (isinstance(e, dict) and f"{prefix}.{e['name']}" in dropped)]
            entries = doc[list_key]
            for d in dropped:
                index["quick_ref"].pop(d, None)
            removed.extend(dropped)
            changed = True
        if list_key == "functions":
            mod_key = prefix[len("itasca.") :]
            mod_marker, _ = live.availability(prefix)
            if _strip_legacy_notes(doc):
                marked.append(f"{prefix} 9.7 note stripped")
                changed = True
            if "availability" in doc and mod_marker is not None and doc["availability"] != mod_marker:
                doc["availability"] = mod_marker
                marked.append(f"{prefix} {mod_marker['versions']} (was stale)")
                changed = True
            if "availability" not in doc and mod_marker:
                doc["availability"] = mod_marker
                marked.append(f"{prefix} {mod_marker['versions']}")
                changed = True
            if "availability" in doc and index["modules"][mod_key].get("availability") != doc["availability"]:
                index["modules"][mod_key]["availability"] = doc["availability"]
                changed = True
        if changed:
            new_names = [n for n in live.members(prefix) if n not in names]
            if list_key == "methods" and new_names and isinstance(doc.get("method_groups"), dict):
                _extend_groups(doc["method_groups"], new_names)
            _write(path, doc)
            if list_key == "functions":
                mod_key = prefix[len("itasca.") :]
                index["modules"][mod_key]["functions"] = [e["name"] for e in entries if isinstance(e, dict)]
    return added, marked, removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dumps", type=Path, required=True)
    parser.add_argument("--engine", choices=sorted(ENGINES), action="append")
    args = parser.parse_args()
    for engine in args.engine or sorted(ENGINES):
        live = Live(args.dumps, engine)
        index_path = RESOURCES / engine / "python_sdk_docs" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        modules = add_modules(engine, live, index)
        members, markers, removed = add_members_and_markers(engine, live, index)
        # Existing keys keep their order (no churn); new keys are appended as added.
        index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", "utf-8")
        print(f"== {engine}: builds {sorted(live.builds)}")
        print(f"   A. modules added: {len(modules)}")
        for m in modules:
            print(f"      {m}")
        print(f"   B. members added: {len(members)}")
        for m in members:
            print(f"      {m}")
        print(f"   C. availability markers added: {len(markers)}")
        for m in markers:
            print(f"      {m}")
        print(f"   D. members removed (exposed by no build that counts): {len(removed)}")
        for m in removed:
            print(f"      {m}")
    patched = apply_overrides()
    fixed = apply_text_fixes()
    print(f"== docstring misspellings fixed in: {len(fixed)} files")
    for f in fixed:
        print(f"   {f}")
    print(f"== overrides applied: {len(patched)}")
    for p in patched:
        print(f"   {p}")


if __name__ == "__main__":
    main()
