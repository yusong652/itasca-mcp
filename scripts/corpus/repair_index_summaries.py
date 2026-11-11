"""Replace index summaries that were cut mid-word with whole sentences.

The category indexes carry a one-line summary per item, originally taken as a
fixed-length slice of the item's own description (120, 160, 180 or 50
characters), so most ended inside a word: "...applicable to". Where an index
summary is such a slice, this rewrites it as the leading whole sentences of
the description, up to a soft length.

Hand-written summaries (not a prefix of the item description) are left alone.
Idempotent. Usage:
    uv run python scripts/corpus/repair_index_summaries.py [--write]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from itasca_mcp.knowledge.references.loader import ReferenceLoader

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"
SOFT_LIMIT = 220
ENDS = re.compile(r"[.!?][)\]'\"”]?$")
SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(‘'\"“])")
EQUATION_LEAD = re.compile(r"\(\d+\)\s*$")
NO_BREAK = ("et al.", "e.g.", "i.e.", "vs.", "Eq.", "Eqs.", "Fig.", "Figs.", "cf.", "approx.", "resp.")


def leading_sentences(text: str, soft_limit: int = SOFT_LIMIT) -> str:
    """The first sentence, plus following ones while the total stays within the soft limit."""
    text = " ".join(text.split())
    equation = text.find("\\[")
    if equation > 0:  # a display equation follows: stop at the sentence that introduces it
        text = EQUATION_LEAD.sub("", text[:equation]).rstrip(" :,") + "."
    sentences: list[str] = []
    for piece in SPLIT.split(text):
        if sentences and sentences[-1].endswith(NO_BREAK):
            sentences[-1] += " " + piece
        else:
            sentences.append(piece)
    out = sentences[0]
    for sentence in sentences[1:]:
        if len(out) + 1 + len(sentence) > soft_limit:
            break
        out += " " + sentence
    return out


def main() -> None:
    write = "--write" in sys.argv
    changed_total = 0
    for index_path in sorted(RESOURCES.glob("*/references/*/index.json")):
        engine, _, category = index_path.relative_to(RESOURCES).parts[:3]
        raw = index_path.read_bytes()
        index = json.loads(raw.decode("utf-8"))
        changed = 0
        for key in ("models", "elements", "items"):
            entries = index.get(key)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                name = entry.get("name") if isinstance(entry, dict) else None
                if not name:
                    continue
                doc = ReferenceLoader.load_item_doc(category, name, software=engine) or {}
                full = doc.get("description")
                if not isinstance(full, str):
                    continue
                full = " ".join(full.split())
                for field in ("description", "short_description"):
                    value = entry.get(field)
                    if not isinstance(value, str) or not value or ENDS.search(value.strip()):
                        continue
                    stub = " ".join(value.split())
                    if len(stub) >= len(full) or not full.startswith(stub):
                        continue
                    summary = leading_sentences(full)
                    if summary != value:
                        entry[field] = summary
                        changed += 1
        if changed:
            changed_total += changed
            print(f"{changed:3d}  {index_path.relative_to(RESOURCES).as_posix()}")
            if write:
                newline = "\r\n" if b"\r\n" in raw else "\n"
                with open(index_path, "w", encoding="utf-8", newline=newline) as handle:
                    json.dump(index, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
    print(changed_total, "summaries", "WRITTEN" if write else "(dry run)")


if __name__ == "__main__":
    main()
