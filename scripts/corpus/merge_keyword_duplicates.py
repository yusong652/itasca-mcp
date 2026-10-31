"""Finish the nested-keyword repair where hand edits blocked it.

repair_nested_keywords.py replaced collapsed keyword rows only where the corpus
row still equalled the old parser output. Two shapes slipped through:

* The row had been hand-corrected first (renamed to the right keyword, a live
  note added), so it no longer matched and kept its bare syntax: 3DEC
  ``block mechanical damping keyword`` lost local/combined/rayleigh/maxwell/...
* A live '?' probe had added a stub for the keyword the parser had lost
  ('Live-enumerated on 3DEC 9.7.47 ...; not on the official page'). Once the
  repair restored the real keyword, the stub sat beside it as a duplicate,
  claiming the documented keyword was undocumented.

For each keyword the fixed parser emits with nested options, this pass
* drops same-name probe stubs (their description says 'enumerated') when a row
  carrying the options exists;
* otherwise merges same-name rows into one: the parser's syntax, the hand-written
  description, then the parser's option text where the hand text lacks it.

Usage:
    uv run python scripts/corpus/merge_keyword_duplicates.py [--version 7.0] [--write]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_pfc600 import CommandHTMLParser  # noqa: E402
from repair_nested_keywords import DOC_ROOTS, RESOURCES, dump_like, keywords, page_index, spaced  # noqa: E402

STUB = re.compile(r"enumerated", re.IGNORECASE)
# The probe notes' claim that the page lacks the keyword, false once its options are restored.
UNDOCUMENTED = re.compile(r"[;,]?\s*(?:not on the official page|absent from the previous corpus list)")
# The parser misnests these: contact history 'gap' has no 'localforce-x' option.
SKIP = {("pfc", "contact", "history", "gap")}


def option_names(syntax: str) -> list[str]:
    """First-level option names inside a keyword's outer {...}."""
    start = syntax.find("{")
    if start < 0:
        return []
    depth, current, parts = 0, "", []
    for ch in syntax[start + 1 :]:
        if ch == "{":
            depth += 1
        elif ch == "}":
            if depth == 0:
                parts.append(current)
                break
            depth -= 1
        if depth == 0 and ch == "|":
            parts.append(current)
            current = ""
            continue
        if depth == 0:
            current += ch
    names = []
    for part in parts:
        m = re.match(r"\s*\[?\s*([a-z][\w-]*)", part)
        if m:
            names.append(m.group(1))
    return names


def options_text(description: str) -> str:
    i = description.find("Options:")
    return description[i:] if i >= 0 else ""


PLACEHOLDER = {
    "keyword",
    "<keyword>",
    "...",
    "[keyword",
    "...]",
    "[keyword]",
    "keyword...",
    "[range]",
    "<range>",
    "[keyword...]",
}


def is_placeholder(syntax: str, name: str) -> bool:
    """'damping keyword', 'flaw', 'property <keyword> ...': nothing a hand edit could have corrected."""
    rest = syntax.strip().removeprefix(name).split()
    return all(tok in PLACEHOLDER for tok in rest)


def merge(rows: list[dict], parsed: dict) -> dict | None:
    """One row for this keyword, or None when nothing needs to change."""
    full = [r for r in rows if "{" in r["syntax"]]
    if full:
        if len(rows) == 1:
            return None
        keep = dict(full[0])
        for r in rows:
            if r is full[0] or STUB.search(r.get("description") or ""):
                continue
            extra = (r.get("description") or "").strip()
            if extra and extra not in keep.get("description", ""):
                desc = keep.get("description", "")
                keep["description"] = f"{extra} {desc}" if desc.startswith("Options:") else f"{desc} {extra}"
        return keep
    names = option_names(parsed["syntax"])
    hand = " ".join((r.get("description") or "") for r in rows if not STUB.search(r.get("description") or ""))
    hand = hand.strip() or (rows[0].get("description") or "")
    missing = [n for n in names if n not in hand]
    if not missing and len(rows) == 1:
        return None
    keep = dict(rows[0])
    # A non-placeholder syntax may be a live correction of the manual's: keep it.
    if is_placeholder(keep["syntax"], keep["name"].removeprefix("kwd:")):
        keep["syntax"] = spaced(parsed["syntax"])
    opts = options_text(parsed["description"])
    if missing and opts:
        hand = f"{UNDOCUMENTED.sub('', hand)} {opts}".strip()
    keep["description"] = hand
    return keep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="9.0", choices=sorted(DOC_ROOTS))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    pages = page_index(DOC_ROOTS[args.version])
    changed_total = 0
    for path in sorted(RESOURCES.glob("*/command_docs/commands/*/*.json")):
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        block = data.get("versions", {}).get(args.version)
        if not block:
            continue
        kws = block.get("keywords", [])
        changes = []
        for text in pages.get(f"{path.parent.name}/{path.stem}", []):
            for parsed in keywords(CommandHTMLParser, text):
                if "{" not in parsed["syntax"]:
                    continue
                engine = path.parents[3].name
                if (engine, path.parent.name, path.stem, parsed["name"]) in SKIP:
                    continue
                idx = [i for i, k in enumerate(kws) if k["name"].removeprefix("kwd:") == parsed["name"]]
                if not idx:
                    continue
                row = merge([kws[i] for i in idx], parsed)
                if row is None:
                    continue
                kws[idx[0]] = row
                for i in reversed(idx[1:]):
                    del kws[i]
                changes.append(f"{parsed['name']} ({len(idx)} row{'s' if len(idx) > 1 else ''})")
        if changes:
            changed_total += len(changes)
            print(f"{path.relative_to(RESOURCES)}: {', '.join(changes)}")
            if args.write:
                path.write_text(dump_like(data, raw), encoding="utf-8")
    print(f"changed {changed_total}" + ("" if args.write else " (dry run)"))


if __name__ == "__main__":
    main()
