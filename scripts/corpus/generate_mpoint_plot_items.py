"""Generate the MPoint (MPM) ``plot-items`` reference category.

Plot item types are engine-specific, so they cannot be borrowed from another
engine — this authors an MPoint-specific category. MPoint's distinctive
plottable entities are the material points and the background grid:
``mpoint`` (material points), ``mpoint-vector`` / ``meshnode-vector`` (vector
fields), ``mpoint-tensor`` (tensor glyphs), ``mpoint-hybrid`` (hybrid points),
``meshpoint`` (background-grid mesh points).

Every keyword list was probed live against MPoint 3D 9 via the bridge with
``plot item create <type> ?`` (and ``... <kw> ?`` to drill into color-by /
value / draw-as), then baked in here as constants so generation needs no live
binary.

Evidence grade: ``state``. The keyword *names* were already right -- all five
top-level sets matched the engine exactly. What only execution caught was
grammar: ``scale <float>`` and ``color-by label <string>`` are both rejected by
the engine, and ``meshpoint``'s ``label`` is a bare switch where
``mpoint-hybrid``'s takes a string, despite the two items having byte-identical
top-level keyword lists. All six item types were then created together on a
cycled model and the plot exported, so they are known to render; the legend
reads the set values back. ``VERIFIED_EXAMPLE_COMMANDS`` is the set actually
executed, and generation fails if a documented example is not in it.

This is the first MPoint reference category, so it also creates
``mpoint/references/index.json``.

Output (MPoint-local):
    mpoint/references/index.json                    (top index, category entry)
    mpoint/references/plot-items/index.json         (category index)
    mpoint/references/plot-items/<type>/index.json  (one per item type)
    mpoint/references/plot-items/mpoint/color-by.json (sub-item)

Usage:
    uv run python scripts/corpus/generate_mpoint_plot_items.py
"""

import json
from pathlib import Path
from typing import Any

try:
    import mpoint_dimensions as dims
except ModuleNotFoundError:  # running as a package
    from . import mpoint_dimensions as dims  # type: ignore[no-redef]

RES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
OUT = RES / "mpoint/references"
CAT_DIR = OUT / "plot-items"

# ---------------------------------------------------------------------------
# Live-probed keyword sets (MPoint 3D 9, `plot item create <type> ?`).
# ---------------------------------------------------------------------------

MPOINT_TOP = [
    "active",
    "clear",
    "clip",
    "color-by",
    "cut",
    "extra",
    "fixity",
    "global",
    "group",
    "hide-null",
    "label",
    "legend",
    "map",
    "model",
    "pixel-size",
    "quality",
    "range",
    "state",
    "transparency",
    "uniform",
    # contour-shaping modifiers (also valid at top level): above below interval
    # log maximum minimum ramp reversed
    "above",
    "below",
    "interval",
    "log",
    "maximum",
    "minimum",
    "ramp",
    "reversed",
]
# `mpoint color-by` chooses between a continuous contour and categorical label.
MPOINT_COLORBY = ["contour", "label"]
# `mpoint color-by contour <...>`: the contoured quantity is given via
# `value <name>` or `property <name>` (a string), with these display modifiers.
MPOINT_CONTOUR_MODIFIERS = [
    "above",
    "active",
    "below",
    "clip",
    "color-by",
    "component",
    "compression-positive",
    "cut",
    "hide-null",
    "interval",
    "legend",
    "log",
    "map",
    "maximum",
    "minimum",
    "pixel-size",
    "property",
    "quality",
    "ramp",
    "range",
    "reversed",
    "transparency",
    "value",
]
# Categorical colouring keywords accepted directly on the mpoint item.
MPOINT_CATEGORICAL = ["state", "model", "fixity", "group", "label", "uniform", "extra"]

# Argument types, read off `plot item create mpoint <kw> ?`. A keyword whose
# probe answers with the *parent* keyword list again takes no argument at all --
# that re-enumeration means "I am done, what next", not "I am invalid".
MPOINT_ARG_TYPES = {
    "extra": "integer between 1 and 128",
    "group": "string",
    "hide-null": "boolean",
    "interval": "float >= 1.4e-45, or the keyword 'automatic'",
    "label": "string",
    "fixity": "none (bare switch)",
    "model": "none (bare switch)",
    "state": "none (bare switch; takes an optional 'omitPast <bool>')",
    "uniform": "none (bare switch)",
}

