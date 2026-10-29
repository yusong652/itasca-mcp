"""Restore command keywords whose nested options the HTML parser collapsed.

A keyword's <dd> can hold its own <dl> of options (dt id ``kwd:point.gridpoint``
inside the dd of ``kwd:point``). Until the parser learned to nest, it emitted such
a keyword under its *last* option's name and syntax with every paragraph of the
block as description: ``zone create`` lost ``point`` to ``gridpoint <s>``,
``model solve`` lost ``mechanical``/``fish-call``/... to five ``time-total-zone``
rows.

The corpus has been hand-edited since it was parsed, so it is not regenerated.
For each page this runs the old parser (a copy of parse_pfc600.py from before the
fix, passed with --old) and the fixed one side by side; their top-level keywords
align one to one. A corpus entry is replaced where it still equals the old
output, ignoring whitespace. Where its description was edited by hand since, the
edits are carried over onto the new text when each can be placed unambiguously;
otherwise the entry is listed for manual review and left alone.

Usage:
    git show 879a71d:scripts/corpus/parse_pfc600.py > parse_pfc600_old.py
    uv run python scripts/corpus/repair_nested_keywords.py --old parse_pfc600_old.py [--version 7.0] [--write]
"""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_pfc600 import CommandHTMLParser  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
RESOURCES = REPO / "src/itasca_mcp/knowledge/resources"
ITASCA = Path("C:/Program Files/Itasca")
DOC_ROOTS = {
    "6.0": [ITASCA / "PFC600/exe64/doc"],
    "7.0": [ITASCA / p / "exe64/doc" for p in ("PFC700", "FLAC3D700", "3DEC700")],
    "9.0": [ITASCA / "ItascaSoftware900/exe64/doc"],
}
COMMAND_ID = re.compile(r'id="command:([^"]+)"')
# Shared field-data modifiers ('stress quantity zz'): vocabulary of a keyword, which
# the corpus marks 'kwd:' (see reparse_mpoint_commands.py).
FIELD_DATA = {"component", "method", "null", "quantity", "source", "type"}


