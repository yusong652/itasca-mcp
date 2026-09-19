"""Generate the MassFlow ``plot-items`` reference category.

Plot item types are engine-specific, so they cannot be borrowed — this authors a
MassFlow-specific category. MassFlow's distinctive plottable entities are the
gravity-flow / caving objects: drawpoints, the orebody mine-blocks, isolated
movement zones (IMZ), provenance markers (live + extracted), the flow vector
field, particle traces, and history sampling locations.

Every keyword set was probed live against MassFlow 3D 9 via the bridge with
``plot item create <type> ?`` (and ``... <kw> ?`` to drill into colorby /
color-by / size-by), then baked here as constants so generation needs no live
binary. Binary keyword spellings are preserved verbatim (including the binary's
``meandiamter-dyn`` typo) so the docs match what the engine actually accepts.

Output (MassFlow-local):
    massflow/references/index.json                    (top index, category entry)
    massflow/references/plot-items/index.json         (category index)
    massflow/references/plot-items/<type>/index.json  (one per item group)
    massflow/references/plot-items/<type>/color-by.json (sub-item, where rich)

Usage:
    uv run python scripts/corpus/generate_massflow_plot_items.py
"""

import json
from pathlib import Path
from typing import Any

RES = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources")
OUT = RES / "massflow/references"
CAT_DIR = OUT / "plot-items"

# ---------------------------------------------------------------------------
# Live-probed keyword sets (MassFlow 3D 9, `plot item create <type> ?`).
# ---------------------------------------------------------------------------

# drawpoint / mineblock / imz share this top-level set.
POLYGON_TOP = [
    "active",
    "clip",
    "color-list",
    "colorby",
    "contour",
    "cut",
    "cut-line",
    "label",
    "legend",
    "map",
    "polygons",
    "range",
    "transparency",
]
# marker / marker-extracted top-level set.
MARKER_TOP = [
    "active",
    "clip",
    "color-by",
    "color-list",
    "contour",
    "group",
    "legend",
    "map",
    "mark",
    "pixel-size",
    "range",
    "scale",
    "size-by",
    "transparency",
]
FLOW_VECTOR_TOP = [
    "active",
    "by-magnitude",
    "clip",
    "color",
    "color-list",
    "color-mode",
    "cut",
    "draw-as",
    "legend",
    "point-to-base",
    "quality",
    "range",
    "scale",
    "shape",
    "transparency",
]
PARTICLE_TRACE_TOP = ["active", "contour", "legend", "line", "skip", "trace-name", "transparency"]
CHART_TABLE_TOP = [
    "active",
    "axis-x",
    "axis-y",
    "chart",
    "labels",
    "legend",
    "marks",
    "swap",
    "table",
    "title",
    "transparency",
]

CHART_HISTORY_TOP = [
    "active",
    "axis-x",
    "axis-y",
    "begin",
    "chart",
    "end",
    "history",
    "labels",
    "legend",
    "marks",
    "skip",
    "swap",
    "title",
    "transparency",
    "vs",
]

HISTORY_LOC_TOP = [
    "active",
    "color-list",
    "cut",
    "legend",
    "mark",
    "numbers",
    "pixel-size",
    "range",
    "scale",
    "transparency",
]