# `mpoint state` is the one categorical switch with a modifier of its own, and
# it is spelled in camelCase -- the only such keyword in this family.
MPOINT_STATE_MODIFIER = {
    "keyword": "omitPast",
    "syntax": "state omitPast <bool>",
    "description": (
        "Omit material points whose plastic state is historical (yielded in the past but elastic "
        "now), leaving only points currently at yield. Undocumented in the official pages; found by "
        "probing 'plot item create mpoint state ?', whose keyword list is the parent list plus this."
    ),
    "verified": "state -- MPoint3D 9.7, accepted as 'state omitPast on'",
}

MPOINT_VECTOR_TOP = [
    "active",
    "by-magnitude",
    "clip",
    "color",
    "cut",
    "draw-as",
    "legend",
    "map",
    "maxnumber",
    "point-to-base",
    "quality",
    "range",
    "scale",
    "shape",
    "skip",
    "transparency",
    "value",
]
VECTOR_VALUES = ["discharge", "displacement", "fob", "velocity", "velocity-applied"]
VECTOR_DRAW_AS = ["arrow", "disk", "line"]

MPOINT_TENSOR_TOP = ["strain", "strainrate", "stress"]
# Each of the three tensor quantities opens the same 13-keyword sub-context
# (`plot item create mpoint-tensor stress ?`). This level was previously
# undocumented, so the reference stopped at "stress [...]".
TENSOR_SUB_KEYWORDS = [
    "active",
    "clip",
    "color-by",
    "color-list",
    "cut",
    "legend",
    "line",
    "map",
    "maxnumber",
    "range",
    "scale",
    "skip",
    "transparency",
]

# mpoint-hybrid and meshpoint share this lighter grid-point keyword set.
GRIDPOINT_TOP = [
    "active",
    "clear",
    "clip",
    "cut",
    "global",
    "label",
    "legend",
    "map",
    "pixel-size",
    "quality",
    "range",
    "transparency",
]


def _kw(name: str, desc: str, syntax: str) -> dict[str, str]:
    return {"keyword": name, "description": desc, "syntax": syntax}


SHARED_KW = {
    "active": _kw("active", "Show or hide the item without removing it.", "active <bool>"),
    "range": _kw(
        "range",
        "Filter which entities are drawn using range elements (see references/range-elements).",
        "range <range-element> [...]",
    ),
    "legend": _kw("legend", "Show/configure the item legend.", "legend <sub-keyword> [<value>]"),
    "transparency": _kw(
        "transparency", "Set item transparency (0 opaque .. 100 fully transparent).", "transparency <0-100>"
    ),
    "cut": _kw("cut", "Apply a 3D cutting plane to the item.", "cut active on origin (x,y,z) normal (nx,ny,nz)"),
    "clip": _kw("clip", "Clip the item against the global model clip box.", "clip <bool>"),
    "map": _kw("map", "Configure the contour colour map (ranges, intervals, colours).", "map <sub-keyword> [<value>]"),
    "color-by": _kw(
        "color-by",
        "Choose continuous (contour) or categorical (label) colouring. See sub-item 'color-by'.",
        "color-by <contour|label> ...",
    ),
    # 'label' is NOT uniform across item types, despite mpoint-hybrid and
    # meshpoint having byte-identical top-level keyword lists. On mpoint and
    # mpoint-hybrid it takes a string; on meshpoint it is a bare switch opening
    # a categorical sub-context. Items pick the right one via LABEL_KW.
    "label": _kw("label", "Categorical colour/label by a named attribute.", "label <string>"),
    "state": _kw(
        "state",
        "Colour material points by constitutive-model state (elastic/plastic/yielded). Bare switch; "
        "accepts an optional 'omitPast <bool>' to drop points that only yielded in the past.",
        "state [omitPast <bool>]",
    ),
    "model": _kw("model", "Colour material points by the assigned constitutive model. Bare switch.", "model"),
    "fixity": _kw("fixity", "Colour material points by velocity/fluid fixity condition. Bare switch.", "fixity"),
    "group": _kw("group", "Colour material points by group (optionally a slot).", "group <string> [slot <slot>]"),
    "value": _kw(
        "value", "Vector quantity to draw (discharge/displacement/fob/velocity/velocity-applied).", "value <quantity>"
    ),
    "draw-as": _kw("draw-as", "Glyph used to draw each vector.", "draw-as <arrow|disk|line>"),
    # 'scale <float>' is rejected by the engine: scale takes a mode keyword
    # first. 'scale value 2.0' is the literal form, confirmed by the rendered
    # legend reading back "Scale: 2".
    "scale": _kw(
        "scale",
        "Scale the drawn glyphs. Takes a mode keyword, not a bare number: 'value <float>' for a "
        "fixed factor, 'automatic' to let the plot fit them, 'target' to size against a target.",
        "scale <automatic | target | value <float>>",
    ),
    "by-magnitude": _kw("by-magnitude", "Colour vectors by their magnitude.", "by-magnitude <bool>"),
    "skip": _kw("skip", "Draw every Nth vector to thin a dense field.", "skip <int <= 1000>"),
    "maxnumber": _kw(
        "maxnumber",
        "Cap how many glyphs are drawn.",
        "maxnumber <int between 10 and 1000000000>",
    ),
    "global": _kw("global", "Draw across the whole model (ignore per-plot clipping).", "global <bool>"),
    "quality": _kw("quality", "Rendering quality / point tessellation level.", "quality <int>"),
}


