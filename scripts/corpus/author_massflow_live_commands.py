"""Author the MassFlow commands that exist in the 9.7 binary but not in the docs.

`parse_massflow.py` derives the corpus from the 30 `cmd_massflow.*` HTML pages.
Live enumeration on MassFlow 9.7.47 (`<command> ?`) shows the binary carries
**47** command leaves, so 17 of them have no page to parse. This script writes
those 17 from live evidence, and applies the keyword-level corrections the same
sweep turned up on the 30 parsed files.

Every claim here is annotated with the evidence that backs it, following the
grading in the verification workspace (`G:\\Han\\Han\\itasca-doc\\massflow.md`):

* ``syntax`` - the engine enumerated or accepted the token
* ``state``  - the command was executed and its effect read back

It is idempotent: rerunning it rewrites the same files.

Run ``generate_massflow_index.py`` afterwards to refresh ``index.json``.

Usage:
    uv run python scripts/corpus/author_massflow_live_commands.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"
CMD_DIR = RESOURCES / "massflow" / "command_docs" / "commands" / "massflow"

# ---------------------------------------------------------------------------
# 1. Filename alignment: the binary spells it `mine-block`, the doc pages spell
#    it `mineblock`. browse_commands resolves "massflow mine-block group" by
#    replacing spaces with dashes, so `mineblock-group.json` made the real
#    command spelling unreachable through the MCP tool.
# ---------------------------------------------------------------------------

RENAMES = {
    # The command-name lookup in browse_commands is case-sensitive, so the file
    # stem has to carry the binary's mixed-case spelling too.
    "couplingflac3d.json": "couplingFLAC3D.json",
    "couplingfunction.json": "couplingFunction.json",
    "mineblock-group.json": "mine-block-group.json",
    "mineblock-import.json": "mine-block-import.json",
    "mineblock-list.json": "mine-block-list.json",
}


# ---------------------------------------------------------------------------
# 2. Commands present in the binary with no HTML page.
# ---------------------------------------------------------------------------

UNDOCUMENTED_NOTE = (
    "Not in the MassFlow manual — this command has no page in the 9.7 doc tree. "
    "Syntax below is read from the live 9.7.47 binary."
)

NEW_COMMANDS: dict[str, dict[str, Any]] = {
    # --- top level ---------------------------------------------------------
    "collapse-only.json": {
        "command": "massflow collapse-only",
        "search_keywords": ["massflow", "collapse-only", "collapse"],
        "description": (
            "Listed by `massflow ?` on the 9.7 binary. No manual page exists and its "
            "keyword set is not known: enumerating it with `massflow collapse-only ?` "
            "terminates the MassFlow process (reproduced twice on 9.7.47), so the "
            "keyword slot has never been read."
        ),
        "syntax": "massflow collapse-only",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "Do not probe this command with `?` — it kills the engine process.",
        ],
    },
    "couplingFLAC3D.json": {
        "command": "massflow couplingFLAC3D",
        "search_keywords": ["massflow", "couplingFLAC3D", "coupling", "flac3d", "coupled"],
        "description": (
            "Control the FLAC3D mechanical coupling of the gravity-flow solution. "
            "MassFlow runs the FLAC3D zone engine in the same process, which is what "
            "the shipped 'Massflow Coupling Example' drives; this command is the "
            "built-in switch for it."
        ),
        "syntax": "massflow couplingFLAC3D <keyword>",
        "keywords": [
            {"name": "on", "syntax": "on", "description": "Enable the FLAC3D coupling."},
            {"name": "off", "syntax": "off", "description": "Disable the FLAC3D coupling."},
            {
                "name": "frequency-days",
                "syntax": "frequency-days <i>",
                "description": "Number of flow days between mechanical updates.",
            },
        ],
        "notes": [
            UNDOCUMENTED_NOTE,
            "The command spelling is mixed case in the binary: couplingFLAC3D.",
            "Keyword set is syntax-verified; the coupled behaviour itself has not been executed and read back.",
            "The shipped coupling example drives the coupling from FISH instead "
            "(`massflow compute period 1` inside a loop that updates zone state).",
        ],
        "related_commands": ["massflow couplingFunction", "massflow compute"],
    },
    "couplingFunction.json": {
        "command": "massflow couplingFunction",
        "search_keywords": ["massflow", "couplingFunction", "coupling", "fish", "callback"],
        "description": (
            "Name the FISH function used by the FLAC3D coupling. The binary accepts "
            "any string at this slot, including a name that is not defined."
        ),
        "syntax": "massflow couplingFunction <s>",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "Accepting the name is syntax-verified; when and how the function is "
            "called has not been executed and read back.",
        ],
        "related_commands": ["massflow couplingFLAC3D"],
    },
    # --- drawpoint: tab-delimited and dialog variants ----------------------
    "drawpoint-import-txt.json": {
        "command": "massflow drawpoint import-txt",
        "search_keywords": ["massflow", "drawpoint", "import-txt", "tab", "text"],
        "description": (
            "Import a drawpoint description from a TAB-delimited text file. Same "
            "content and column order as `massflow drawpoint import`, which reads the "
            "comma-delimited CSV form of the same table."
        ),
        "syntax": "massflow drawpoint import-txt <s>",
        "keywords": [],
        "notes": [UNDOCUMENTED_NOTE],
        "related_commands": ["massflow drawpoint import"],
    },
    "drawpoint-import-drawbell-txt.json": {
        "command": "massflow drawpoint import-drawbell-txt",
        "search_keywords": ["massflow", "drawpoint", "drawbell", "import", "tab", "text"],
        "description": (
            "Import drawbell types from a TAB-delimited text file — the tab-delimited "
            "form of `massflow drawpoint import-drawbell`."
        ),
        "syntax": "massflow drawpoint import-drawbell-txt <s>",
        "keywords": [],
        "notes": [UNDOCUMENTED_NOTE],
        "related_commands": ["massflow drawpoint import-drawbell"],
    },
    "drawpoint-import-drawperiod-txt.json": {
        "command": "massflow drawpoint import-drawperiod-txt",
        "search_keywords": ["massflow", "drawpoint", "drawperiod", "schedule", "tab", "text"],
        "description": (
            "Import a draw schedule from a TAB-delimited text file — the tab-delimited "
            "form of `massflow drawpoint import-drawperiod`."
        ),
        "syntax": "massflow drawpoint import-drawperiod-txt <s>",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "On 9.7.47 this command terminated the MassFlow process every time it was "
            "given the tab-delimited draw-schedule file shipped with the tutorial "
            "project — with and without a block model loaded, and with a "
            "newline-terminated copy of the same file. The CSV path "
            "(`massflow drawpoint import-drawperiod`) reads the same schedule without "
            "incident, as do the sibling `import-txt` and `import-drawbell-txt`.",
        ],
        "related_commands": ["massflow drawpoint import-drawperiod"],
    },
    "drawpoint-add-drawperiod-txt.json": {
        "command": "massflow drawpoint add-drawperiod-txt",
        "search_keywords": ["massflow", "drawpoint", "add-drawperiod", "schedule", "tab", "text"],
        "description": (
            "Append a draw schedule from a TAB-delimited text file — the tab-delimited "
            "form of `massflow drawpoint add-drawperiod`."
        ),
        "syntax": "massflow drawpoint add-drawperiod-txt <s>",
        "keywords": [],
        "notes": [UNDOCUMENTED_NOTE],
        "related_commands": ["massflow drawpoint add-drawperiod"],
    },
    "drawpoint-import-GUI.json": {
        "command": "massflow drawpoint import-GUI",
        "search_keywords": ["massflow", "drawpoint", "import", "gui", "dialog"],
        "description": (
            "Import a drawpoint description through the MassFlow file-selection dialog instead of a filename argument."
        ),
        "syntax": "massflow drawpoint import-GUI",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "Interactive only: the command opens a modal dialog and waits for a file to "
            "be chosen in the MassFlow window, so it cannot be driven from a data file "
            "or from an automation bridge. Use `massflow drawpoint import` there.",
        ],
        "related_commands": ["massflow drawpoint import"],
    },
    "drawpoint-import-drawbell-GUI.json": {
        "command": "massflow drawpoint import-drawbell-GUI",
        "search_keywords": ["massflow", "drawpoint", "drawbell", "import", "gui", "dialog"],
        "description": "Import drawbell types through the MassFlow file-selection dialog.",
        "syntax": "massflow drawpoint import-drawbell-GUI",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "Interactive only — see `massflow drawpoint import-GUI`.",
        ],
        "related_commands": ["massflow drawpoint import-drawbell"],
    },
    "drawpoint-import-drawperiod-GUI.json": {
        "command": "massflow drawpoint import-drawperiod-GUI",
        "search_keywords": ["massflow", "drawpoint", "drawperiod", "import", "gui", "dialog"],
        "description": "Import a draw schedule through the MassFlow file-selection dialog.",
        "syntax": "massflow drawpoint import-drawperiod-GUI",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "Interactive only — see `massflow drawpoint import-GUI`.",
        ],
        "related_commands": ["massflow drawpoint import-drawperiod"],
    },
    # --- marker ------------------------------------------------------------
    "marker-air-porosity.json": {
        "command": "massflow marker air-porosity",
        "search_keywords": ["massflow", "marker", "air-porosity", "porosity", "air", "void"],
        "description": (
            "Set the porosity value used for air markers — the zero-mass markers "
            "MassFlow inserts wherever an IMZ meets a vertical boundary to flow, which "
            "are what track the air gap and drive free-surface rilling. The value slot "
            "is a floating point number between 0 and 1 (engine-enforced)."
        ),
        "syntax": "massflow marker air-porosity <f>",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "What the setting changes has not been read back: the manual describes air "
            "markers but not this command, and MassFlow exposes no FISH accessor for "
            "the value. The command runs without error and a subsequent "
            "`massflow compute` proceeds normally.",
        ],
        "related_commands": ["massflow marker initialize"],
    },
    "marker-trace-report-daily.json": {
        "command": "massflow marker trace-report-daily",
        "search_keywords": ["massflow", "marker", "trace", "report", "daily"],
        "description": (
            "Write a per-day trace-marker report. Output goes to `traceMarkerReportDaily.csv` in the working directory."
        ),
        "syntax": "massflow marker trace-report-daily",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "The output filename was read back from disk after running the command on "
            "a computed model; the command takes no filename keyword.",
        ],
        "related_commands": ["massflow marker trace-report", "massflow marker trace"],
    },
    # --- mine-block --------------------------------------------------------
    "mine-block-export.json": {
        "command": "massflow mine-block export",
        "search_keywords": ["massflow", "mine-block", "export", "f3grid", "flac3d", "grid"],
        "description": (
            "Export the mine-block model as a FLAC3D grid file. The extension "
            "`.f3grid` is appended to the name given, and the grid follows the block "
            "centres and block size — one hexahedral zone per mine block. This is the "
            "handover point to a coupled FLAC3D mechanical model."
        ),
        "syntax": "massflow mine-block export <s>",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "Verified by running it on the 9696-block tutorial model: the command "
            "reported `The BlockModel has been exported to <name>.f3grid` and the file "
            "on disk opens with `*GRIDPOINTS` / `G <id>, <x>, <y>, <z>` records.",
        ],
        "related_commands": ["massflow mine-block export-caved", "massflow mine-block import"],
    },
    "mine-block-export-caved.json": {
        "command": "massflow mine-block export-caved",
        "search_keywords": ["massflow", "mine-block", "export", "caved", "csv", "state"],
        "description": (
            "Export the current caved state of the mine-block model as a "
            "comma-delimited CSV. The header repeats the imported block columns and "
            "adds `HasCaved` and `CavedPeriod`, so the file can be re-imported as a "
            "block model that starts from the caved state."
        ),
        "syntax": "massflow mine-block export-caved <s>",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "The filename is used verbatim — unlike `massflow mine-block export`, no extension is appended.",
            "Verified on the tutorial model: the file carries "
            "`Easting,Northing,Elevation,HasCaved,CavedPeriod,BlockID,...` followed by "
            "one row per block.",
        ],
        "related_commands": ["massflow mine-block export", "massflow mine-block import"],
    },
    "mine-block-import-txt.json": {
        "command": "massflow mine-block import-txt",
        "search_keywords": ["massflow", "mine-block", "import", "txt", "tab", "text"],
        "description": (
            "Import a mine block description from a TAB-delimited text file. Same "
            "columns as `massflow mine-block import`, which reads the comma-delimited "
            "CSV form."
        ),
        "syntax": "massflow mine-block import-txt <s>",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "The tab-delimited files shipped with the example projects start with a "
            "`Delimiter: r;` line ahead of the header row.",
            "Verified on the tutorial's `mineblocks.txt`: 9696 blocks imported.",
        ],
        "related_commands": ["massflow mine-block import"],
    },
    "mine-block-import-old.json": {
        "command": "massflow mine-block import-old",
        "search_keywords": ["massflow", "mine-block", "import", "old", "legacy"],
        "description": (
            "Import a mine block description in the legacy MassFlow block-model text "
            "format. The legacy header carries extra columns the current format "
            "computes instead (`CavePerioDyn`, `MeanDia`, `MeanDiaDyn`, `SDDia`, "
            "`Pmin`, `Kexp`)."
        ),
        "syntax": "massflow mine-block import-old <s>",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "On 9.7.47 this command terminated the MassFlow process when given "
            "`mineblocks-old.txt`, the legacy file shipped with the tutorial project. "
            "`massflow mine-block import-txt` reads the current-format file from the "
            "same directory without incident.",
        ],
        "related_commands": ["massflow mine-block import", "massflow mine-block import-txt"],
    },
    "mine-block-import-GUI.json": {
        "command": "massflow mine-block import-GUI",
        "search_keywords": ["massflow", "mine-block", "import", "gui", "dialog"],
        "description": "Import a mine block description through the MassFlow file-selection dialog.",
        "syntax": "massflow mine-block import-GUI",
        "keywords": [],
        "notes": [
            UNDOCUMENTED_NOTE,
            "Interactive only — see `massflow drawpoint import-GUI`.",
        ],
        "related_commands": ["massflow mine-block import"],
    },
}


# ---------------------------------------------------------------------------
# 3. Corrections to the 30 parsed files.
# ---------------------------------------------------------------------------

LIST_KEYWORDS = [
    {
        "name": "extra",
        "syntax": "extra <i>",
        "description": "List extra-variable information from slot i (1 to 128).",
    },
    {
        "name": "information",
        "syntax": "information",
        "description": "List the per-object information table.",
    },
]

ON_OFF = [
    {"name": "on", "syntax": "on", "description": "Enable."},
    {"name": "off", "syntax": "off", "description": "Disable."},
]


def _kw(name: str, syntax: str, description: str) -> dict[str, str]:
    return {"name": name, "syntax": syntax, "description": description}


PATCHES: dict[str, dict[str, Any]] = {
    "initialize.json": {
        "add_keywords": [
            _kw(
                "markerfraglimit-lower",
                "markerfraglimit-lower <f>",
                "Lower limit on marker fragment size.",
            ),
            _kw(
                "markerfraglimit-upper",
                "markerfraglimit-upper <f>",
                "Upper limit on marker fragment size.",
            ),
            _kw("timing", "timing <b>", "Report solution timing while computing."),
        ],
        "notes": [
            "Keyword set verified against the live 9.7.47 binary (`massflow initialize ?` enumerates 16 keywords).",
            "`markerfraglimit-lower` / `markerfraglimit-upper` / `timing` have no page "
            "in the manual; they are readable and writable from FISH as "
            "massflow.markerfraglimit.lower / .upper.",
        ],
    },
    "drawpoint-list.json": {
        "set_keywords": LIST_KEYWORDS,
        "notes": [
            "The abbreviation accepted by the engine is `information`, not `info`.",
            "`group` is a sibling command (`massflow drawpoint group`), not a keyword of `list`.",
        ],
    },
    "marker-list.json": {
        "set_keywords": LIST_KEYWORDS,
        "notes": [
            "The abbreviation accepted by the engine is `information`, not `info`.",
            "`group` is a sibling command (`massflow marker group`), not a keyword of `list`.",
            "MassFlow adds marker-specific range elements: `range marker-type <i>` "
            "(-2 to 3) and the flag `range active`.",
        ],
    },
    "mine-block-list.json": {
        "set_keywords": LIST_KEYWORDS,
        "notes": [
            "The abbreviation accepted by the engine is `information`, not `info`.",
            "`group` is a sibling command (`massflow mine-block group`), not a keyword of `list`.",
        ],
    },
    "fines-migration.json": {
        "syntax": "massflow fines-migration <keyword>",
        "set_keywords": ON_OFF,
        "notes": ["The value is a keyword (`on` / `off`), not a quoted string."],
    },
    "secondary-fragmentation.json": {
        "syntax": "massflow secondary-fragmentation <keyword>",
        "set_keywords": ON_OFF,
        "notes": ["The value is a keyword (`on` / `off`), not a quoted string."],
    },
    "drawpoint-dump-drawperiod.json": {
        "syntax": "massflow drawpoint dump-drawperiod name <s> [keyword]",
        "notes": [
            "`name` is required: without it the command fails with "
            "`MASSFLOW DRAWPOINT DUMP-SCHEDULE: Table not be created`.",
        ],
    },
    "drawpoint-extraction-report.json": {
        "syntax": "massflow drawpoint extraction-report [filename <s>]",
        "set_keywords": [
            _kw(
                "filename",
                "filename <s>",
                "Write the report to this file instead of the default.",
            )
        ],
        "notes": [
            "Without `filename` the report is written to `periodExtractionReport.txt` in the working directory.",
        ],
    },
    "marker-trace-report.json": {
        "syntax": "massflow marker trace-report [filename <s>]",
        "set_keywords": [
            _kw(
                "filename",
                "filename <s>",
                "Write the report to this file instead of the default.",
            )
        ],
        "notes": [
            "Without `filename` the report is written to `traceMarkerReport.txt` in the working directory.",
            "`filename` is accepted but is not listed by the engine's own "
            "`massflow marker trace-report ?` enumeration.",
        ],
    },
    "marker-report-export.json": {
        "syntax": "massflow marker report-export [<s>]",
        "notes": [
            "The filename is optional. Without it the report is written to "
            "`massflow_Day<N>.txt`, where N is the current flow day.",
        ],
    },
    "record.json": {
        "syntax": "massflow record name <s> [keyword ...]",
        "notes": [
            "`name` is required and comes first: bare `massflow record` fails with "
            "`MASSFLOW RECORD: Table not be created`.",
        ],
    },
    "compute.json": {
        "notes": [
            "Both keywords are increments, not totals: they add to what has already "
            "been run. With neither keyword the command runs the `compute-days` / "
            "`compute-period` budget set by `massflow initialize`.",
        ],
    },
}


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_new_doc(spec: dict[str, Any]) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "category": "massflow",
        "search_keywords": spec["search_keywords"],
        "description": spec["description"],
        "python_sdk_alternative": {"available": False},
        "versions": {
            "9.0": {
                "command": spec["command"],
                "syntax": spec["syntax"],
                "keywords": spec.get("keywords", []),
                "examples": spec.get("examples", []),
            }
        },
    }
    if spec.get("notes"):
        doc["notes"] = spec["notes"]
    if spec.get("related_commands"):
        doc["related_commands"] = spec["related_commands"]
    return doc


def apply_patch(doc: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    entry = doc["versions"]["9.0"]
    if "syntax" in patch:
        entry["syntax"] = patch["syntax"]
    if "set_keywords" in patch:
        entry["keywords"] = patch["set_keywords"]
    if "add_keywords" in patch:
        have = {k["name"] for k in entry.get("keywords", [])}
        entry.setdefault("keywords", [])
        for kw in patch["add_keywords"]:
            if kw["name"] not in have:
                entry["keywords"].append(kw)
        entry["keywords"].sort(key=lambda k: k["name"])
    if "notes" in patch:
        doc["notes"] = patch["notes"]
    return doc


def main() -> int:
    renamed = 0
    for old, new in RENAMES.items():
        old_path, new_path = CMD_DIR / old, CMD_DIR / new
        if old_path.exists():
            old_path.rename(new_path)
            renamed += 1

    written = 0
    for filename, spec in NEW_COMMANDS.items():
        _write(CMD_DIR / filename, build_new_doc(spec))
        written += 1

    patched = 0
    for filename, patch in PATCHES.items():
        path = CMD_DIR / filename
        if not path.exists():
            raise FileNotFoundError(path)
        _write(path, apply_patch(_read(path), patch))
        patched += 1

    total = len(list(CMD_DIR.glob("*.json")))
    print(f"renamed {renamed}, wrote {written} new, patched {patched}")
    print(f"massflow command files now: {total}")
    print("next: uv run python scripts/corpus/generate_massflow_index.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