# `colorby` categorical attribute sets (per item, live-probed).
DRAWPOINT_COLORBY = ["dpactive", "drawbell", "extra", "group", "uniform"]
MINEBLOCK_COLORBY = [
    "caved",
    "density",
    "fric",
    "group",
    "inimaxporos",
    "iniporos",
    "meandiameter",
    "meandiamter-dyn",
    "period",
    "period-dyn",
    "state",
    "ucs",
]
IMZ_COLORBY = ["group", "uniform"]
# marker uses `color-by <contour|label>` (modes) + `size-by <...>`.
MARKER_COLORBY_MODES = ["contour", "label"]
MARKER_SIZE_BY = ["meanDiameter", "pixels", "uniform"]
# contour display modifiers (drawpoint/mineblock/imz `contour ...`, live-probed).
CONTOUR_MODIFIERS = [
    "above",
    "below",
    "interval",
    "log",
    "maximum",
    "minimum",
    "ramp",
    "reversed",
    "value",
    "extra",
    "legend",
    "map",
    "range",
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
    "cut-line": _kw("cut-line", "Draw the outline where a cutting plane intersects the item.", "cut-line <bool>"),
    "clip": _kw("clip", "Clip the item against the global model clip box.", "clip <bool>"),
    "map": _kw("map", "Configure the contour colour map (ranges, intervals, colours).", "map <sub-keyword> [<value>]"),
    "color-list": _kw("color-list", "Set the discrete colour list used for categorical colouring.", "color-list ..."),
    "colorby": _kw(
        "colorby",
        "Categorical colouring by a named attribute. See sub-item 'color-by' for the attribute set.",
        "colorby <attribute>",
    ),
    "color-by": _kw(
        "color-by",
        "Choose continuous (contour) or categorical (label) colouring. See sub-item 'color-by'.",
        "color-by <contour|label> ...",
    ),
    "contour": _kw(
        "contour",
        "Continuous contour colouring of a value, with display modifiers (above/below/log/ramp/...).",
        "contour value <quantity> [modifiers...]",
    ),
    "label": _kw("label", "Categorical colour/label by a named attribute.", "label <string>"),
    "polygons": _kw("polygons", "Draw the item as filled polygons.", "polygons <bool>"),
    "mark": _kw("mark", "Marker glyph drawn at each location.", "mark <glyph>"),
    "pixel-size": _kw("pixel-size", "Marker size in pixels.", "pixel-size <int>"),
    "scale": _kw("scale", "Scale factor for the drawn glyphs/vectors.", "scale <float>"),
    "size-by": _kw(
        "size-by",
        "Size markers by an attribute (meanDiameter/pixels/uniform).",
        "size-by <meanDiameter|pixels|uniform>",
    ),
    "group": _kw("group", "Colour/filter by group (optionally a slot).", "group [slot <slot>]"),
    "numbers": _kw("numbers", "Annotate each location with its history number.", "numbers <bool>"),
    "by-magnitude": _kw("by-magnitude", "Colour vectors by their magnitude.", "by-magnitude <bool>"),
    "color": _kw("color", "Set a single uniform vector colour.", "color <color>"),
    "color-mode": _kw("color-mode", "Vector colouring mode (uniform vs by-magnitude).", "color-mode <mode>"),
    "draw-as": _kw("draw-as", "Glyph used to draw each vector.", "draw-as <arrow|...>"),
    "shape": _kw("shape", "Vector glyph shape.", "shape <shape>"),
    "point-to-base": _kw("point-to-base", "Anchor vectors at their base point.", "point-to-base <bool>"),
    "quality": _kw("quality", "Rendering quality / tessellation level.", "quality <int>"),
    "line": _kw("line", "Draw traces as connected lines.", "line <bool>"),
    "skip": _kw("skip", "Draw every Nth trace/marker to thin a dense field.", "skip <int>"),
    "trace-name": _kw("trace-name", "Select which named particle trace to draw.", "trace-name <string>"),
    "table": _kw("table", "Table to plot, by name or number.", "table <name>"),
    "history": _kw("history", "History to plot, by name or number.", "history <name>"),
    "chart": _kw("chart", "Chart style and series appearance.", "chart <sub-keyword> [<value>]"),
    "axis-x": _kw("axis-x", "Configure the x axis (label, log, limits, exponent).", "axis-x <sub-keyword> [<value>]"),
    "axis-y": _kw("axis-y", "Configure the y axis (label, log, limits, exponent).", "axis-y <sub-keyword> [<value>]"),
    "labels": _kw("labels", "Show per-point value labels.", "labels <bool>"),
    "marks": _kw("marks", "Draw a glyph at each data point.", "marks <bool>"),
    "swap": _kw("swap", "Swap the x and y series.", "swap <bool>"),
    "title": _kw("title", "Chart title.", "title <string>"),
    "begin": _kw("begin", "First step/value of the history to plot.", "begin <value>"),
    "end": _kw("end", "Last step/value of the history to plot.", "end <value>"),
    "vs": _kw("vs", "Plot this history against another one instead of against step.", "vs <name>"),
}