# Per-item overrides for keywords that share a name but not a grammar.
# 'meshpoint label' is the one case found: same spelling, same position in a
# byte-identical top-level list, different arity.
MESHPOINT_LABEL_KW = _kw(
    "label",
    "Bare switch that turns on categorical colouring of grid nodes and opens a sub-context: "
    "'label extra <1..128>', 'label fixity', 'label group <string>', 'label uniform'. Unlike "
    "mpoint-hybrid's 'label', it takes no string of its own -- 'label \"name\"' is rejected.",
    "label [extra <int> | fixity | group <string> | uniform | ...]",
)
MESHPOINT_LABEL_SUB = ["extra", "fixity", "group", "uniform"]

ITEM_KW_OVERRIDES: dict[str, dict[str, dict[str, str]]] = {
    "meshpoint": {"label": MESHPOINT_LABEL_KW},
}


def _basic(keywords: list[str], item: str | None = None) -> list[dict[str, str]]:
    over = ITEM_KW_OVERRIDES.get(item or "", {})
    return [over.get(k, SHARED_KW[k]) for k in keywords if k in SHARED_KW]


PROBE_NOTE = (
    "Probe live with 'plot item create <type> ?' to list top-level keywords, then "
    "'plot item create <type> <kw> ?' for sub-options. Do NOT probe with a bogus token: "
    "'plot item create <type> zzbogus' creates the item and then reports 'Unused extra parameter' "
    "without ever enumerating. Keyword sets here are binary-validated against MPoint 3D 9."
)

# Every command in a `common_usage_patterns` entry, executed on the live engine.
# A documented example that was never run is how 'scale 1.0' shipped broken: the
# keyword is real, the item is real, and the line is still rejected.
VERIFIED_EXAMPLE_COMMANDS = [
    "plot item create meshpoint active on",
    "plot item create mpoint color-by contour value stress-zz legend active on",
    "plot item create mpoint color-by contour value displacement legend active on",
    "plot item create mpoint state legend active on",
    "plot item create mpoint model legend active on",
    "plot item create mpoint-hybrid active on",
    "plot item create mpoint-tensor stress legend active on",
    "plot item create mpoint-tensor stress scale value 1.5",
    "plot item create mpoint-vector value velocity draw-as arrow scale value 1.0",
    "plot item create mpoint-vector value displacement by-magnitude on",
    "plot item create meshnode-vector value velocity draw-as arrow",
]

