"""Author the zone commands MPoint has but the borrowed FLAC corpus lacks.

Two groups, both found during the MPoint verification campaign (2026-09-14):

1. ``zone joint ...`` -- documented, but in the ``wad/`` (wall-and-discontinuity)
   doc tree rather than ``flac3d/``, which is why the FLAC corpus never picked it
   up. Parsed here from the installed HTML.

2. ``zone gp`` / ``zone convergence-norm`` / ``zone export-data`` /
   ``zone import-data`` -- accepted by the engine but absent from every doc tree
   and from ``out_commands.txt``. Authored from live enumeration only, and each
   file says so.

These land under ``mpoint/`` rather than ``flac/`` on purpose: availability was
established against MPoint3D 9.7, and whether FLAC3D ships them is unverified
(owed to the FLAC checklist). ``generate_mpoint_index.py`` merges this directory
over the borrowed FLAC entries.

Usage:
    uv run python scripts/corpus/parse_mpoint_zone_extras.py
"""

import json
from pathlib import Path

try:
    from parse_pfc600 import CommandHTMLParser, normalize_syntax
except ModuleNotFoundError:
    from .parse_pfc600 import CommandHTMLParser, normalize_syntax

WAD_DOC = Path("C:/Program Files/Itasca/Itasca Software Subscription/exe64/doc/wad")
OUT_DIR = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/mpoint/command_docs/commands/zone")

LIVE_NOTE = "Live-probed on MPoint3D 9.7 (2026-09-14). Availability in FLAC3D is unverified."

# --- group 1: zone joint, parsed from the wad doc tree -----------------------

JOINT_PAGES = [
    "configure",
    "create",
    "create-contact",
    "delete",
    "gridpoint-stiffness",
    "initialize-stresses",
    "permeability",
    "pore-pressure-update",
    "results",
]

JOINT_EXTRA_NOTES = {
    "create-contact": [
        "The engine accepts both 'create-contact' (the documented spelling) and "
        "'create-contacts'; 'zone joint ?' enumerates only the plural. Aliases. (syntax)",
    ],
    "configure": [
        "WARNING: running 'zone joint configure' also issues 'model large-strain off' and "
        "installs a default vertex-facet contact model. Large-strain off freezes positions, "
        "so re-assert 'model large-strain on' afterwards if you need motion. (state)",
    ],
}

# --- group 2: undocumented, authored from live enumeration -------------------

LIVE_ONLY = {
    "joint-delete-attach": {
        "command": "zone joint delete-attach",
        "syntax": "zone joint delete-attach [range]",
        "description": "Delete the attach conditions created for zone joints from the gridpoints in range.",
        "keywords": [],
        "notes": [
            "Undocumented: 'zone joint ?' enumerates it, but the wad doc tree has no page for "
            "it and out_commands.txt has no entry (it lists only 'zone joint delete' and its "
            "'free-faces' keyword).",
            "Running it reports '--- Deleted attach condition from 0 gridpoints', which is "
            "where the description above comes from. (syntax)",
            LIVE_NOTE,
        ],
    },
    "gp": {
        "command": "zone gp",
        "syntax": "zone gp [keyword] [range]",
        "description": (
            "Alias for 'zone gridpoint'. Enumerates an identical keyword set and behaves "
            "identically; see the 'zone gridpoint' entries for the documented syntax."
        ),
        "keywords": [
            {"name": k, "syntax": k, "description": f"See 'zone gridpoint {k}'."}
            for k in [
                "create",
                "fix",
                "force-reaction",
                "force-reaction-x",
                "force-reaction-y",
                "force-reaction-z",
                "free",
                "group",
                "import",
                "initialize",
                "list",
                "merge",
                "pore-pressure",
                "system",
            ]
        ],
        "notes": [
            "Undocumented: no page in any installed doc tree and no entry in out_commands.txt.",
            "Established as an exact alias by comparing enumerations: 'zone gp ?' and "
            "'zone gridpoint ?' return the same 14 keywords. (syntax)",
            LIVE_NOTE,
        ],
    },
    "convergence-norm": {
        "command": "zone convergence-norm",
        "syntax": "zone convergence-norm keyword",
        "description": "Select the norm used when testing convergence of the zone solution.",
        "keywords": [
            {"name": "infinity", "syntax": "infinity", "description": "Use the infinity norm."},
            {"name": "maximum", "syntax": "maximum", "description": "Use the maximum norm."},
        ],
        "notes": [
            "Undocumented: no page in any installed doc tree and no entry in out_commands.txt.",
            "Keyword set from live enumeration; the per-keyword meaning is not documented "
            "anywhere and is stated here only as the keyword name. (syntax)",
            LIVE_NOTE,
        ],
    },
    "export-data": {
        "command": "zone export-data",
        "syntax": "zone export-data <sfile> ...",
        "description": "Export zone field data to a file.",
        "keywords": [],
        "notes": [
            "Undocumented: no page in any installed doc tree and no entry in out_commands.txt.",
            "Probing with a non-filename token returns 'Error opening file', i.e. the first "
            "parameter is a filename; no keyword table is exposed. (syntax)",
            LIVE_NOTE,
        ],
    },
    "import-data": {
        "command": "zone import-data",
        "syntax": "zone import-data <sfile> ...",
        "description": "Import zone field data from a file.",
        "keywords": [],
        "notes": [
            "Undocumented: no page in any installed doc tree and no entry in out_commands.txt.",
            "Probing with a non-filename token returns 'Error opening file', i.e. the first "
            "parameter is a filename; no keyword table is exposed. (syntax)",
            LIVE_NOTE,
        ],
    },
}


def write_doc(stem: str, command: str, syntax: str, description: str, keywords: list, notes: list) -> None:
    doc = {
        "category": "zone",
        "search_keywords": command.split(),
        "description": description,
        "notes": notes,
        "python_sdk_alternative": {"available": False},
        "versions": {
            "9.0": {
                "command": command,
                "syntax": syntax,
                "keywords": keywords,
                "examples": [],
            }
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{stem}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    print("=== MPoint zone extras ===\n")

    for sub in JOINT_PAGES:
        matches = list(WAD_DOC.rglob(f"cmd_zone.joint.{sub}.html"))
        if not matches:
            print(f"  [MISS] no wad page for zone joint {sub}")
            continue
        parser = CommandHTMLParser()
        parser.feed(matches[0].read_text(encoding="utf-8", errors="replace"))
        command = parser.command_name or f"zone joint {sub}"
        notes = [
            "Documented in the 'wad' (wall-and-discontinuity) doc tree, not under flac3d/ -- "
            "which is why this family is absent from the FLAC zone corpus.",
            LIVE_NOTE,
        ] + JOINT_EXTRA_NOTES.get(sub, [])
        write_doc(
            f"joint-{sub}", command, normalize_syntax(parser.command_syntax), parser.description, parser.keywords, notes
        )
        print(f"  [ADD]  joint-{sub}.json  ({command})  keywords={len(parser.keywords)}")

    for stem, spec in LIVE_ONLY.items():
        write_doc(stem, spec["command"], spec["syntax"], spec["description"], spec["keywords"], spec["notes"])
        print(f"  [ADD]  {stem}.json  ({spec['command']})  keywords={len(spec['keywords'])}  [live-only]")

    print("\nNext: uv run python scripts/corpus/generate_mpoint_index.py")


if __name__ == "__main__":
    main()