def _basic(keywords: list[str]) -> list[dict[str, str]]:
    return [SHARED_KW[k] for k in keywords if k in SHARED_KW]


# `plot item create ?` on MassFlow 9.7.47, verbatim.
BINARY_ITEM_TYPES = [
    "axes",
    "chart-history",
    "chart-table",
    "data-label",
    "data-scalar",
    "data-tensor",
    "data-vector",
    "drawpoint",
    "flow-vector",
    "fos",
    "fracture",
    "geometry",
    "history-locations",
    "imz",
    "marker",
    "marker-extracted",
    "mineblock",
    "particle-trace",
    "particle-trace-marker",
    "scalebox",
]

PROBE_NOTE = (
    "Probe live with 'plot item create <type> ?' to list top-level keywords, then "
    "'plot item create <type> <kw> ?' for sub-options. Keyword sets here are binary-validated "
    "against MassFlow 3D 9."
)

ITEMS: list[dict[str, Any]] = [
    {
        "name": "drawpoint",
        "item_types": ["drawpoint"],
        "search_keywords": ["drawpoint", "draw", "extraction", "drawbell", "caving"],
        "description": (
            "Drawpoints — the extraction points that drive gravity flow. Colour categorically with "
            "'colorby' (dpactive/drawbell/extra/group/uniform) or continuously with 'contour value <q>'."
        ),
        "base_syntax": "plot item create drawpoint <keywords...>",
        "top_level_keywords": POLYGON_TOP,
        "basic_keywords": _basic(
            ["active", "colorby", "contour", "label", "polygons", "range", "legend", "map", "cut", "transparency"]
        ),
        "colorby_attributes": DRAWPOINT_COLORBY,
        "common_usage_patterns": [
            {
                "use_case": "Active drawpoints",
                "command": "plot item create drawpoint colorby dpactive legend active on",
                "description": "Colour drawpoints by whether they are currently active.",
            },
            {
                "use_case": "By drawbell",
                "command": "plot item create drawpoint colorby drawbell",
                "description": "Colour drawpoints by their drawbell assignment.",
            },
        ],
        "_colorby_kind": "categorical",
    },
    {
        "name": "mineblock",
        "item_types": ["mineblock"],
        "search_keywords": ["mineblock", "mine-block", "orebody", "grade", "ucs", "porosity", "fragmentation"],
        "description": (
            "Mine-blocks — the tagged orebody cells carrying grade/material state. Rich categorical "
            "colouring via 'colorby' (caved/density/fric/porosity/meandiameter/period/state/ucs/...)."
        ),
        "base_syntax": "plot item create mineblock <keywords...>",
        "top_level_keywords": POLYGON_TOP,
        "basic_keywords": _basic(
            ["active", "colorby", "contour", "label", "polygons", "range", "legend", "map", "cut", "transparency"]
        ),
        "colorby_attributes": MINEBLOCK_COLORBY,
        "common_usage_patterns": [
            {
                "use_case": "Caved state",
                "command": "plot item create mineblock colorby caved legend active on",
                "description": "Colour mine-blocks by whether they have caved.",
            },
            {
                "use_case": "Compressive strength",
                "command": "plot item create mineblock colorby ucs legend active on",
                "description": "Colour mine-blocks by UCS (uniaxial compressive strength).",
            },
            {
                "use_case": "Mean fragment size",
                "command": "plot item create mineblock colorby meandiameter",
                "description": "Colour by mean fragment diameter.",
            },
        ],
        "_colorby_kind": "categorical",
    },
    {
        "name": "imz",
        "item_types": ["imz"],
        "search_keywords": ["imz", "isolated movement zone", "movement", "draw"],
        "description": (
            "Isolated Movement Zones (IMZ) — the volumes of material mobilised above a drawpoint. "
            "Colour by 'colorby group' or 'uniform', or contour a value."
        ),
        "base_syntax": "plot item create imz <keywords...>",
        "top_level_keywords": POLYGON_TOP,
        "basic_keywords": _basic(
            ["active", "colorby", "contour", "label", "polygons", "range", "legend", "map", "cut", "transparency"]
        ),
        "colorby_attributes": IMZ_COLORBY,
        "common_usage_patterns": [
            {
                "use_case": "Show IMZ by group",
                "command": "plot item create imz colorby group",
                "description": "Render isolated movement zones coloured by group.",
            },
        ],
        "_colorby_kind": "categorical",
    },
    {
        "name": "marker",
        "item_types": ["marker", "marker-extracted"],
        "search_keywords": ["marker", "provenance", "trace", "extracted", "size-by", "fragment"],
        "description": (
            "Provenance markers seeded in the rock mass to trace material flow. 'color-by' selects "
            "continuous (contour) vs categorical (label) colouring; 'size-by' scales glyphs by "
            "meanDiameter/pixels/uniform. The 'marker-extracted' item draws markers already drawn "
            "through a drawpoint with an identical keyword set."
        ),
        "base_syntax": "plot item create marker <keywords...>",
        "top_level_keywords": MARKER_TOP,
        "basic_keywords": _basic(
            ["active", "color-by", "size-by", "mark", "pixel-size", "scale", "group", "range", "legend", "transparency"]
        ),
        "common_usage_patterns": [
            {
                "use_case": "Markers by size",
                "command": "plot item create marker size-by meanDiameter",
                "description": "Scale marker glyphs by mean fragment diameter.",
            },
            {
                "use_case": "Extracted markers",
                "command": "plot item create marker-extracted color-by label group",
                "description": "Show markers already extracted, coloured by group.",
            },
        ],
        "notes_extra": [
            "marker-extracted shares this exact keyword set (draws only extracted markers).",
            "size-by options: " + ", ".join(MARKER_SIZE_BY) + ".",
        ],
        "_colorby_kind": "marker",
    },
    {
        "name": "flow-vector",
        "item_types": ["flow-vector"],
        "search_keywords": ["flow", "vector", "velocity", "draw-as", "by-magnitude"],
        "description": (
            "Material flow velocity vectors. 'draw-as'/'shape' pick the glyph, 'by-magnitude'/'color-mode' "
            "control colouring, 'scale' sizes the arrows."
        ),
        "base_syntax": "plot item create flow-vector <keywords...>",
        "top_level_keywords": FLOW_VECTOR_TOP,
        "basic_keywords": _basic(
            [
                "active",
                "draw-as",
                "shape",
                "by-magnitude",
                "color",
                "color-mode",
                "scale",
                "point-to-base",
                "range",
                "legend",
                "transparency",
            ]
        ),
        "common_usage_patterns": [
            {
                "use_case": "Flow arrows by magnitude",
                "command": "plot item create flow-vector draw-as arrow by-magnitude on scale 1.0",
                "description": "Velocity arrows coloured by magnitude.",
            },
        ],
    },
    {
        "name": "particle-trace",
        "item_types": ["particle-trace", "particle-trace-marker"],
        "search_keywords": ["particle", "trace", "streamline", "trace-name", "path"],
        "description": (
            "Particle traces — streamline paths of tracked material. 'trace-name' selects the named "
            "trace, 'line'/'skip' control rendering, 'contour' colours along the path. The "
            "'particle-trace-marker' variant draws marker-seeded traces with the same keywords."
        ),
        "base_syntax": "plot item create particle-trace <keywords...>",
        "top_level_keywords": PARTICLE_TRACE_TOP,
        "basic_keywords": _basic(["active", "line", "skip", "trace-name", "contour", "legend", "transparency"]),
        "common_usage_patterns": [
            {
                "use_case": "Draw a named trace",
                "command": "plot item create particle-trace trace-name flow1 line on",
                "description": "Render the 'flow1' particle trace as lines.",
            },
        ],
        "notes_extra": [
            "particle-trace-marker shares this exact keyword set (traces seeded from markers).",
        ],
    },
    {
        "name": "history-locations",
        "item_types": ["history-locations"],
        "search_keywords": ["history", "location", "monitor", "sampling", "numbers"],
        "description": (
            "History sampling locations — where time-series histories are recorded. 'mark'/'numbers' "
            "annotate each point, 'pixel-size'/'scale' size the glyphs."
        ),
        "base_syntax": "plot item create history-locations <keywords...>",
        "top_level_keywords": HISTORY_LOC_TOP,
        "basic_keywords": _basic(
            ["active", "mark", "numbers", "pixel-size", "scale", "range", "legend", "cut", "transparency"]
        ),
        "common_usage_patterns": [
            {
                "use_case": "Label history points",
                "command": "plot item create history-locations mark cross numbers on",
                "description": "Show history sampling points with their numbers.",
            },
        ],
    },
    {
        "name": "chart-table",
        "item_types": ["chart-table"],
        "search_keywords": ["chart", "table", "curve", "record", "size-distribution", "mass", "xy"],
        "description": (
            "XY chart of a table. This is how MassFlow results are read: 'massflow record' writes "
            "extracted mass per period into a table, 'massflow drawpoint dump-drawperiod' writes a "
            "draw schedule into one, and 'massflow marker size-distribution' writes the cumulative "
            "fragment-size curve into one."
        ),
        "base_syntax": "plot item create chart-table table <name> <keywords...>",
        "top_level_keywords": CHART_TABLE_TOP,
        "basic_keywords": _basic(
            [
                "active",
                "table",
                "chart",
                "axis-x",
                "axis-y",
                "labels",
                "marks",
                "swap",
                "title",
                "legend",
                "transparency",
            ]
        ),
        "common_usage_patterns": [
            {
                "use_case": "Extracted mass by period",
                "command": "plot item create chart-table table 'all DPs'",
                "description": "Plot the table written by `massflow record name 'all DPs'`.",
            },
            {
                "use_case": "Fragment size distribution",
                "command": "plot item create chart-table table 'size-distribution' axis-x log on",
                "description": (
                    "Plot the cumulative percent-passing curve written by "
                    "`massflow marker size-distribution`, with a log size axis."
                ),
            },
        ],
    },
    {
        "name": "chart-history",
        "item_types": ["chart-history"],
        "search_keywords": ["chart", "history", "time series", "monitor"],
        "description": (
            "XY chart of a recorded history. 'vs' plots one history against another instead of "
            "against step; 'begin'/'end'/'skip' window and thin the series."
        ),
        "base_syntax": "plot item create chart-history history <name> <keywords...>",
        "top_level_keywords": CHART_HISTORY_TOP,
        "basic_keywords": _basic(
            [
                "active",
                "history",
                "vs",
                "begin",
                "end",
                "skip",
                "chart",
                "axis-x",
                "axis-y",
                "labels",
                "marks",
                "swap",
                "title",
                "legend",
                "transparency",
            ]
        ),
        "common_usage_patterns": [
            {
                "use_case": "Plot a history",
                "command": "plot item create chart-history history 1",
                "description": "Plot history 1 against step.",
            },
            {
                "use_case": "One history against another",
                "command": "plot item create chart-history history 2 vs 1",
                "description": "Cross-plot history 2 against history 1.",
            },
        ],
    },
]