LIVE_VERIFICATION = {
    "grade": "state",
    "engine": "MPoint3D 9.7 (Itasca Software Subscription)",
    "date": "2026-09-14",
    "method": (
        "Keyword sets enumerated with 'plot item create <type> ?' and drilled down with "
        "'<kw> ?'. Then all six item types were created together on a cycled 8-point model and "
        "the plot exported to a bitmap, so the items are known to render, not merely to parse. "
        "The rendered legend reads the values back ('Scale: 2', 'Scale: 1.5'), which is what "
        "confirms the corrected 'scale value <float>' form."
    ),
    "corrections": [
        "'scale <float>' was wrong for mpoint-vector and mpoint-tensor: scale takes a mode keyword "
        "first ('scale value 2.0'). A bare 'scale 2.0' is rejected.",
        "'color-by label <string>' was wrong: the label mode takes no argument.",
        "meshpoint's 'label' was documented as 'label <string>' copied from mpoint-hybrid. It is "
        "actually a bare switch opening a categorical sub-context.",
    ],
    "additions": [
        "mpoint-tensor's three quantities each expose a 13-keyword sub-context that was undocumented.",
        "'state omitPast <bool>' -- an undocumented camelCase modifier.",
        "Argument types and bounds for the top-level keywords (extra 1..128, skip <=1000, "
        "maxnumber 10..1e9, interval float|automatic, and which keywords are bare switches).",
    ],
    "traps": [
        "A keyword probe that answers with the item's own top-level list again means the keyword "
        "is a BARE SWITCH that consumed nothing -- not that it was rejected. 'fixity', 'model', "
        "'uniform' and 'color-by label' all look 'invalid' this way.",
        "Identical top-level keyword lists do not imply identical grammar. mpoint-hybrid and "
        "meshpoint have byte-identical 12-keyword lists, but their 'label' keywords differ in "
        "arity. The previous docs shared one description between them and were wrong for one.",
        "Item types enumerate across ALL engines on the unified binary (ball, block, structure-*, "
        "zone-*, cfd*, fracture ...). Only the mpoint/meshpoint family belongs to this engine; "
        "the rest are documented under their owning engine.",
    ],
}

