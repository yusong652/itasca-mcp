"""Rewrite MPoint command/keyword syntax from the 9.8 manual pages.

The MPoint corpus was built by flattening the MPM pages' markup, which loses the
brackets of placeholders ('<i>' is a <span class="varint">, not text) and eats the
opening bracket of an optional group ('<<a ...>range</a>>' -> 'range>'). See
_SyntaxLabel in reparse_mpoint_commands.py for the rendering that fixes it.

This script re-reads only the syntax strings (command and keywords, matched by
name) from the newest installed MPM pages and leaves descriptions, notes and the
keyword set alone. Pages the corpus does not know, and corpus commands with no
page, are reported for the next live reconcile rather than touched.

Usage:
    uv run python scripts/corpus/repair_mpoint_syntax.py [--write]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reparse_mpoint_commands import parse_page  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "src/itasca_mcp/knowledge/resources/mpoint/command_docs/commands/mpoint"
DOC_CANDIDATES = [
    Path(r"C:/Program Files/Itasca/Itasca Software Subscription/exe64/doc"),
    Path(r"C:/Program Files/Itasca/ItascaSoftware900/exe64/doc"),
]


def page_dir() -> Path:
    for root in DOC_CANDIDATES:
        hits = sorted(root.rglob("cmd_mpoint.create.html")) if root.exists() else []
        if hits:
            return hits[0].parent
    raise SystemExit("no MPM command pages found")


def main() -> int:
    write = "--write" in sys.argv
    pages = page_dir()
    print(f"pages: {pages}")
    seen_keys: set[str] = set()
    changed_files = 0
    # node commands sit in a sibling folder (mpoint.node/), like 3DEC's block.contact/
    for page in sorted(pages.parent.rglob("cmd_mpoint.*.html")):
        key = page.stem[len("cmd_mpoint.") :].replace(".", "-")
        seen_keys.add(key)
        target = ROOT / f"{key}.json"
        if not target.exists():
            print(f"[no corpus file] {key}  <- {page.name}")
            continue
        parsed = parse_page(page)
        if parsed is None:
            print(f"[unparsed] {page.name}")
            continue
        raw = target.read_text(encoding="utf-8")
        doc = json.loads(raw)
        block = doc["versions"].get("9.0")
        if not isinstance(block, dict):
            print(f"[no 9.0 block] {key}")
            continue
        edits: list[str] = []
        if block.get("syntax") != parsed["syntax"]:
            edits.append(f"  syntax: {block.get('syntax')!r} -> {parsed['syntax']!r}")
            block["syntax"] = parsed["syntax"]
        by_name = {k["name"]: k for k in parsed["keywords"]}
        for kw in block.get("keywords") or []:
            new = by_name.get(kw.get("name"))
            if new is None:
                print(f"  [keyword not on page] {key}: {kw.get('name')}")
                continue
            if kw.get("syntax") != new["syntax"]:
                edits.append(f"  {kw['name']}: {kw.get('syntax')!r} -> {new['syntax']!r}")
                kw["syntax"] = new["syntax"]
        for name in by_name.keys() - {k.get("name") for k in block.get("keywords") or []}:
            print(f"  [keyword only on page] {key}: {name}")
        if edits:
            changed_files += 1
            print(f"[{key}]")
            print("\n".join(edits))
            if write:
                target.write_text(
                    json.dumps(doc, ensure_ascii=False, indent=2) + ("\n" if raw.endswith("\n") else ""),
                    encoding="utf-8",
                    newline="\n",
                )
    for f in sorted(ROOT.glob("*.json")):
        if f.stem not in seen_keys:
            syntax = (json.loads(f.read_text(encoding="utf-8"))["versions"].get("9.0") or {}).get("syntax")
            print(f"[no page] {f.stem}: {syntax!r}")
    print(f"{'wrote' if write else 'would change'} {changed_files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
