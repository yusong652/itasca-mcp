"""Generate the ``fish_docs`` corpus: one JSON file per FISH intrinsic namespace.

FISH intrinsics form a purely lexical tree (``ball`` -> ``ball.pos`` ->
``ball.pos.x``); the live ``fish list intrinsics`` table is the authority for
which names exist and what their signatures are, and the official
``out_fish.txt`` (shipped under ``exe64/doc``) contributes the HTML anchor and
the 2D/3D marker. This script merges both into flat per-namespace files; the
loader rebuilds the tree from the dotted names.

Layout (RESOURCES-root-relative file pointers, like the command/python index):

    _common/fish_docs/<ns>.json        kernel namespaces shared by engines
    <engine>/fish_docs/<ns>.json       product-family namespaces
    <engine>/fish_docs/index.json      which namespaces this engine exposes

Engine isolation: a kernel namespace is listed for an engine only when a
*clean* (non-unified) live table of that engine shows it. PFC 9.x and FLAC 9.x
GUIs load every product plugin, so their tables list each other's families and
cannot serve as evidence; PFC 6.0 (a standalone product) and 3DEC/MassFlow 9.x
tables are clean. Engines without a clean table fall back to the full kernel
set and are flagged ``kernel_verified: false`` in their index.

Usage:
    uv run python scripts/corpus/generate_fish_docs.py
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
RES = REPO / "src" / "itasca_mcp" / "knowledge" / "resources"
WORK = Path("G:/Han/Han/itasca-doc")
ITASCA = Path("C:/Program Files/Itasca")

# --- live tables ("name | signature" console logs, name lists, or name->sig json)
LIVE: dict[str, dict[str, Path]] = {
    "pfc": {
        "6.0": WORK / "pfc60_fish_intrinsics.log",  # PFC3D 6.00 (clean; columnar table, see read_live)
        "7.0": WORK / "pfc70_fish_intrinsics.log",  # PFC3D 7.00 (unified)
        "9.0": WORK / "pfc98_fish_intrinsics.log",  # PFC3D 9.8 (unified)
    },
    "flac": {
        "7.0": WORK / "flac70_fish_intrinsics.log",  # FLAC3D 7.00 (unified: identical to PFC 7.00's table)
        "9.0": WORK / "flac98_fish_intrinsics.log",  # FLAC3D 9.8 (unified)
    },
    "3dec": {
        "7.0": WORK / "fish_intrinsics_3dec70.txt",  # 3DEC 7.00 (clean)
        "9.0": WORK / "3dec98_fish_intrinsics.log",  # 3DEC 9.8 (clean)
    },
    "massflow": {"9.0": WORK / "massflow_fish_intrinsics.log"},  # MassFlow 9.7 (clean)
    # MPoint 9.8 (unified: identical to PFC's table, so it cannot decide kernel membership)
    "mpoint": {"9.0": WORK / "mpoint98_fish_intrinsics.log"},
}
# Engines whose kernel-namespace membership is decided by a clean live table.
CLEAN_TABLE: dict[str, tuple[str, str]] = {
    "pfc": ("pfc", "6.0"),
    "3dec": ("3dec", "9.0"),
    "massflow": ("massflow", "9.0"),
}
# Kernel namespaces that post-date the clean table (PFC 6.0) but exist on 9.x PFC.
CLEAN_TABLE_ADDITIONS: dict[str, set[str]] = {"pfc": {"cluster", "structure", "accumulator"}}
# PFC 6.0's only struct.* names (struct.check / struct.name) are the FISH *structure type*
# utilities that 7.0 renamed to structure.*; they are not structural elements, so they must
# not pull the struct.* (beam/cable/liner...) namespace into PFC.
CLEAN_TABLE_REMOVALS: dict[str, set[str]] = {"pfc": {"struct"}}
ALL_VERSIONS = ["6.0", "7.0", "9.0"]
# Namespace files are <ns>.json; the one name that would collide with the engine index.
FILE_NAME_OVERRIDES = {"index": "index-intrinsic.json"}

STATIC: dict[str, Path] = {
    "6.0": ITASCA / "PFC600/exe64/doc/out_fish.txt",
    "7.0": ITASCA / "PFC700/exe64/doc/out_fish.txt",  # identical unified file ships with 3DEC700/FLAC3D700
    "9.0": ITASCA / "Itasca Software Subscription/exe64/doc/out_fish.txt",  # 9.8
}

ENGINE_VERSIONS = {
    "pfc": ["6.0", "7.0", "9.0"],
    "flac": ["7.0", "9.0"],
    "3dec": ["7.0", "9.0"],
    "mpoint": ["9.0"],
    "massflow": ["9.0"],
}

# --- namespace routing (decided 2026-10-29 from three-engine live tables + doc prefixes)
KERNEL = [
    "accumulator", "array", "boolean", "cluster", "code", "comp", "creep", "data", "dfn", "domain",
    "dynamic", "false", "file", "float", "fluid", "fracture", "geom", "global", "group", "index", "int",
    "io", "list", "map", "math", "matrix", "mech", "memory", "null", "range", "string", "struct",
    "structure", "table", "tensor", "thermal", "time", "true", "type", "vector", "version",
]  # fmt: skip
FAMILIES: dict[str, list[str]] = {
    # contact/fragment are documented under common/ but only PFC can model with them.
    "pfc": ["ball", "brick", "cfd", "clump", "contact", "element", "fragment", "inlet", "measure", "rblock", "wall"],
    "flac": ["attach", "gp", "interface", "zone"],
    "3dec": ["block", "fblock", "feblock", "flowknot", "flowplane", "sel"],  # sel: 7.0-only legacy SEL
    "mpoint": ["mpoint"],
    "massflow": ["massflow"],
}
EXCLUDED: dict[str, str] = {
    "mail": "e-mail utilities; outside modelling scope (same policy as itasca.util)",
    "socket": "raw socket utilities; outside modelling scope (same policy as itasca.util)",
    "system": "OS/process utilities; outside modelling scope (same policy as itasca.util)",
    "sketch": "FISH face of the FLAC GUI sketch tool; interactive-only",
    "building_blocks": "FISH face of the FLAC GUI building-blocks tool; interactive-only",
    "extrude": "FISH face of the FLAC 7.0 extruder GUI tool (sketch in 9.x); interactive-only",
}

# Names are dotted identifiers; a few carry a hyphen (massflow.marker.moved-day, block.lf-next).
ROW = re.compile(r"^\s*([A-Za-z_][\w.-]*)\s*\|\s*(.+?)\s*$")
GETTER = re.compile(
    r"^(?P<ret>[^=]+?)\s*(?::=|=)\s*(?P<name>[A-Za-z_][\w.-]*)(?:\((?P<args>.*)\))?(?:\s*(?::=|=)\s*(?P<set>.+?))?\s*$"
)
SETTER_ONLY = re.compile(r"^(?P<name>[A-Za-z_][\w.-]*)(?:\((?P<args>.*)\))?\s*(?::=|=)\s*(?P<set>.+?)\s*$")
# Curated leftovers of the retired references/fish-intrinsics category: family labels,
# the MassFlow page descriptions, retired-name renames, MPoint 2D differences, item notes.
HINTS_FILE = Path(__file__).with_name("fish_family_hints.json")
SUFFIX = re.compile(r"\)\s*\((?P<note>[^()]*)\)\s*$")


_TYPE_60 = {"v3": "vec3", "v2": "vec2"}


def read_columnar_60(text: str) -> dict[str, str | None]:
    """PFC 6.0 prints a fixed-width table (Plugin / Name / Return / Arg / Write / Arguments).

    Rebuild the 7.0+ style ``ret := name(args) [:= ret]`` so every version shares
    one signature grammar; 6.0's shorter type names (v3, ball) are kept except
    v3/v2, which are spelled vec3/vec2 everywhere else.
    """
    lines = text.splitlines()
    header = next(i for i, line in enumerate(lines) if line.startswith("Plugin") and "Arguments" in line)
    cols = {key: lines[header].index(key) for key in ("Name", "Return", "Arg", "Write", "Arguments")}
    rows: dict[str, str | None] = {}
    for line in lines[header + 2 :]:
        if not line.strip() or line.startswith(("pfc3d>", "*")):
            continue
        name = line[cols["Name"] : cols["Return"]].strip()
        if not re.fullmatch(r"[A-Za-z_][\w.-]*", name):
            continue
        ret = line[cols["Return"] : cols["Arg"]].strip()
        ret = "/".join(_TYPE_60.get(t, t) for t in ret.split("/")) if ret else "any"
        write = line[cols["Write"] : cols["Arguments"]].strip() == "Yes"
        args = line[cols["Arguments"] :].strip()
        sig = f"{ret} := {name}({args})"
        if write:
            sig += f" := {ret}"
        rows.setdefault(name, sig)
    return rows


def read_live(path: Path) -> dict[str, str | None]:
    """name -> signature (None when the source lists names only)."""
    if path.suffix == ".json":
        return dict(json.loads(path.read_text(encoding="utf-8")).items())
    rows: dict[str, str | None] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    if "Plugin Name" in text:  # PFC 6.0 columnar table
        return read_columnar_60(text)
    if "|" not in text:  # bare name list
        return {line.strip(): None for line in text.splitlines() if line.strip()}
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            rows.setdefault(m.group(1), m.group(2))
    return rows


def normalize_sig(sig: str) -> str:
    """The live table mixes ``=`` and ``:=`` for the same intrinsic across versions; keep one spelling."""
    return re.sub(r"(?<![:<>!])=(?!=)", ":=", sig).replace(": =", ":=")


def read_static(path: Path) -> dict[str, dict[str, Any]]:
    """name -> {doc, prefix, dimension, note, signature} from an out_fish.txt."""
    out: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.rstrip().split(" ", 2)
        if len(parts) < 2 or not parts[0]:
            continue
        name, doc = parts[0], parts[1]
        entry = out.setdefault(
            name, {"doc": doc, "prefix": doc.split("/")[0], "dimension": None, "note": None, "signature": None}
        )
        if len(parts) == 3:
            plain = html.unescape(re.sub(r"<[^>]+>", "", parts[2])).strip()
            if entry["signature"] is None:
                entry["signature"] = normalize_sig(SUFFIX.sub(")", plain))
            m = SUFFIX.search(plain)
            if m:
                note = m.group("note").strip()
                entry["note"] = note
                low = note.lower()
                entry["dimension"] = "2D" if "2d" in low else "3D" if "3d" in low else None
    return out


def split_args(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    args: list[dict[str, Any]] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok == "...":
            args.append({"type": "...", "variadic": True})
            continue
        optional = tok.startswith("<") and tok.endswith(">")
        if optional:
            tok = tok[1:-1]
        byref = tok.startswith("&")
        if byref:
            tok = tok[1:]
        arg: dict[str, Any] = {"type": tok}
        if optional:
            arg["optional"] = True
        if byref:
            arg["by_reference"] = True
        args.append(arg)
    return args


def parse_signature(name: str, sig: str) -> dict[str, Any]:
    m = GETTER.match(sig)
    if m and m.group("name") == name:
        return {
            "returns": m.group("ret").strip(),
            "args": split_args(m.group("args")),
            "settable": m.group("set") is not None,
        }
    m = SETTER_ONLY.match(sig)
    if m and m.group("name") == name:
        return {"returns": None, "args": split_args(m.group("args")), "settable": True}
    raise ValueError(f"unparsed signature for {name}: {sig!r}")


def load_hints() -> dict[str, Any]:
    """The frozen curated data (see HINTS_FILE); every section is optional."""
    data: dict[str, Any] = json.loads(HINTS_FILE.read_text(encoding="utf-8"))
    for key in ("family_by_name", "description_by_name", "engine_index_extras", "namespace_notes"):
        data.setdefault(key, {})
    return data


VERIFICATION = {
    "pfc": (
        "Generated 2026-10-29. Names/signatures: live 'fish list intrinsics' of PFC3D 9.8 (3772 rows, unified "
        "kernel table), PFC3D 7.00 (3793, unified) and PFC3D 6.00 (1542; a columnar Name/Return/Arg/Write table "
        "rebuilt into the 7.0+ signature grammar; this standalone-product table also decides which kernel "
        "namespaces PFC exposes). Anchors: exe64/doc/out_fish.txt of 9.8/7.0/6.0. contact.* "
        "and fragment.* are documented under common/ but assigned to PFC (3DEC lacks them; FLAC cannot model with "
        "them). creep/dynamic/fluid process namespaces are FLAC-side and are not listed for PFC."
    ),
    "flac": (
        "Generated 2026-10-29. Names/signatures: live 'fish list intrinsics' of FLAC3D 9.8 (3951 rows, unified "
        "kernel table) and FLAC3D 7.00 (3793 rows, also unified and identical to PFC3D 7.00's table). Neither "
        "table is clean, so FLAC lists every kernel namespace (it is the kernel's home product)."
    ),
    "3dec": (
        "Generated 2026-10-29. Names/signatures: live 'fish list intrinsics' of 3DEC 9.8 (1681 rows; 3DEC's table "
        "is clean - no PFC/FLAC families - so it also decides kernel membership) and 3DEC 7.00 (1970 rows, also "
        "clean; carries the 7.0-only sel.* legacy structural-element family). Anchors from the 9.8/7.0 out_fish.txt."
    ),
    "mpoint": (
        "Generated 2026-10-29. Names/signatures: live 'fish list intrinsics' of MPoint 9.8 (3772 rows - the same "
        "unified kernel table the PFC 9.8 GUI prints, so it cannot decide which kernel namespaces MPoint exposes; "
        "kernel membership mirrors FLAC). Anchors from the 9.8 out_fish.txt."
    ),
    "massflow": (
        "Generated 2026-10-29. Names/signatures: live 'fish list intrinsics' of MassFlow 9.7 (1323 rows, clean "
        "table; decides kernel membership). Anchors from the 9.8 out_fish.txt."
    ),
}


def main() -> None:
    live = {e: {v: read_live(p) for v, p in vs.items()} for e, vs in LIVE.items()}
    static = {v: read_static(p) for v, p in STATIC.items()}
    curated = load_hints()
    hints: dict[str, str] = curated["family_by_name"]
    descriptions: dict[str, str] = curated["description_by_name"]

    # Which engine lists which namespace (kernel membership from clean tables).
    engine_ns: dict[str, dict[str, str]] = {}  # engine -> ns -> scope
    kernel_verified: dict[str, bool] = {}
    for engine in ENGINE_VERSIONS:
        scopes = {ns: engine for ns in FAMILIES[engine]}
        if engine in CLEAN_TABLE:
            ce, cv = CLEAN_TABLE[engine]
            seen = {n.split(".")[0] for n in live[ce][cv]} | CLEAN_TABLE_ADDITIONS.get(engine, set())
            seen -= CLEAN_TABLE_REMOVALS.get(engine, set())
            kernel_verified[engine] = True
        else:
            seen = set(KERNEL)
            kernel_verified[engine] = False
        for ns in KERNEL:
            if ns in seen:
                scopes[ns] = "common"
        engine_ns[engine] = scopes

    # Build the per-namespace entry tables from every live source.
    names_by_ns: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for engine, versions in live.items():
        for version, rows in versions.items():
            for name, sig in rows.items():
                ns = name.split(".")[0]
                if ns not in FAMILIES[engine] and ns not in KERNEL:
                    continue  # other engines' families leaking through a unified table
                entry = names_by_ns[ns].setdefault(name, {"name": name, "sigs": {}, "seen": defaultdict(set)})
                entry["seen"][engine].add(version)
                if sig:
                    entry["sigs"].setdefault(version, normalize_sig(sig))

    def versions_for(entry: dict[str, Any], ns: str, engine: str | None) -> dict[str, bool]:
        """Availability per corpus version from live evidence only.

        ``engine=None`` gives the kernel's union view across every engine and version.
        """
        out: dict[str, bool] = {}
        seen = entry["seen"]
        for v in ALL_VERSIONS if engine is None else ENGINE_VERSIONS[engine]:
            if ns in KERNEL:
                out[v] = any(v in s for s in seen.values())
            else:
                out[v] = v in seen.get(engine, set())
        return out

    written: dict[str, Path] = {}
    for ns, table in sorted(names_by_ns.items()):
        scope = "common" if ns in KERNEL else next(e for e, fams in FAMILIES.items() if ns in fams)
        engines = sorted(e for e, m in engine_ns.items() if ns in m)
        ref_engine = None if scope == "common" else scope
        entries = []
        for name in sorted(table):
            entry = table[name]
            sig = entry["sigs"].get("9.0") or entry["sigs"].get("7.0")
            st = static["9.0"].get(name) or static["7.0"].get(name) or static["6.0"].get(name)
            rec: dict[str, Any] = {"name": name}
            if not sig and entry["sigs"].get("6.0"):
                sig = entry["sigs"]["6.0"]  # 6.0-only name: signature rebuilt from the 6.0 columnar table
                rec["signature_source"] = "6.0"
            if not sig and st and st["signature"]:
                sig = st["signature"]  # names the live tables list without a signature (6.0 name list)
                rec["signature_source"] = "static"
            if sig:
                rec["signature"] = sig
                rec.update(parse_signature(name, sig))
            else:
                rec.update({"signature": None, "returns": None, "args": [], "settable": None})
            sigs = entry["sigs"]
            if "7.0" in sigs and "9.0" in sigs and sigs["7.0"] != sigs["9.0"]:
                rec["signature_7.0"] = sigs["7.0"]
            rec["versions"] = versions_for(entry, ns, ref_engine)
            if st:
                rec["doc"] = st["doc"]
                if st["dimension"]:
                    rec["dimension"] = st["dimension"]
                elif st["note"]:
                    rec["note"] = st["note"]
            else:
                rec["doc"] = None
            if name in hints:
                rec["family"] = hints[name]
            if name in descriptions:
                rec["description"] = descriptions[name]
            rec["python_equivalent"] = None
            entries.append(rec)
        target_dir = RES / ("_common" if scope == "common" else scope) / "fish_docs"
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / FILE_NAME_OVERRIDES.get(ns, f"{ns}.json")
        payload = {
            "namespace": ns,
            "scope": scope,
            "engines": engines,
            "count": len(entries),
            "undocumented": sum(1 for e in entries if e["doc"] is None),
            "entries": entries,
        }
        if ns in curated["namespace_notes"]:
            payload["notes"] = curated["namespace_notes"][ns]
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written[ns] = path

    # Per-engine index.
    for engine, versions in ENGINE_VERSIONS.items():
        namespaces: dict[str, Any] = {}
        for ns, scope in sorted(engine_ns[engine].items()):
            if ns not in written:
                continue
            avail: Counter[str] = Counter()
            for entry in names_by_ns[ns].values():
                for v, ok in versions_for(entry, ns, engine).items():
                    if ok:
                        avail[v] += 1
            namespaces[ns] = {
                "file": written[ns].relative_to(RES).as_posix(),
                "scope": scope,
                "count": len(names_by_ns[ns]),
                "available": {v: avail.get(v, 0) for v in versions},
            }
        excluded = {}
        seen_names = {name for rows in live[engine].values() for name in rows}
        for ns, reason in EXCLUDED.items():
            n = sum(1 for k in seen_names if k.split(".")[0] == ns)
            if n:
                excluded[ns] = {"count": n, "reason": reason}
        index = {
            "version": "1.0",
            "software": engine,
            "description": (
                "FISH intrinsic namespaces available in this engine. Names and signatures come from the live "
                "'fish list intrinsics' table; 'doc' is the official HTML anchor under exe64/doc. Browse by dotted "
                "prefix (ball -> ball.pos -> ball.pos.x); an entry can be both a function and a prefix."
            ),
            "versions": versions,
            "kernel_verified": kernel_verified[engine],
            "namespaces": namespaces,
            "excluded_namespaces": excluded,
            **curated["engine_index_extras"].get(engine, {}),
            "verification": VERIFICATION[engine],
        }
        out = RES / engine / "fish_docs" / "index.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        total = sum(v["count"] for v in namespaces.values())
        print(f"{engine}: {len(namespaces)} namespaces, {total} entries, kernel_verified={kernel_verified[engine]}")
    print(f"{len(written)} namespace files")


if __name__ == "__main__":
    main()