ITEMS: list[dict[str, Any]] = [
    {
        "name": "mpoint",
        "item_types": ["mpoint"],
        "search_keywords": ["material point", "mpoint", "stress", "displacement", "state", "model", "contour"],
        "description": (
            "Material points — the core MPM entity. Colour by a continuous field via 'color-by contour "
            "value <quantity>' (or 'property <name>'), or categorically by 'state' (constitutive-model "
            "state), 'model' (assigned cmodel), 'fixity', or 'group'."
        ),
        "base_syntax": "plot item create mpoint <keywords...>",
        "top_level_keywords": sorted(set(MPOINT_TOP)),
        "basic_keywords": _basic(
            [
                "active",
                "color-by",
                "state",
                "model",
                "fixity",
                "group",
                "label",
                "range",
                "legend",
                "map",
                "cut",
                "transparency",
            ]
        ),
        "sub_items": [
            {
                "name": "color-by",
                "file": "color-by.json",
                "description": "Continuous contour (value/property) vs categorical label colouring of material points.",
            },
        ],
        "common_usage_patterns": [
            {
                "use_case": "Stress field",
                "command": "plot item create mpoint color-by contour value stress-zz legend active on",
                "description": "Contour material points by a stress component.",
            },
            {
                "use_case": "Displacement",
                "command": "plot item create mpoint color-by contour value displacement legend active on",
                "description": "Continuous displacement-magnitude colour map.",
            },
            {
                "use_case": "Model state",
                "command": "plot item create mpoint state legend active on",
                "description": "Colour points by constitutive-model state (elastic/plastic).",
            },
            {
                "use_case": "By constitutive model",
                "command": "plot item create mpoint model legend active on",
                "description": "Colour points by their assigned cmodel.",
            },
        ],
        "_colorby": True,
    },
    {
        "name": "mpoint-vector",
        "item_types": ["mpoint-vector", "meshnode-vector"],
        "search_keywords": ["vector", "velocity", "displacement", "discharge", "material point", "background node"],
        "description": (
            "Vector field drawn at material points. 'value' selects the quantity (velocity, displacement, "
            "discharge, fob, velocity-applied); 'draw-as' picks the glyph (arrow/disk/line). The "
            "'meshnode-vector' item draws the same vector quantities at background-grid nodes with an "
            "identical keyword set."
        ),
        "base_syntax": "plot item create mpoint-vector <keywords...>",
        "top_level_keywords": MPOINT_VECTOR_TOP,
        "basic_keywords": _basic(
            ["active", "value", "draw-as", "scale", "by-magnitude", "skip", "range", "legend", "map", "transparency"]
        ),
        "sub_items": [],
        "common_usage_patterns": [
            {
                "use_case": "Velocity arrows",
                "command": "plot item create mpoint-vector value velocity draw-as arrow scale value 1.0",
                "description": "Velocity vectors at material points.",
            },
            {
                "use_case": "Displacement field",
                "command": "plot item create mpoint-vector value displacement by-magnitude on",
                "description": "Displacement vectors coloured by magnitude.",
            },
            {
                "use_case": "Grid-node velocity",
                "command": "plot item create meshnode-vector value velocity draw-as arrow",
                "description": "Same vectors at the background-grid nodes.",
            },
        ],
        "notes_extra": [
            "value quantities: " + ", ".join(VECTOR_VALUES) + ".",
            "draw-as glyphs: " + ", ".join(VECTOR_DRAW_AS) + ".",
            "meshnode-vector shares this exact keyword set (drawn at grid nodes instead of material points).",
        ],
    },
    {
        "name": "mpoint-tensor",
        "item_types": ["mpoint-tensor"],
        "search_keywords": ["tensor", "stress", "strain", "strainrate", "material point", "glyph"],
        "description": (
            "Tensor glyphs at material points. Pick the tensor field: 'stress', 'strain', or 'strainrate'. "
            "Useful for visualising principal-stress orientation and magnitude across the MPM body."
        ),
        "base_syntax": "plot item create mpoint-tensor <stress|strain|strainrate> [...]",
        "top_level_keywords": MPOINT_TENSOR_TOP,
        "basic_keywords": [
            _kw("stress", "Draw the stress tensor glyph at each material point.", "stress [<sub-keyword> ...]"),
            _kw("strain", "Draw the strain tensor glyph.", "strain [<sub-keyword> ...]"),
            _kw("strainrate", "Draw the strain-rate tensor glyph.", "strainrate [<sub-keyword> ...]"),
        ],
        "sub_items": [
            {
                "name": quantity,
                "syntax": f"plot item create mpoint-tensor {quantity} [<sub-keyword> ...]",
                "description": (
                    f"Tensor glyphs for the {quantity} field. All display keywords live at this level, "
                    "not at the item's top level, which offers only the three quantities."
                ),
                "keywords": TENSOR_SUB_KEYWORDS,
                "verified": "state -- MPoint3D 9.7, identical 13-keyword set for all three quantities",
            }
            for quantity in MPOINT_TENSOR_TOP
        ],
        "common_usage_patterns": [
            {
                "use_case": "Stress tensor",
                "command": "plot item create mpoint-tensor stress legend active on",
                "description": "Principal-stress glyphs at material points.",
            },
            {
                "use_case": "Fixed glyph size",
                "command": "plot item create mpoint-tensor stress scale value 1.5",
                "description": "'scale' needs the 'value' keyword; a bare 'scale 1.5' is rejected.",
            },
        ],
    },
    {
        "name": "mpoint-hybrid",
        "item_types": ["mpoint-hybrid"],
        "search_keywords": ["hybrid", "coupled", "material point", "gridpoint coupling"],
        "description": (
            "Hybrid material points — points coupled to the background grid via 'mpoint hybrid-points'. "
            "Lighter keyword set (geometry/label/clip), for showing where MPM couples to gridpoints."
        ),
        "base_syntax": "plot item create mpoint-hybrid <keywords...>",
        "top_level_keywords": GRIDPOINT_TOP,
        "basic_keywords": _basic(["active", "label", "global", "range", "legend", "map", "cut", "transparency"]),
        "sub_items": [],
        "common_usage_patterns": [
            {
                "use_case": "Show hybrid points",
                "command": "plot item create mpoint-hybrid active on",
                "description": "Render the coupled hybrid material points.",
            },
        ],
    },
    {
        "name": "meshpoint",
        "item_types": ["meshpoint"],
        "search_keywords": ["mesh point", "background grid", "node", "grid"],
        "description": (
            "Background-grid mesh points — the fixed computational grid through which material points move. "
            "Use to inspect the grid resolution and extent relative to the material-point body."
        ),
        "base_syntax": "plot item create meshpoint <keywords...>",
        "top_level_keywords": GRIDPOINT_TOP,
        "basic_keywords": _basic(
            ["active", "label", "global", "range", "legend", "map", "cut", "transparency"], item="meshpoint"
        ),
        "sub_items": [
            {
                "name": "label",
                "syntax": "plot item create meshpoint label [<sub-keyword> ...]",
                "description": (
                    "Categorical colouring of grid nodes. 'label' itself takes no argument; it opens a "
                    "sub-context whose keywords are NOT offered at the item's top level."
                ),
                "keywords": MESHPOINT_LABEL_SUB,
                "verified": "state -- MPoint3D 9.7; each sub-keyword accepted after 'label', rejected before it",
            }
        ],
        "common_usage_patterns": [
            {
                "use_case": "Show background grid",
                "command": "plot item create meshpoint active on",
                "description": "Render the background-grid mesh points.",
            },
        ],
    },
]


