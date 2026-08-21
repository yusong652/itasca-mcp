"""Inject 3DEC 7.0 version blocks into the 3dec command corpus from local HTML docs.

Unlike parse_3dec900.py (one-time bootstrap that wrote fresh 9.0-only files),
this script INJECTS a "7.0" block into the pre-existing 3dec command JSONs,
mirroring how parse_pfc900.py adds 9.0 blocks to the PFC corpus:

- Page exists in 7.0 HTML and corpus file exists -> set versions["7.0"] only;
  every other field (9.0 block, curated descriptions, notes) is preserved.
- Page exists in 7.0 HTML but corpus file does not (7.0-only command, e.g. the
  whole `sel` family) -> create a fresh file with a 7.0-only versions dict.
- Corpus file exists but 7.0 HTML has no page (9.x-only command) -> left
  untouched; CommandLoader._resolve_versioned_doc reports it as unavailable
  in 7.0. These are listed in the run report for checklist triage.

CAUTION (same trap as parse_pfc700, see project memory): rerunning replaces
versions["7.0"] wholesale, destroying any hand-curation inside that block.
Run for bootstrap; afterwards edit the JSONs directly.

Engine-specific command families (file-name prefix -> category):
    cmd_block.*      -> block
    cmd_feblock.*    -> feblock
    cmd_fblock.*     -> fblock
    cmd_flowknot.*   -> flowknot
    cmd_flowplane.*  -> flowplane
    cmd_sel.*        -> sel        (7.0-only family; 9.x moved these into
                                    structure hybrid/dowel etc.)

Shared-kernel commands (model/fish/geometry/data/...) are NOT handled here;
the 3DEC command index reuses the _common/ corpus, which already carries
6.0/7.0/9.0 blocks.

Usage:
    uv run python scripts/corpus/parse_3dec700.py
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

DEC700_DOC = Path("C:/Program Files/Itasca/3DEC700/exe64/doc/3dec")
COMMANDS_DIR = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/3dec/command_docs/commands")

PREFIX_TO_CATEGORY = {
    "cmd_block.": "block",
    "cmd_feblock.": "feblock",
    "cmd_fblock.": "fblock",
    "cmd_flowknot.": "flowknot",
    "cmd_flowplane.": "flowplane",
    "cmd_sel.": "sel",
}


def classify(stem: str) -> tuple[str, str] | None:
    """Map an HTML stem to (category, json_stem).

    >>> classify("cmd_block.contact.apply")
    ('block', 'contact-apply')
    >>> classify("cmd_sel.hybrid.create")
    ('sel', 'hybrid-create')
    """
    for prefix, category in PREFIX_TO_CATEGORY.items():
        if stem.startswith(prefix):
            sub = stem[len(prefix) :].replace(".", "-")
            return category, sub
    return None


def parse_html_file(html_path: Path) -> dict:
    parser = CommandHTMLParser()
    parser.feed(html_path.read_text(encoding="utf-8", errors="replace"))
    return {
        "command": parser.command_name,
        "syntax": parser.command_syntax,
        "keywords": parser.keywords,
        "description": parser.description,
    }


def build_version_block(parsed: dict) -> dict:
    return {
        "command": parsed["command"],
        "syntax": normalize_syntax(parsed["syntax"]),
        "keywords": parsed["keywords"],
        "examples": [],
    }


def build_new_doc(category: str, parsed: dict) -> dict:
    """Fresh file for a 7.0-only command (same shape as the 9.0 bootstrap)."""
    return {
        "category": category,
        "search_keywords": parsed["command"].split(),
        "description": parsed["description"],
        "python_sdk_alternative": {"available": False},
        "versions": {"7.0": build_version_block(parsed)},
    }


def main() -> None:
    print("=== 3DEC 7.0 command documentation injector ===\n")
    if not DEC700_DOC.exists():
        print(f"[ERROR] 3DEC 7.0 doc root not found: {DEC700_DOC}")
        return

    injected: dict[str, int] = {}
    created: list[str] = []
    skipped: list[str] = []
    seen: set[Path] = set()

    for html_path in sorted(DEC700_DOC.rglob("cmd_*.html")):
        mapped = classify(html_path.stem)
        if mapped is None:
            continue
        category, json_stem = mapped

        parsed = parse_html_file(html_path)
        command = parsed["command"]
        # FISH-intrinsic pages have a dotted h1 ("block.disp"); skip them.
        if not command or "." in command:
            skipped.append(html_path.name)
            print(f"  [SKIP] not a command page: {html_path.name}")
            continue

        out_dir = COMMANDS_DIR / category
        out_path = out_dir / f"{json_stem}.json"
        seen.add(out_path)

        if out_path.exists():
            doc = json.loads(out_path.read_text(encoding="utf-8"))
            doc.setdefault("versions", {})["7.0"] = build_version_block(parsed)
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            doc = build_new_doc(category, parsed)
            created.append(f"{category}/{json_stem}.json")

        out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        injected[category] = injected.get(category, 0) + 1

    # Corpus files with no 7.0 page -> 9.x-only, listed for checklist triage.
    nine_only = [
        str(p.relative_to(COMMANDS_DIR)).replace("\\", "/")
        for p in sorted(COMMANDS_DIR.rglob("*.json"))
        if p not in seen
    ]

    print("\n--- 7.0 blocks injected per category ---")
    for category in PREFIX_TO_CATEGORY.values():
        print(f"  {category:12s}: {injected.get(category, 0)}")
    print(f"  total       : {sum(injected.values())}")
    print(f"\n--- new 7.0-only files ({len(created)}) ---")
    for name in created:
        print(f"  {name}")
    print(f"\n--- corpus files with NO 7.0 page ({len(nine_only)}) ---")
    for name in nine_only:
        print(f"  {name}")
    if skipped:
        print(f"\n  skipped     : {len(skipped)} -> {skipped}")
    print("\nDone.")


if __name__ == "__main__":
    main()