def _write_categorical_colorby(item_dir: Path, item: dict[str, Any]) -> None:
    doc = {
        "name": "color-by",
        "parent_item": item["name"],
        "description": (
            f"Colour {item['name']} categorically via 'colorby <attribute>', or continuously via "
            "'contour value <quantity>'. Probed against MassFlow 3D 9."
        ),
        "base_syntax": f"plot item create {item['name']} colorby <attribute> | contour value <quantity> ...",
        "modes": [
            {
                "mode": "colorby",
                "syntax": "colorby <attribute>",
                "description": "Categorical colouring by a named attribute.",
                "attributes": item["colorby_attributes"],
            },
            {
                "mode": "contour",
                "syntax": "contour value <quantity> [modifiers...]",
                "description": "Continuous colouring of a value with display modifiers.",
                "modifiers": CONTOUR_MODIFIERS,
            },
        ],
        "notes": [PROBE_NOTE],
    }
    (item_dir / "color-by.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", "utf-8")


def _write_marker_colorby(item_dir: Path, item: dict[str, Any]) -> None:
    doc = {
        "name": "color-by",
        "parent_item": item["name"],
        "description": "Marker colouring ('color-by') and sizing ('size-by'), probed against MassFlow 3D 9.",
        "base_syntax": "plot item create marker color-by <contour|label> ... ; size-by <meanDiameter|pixels|uniform>",
        "modes": [
            {
                "mode": "contour",
                "syntax": "color-by contour [above below interval log maximum minimum ramp reversed]",
                "description": "Continuous colouring of the marker scalar field.",
            },
            {
                "mode": "label",
                "syntax": "color-by label <attribute>",
                "description": "Categorical colouring by a named attribute (e.g. group).",
            },
        ],
        "size_by": MARKER_SIZE_BY,
        "notes": [
            "size-by scales each marker glyph (meanDiameter = by fragment size).",
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

        kind = item.get("_colorby_kind")
        sub_items = []
        if kind in ("categorical", "marker"):
            sub_items = [
                {
                    "name": "color-by",
                    "file": "color-by.json",
                    "description": f"Colouring/sizing options for the {name} plot item.",
                }
            ]

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
            "sub_items": sub_items,
            "common_usage_patterns": item["common_usage_patterns"],
            "notes": [PROBE_NOTE, *item.get("notes_extra", [])],
        }
        (item_dir / "index.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", "utf-8")

        if kind == "categorical":
            _write_categorical_colorby(item_dir, item)
        elif kind == "marker":
            _write_marker_colorby(item_dir, item)

        catalog.append(
            {
                "name": name,
                "file": f"{name}/index.json",
                "description": item["description"].split(".")[0] + ".",
                "common_use": ", ".join(item["item_types"]),
            }
        )
        print(
            f"  {name:<18} types={len(item['item_types'])} top_kw={len(item['top_level_keywords'])} subs={len(sub_items)}"
        )

    (CAT_DIR / "index.json").write_text(
        json.dumps(
            {
                "type": "plot_item_keywords",
                "description": (
                    "Configuration keywords for MassFlow plot item types created via "
                    "'plot item create <type>'. Item types and keyword sets are binary-validated against "
                    "MassFlow 3D 9."
                ),
                "usage_context": "plot item create <type> <keyword> <keyword> ...",
                "items": catalog,
                "binary_item_types": BINARY_ITEM_TYPES,
                "notes": [
                    "Plot-item keywords are appended after the item type.",
                    PROBE_NOTE,
                    "`binary_item_types` is what `plot item create ?` enumerates on MassFlow "
                    "9.7.47. The MassFlow-specific caving entities and the two chart types are "
                    "documented here; the remaining shared-kernel items (axes, data-label, "
                    "data-scalar, data-tensor, data-vector, fos, fracture, geometry, scalebox) "
                    "are named but not detailed.",
                    "Results reach a chart through a table: `massflow record` and "
                    "`massflow drawpoint dump-drawperiod` write tables, and "
                    "`massflow marker size-distribution` writes the fragment-size curve.",
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        "utf-8",
    )

    top_path = OUT / "index.json"
    top = json.loads(top_path.read_text(encoding="utf-8")) if top_path.exists() else {"categories": {}}
    top.setdefault("categories", {})["plot-items"] = {
        "name": "Plot Items",
        "description": (
            "MassFlow plot item types — drawpoints, mine-blocks, isolated movement zones (imz), "
            "provenance markers (marker/marker-extracted), the flow vector field, particle traces, and "
            "history locations. Vocabulary for 'plot item create <type> ...'."
        ),
        "directory": "plot-items",
        "index_file": "plot-items/index.json",
        "summary": f"{len(catalog)} MassFlow plot item groups (drawpoint/mineblock/imz/marker/flow-vector/particle-trace/history-locations/chart-table/chart-history)",
        "usage": "plot item create drawpoint colorby dpactive | plot item create mineblock colorby ucs | plot item create flow-vector draw-as arrow",
    }
    top_path.write_text(json.dumps(top, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"\nWrote {CAT_DIR} ({len(catalog)} plot item groups) + updated top references index")


if __name__ == "__main__":
    main()