def _write_colorby(item_dir: Path) -> None:
    doc = {
        "name": "color-by",
        "parent_item": "mpoint",
        "description": "Colour material points continuously ('contour') or categorically ('label'), probed against MPoint 3D 9.",
        "base_syntax": "plot item create mpoint color-by <contour|label> ...",
        "modes": [
            {
                "mode": "contour",
                "syntax": "color-by contour value <quantity> | color-by contour property <name>",
                "description": "Continuous field colouring. The quantity is given by 'value <name>' (built-in field) or 'property <name>' (named property), not a fixed keyword enum.",
                "modifiers": MPOINT_CONTOUR_MODIFIERS,
            },
            {
                "mode": "label",
                "syntax": "color-by label",
                "description": (
                    "Switches the item to categorical colouring. Takes no argument of its own -- "
                    "'color-by label \"name\"' is rejected. Pick the attribute with one of the "
                    "categorical keywords that follow it (" + ", ".join(MPOINT_CATEGORICAL) + "). "
                    "Note the item's own top-level 'label' is different and DOES take a string."
                ),
                "modifiers": MPOINT_CATEGORICAL,
                "verified": "state -- MPoint3D 9.7",
            },
        ],
        "categorical_keywords": MPOINT_CATEGORICAL,
        "notes": [
            "For built-in vector quantities (velocity, displacement) prefer the 'mpoint-vector' item.",
            "'state' / 'model' / 'fixity' / 'group' are accepted directly on the mpoint item for categorical colouring.",
            PROBE_NOTE,
        ],
    }
    (item_dir / "color-by.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", "utf-8")


