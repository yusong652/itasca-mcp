"""Bring the MassFlow ``range-elements`` reference up to the live 48.

``wire_massflow_common_references.py`` pointed MassFlow at the 22 range elements
that happen to live in ``_common``, and left the FLAC prose on the category
index: it told MassFlow users these filters are "used after the 'range' keyword
in FLAC commands" and illustrated them with ``zone group ... range position-x``
and ``structure node fix velocity range cylinder ...`` — and ``structure`` does
not exist in MassFlow at all.

The live binary accepts **48** range elements. 26 of them were missing,
including ``active`` and ``marker-type``, which are MassFlow's own and which the
vendor's `unittests.dat` uses on the first page.

This script:

1. parses the shared kernel page ``common/module/.../rangephrasereference.html``
   (61 elements, with sub-keywords), which is the only official source for any
   of this;
2. writes the 20 shared elements MassFlow accepts and ``_common`` lacked into
   ``_common/references/range-elements/`` — additive only, no existing shared
   doc is touched, and they are registered in the MassFlow index alone because
   MassFlow is the only binary they were enumerated against;
3. writes the 6 elements with no page at all into MassFlow's own directory:
   ``active`` and ``marker-type`` (MassFlow-specific, documented on the shared
   page but with no ``_common`` file) and ``fid`` / ``fidlist`` / ``name`` /
   ``remove`` (accepted by the binary, absent from the manual);
4. rewrites the MassFlow category index over all 48 with MassFlow prose and
   MassFlow examples.

Argument types come from live enumeration on MassFlow 9.7.47
(``massflow marker list range <element> ?``).

Usage:
    uv run python scripts/corpus/generate_massflow_range_elements.py
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"
COMMON_DIR = RESOURCES / "_common" / "references" / "range-elements"
MASSFLOW_DIR = RESOURCES / "massflow" / "references" / "range-elements"
MASSFLOW_REF_INDEX = RESOURCES / "massflow" / "references" / "index.json"

RANGE_PAGE = Path(
    "C:/Program Files/Itasca/Itasca Software Subscription/exe64/doc/common/module/doc/manual/"
    "range_manual/range_commands/rangephrasereference.html"
)

PAGE_SOURCE = "Itasca 9.7 shared kernel manual: Range Phrase Keyword Reference"
LIVE_SOURCE = "Live enumeration on MassFlow 9.7.47 (`massflow marker list range <element> ?`)"


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------


def _text(fragment: str) -> str:
    fragment = re.sub(r"(?is)<script.*?</script>", "", fragment)
    fragment = re.sub(r"(?i)</p>", "\n", fragment)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    fragment = html.unescape(fragment)
    fragment = re.sub(r"[ \t]+", " ", fragment)
    return re.sub(r"\n\s*\n+", "\n", fragment).strip()


def parse_range_page() -> dict[str, dict[str, Any]]:
    """Return {element: {"signature", "description", "sub_keywords": [...]}}."""
    raw = RANGE_PAGE.read_text(encoding="utf-8", errors="replace")
    blocks = re.findall(r'<dt[^>]*id="kwd:range\.([^"]+)"[^>]*>(.*?)</dt>\s*<dd>(.*?)</dd>', raw, re.S)
    out: dict[str, dict[str, Any]] = {}
    for anchor, dt, dd in blocks:
        signature = " ".join(_text(dt).split())
        description = " ".join(_text(dd).split())
        if "." in anchor:
            parent, sub = anchor.split(".", 1)
            entry = out.setdefault(parent, {"signature": "", "description": "", "sub_keywords": []})
            entry["sub_keywords"].append({"name": sub, "syntax": signature, "description": description})
        else:
            entry = out.setdefault(anchor, {"signature": "", "description": "", "sub_keywords": []})
            entry["signature"] = signature
            entry["description"] = description
    return out


# ---------------------------------------------------------------------------
# What MassFlow accepts, and how each slot is typed
# ---------------------------------------------------------------------------

# `massflow marker list range ?` on MassFlow 9.7.47, verbatim.
LIVE_ELEMENTS = [
    "active",
    "annulus",
    "by",
    "cmodel",
    "component-id",
    "component-id-list",
    "contact",
    "cylinder",
    "deselected",
    "dfn",
    "displacement",
    "ellipse",
    "extent",
    "extra",
    "extra-list",
    "fid",
    "fidlist",
    "fish",
    "geometry-distance",
    "geometry-space",
    "group",
    "id",
    "id-list",
    "interface",
    "marker-type",
    "name",
    "named-range",
    "not",
    "orientation",
    "plane",
    "polygon",
    "position",
    "position-x",
    "position-y",
    "position-z",
    "project-range",
    "rectangle",
    "remove",
    "seed",
    "selected",
    "set",
    "sphere",
    "state",
    "surface",
    "union",
    "use-hidden",
    "velocity",
    "volume",
]

# Elements `_common` already ships. Their docs are left untouched.
ALREADY_IN_COMMON = [
    "annulus",
    "by",
    "cylinder",
    "ellipse",
    "extent",
    "extra",
    "extra-list",
    "fish",
    "group",
    "id",
    "id-list",
    "named-range",
    "not",
    "plane",
    "polygon",
    "position",
    "position-x",
    "position-y",
    "position-z",
    "rectangle",
    "sphere",
    "union",
]

# Elements with no page anywhere — syntax is live-only, so they go in MassFlow's
# own directory rather than the shared one.
NO_PAGE = ["fid", "fidlist", "name", "remove"]

# On the shared page, but MassFlow's own filters -> MassFlow's directory.
MASSFLOW_SPECIFIC = ["active", "marker-type"]

CATEGORY_OF = {
    "geometric": [
        "annulus",
        "cylinder",
        "ellipse",
        "plane",
        "polygon",
        "position",
        "position-x",
        "position-y",
        "position-z",
        "rectangle",
        "sphere",
        "volume",
        "geometry-distance",
        "geometry-space",
        "surface",
        "orientation",
        "seed",
    ],
    "attribute": [
        "id",
        "id-list",
        "component-id",
        "component-id-list",
        "fid",
        "fidlist",
        "group",
        "name",
        "named-range",
        "cmodel",
        "state",
        "marker-type",
        "active",
        "dfn",
        "interface",
        "contact",
        "set",
        "displacement",
        "velocity",
    ],
    "user_defined": ["extra", "extra-list", "fish"],
    "logical": [
        "union",
        "not",
        "extent",
        "by",
        "selected",
        "deselected",
        "use-hidden",
        "remove",
        "project-range",
    ],
}

CATEGORY_NAME = {
    "geometric": "Geometric Elements",
    "attribute": "Attribute Elements",
    "user_defined": "User-Defined Elements",
    "logical": "Logical / Modifier Elements",
}

# Argument slot as the engine enumerated it. A value of None means the element
# is a bare flag: the engine offers only the next range element after it.
LIVE_ARGUMENT: dict[str, str | None] = {
    "active": None,
    "cmodel": "<s>",
    "component-id": "<i>",
    "component-id-list": "<i> ...",
    "contact": "<keyword> ...",
    "deselected": None,
    "dfn": "<s>",
    "displacement": "<f>",
    "fid": "<i>",
    "fidlist": "<i> ...",
    "geometry-distance": "<s>",
    "geometry-space": "<s>",
    "interface": "<name>",
    "marker-type": "<i>",
    "name": "<s>",
    "orientation": "<keyword> ...",
    "project-range": "<named-range|s>",
    "remove": "<i>",
    "seed": "<v>",
    "selected": None,
    "set": "<keyword> ...",
    "state": "<s>",
    "surface": "<keyword> ...",
    "use-hidden": None,
    "velocity": "<f>",
    "volume": "<f>",
}

# Notes that only apply on MassFlow, or that record a doc/binary divergence.
EXTRA_NOTES: dict[str, list[str]] = {
    "active": [
        "MassFlow-specific. The manual documents it on the shared range page but `_common` carries no file for it.",
        "Used by the vendor's own unittests.dat: `massflow marker list range active`.",
    ],
    "marker-type": [
        "MassFlow-specific. The manual defines five type codes (-2 unbulked for IMZ "
        "growth, -1 unbulked for collapse, 0 unbulked for rilling, 1 partially bulked, "
        "2 fully bulked) but the engine accepts integers between -2 and 3.",
        "Used by the vendor's own unittests.dat: `massflow marker list range marker-type 2`.",
    ],
    "fid": ["No page in the 9.7 manual; the argument type is read from live enumeration."],
    "fidlist": ["No page in the 9.7 manual; the argument type is read from live enumeration."],
    "name": ["No page in the 9.7 manual; the argument type is read from live enumeration."],
    "remove": ["No page in the 9.7 manual; the argument type is read from live enumeration."],
    "cmodel": [
        "Selects zones by constitutive model name. In MassFlow this only bites in a "
        "coupled FLAC3D analysis — mine blocks, drawpoints and markers have no cmodel.",
    ],
    "orientation": [
        "The engine offers no token list at this slot; the sub-keywords below come from the shared kernel manual.",
    ],
    "surface": [
        "The engine offers no token list at this slot; the sub-keywords below come from the shared kernel manual.",
    ],
}

MASSFLOW_EXAMPLES: dict[str, list[str]] = {
    "active": ["massflow marker list range active", "massflow drawpoint list range active"],
    "marker-type": ["massflow marker list range marker-type 2"],
    "group": ["massflow drawpoint group 'left' range position-x 0 1530"],
    "position-x": ["massflow mine-block group 'right' range position-x 1500 2000"],
    "position-z": ["massflow marker group 'top' range position-z 350 500"],
    "id": ["massflow mine-block list range id 1"],
}


def category_for(name: str) -> str:
    for cat, names in CATEGORY_OF.items():
        if name in names:
            return cat
    return "attribute"


def build_element_doc(name: str, page: dict[str, dict[str, Any]]) -> dict[str, Any]:
    parsed = page.get(name, {})
    argument = LIVE_ARGUMENT.get(name)
    syntax = name if argument is None else f"{name} {argument}"
    doc: dict[str, Any] = {
        "name": name,
        "category": category_for(name),
        "category_name": CATEGORY_NAME[category_for(name)],
        "syntax": syntax,
        "description": parsed.get("description") or "Accepted by the engine; not described in the 9.7 manual.",
        "search_keywords": sorted({name, *name.split("-")}),
    }
    if parsed.get("signature"):
        doc["documented_syntax"] = parsed["signature"]
    if parsed.get("sub_keywords"):
        doc["sub_keywords"] = parsed["sub_keywords"]
    notes = list(EXTRA_NOTES.get(name, []))
    if notes:
        doc["notes"] = notes
    if name in MASSFLOW_EXAMPLES:
        doc["examples"] = [f"... range {e.split(' range ', 1)[1]}" for e in MASSFLOW_EXAMPLES[name]]
        doc["command_examples"] = MASSFLOW_EXAMPLES[name]
    doc["official_documentation"] = PAGE_SOURCE if parsed.get("description") else LIVE_SOURCE
    return doc


def build_index(page: dict[str, dict[str, Any]]) -> dict[str, Any]:
    elements = []
    for name in sorted(LIVE_ELEMENTS):
        if name in ALREADY_IN_COMMON:
            existing = json.loads((COMMON_DIR / f"{name}.json").read_text(encoding="utf-8"))
            short = existing.get("description", "")
            file_ptr = f"_common/references/range-elements/{name}.json"
        elif name in NO_PAGE or name in MASSFLOW_SPECIFIC:
            short = build_element_doc(name, page)["description"]
            file_ptr = f"massflow/references/range-elements/{name}.json"
        else:
            short = build_element_doc(name, page)["description"]
            file_ptr = f"_common/references/range-elements/{name}.json"
        if len(short) > 100:
            short = short[:97] + "..."
        elements.append(
            {
                "name": name,
                "file": file_ptr,
                "short_description": short,
                "category": category_for(name),
            }
        )

    categories = {
        cat: {
            "name": CATEGORY_NAME[cat],
            "description": desc,
            "elements": [n for n in sorted(LIVE_ELEMENTS) if category_for(n) == cat],
        }
        for cat, desc in (
            ("geometric", "Select objects by spatial region."),
            ("attribute", "Select objects by ID, group, name, model, or MassFlow state."),
            ("user_defined", "Select objects by extra-variable slot or a FISH function."),
            ("logical", "Combine, invert, or scope the elements around them."),
        )
    }

    return {
        "type": "range_elements",
        "description": (
            "Range elements are the filtering syntax that follows the `range` keyword in "
            "a MassFlow command. They scope a command to a subset of drawpoints, mine "
            "blocks or markers by spatial region, by attribute, or by MassFlow state."
        ),
        "usage_pattern": {
            "syntax": "<command> ... range <element> [params] <element> [params] ...",
            "examples": [
                "massflow drawpoint group 'left' range position-x 0 1530",
                "massflow mine-block group 'right' range position-x 1500 2000",
                "massflow marker list range marker-type 2",
                "massflow marker list range active",
                "massflow mine-block list range id 1",
            ],
            "notes": [
                "Multiple range elements intersect (AND) by default; `union` switches the whole phrase to OR.",
                "`not` inverts the element it follows; `extent` requires the object's whole "
                "extent inside a geometric element rather than just its centroid.",
                "A command with no range phrase affects every object of the type it acts on.",
            ],
        },
        "categories": categories,
        "elements": elements,
        "notes": [
            "The 48 elements listed here are what MassFlow 9.7.47 enumerates. The shared "
            "kernel manual documents 61; the 13 it carries that MassFlow rejects belong to "
            "3DEC blocks, structural elements, joints, or 2D.",
            "`active` and `marker-type` are MassFlow's own filters.",
            "`fid`, `fidlist`, `name` and `remove` are accepted by the binary but have no page in the 9.7 manual.",
            "`cmodel`, `contact`, `dfn` and `interface` reach FLAC3D zone objects and only "
            "apply in a coupled analysis.",
        ],
        "related_commands": [
            "massflow drawpoint group",
            "massflow mine-block group",
            "massflow marker group",
            "massflow drawpoint list",
            "massflow mine-block list",
            "massflow marker list",
        ],
        "official_documentation": PAGE_SOURCE,
    }


CATEGORY_ENTRY = {
    "name": "Range Elements",
    "description": (
        "Geometric, attribute and logical `range ...` filters that scope a MassFlow "
        "command to a subset of drawpoints, mine blocks or markers — including "
        "MassFlow's own `active` and `marker-type`."
    ),
    "directory": "range-elements",
    "index_file": "range-elements/index.json",
    "summary": "48 range filter elements as enumerated by MassFlow 9.7 (42 shared kernel, 6 MassFlow-local)",
    "usage": "<any command> ... range <element> <args> [union|not|extent ...]",
}


def main() -> int:
    page = parse_range_page()
    MASSFLOW_DIR.mkdir(parents=True, exist_ok=True)

    wrote_common, wrote_local = 0, 0
    for name in LIVE_ELEMENTS:
        if name in ALREADY_IN_COMMON:
            continue
        doc = build_element_doc(name, page)
        if name in NO_PAGE or name in MASSFLOW_SPECIFIC:
            (MASSFLOW_DIR / f"{name}.json").write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            wrote_local += 1
        else:
            (COMMON_DIR / f"{name}.json").write_text(
                json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            wrote_common += 1

    (MASSFLOW_DIR / "index.json").write_text(
        json.dumps(build_index(page), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    ref_index = json.loads(MASSFLOW_REF_INDEX.read_text(encoding="utf-8"))
    ref_index["categories"]["range-elements"] = CATEGORY_ENTRY
    MASSFLOW_REF_INDEX.write_text(json.dumps(ref_index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"parsed {len(page)} elements from the shared kernel page")
    print(f"wrote {wrote_common} new shared docs to {COMMON_DIR}")
    print(f"wrote {wrote_local} MassFlow-local docs to {MASSFLOW_DIR}")
    print(f"MassFlow range index now lists {len(LIVE_ELEMENTS)} elements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
