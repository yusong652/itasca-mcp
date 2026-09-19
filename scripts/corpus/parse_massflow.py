"""Generate MassFlow command documentation JSON from local HTML docs.

MassFlow is the gravity-flow / caving product in the Itasca Software
Subscription. It runs on the shared Itasca 9.x kernel (and the FLAC3D zone
engine for optional coupled mechanical analysis), so this builds fresh
9.0-only command files (same shape as parse_mpoint.py / parse_3dec900.py):

    {
      "category": "massflow",
      "search_keywords": [...],
      "description": "...",
      "python_sdk_alternative": {"available": false},
      "versions": {"9.0": {"command", "syntax", "keywords", "examples"}}
    }

MassFlow's only engine-specific command family is ``massflow`` (material flow
compute, drawpoints, markers, mine-blocks, fines migration, secondary
fragmentation, recording). Everything else (model/data/fish/geometry/history/
plot/program/project/table/fracture) is the shared 9.0 kernel reused from
``_common/`` via generate_massflow_index.py.

The FLAC3D ``zone`` family is reachable on the MassFlow binary too (for coupled
analysis) but is deliberately NOT borrowed here: MassFlow3D's zone command set
diverges from the flac corpus (e.g. no ``zone create2d`` / ``zone
consolidation``) and MassFlow ships no zone docs of its own, so borrowing
wholesale would be inaccurate. Zone docs remain reachable via software="flac".

File-name prefix -> category:
    cmd_massflow.*  -> massflow   (incl. cmd_massflow.drawpoint.* etc. as
                                   hyphenated sub-namespace stems)

Usage:
    uv run python scripts/corpus/parse_massflow.py
"""

import json
from pathlib import Path

try:
    from parse_pfc600 import CommandHTMLParser, normalize_syntax
except ModuleNotFoundError:
    from .parse_pfc600 import CommandHTMLParser, normalize_syntax

# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------

MASSFLOW_DOC = Path("C:/Program Files/Itasca/Itasca Software Subscription/exe64/doc/massflow")
COMMANDS_DIR = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/massflow/command_docs/commands")

PREFIX_TO_CATEGORY = {
    "cmd_massflow.": "massflow",
}


def classify(stem: str) -> tuple[str, str] | None:
    """Map an HTML stem to (category, json_stem).

    The JSON stem has to match the command as the *binary* spells it, because
    ``browse_commands`` resolves "massflow mine-block group" by replacing spaces
    with dashes. The HTML pages spell that family ``mineblock``, so the stem is
    re-hyphenated here.

    >>> classify("cmd_massflow.compute")
    ('massflow', 'compute')
    >>> classify("cmd_massflow.drawpoint.import")
    ('massflow', 'drawpoint-import')
    >>> classify("cmd_massflow.mineblock.group")
    ('massflow', 'mine-block-group')
    """
    for prefix, category in PREFIX_TO_CATEGORY.items():
        if stem.startswith(prefix):
            sub = stem[len(prefix) :].replace(".", "-")
            if sub.startswith("mineblock-"):
                sub = "mine-block-" + sub[len("mineblock-") :]
            return category, sub
    return None


def build_doc(category: str, parsed: dict) -> dict:
    """Assemble a 9.0-only command doc in the FLAC/3DEC/MPoint corpus shape."""
    command = parsed["command"]
    syntax = normalize_syntax(parsed["syntax"])
    return {
        "category": category,
        "search_keywords": command.split(),
        "description": parsed["description"],
        "python_sdk_alternative": {"available": False},
        "versions": {
            "9.0": {
                "command": command,
                "syntax": syntax,
                "keywords": parsed["keywords"],
                "examples": [],
            }
        },
    }


def parse_html_file(html_path: Path) -> dict:
    parser = CommandHTMLParser()
    parser.feed(html_path.read_text(encoding="utf-8", errors="replace"))
    return {
        "command": parser.command_name,
        "syntax": parser.command_syntax,
        "keywords": parser.keywords,
        "description": parser.description,
    }


def main() -> None:
    print("=== MassFlow 9.0 command documentation generator ===\n")
    if not MASSFLOW_DOC.exists():
        print(f"[ERROR] MassFlow doc root not found: {MASSFLOW_DOC}")
        return

    counts: dict[str, int] = {}
    skipped: list[str] = []

    for html_path in sorted(MASSFLOW_DOC.rglob("cmd_*.html")):
        mapped = classify(html_path.stem)
        if mapped is None:
            continue
        category, json_stem = mapped

        parsed = parse_html_file(html_path)
        command = parsed["command"]
        # FISH-intrinsic pages (id="function:...") have a dotted h1 rather than
        # a space-separated command. Skip them.
        if not command or "." in command:
            skipped.append(html_path.name)
            print(f"  [SKIP] not a command page: {html_path.name}")
            continue

        doc = build_doc(category, parsed)

        out_dir = COMMANDS_DIR / category
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{json_stem}.json"
        out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        counts[category] = counts.get(category, 0) + 1
        print(f"  [OK] {command:45s} -> {category}/{json_stem}.json")

    print("\n--- per-category counts ---")
    for category in PREFIX_TO_CATEGORY.values():
        print(f"  {category:12s}: {counts.get(category, 0)}")
    print(f"  total       : {sum(counts.values())}")
    if skipped:
        print(f"  skipped     : {len(skipped)} -> {skipped}")
    print("\nDone.")


if __name__ == "__main__":
    main()