def load_old_parser(path: Path):
    spec = importlib.util.spec_from_file_location("parse_pfc600_old", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CommandHTMLParser


def page_index(roots: list[Path]) -> dict[str, list[str]]:
    """Corpus key 'zone/gridpoint-pore-pressure' -> HTML texts of that command's pages."""
    pages: dict[str, list[str]] = defaultdict(list)
    for root in roots:
        for path in root.rglob("cmd_*.html"):
            text = path.read_text(encoding="utf-8", errors="replace")
            m = COMMAND_ID.search(text)
            if m:
                head, _, rest = m.group(1).partition(".")
                key = f"{head}/{rest.replace('.', '-')}"
                if text not in pages[key]:  # the 7.0 installs ship the same shared pages
                    pages[key].append(text)
    return pages


def keywords(parser_cls, text: str) -> list[dict]:
    parser = parser_cls()
    parser.feed(text)
    return parser.keywords


def corpus_name(name: str, prefixed: bool) -> str:
    """'kwd:point' (a shared-block id) reads 'point' where the file's keywords are all bare."""
    bare = name.removeprefix("kwd:")
    return name if prefixed or bare in FIELD_DATA else bare


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def spaced(syntax: str) -> str:
    """The corpus spacing convention ('<i1> [<i2>...]', not the parser's '<i1>[<i2>...]')."""
    syntax = re.sub(r"(?<=[>\]}])(?=[<\[{\w])", " ", syntax)
    syntax = re.sub(r"(?<=\w)(?=[<\[{])", " ", syntax)
    return re.sub(r"\s+", " ", syntax).strip()


def similarity(a: str | None, b: str) -> float:
    return difflib.SequenceMatcher(None, a or "", b).ratio()


def transplant(parsed: str, edited: str, fresh: str) -> str | None:
    """Apply the hand edits that turned ``parsed`` into ``edited`` to ``fresh``.

    Each edit is located in ``fresh`` by its surrounding text; None when one cannot
    be placed unambiguously (or the edit rewrote most of the text).
    """
    matcher = difflib.SequenceMatcher(None, parsed, edited, autojunk=False)
    if matcher.ratio() < 0.6:
        return None
    for group in matcher.get_grouped_opcodes(15):
        before = parsed[group[0][1] : group[-1][2]]
        after = edited[group[0][3] : group[-1][4]]
        if fresh.count(before) != 1:
            return None
        fresh = fresh.replace(before, after)
    return fresh


def dump_like(data: dict, raw: str) -> str:
    """Serialize keeping the file's escaping: files mix raw characters and \\u escapes."""
    text = json.dumps(data, indent=2, ensure_ascii=True)
    for ch in {c for c in raw if not c.isascii()}:
        text = text.replace(json.dumps(ch)[1:-1], ch)
    return text + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", type=Path, required=True)
    ap.add_argument("--version", default="9.0", choices=sorted(DOC_ROOTS))
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    old_cls = load_old_parser(args.old)
    pages = page_index(DOC_ROOTS[args.version])

    replaced = review = 0
    for path in sorted(RESOURCES.glob("*/command_docs/commands/*/*.json")):
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        block = data.get("versions", {}).get(args.version)
        if not block:
            continue
        key = f"{path.parent.name}/{path.stem}"
        kws = block.get("keywords", [])
        prefixed = any(k["name"].startswith("kwd:") for k in kws)
        changed = []
        for text in pages.get(key, []):
            for old, new in zip(keywords(old_cls, text), keywords(CommandHTMLParser, text)):
                if old == new:
                    continue
                # Collapsed rows often share name and syntax (five 'time-total-zone' in
                # model solve); the description, which carries the parent's text, tells them apart.
                # The FLAC parser named the survivor after its whole id path
                # ('property-torsion-constant', 'history-stress-shear-position').
                same = [
                    i
                    for i, e in enumerate(kws)
                    if (
                        e["name"] == old["name"]
                        or (e["name"].startswith(new["name"] + "-") and e["name"].endswith("-" + old["name"]))
                    )
                    and squash(e["syntax"]) == squash(old["syntax"])
                ]
                exact = [i for i in same if squash(kws[i].get("description")) == squash(old["description"])]
                if exact:
                    i = exact[0]
                    extra = {k: v for k, v in kws[i].items() if k not in ("name", "syntax", "description")}
                    kws[i] = {
                        "name": corpus_name(new["name"], prefixed),
                        "syntax": spaced(new["syntax"]),
                        "description": new["description"],
                        **extra,
                    }
                    changed.append(f"{old['name']} -> {new['name']}")
                elif same and not any(e["name"] == new["name"] for e in kws):
                    i = max(same, key=lambda j: similarity(kws[j].get("description"), old["description"]))
                    description = transplant(old["description"], kws[i].get("description") or "", new["description"])
                    if description is None:
                        review += 1
                        print(
                            f"  REVIEW {path.relative_to(RESOURCES)}: '{old['name']}' was edited by hand; parent '{new['name']}'"
                        )
                        continue
                    extra = {k: v for k, v in kws[i].items() if k not in ("name", "syntax", "description")}
                    kws[i] = {
                        "name": corpus_name(new["name"], prefixed),
                        "syntax": spaced(new["syntax"]),
                        "description": description,
                        **extra,
                    }
                    changed.append(f"{old['name']} -> {new['name']} (hand edits carried over)")
        if changed:
            replaced += len(changed)
            print(f"{path.relative_to(RESOURCES)}: {', '.join(changed)}")
            if args.write:
                path.write_text(dump_like(data, raw), encoding="utf-8")
    print(f"replaced {replaced}, review {review}" + ("" if args.write else " (dry run)"))


if __name__ == "__main__":
    main()