def main() -> None:
    CAT_DIR.mkdir(parents=True, exist_ok=True)
    catalog = []
    for item in ITEMS:
        name = item["name"]
        item_dir = CAT_DIR / name
        item_dir.mkdir(exist_ok=True)
        doc: dict[str, Any] = {
            "name": name,
            "item_type": name,
            "item_types": item["item_types"],
            "dimension": "mixed",
            "search_keywords": item["search_keywords"],
            "description": item["description"],
            "base_syntax": item["base_syntax"],
            "top_level_keywords": item["top_level_keywords"],
            "basic_keywords": item["basic_keywords"],
            "sub_items": item.get("sub_items", []),
            "common_usage_patterns": item["common_usage_patterns"],
            "notes": [PROBE_NOTE, *item.get("notes_extra", [])],
        }
        doc["dimension_differences"] = {
            "3d_only_keywords": [k for k in dims.PLOT_KEYWORDS_3D_ONLY if k in item["top_level_keywords"]],
            "mpoint2d_only_keywords": (dims.PLOT_KEYWORDS_2D_ONLY if name in dims.PLOT_2D_ONLY_APPLIES_TO else []),
            "note": dims.PLOT_KEYWORD_NOTE,
        }
        if name == "mpoint":
            # Argument types matter more than keyword names here: an LLM that
            # knows 'extra' exists still cannot write the command without
            # knowing it wants an integer in 1..128.
            doc["keyword_argument_types"] = MPOINT_ARG_TYPES
            doc["undocumented_modifiers"] = [MPOINT_STATE_MODIFIER]
        (item_dir / "index.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", "utf-8")
        if item.get("_colorby"):
            _write_colorby(item_dir)
        catalog.append(
            {
                "name": name,
                "file": f"{name}/index.json",
                "description": item["description"].split(".")[0] + ".",
                "common_use": ", ".join(item["item_types"]),
            }
        )
        print(
            f"  {name:<16} types={len(item['item_types'])} top_kw={len(item['top_level_keywords'])} subs={len(item.get('sub_items', []))}"
        )

    documented = [u["command"] for it in ITEMS for u in it["common_usage_patterns"]]
    unverified = sorted(set(documented) - set(VERIFIED_EXAMPLE_COMMANDS))
    unused = sorted(set(VERIFIED_EXAMPLE_COMMANDS) - set(documented))
    if unverified or unused:
        raise SystemExit(
            "documented examples must match the set executed on the engine:\n"
            f"  documented but never run : {unverified}\n"
            f"  run but not documented   : {unused}"
        )

    (CAT_DIR / "index.json").write_text(
        json.dumps(
            {
                "type": "plot_item_keywords",
                "description": (
                    "Configuration keywords for MPoint (MPM) plot item types created via "
                    "'plot item create <type>'. Item types and keyword sets are binary-validated against "
                    "MPoint 3D 9."
                ),
                "usage_context": "plot item create <type> <keyword> <keyword> ...",
                "items": catalog,
                "live_verification": LIVE_VERIFICATION,
                "verified_example_commands": VERIFIED_EXAMPLE_COMMANDS,
                "dimension_differences": {
                    "item_types": "identical -- all six exist on both binaries",
                    "3d_only_keywords": dims.PLOT_KEYWORDS_3D_ONLY,
                    "mpoint2d_only_keywords": dims.PLOT_KEYWORDS_2D_ONLY,
                    "mpoint2d_only_applies_to": dims.PLOT_2D_ONLY_APPLIES_TO,
                    "note": dims.PLOT_KEYWORD_NOTE,
                    "verified": dims.DIMENSION_VERIFICATION,
                },
                "notes": [
                    "Plot-item keywords are appended after the item type.",
                    PROBE_NOTE,
                    "MPoint also accepts the shared/other-engine plot items (zone, structure-*, fracture, "
                    "geometry, chart-*, ...); this documents the MPoint-specific material-point and "
                    "background-grid entities.",
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        "utf-8",
    )

    # First MPoint reference category — create the top references index.
    top_path = OUT / "index.json"
    if top_path.exists():
        top = json.loads(top_path.read_text(encoding="utf-8"))
    else:
        top = {
            "type": "mpoint_references",
            "description": "MPoint (MPM) reference documentation: syntax elements (property vocabularies) used within commands.",
            "categories": {},
            "navigation": {
                "root": "List all reference categories",
                "category": "List items in category (e.g., 'plot-items')",
                "item": "Full documentation (e.g., 'plot-items mpoint')",
            },
            "notes": [
                "References are syntax elements used within commands, not standalone commands",
                "Use itasca_browse_commands (software='mpoint') for command syntax",
                "Use itasca_browse_reference (software='mpoint') for reference documentation",
            ],
        }
    top.setdefault("categories", {})["plot-items"] = {
        "name": "Plot Items",
        "description": (
            "MPoint plot item types — material points (mpoint), vector/tensor fields "
            "(mpoint-vector/meshnode-vector, mpoint-tensor), hybrid points (mpoint-hybrid) and the "
            "background grid (meshpoint). Vocabulary for 'plot item create <type> ...'."
        ),
        "directory": "plot-items",
        "index_file": "plot-items/index.json",
        "summary": f"{len(catalog)} MPoint plot item groups (mpoint/vector/tensor/hybrid/meshpoint)",
        "usage": "plot item create mpoint color-by contour value <q> | plot item create mpoint-vector value velocity ...",
    }
    top_path.write_text(json.dumps(top, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"\nWrote {CAT_DIR} ({len(catalog)} plot item groups) + top references index")


if __name__ == "__main__":
    main()
