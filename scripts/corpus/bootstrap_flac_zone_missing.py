"""Add the FLAC zone command pages that exist in the installed docs but not the corpus.

Discovered during the MPoint verification campaign (2026-09-14): diffing the
Itasca 9.7 FLAC3D doc tree against ``flac/command_docs/commands/zone/`` showed
eight pages with no corpus file. Six of them are commands MPoint accepts, so
they block the MPoint zone borrow; this script parses those six.

Each page is parsed from every doc tree that ships it, so a command present in
both FLAC3D 7.0 and 9.x gets both version blocks (matching the rest of the flac
zone corpus). ``zone remesh`` is left out on purpose: it is a genuine FLAC gap
but MPoint3D 9.7 rejects it, so it belongs to the FLAC campaign.

Existing files are never overwritten -- this only fills gaps.

Usage:
    uv run python scripts/corpus/bootstrap_flac_zone_missing.py
"""

import json
from pathlib import Path

try:
    from parse_pfc600 import CommandHTMLParser, normalize_syntax
except ModuleNotFoundError:
    from .parse_pfc600 import CommandHTMLParser, normalize_syntax

DOC_TREES = {
    "7.0": Path("C:/Program Files/Itasca/FLAC3D700/exe64/doc"),
    "9.0": Path("C:/Program Files/Itasca/Itasca Software Subscription/exe64/doc/flac3d"),
}
ZONE_DIR = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/flac/command_docs/commands/zone")

# HTML page stem -> corpus file stem
TARGETS = {
    "cmd_zone.null": "null",
    "cmd_zone.effective-stress-cutoff": "effective-stress-cutoff",
    "cmd_zone.fluid-density": "fluid-density",
    "cmd_zone.gridpoint.force-reaction": "gridpoint-force-reaction",
    "cmd_zone.gridpoint.pore-pressure": "gridpoint-pore-pressure",
    "cmd_zone.geometry": "geometry",
}


def parse_page(path: Path) -> dict:
    parser = CommandHTMLParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return {
        "command": parser.command_name,
        "syntax": parser.command_syntax,
        "keywords": parser.keywords,
        "description": parser.description,
    }


def main() -> None:
    print("=== FLAC zone gap bootstrap ===\n")
    written = 0
    for page_stem, out_stem in TARGETS.items():
        out_path = ZONE_DIR / f"{out_stem}.json"
        if out_path.exists():
            print(f"  [SKIP] already in corpus: {out_stem}.json")
            continue

        versions: dict[str, dict] = {}
        description = ""
        command = ""
        for version, root in DOC_TREES.items():
            matches = list(root.rglob(f"{page_stem}.html"))
            if not matches:
                continue
            parsed = parse_page(matches[0])
            if not parsed["command"]:
                print(f"  [WARN] unparseable: {matches[0].name} ({version})")
                continue
            command = parsed["command"]
            description = description or parsed["description"]
            versions[version] = {
                "command": command,
                "syntax": normalize_syntax(parsed["syntax"]),
                "keywords": parsed["keywords"],
                "examples": [],
            }

        if not versions:
            print(f"  [MISS] no doc page found for {page_stem}")
            continue

        doc = {
            "category": "zone",
            "search_keywords": command.split(),
            "description": description,
            "python_sdk_alternative": {"available": False},
            "versions": versions,
        }
        out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1
        print(f"  [ADD]  {out_stem}.json  ({command})  versions={sorted(versions)}")

    print(f"\nWrote {written} file(s) to {ZONE_DIR}")
    print("Next: regenerate the flac and mpoint indexes.")


if __name__ == "__main__":
    main()
