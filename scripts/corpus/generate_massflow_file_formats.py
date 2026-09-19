"""Generate the MassFlow ``file-formats`` reference category.

MassFlow has no property-setting command. Mine-block material properties,
drawpoint geometry, drawbell shapes and the whole draw schedule arrive only
through import files, and every result leaves through a report file. The file
formats *are* the API.

The command pages carry the format specifications and the theory chapter's
"Model Inputs" / "Model Outputs" sections carry the meaning of every column,
but ``parse_massflow.py`` keeps only each page's one-line lead — so the corpus
said `massflow mine-block import` "imports a mine block description" and
nothing else. This script writes that lost material back as a reference
category, with the output formats added from files read off disk after running
the commands on MassFlow 9.7.47.

Sources, per item:

* ``docs``  - Itasca 9.7 ``doc\\massflow`` (command page or theory chapter)
* ``state`` - the file produced by running the command on a live model

It also appends a "File format: see reference topic ..." line to the notes of
every import/export command, so browsing the command leads to the format.

ORDER MATTERS: ``author_massflow_live_commands.py`` rewrites those notes
wholesale, so run it first and this script second.

Usage:
    uv run python scripts/corpus/generate_massflow_file_formats.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"
REF_DIR = RESOURCES / "massflow" / "references"
OUT_DIR = REF_DIR / "file-formats"

DOC_SOURCE = (
    "Itasca 9.7 MassFlow manual: command pages + 'MassFlow Theory and Background' > Model Inputs / Model Outputs"
)


def col(name: str, description: str, *, required: bool = True) -> dict[str, Any]:
    return {"name": name, "required": required, "description": description}


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

BLOCK_MODEL: dict[str, Any] = {
    "name": "block-model",
    "full_name": "Block Model Import File",
    "direction": "input",
    "evidence": "docs + state",
    "description": (
        "The orebody. Every MassFlow model starts here: the block model defines the "
        "geometry of the mine, the material properties, the ore grades and the period "
        "at which each block becomes free to flow. There is no command that sets these "
        "values — they exist only as columns of this file."
    ),
    "commands": [
        "massflow mine-block import <s>",
        "massflow mine-block import-txt <s>",
        "massflow mine-block import-old <s>",
        "massflow mine-block import-GUI",
    ],
    "layout": {
        "delimiter": "comma (`massflow mine-block import`) or tab (`massflow mine-block import-txt`)",
        "header": "line 1 is the column header; block rows follow from line 2",
        "column_order": "free — columns are matched by name, but the names are matched exactly",
        "notes": [
            "The tab-delimited files shipped with the example projects begin with a "
            "`Delimiter: r;` line ahead of the header row.",
            "All blocks must be axis-aligned and the same size; the size may differ "
            "between the three coordinate directions (10 x 15 x 20 m is allowed).",
            "Grades are assumed to be a percentage by mass and FricAng is in degrees. "
            "Any consistent system of units may be used for everything else.",
            "The number of blocks drives the memory requirement.",
        ],
    },
    "columns": [
        col("Easting", "X of the block centre."),
        col("Northing", "Y of the block centre."),
        col("Elevation", "Z of the block centre."),
        col(
            "CavePeriod",
            "Draw-schedule period at which the block becomes free to flow; the block is "
            "released at the start of that period. Use 1 for 'flowable from the start' "
            "and a number larger than the simulated period count for 'never flows' "
            "(i.e. outside the cave limits). CavePeriodDyn is initialised from this and "
            "can then be changed from FISH; when the two differ, the dynamic value wins.",
        ),
        col("BlockID", "Unique integer ID, used for block-extraction reporting."),
        col("SolidsDen", "Specific gravity (true solids density) of the block material."),
        col(
            "InSituPor",
            "Porosity before the material starts flowing. Zero in blocks that have not "
            "caved; greater than zero but below MaxPor in previously caved ground.",
        ),
        col(
            "MaxPor",
            "Porosity once the material has fully bulked during flow — the porosity "
            "inside the IMZs. Typically 0.45-0.55. Not the traditional cave-wide "
            "bulking factor, which averages flowing and stagnant regions.",
        ),
        col(
            "FricAng",
            "Friction angle of the caved rock at maximum porosity, in degrees. Controls "
            "the IMZ base angle (45 + FricAng/2), the free-surface angle of repose "
            "(12 + FricAng/2) and the stresses inside the IMZ (proportional to "
            "1/FricAng). Typically 35-50.",
        ),
        col(
            "PriFragA",
            "Weibull alpha (shape) for the primary fragment-size distribution, s = beta * (-ln(1-r))^(1/alpha).",
        ),
        col("PriFragB", "Weibull beta (fragment size) for the primary fragmentation distribution."),
        col("TenStrA", "Weibull alpha (shape) for the tensile-strength distribution."),
        col("TenStrB", "Weibull beta (tensile strength) — usually estimated from UCS or Is50."),
        col(
            "UCS",
            "Unconfined compressive strength of the intact material, for a standard "
            "5 cm diameter core. Fragment strength is scaled from this for secondary "
            "fragmentation.",
        ),
        col(
            "PercK1",
            "Percolation-rate coefficient k1 for fines migration; recommended base "
            "value 11. Strain-rate sensitive (Pierce 2010 attributes this to k2 in "
            "error).",
        ),
        col("PercK2", "Percolation-rate coefficient k2 for fines migration; recommended base value 4.5."),
        col(
            "PercVMR",
            "Variance-to-mean ratio for percolation distance; the standard deviation is "
            "sqrt(VMR * L) around the mean distance L. Recommended base value 0.5.",
        ),
        col(
            "<grade>",
            "Any number of extra columns. The column heading becomes the grade name; "
            "values are generally a percentage (0-100). Readable from FISH as "
            "massflow.mineblock.ore.name / massflow.mineblock.ore.value, and available "
            "as mineblock plot-item labels.",
            required=False,
        ),
        col(
            "MeanDia / MeanDiaDyn / CavePeriodDyn / SDDia / Pmin / Kexp",
            "Recognised by the reader but normally computed by MassFlow: mean fragment "
            "diameter from the Weibull parameters and its user-writable dynamic twin, "
            "the dynamic cave period, and the legacy diameter/percolation columns. The "
            "legacy `import-old` files carry them explicitly.",
            required=False,
        ),
    ],
    "example": [
        "Easting,Northing,Elevation,CavePeriod,BlockID,SolidsDen,InSituPor,MaxPor,FricAng,PriFragA,PriFragB,TenStrA,TenStrB,UCS,PercK1,PercK2,PercVMR,Litho",
        "1405,-1598,225,1,1,2.6,0,0.2,42,0.86,0.45,2.3803,3803,60000,11,4.5,0.5,9",
    ],
    "notes": [
        "On import the engine echoes the extra grade columns it picked up and the block "
        "count: `--- Number of mine blocks imported: 9696`.",
        "A second import into the same model is refused with `Mine blocks have already "
        "been imported` — start from `model new`.",
        "On MassFlow 9.7.47 `massflow mine-block import-old` terminated the process on "
        "the legacy file shipped with the tutorial project.",
    ],
    "related_formats": ["caved-block-model", "flac3d-grid"],
    "official_documentation": DOC_SOURCE,
}

DRAW_POINTS: dict[str, Any] = {
    "name": "draw-points",
    "full_name": "Draw Point Import File",
    "direction": "input",
    "evidence": "docs + state",
    "description": (
        "Where material is extracted. Each row places one drawpoint and binds it to a "
        "drawbell type defined in the draw-bell file."
    ),
    "commands": [
        "massflow drawpoint import <s>",
        "massflow drawpoint import-txt <s>",
        "massflow drawpoint import-GUI",
    ],
    "layout": {
        "delimiter": "comma (`massflow drawpoint import`) or tab (`massflow drawpoint import-txt`)",
        "header": "line 1 is the column header; drawpoint rows follow from line 2",
        "column_order": (
            "FIXED — unlike the block model, the columns must appear in the order below. "
            "The header strings themselves are not significant."
        ),
    },
    "columns": [
        col(
            "DPName",
            "Unique drawpoint name. For sub-level caving the name must end with the "
            "letter l followed by the level number; levels increase with depth and "
            "increment by 1, which is what recovery-by-origin reporting keys on.",
        ),
        col(
            "X",
            "Easting of the drawpoint — a point on the floor of the draw drift "
            "immediately below the brow, at the centre of the drawbell. Draw actually "
            "occurs at the top of the drift, and for rectangular drawbells half a drift "
            "width in from the edges.",
        ),
        col("Y", "Northing of the drawpoint."),
        col(
            "Z",
            "Elevation of the drawpoint. Drawpoints need not share an elevation, but "
            "all of them must lie inside the block model.",
        ),
        col("DBID", "Integer ID of the drawbell this drawpoint belongs to; two drawpoints on one drawbell share it."),
        col(
            "DBType",
            "Name of the drawbell type, matching a BellName in the draw-bell file. It "
            "must start with `cone` (single-drawpoint block caving), `rect` "
            "(two-drawpoint block caving) or `slc` (sublevel caving ring), then `%` and "
            "an id — e.g. `cone%1`.",
        ),
    ],
    "example": [
        "DPName,X,Y,Z,DBID,DBType",
        "DP1,1500.7,-1552.7,228.4,1,cone%1",
    ],
    "notes": [
        "The engine echoes `--- Number of drawpoints imported from <file>: 7`.",
        "A second import is refused with `Draw points have already been imported`.",
    ],
    "related_formats": ["draw-bells", "draw-schedule"],
    "official_documentation": DOC_SOURCE,
}

DRAW_BELLS: dict[str, Any] = {
    "name": "draw-bells",
    "full_name": "Draw Bell Import File",
    "direction": "input",
    "evidence": "docs + state",
    "description": (
        "The drawbell type catalogue referenced by the DBType column of the drawpoint "
        "file. Three shapes exist — conical, rectangular and SLC ring — and each uses a "
        "different subset of the columns; the unused ones are set to zero."
    ),
    "commands": [
        "massflow drawpoint import-drawbell <s>",
        "massflow drawpoint import-drawbell-txt <s>",
        "massflow drawpoint import-drawbell-GUI",
    ],
    "layout": {
        "delimiter": "comma (`import-drawbell`) or tab (`import-drawbell-txt`)",
        "header": "line 1 is the column header; drawbell rows follow from line 2",
        "column_order": "FIXED — the columns must appear in the order below.",
    },
    "columns": [
        col("BellName", "Unique drawbell type name; must start with `cone`, `rect` or `slc`, then `%` and an id."),
        col("DDWidth", "Draw-drift width."),
        col("DDHeight", "Draw-drift height."),
        col("BellHeight", "Drawbell height. Block caving only — zero for SLC rings."),
        col("SideAngle", "Wall angle (conical) or sidewall angle (rectangular). Zero for SLC rings."),
        col("EndAngle", "End-wall angle, rectangular drawbells only. Zero for conical and SLC."),
        col(
            "DFZDepth",
            "SLC: depth of the disturbed flow zone, measured horizontally from the blast ring across the burden.",
        ),
        col("DFZWidth", "SLC: width of the disturbed flow zone across the ring, centred on the crosscut drift."),
        col("DFZHeight", "SLC: height of the disturbed flow zone, measured vertically up from the brow."),
        col("SideHoleAngle", "SLC: angle of the ring sideholes to the horizontal plane."),
        col("CrossCutSpacing", "SLC: horizontal centre-to-centre distance between crosscuts."),
        col("SublevelSpacing", "SLC: vertical floor-to-floor distance between sublevels."),
        col("Burden", "SLC: ring thickness, measured horizontally along the crosscut."),
        col("RetreatAz", "SLC: azimuth of retreat for the ring, clockwise from north."),
    ],
    "example": [
        "BellName,DDWidth,DDHeight,BellHeight,SideAngle,EndAngle,DFZDepth,DFZWidth,DFZHeight,SideHoleAngle,CrossCutSpacing,SublevelSpacing,Burden,RetreatAz",
        "cone%1,4.5,4.5,13,70,80,0,0,0,0,0,0,0,0",
    ],
    "notes": [
        "In version 9 the only block-caving (cone/rect) properties that affect IMZ "
        "growth are the draw-drift width and height; the rest describe geometry that "
        "does not yet restrict flow.",
        "The SLC properties do drive behaviour: the disturbed-flow-zone shape has a "
        "significant effect on flow, and the ring geometry and retreat azimuth feed "
        "recovery tracking.",
        "The long horizontal dimension of a rectangular drawbell is not in this file — "
        "it is derived from the positions of the two drawpoints that share the drawbell.",
    ],
    "related_formats": ["draw-points"],
    "official_documentation": DOC_SOURCE,
}

DRAW_SCHEDULE: dict[str, Any] = {
    "name": "draw-schedule",
    "full_name": "Draw Schedule (Draw Period) Import File",
    "direction": "input",
    "evidence": "docs + state",
    "description": (
        "How much is drawn, from where, and when. One row per drawpoint, one column per "
        "draw period; the cell is the mass drawn from that drawpoint during that period."
    ),
    "commands": [
        "massflow drawpoint import-drawperiod <s>",
        "massflow drawpoint import-drawperiod-txt <s>",
        "massflow drawpoint import-drawperiod-GUI",
        "massflow drawpoint add-drawperiod <s>",
        "massflow drawpoint add-drawperiod-txt <s>",
    ],
    "layout": {
        "delimiter": "comma (`import-drawperiod`) or tab (`import-drawperiod-txt`)",
        "header": "line 1 names the periods; the first cell is the drawpoint-name column",
        "column_order": "column 1 is DPName; each further column is one draw period",
    },
    "columns": [
        col("DPName", "Drawpoint name, matching the draw-point file. Column 1."),
        col(
            "<period header>",
            "One column per period. The header sets both the period name and its length "
            "in days, in one of three forms: an integer (used as both name and length in "
            "days); a string (used as the name, with a month name giving the length, so "
            "'Sept-08' is 30 days); or `Name%Length` (e.g. `Period1%20` is a period "
            "named Period1 lasting 20 days).",
        ),
    ],
    "example": [
        "DPName,7,7,7,7",
        "DP1,2000,2000,2000,2000",
    ],
    "notes": [
        "Cell values are masses, in units consistent with SolidsDen in the block model.",
        "MassFlow divides the period mass by the period length to get a daily tonnage "
        "and moves markers once a day, so an unrealistically large period mass relative "
        "to the period length under-samples the movement inside the IMZ.",
        "A schedule can be imported at any time. A new import deletes any *undrawn* "
        "periods from the existing schedule and appends the new ones; a partially drawn "
        "period is completed first.",
        "On import the engine reports the total days: `--- Total number of days imported from <file>: 413`.",
        "On MassFlow 9.7.47 `massflow drawpoint import-drawperiod-txt` terminated the "
        "process on the tab-delimited schedule shipped with the tutorial project; the "
        "comma-delimited path reads the same schedule without incident.",
    ],
    "related_formats": ["draw-points"],
    "official_documentation": DOC_SOURCE,
}

TRACE_MARKERS: dict[str, Any] = {
    "name": "trace-markers",
    "full_name": "Trace Marker Import File",
    "direction": "input",
    "evidence": "state",
    "description": (
        "Point locations whose movement is followed through the whole draw. Trace "
        "markers are what the particle-trace plot item and the trace reports are about; "
        "the same thing can be set up one point at a time with `massflow marker trace`."
    ),
    "commands": ["massflow marker import-trace <s>"],
    "layout": {
        "delimiter": "whitespace",
        "header": "none — the file is rows of coordinates",
        "column_order": "x y z",
    },
    "columns": [
        col("x", "Easting of the point to trace."),
        col("y", "Northing of the point to trace."),
        col("z", "Elevation of the point to trace."),
    ],
    "example": [
        "1518.78 -1551.79 270",
        "1534 -1541 384",
    ],
    "notes": [
        "The engine confirms with `--- Trace markers imported.` and gives no count.",
        "A second import is refused with `Trace Markers have already been imported`.",
        "Points must lie inside the block model. A trace point outside it crashed MassFlow 9.7.47 at import time.",
    ],
    "related_formats": ["trace-marker-report", "trace-marker-report-daily"],
    "official_documentation": "Read back from the file shipped with the MassFlow tutorial project; no format page exists.",
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

MARKER_REPORT: dict[str, Any] = {
    "name": "marker-report",
    "full_name": "Marker Report Output File",
    "direction": "output",
    "evidence": "docs + state",
    "description": (
        "The full state of every marker: where it started, where it is, what it is made "
        "of, and — if it has been drawn — which drawpoint took it and on what day. "
        "Extracted markers are listed first, then unextracted ones."
    ),
    "commands": [
        "massflow marker report-export [<s>]",
        "massflow marker report-days <i>",
        "massflow marker report-period <i>",
        "massflow marker filename <s>",
    ],
    "layout": {
        "delimiter": "tab",
        "header": "line 1 is the column header",
        "default_filename": "massflow_Day<N>.txt, where N is the current flow day",
    },
    "columns": [
        col("MarkerID", "Marker ID."),
        col("xStart, yStart, zStart", "Where the marker was created."),
        col("xCurrent, yCurrent, zCurrent", "Current position, or -99 -99 -99 if the marker has been extracted."),
        col("ParentBlock", "ID of the mine block the marker came from."),
        col("Active", "1 if the marker moved during the current period, else 0."),
        col(
            "Grade1..GradeN",
            "The extra ore-grade columns of the block model, under their own headings.",
            required=False,
        ),
        col("Mass", "Mass carried by the marker."),
        col("Volume", "Volume carried by the marker, spacing^3 / (1 - porosity)."),
        col("Porosity", "Marker porosity."),
        col("SolidDen", "Solids density of the host mine block."),
        col("BulkDen", "Bulk density of the host block, density * (1 - porosity)."),
        col("FricAng", "Friction angle of the host block."),
        col("FragDia", "Fragment diameter carried by the marker."),
        col("ShearStr", "Shear strain accumulated by the marker."),
        col("Work", "Work accumulated by the marker."),
        col("DPEnd", "Name of the drawpoint that extracted the marker, or null."),
        col("DayExtr", "Day of extraction, or -99."),
        col("MassExtr", "Cumulative mass extracted, or -99."),
        col(
            "Type",
            "Marker type: -2 unbulked for IMZ growth, -1 unbulked for collapse, "
            "0 unbulked for rilling, 1 partially bulked, 2 fully bulked.",
        ),
        col("TensileStrength", "Tensile strength carried by the marker.", required=False),
    ],
    "notes": [
        "`massflow marker report-days` / `report-period` schedule the report to be "
        "written automatically during the run; `report-export` writes one immediately.",
        "The marker type also drives `range marker-type <i>`, which the engine accepts "
        "for integers between -2 and 3 — one value more than the five the manual "
        "defines.",
        "`TensileStrength` appears in the `report-export` output but not in the "
        "trace-marker report, which otherwise shares the column set.",
    ],
    "related_formats": ["trace-marker-report"],
    "official_documentation": DOC_SOURCE,
}

TRACE_MARKER_REPORT: dict[str, Any] = {
    "name": "trace-marker-report",
    "full_name": "Trace Marker Report Output File",
    "direction": "output",
    "evidence": "state",
    "description": (
        "The marker report restricted to the trace markers — one row per traced point, "
        "in the same tab-delimited column set as the full marker report."
    ),
    "commands": ["massflow marker trace-report [filename <s>]"],
    "layout": {
        "delimiter": "tab",
        "header": "line 1 is the column header",
        "default_filename": "traceMarkerReport.txt",
    },
    "notes": [
        "Columns match the marker report through `Type`; the trace report has no `TensileStrength` column.",
        "`filename` is accepted although the engine's own "
        "`massflow marker trace-report ?` enumeration does not list it.",
    ],
    "related_formats": ["marker-report", "trace-marker-report-daily", "trace-markers"],
    "official_documentation": "Read back from the file the command writes; the command page documents no columns.",
}

TRACE_MARKER_REPORT_DAILY: dict[str, Any] = {
    "name": "trace-marker-report-daily",
    "full_name": "Daily Trace Marker Report Output File",
    "direction": "output",
    "evidence": "state",
    "description": "One row per trace marker per day — the trajectory, for plotting movement over time.",
    "commands": ["massflow marker trace-report-daily"],
    "layout": {
        "delimiter": "comma",
        "header": "line 1 is the column header",
        "default_filename": "traceMarkerReportDaily.csv",
    },
    "columns": [
        col("Day", "Flow day."),
        col("MarkerID", "Marker ID."),
        col("TracerID", "Tracer name; `Unknown` for markers imported by position."),
        col("Easting, Northing, Elevation", "Marker position on that day."),
    ],
    "example": [
        "Day,MarkerID,TracerID,Easting,Northing,Elevation",
        "2,256,Unknown,1519.08,-1552,268.204",
    ],
    "notes": ["The command takes no filename keyword."],
    "related_formats": ["trace-marker-report"],
    "official_documentation": "Not in the manual — the command has no page. Read back from the file it writes.",
}

EXTRACTION_REPORT: dict[str, Any] = {
    "name": "extraction-report",
    "full_name": "Period Extraction Report Output File",
    "direction": "output",
    "evidence": "state",
    "description": (
        "What each drawpoint actually pulled, period by period, broken down by ore "
        "grade and by origin and destination level."
    ),
    "commands": ["massflow drawpoint extraction-report [filename <s>]"],
    "layout": {
        "delimiter": "tab",
        "header": (
            "a two-line preamble (`CurPrd`, `CurPrdName`, `DaysSolved` and their values) "
            "followed by the table header on line 3"
        ),
        "default_filename": "periodExtractionReport.txt",
    },
    "columns": [
        col("DPName", "Drawpoint name."),
        col("Period", "Period number."),
        col("PrdName", "Period name, from the draw-schedule header."),
        col("CumMass", "Cumulative mass extracted at this drawpoint."),
        col("RingMass", "Mass extracted from the SLC ring."),
        col("PeriodMass", "Mass extracted during this period."),
        col("<grade>Mass", "One column per ore grade of the block model, the mass-weighted grade contribution."),
        col("<n>Orig", "Mass originating from level n."),
        col("<n>Dest", "Mass destined for level n."),
    ],
    "example": [
        "CurPrd\tCurPrdName\tDaysSolved",
        "3\t7\t20",
        "DPName\tPeriod\tPrdName\tCumMass\tRingMass\tPeriodMass\tUCSMass\t...\t1Orig\t...\t1Dest\t...",
    ],
    "notes": [
        "The grade columns are named after the extra columns of the block-model file, with `Mass` appended.",
        "The origin/destination columns are the SLC level tracking that the `l<level>` "
        "drawpoint naming convention exists for.",
    ],
    "related_formats": ["block-model", "draw-schedule"],
    "official_documentation": "Read back from the file the command writes; the command page documents no columns.",
}

CAVED_BLOCK_MODEL: dict[str, Any] = {
    "name": "caved-block-model",
    "full_name": "Caved Block Model Export File",
    "direction": "output",
    "evidence": "state",
    "description": (
        "The block model plus its caved state, in the same comma-delimited shape the "
        "importer reads — so a run can be continued from where another one stopped."
    ),
    "commands": ["massflow mine-block export-caved <s>"],
    "layout": {
        "delimiter": "comma",
        "header": "line 1 is the column header",
        "default_filename": "the name given is used verbatim — no extension is appended",
    },
    "columns": [
        col("HasCaved", "1 if the block has caved, else 0."),
        col(
            "CavedPeriod",
            "Period at which the block caved. Note the spelling differs from the importer's `CavePeriod`.",
        ),
        col("<block-model columns>", "Every column of the imported block model, in the exporter's own order."),
    ],
    "example": [
        "Easting,Northing,Elevation,HasCaved,CavedPeriod,BlockID,SolidsDen,InSituPor,MaxPor,FricAng,...",
        "1405,-1598,225,0,1,1,2.6,0,0.2,42,...",
    ],
    "notes": [
        "The column order is not the import order: the exporter puts PercK1 / PercK2 / PercVMR ahead of UCS.",
    ],
    "related_formats": ["block-model"],
    "official_documentation": "Not in the manual — the command has no page. Read back from the file it writes.",
}

FLAC3D_GRID: dict[str, Any] = {
    "name": "flac3d-grid",
    "full_name": "FLAC3D Grid Export File",
    "direction": "output",
    "evidence": "state",
    "description": (
        "The block model as a FLAC3D grid — one hexahedral zone per mine block, "
        "gridpoints at the block corners. This is the handover point to a coupled "
        "mechanical model."
    ),
    "commands": ["massflow mine-block export <s>"],
    "layout": {
        "delimiter": "FLAC3D grid format",
        "header": "`*GRIDPOINTS` section, then the zone section",
        "default_filename": "`.f3grid` is appended to the name given",
    },
    "example": [
        "*GRIDPOINTS",
        "G 1, 1400, -1603, 220",
    ],
    "notes": [
        "The engine confirms with `--- The BlockModel has been exported to <name>.f3grid`.",
        "Unlike `export-caved`, the extension is added for you.",
    ],
    "related_formats": ["block-model", "caved-block-model"],
    "official_documentation": "Not in the manual — the command has no page. Read back from the file it writes.",
}

PROJECT_FILES: dict[str, Any] = {
    "name": "project-files",
    "full_name": "MassFlow Project File Types",
    "direction": "reference",
    "evidence": "docs",
    "description": "What each file extension in a MassFlow project directory holds.",
    "columns": [
        col(".prj", "The project file: interface settings, plots, and links to data files and SAV files."),
        col(
            ".sav",
            "Model state: the imported project data plus any solution data. A SAV is not "
            "linked back to the files it was imported from — changes made after import "
            "do not reach them.",
        ),
        col(
            ".txt",
            "Tab-delimited import/export of the block model, drawpoints and draw schedule; also exported solve data.",
        ),
        col(
            ".out",
            "Tracer marker position and extraction data, in two files written "
            "automatically to the project folder after each solve period.",
        ),
    ],
    "related_formats": ["block-model", "draw-points", "draw-schedule"],
    "official_documentation": DOC_SOURCE,
}


ITEMS: list[dict[str, Any]] = [
    BLOCK_MODEL,
    DRAW_POINTS,
    DRAW_BELLS,
    DRAW_SCHEDULE,
    TRACE_MARKERS,
    MARKER_REPORT,
    TRACE_MARKER_REPORT,
    TRACE_MARKER_REPORT_DAILY,
    EXTRACTION_REPORT,
    CAVED_BLOCK_MODEL,
    FLAC3D_GRID,
    PROJECT_FILES,
]

CATEGORY_ENTRY = {
    "name": "File Formats",
    "description": (
        "The import and export file formats MassFlow models are built from and report "
        "through: block model, draw points, draw bells, draw schedule, trace markers, "
        "the marker / trace / extraction reports, and the caved-block and FLAC3D grid "
        "exports. MassFlow has no property-setting command — mine-block material "
        "properties and the whole draw schedule exist only as columns of these files."
    ),
    "directory": "file-formats",
    "index_file": "file-formats/index.json",
    "summary": "12 MassFlow file formats (5 inputs, 6 outputs, plus the project file types)",
    "usage": "massflow mine-block import '<blocks>.csv' ; massflow drawpoint import '<dps>.csv' ; massflow drawpoint import-drawperiod '<schedule>.csv'",
}


# Commands whose real documentation is the file format, pointed at the topic
# that now holds it. browse_commands prints a command's `notes` verbatim.
CMD_DIR = RESOURCES / "massflow" / "command_docs" / "commands" / "massflow"

POINTERS: dict[str, str] = {
    "mine-block-import": "block-model",
    "mine-block-import-txt": "block-model",
    "mine-block-import-old": "block-model",
    "mine-block-import-GUI": "block-model",
    "mine-block-export": "flac3d-grid",
    "mine-block-export-caved": "caved-block-model",
    "drawpoint-import": "draw-points",
    "drawpoint-import-txt": "draw-points",
    "drawpoint-import-GUI": "draw-points",
    "drawpoint-import-drawbell": "draw-bells",
    "drawpoint-import-drawbell-txt": "draw-bells",
    "drawpoint-import-drawbell-GUI": "draw-bells",
    "drawpoint-import-drawperiod": "draw-schedule",
    "drawpoint-import-drawperiod-txt": "draw-schedule",
    "drawpoint-import-drawperiod-GUI": "draw-schedule",
    "drawpoint-add-drawperiod": "draw-schedule",
    "drawpoint-add-drawperiod-txt": "draw-schedule",
    "drawpoint-extraction-report": "extraction-report",
    "marker-import-trace": "trace-markers",
    "marker-report-export": "marker-report",
    "marker-report-days": "marker-report",
    "marker-report-period": "marker-report",
    "marker-filename": "marker-report",
    "marker-trace-report": "trace-marker-report",
    "marker-trace-report-daily": "trace-marker-report-daily",
}

POINTER_PREFIX = "File format: see reference topic "


def add_format_pointers() -> int:
    touched = 0
    for stem, topic in POINTERS.items():
        path = CMD_DIR / f"{stem}.json"
        if not path.exists():
            raise FileNotFoundError(path)
        doc = json.loads(path.read_text(encoding="utf-8"))
        notes = [n for n in doc.get("notes", []) if not n.startswith(POINTER_PREFIX)]
        notes.append(f"{POINTER_PREFIX}'file-formats {topic}'.")
        doc["notes"] = notes
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        touched += 1
    return touched


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for item in ITEMS:
        (OUT_DIR / f"{item['name']}.json").write_text(
            json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    index = {
        "type": "file_formats",
        "description": CATEGORY_ENTRY["description"],
        "usage_pattern": {
            "inputs": "massflow <family> import[-txt] '<file>' — CSV by default, tab-delimited with the -txt variants",
            "outputs": "massflow marker report-export / trace-report[-daily] ; massflow drawpoint extraction-report ; massflow mine-block export[-caved]",
        },
        "items": [
            {
                "name": item["name"],
                "file": f"{item['name']}.json",
                "full_name": item["full_name"],
                "direction": item["direction"],
            }
            for item in ITEMS
        ],
        "notes": [
            "Block-model columns are matched by name in any order; draw-point and "
            "draw-bell columns are matched by POSITION and must appear in the documented "
            "order.",
            "The `-txt` commands read the same tables tab-delimited. The tab-delimited "
            "block-model files shipped with the example projects start with a "
            "`Delimiter: r;` line.",
        ],
        "related_commands": [
            "massflow mine-block import",
            "massflow drawpoint import",
            "massflow drawpoint import-drawbell",
            "massflow drawpoint import-drawperiod",
            "massflow marker import-trace",
            "massflow marker report-export",
            "massflow drawpoint extraction-report",
            "massflow mine-block export",
        ],
        "official_documentation": DOC_SOURCE,
    }
    (OUT_DIR / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ref_index_path = REF_DIR / "index.json"
    ref_index = json.loads(ref_index_path.read_text(encoding="utf-8"))
    ref_index["categories"]["file-formats"] = CATEGORY_ENTRY
    ref_index_path.write_text(json.dumps(ref_index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    touched = add_format_pointers()

    print(f"wrote {len(ITEMS)} file-format items to {OUT_DIR}")
    print(f"registered 'file-formats' in {ref_index_path}")
    print(f"pointed {touched} command docs at their format topic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
