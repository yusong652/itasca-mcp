"""Re-parse the MPoint command family using the doc's own keyword ids.

Why this exists (MPoint verification campaign, 2026-09-14):

The shared ``CommandHTMLParser`` recovers keyword names from the *text* of each
``<dt>``. On the MPM pages every character sits in its own ``<span>`` and
keyword blocks nest, and the result is that names get paired with the wrong
description -- shifted by one whenever a keyword has sub-keywords. The damage is
not cosmetic: ``mpoint import`` documented its ``from-zones`` keyword (the one
the official QuickStart uses to turn a zone mesh into material points) under the
name ``velocity``.

Sphinx gives us something much better than the text: every ``<dt>`` carries an
id -- ``command:mpoint.import`` for the command, ``kwd:mpoint.import.from-zones``
for a keyword, ``kwd:mpoint.import.from-zones.velocity`` for a sub-keyword. The
name is the last dot-segment and the nesting depth is the segment count, so both
come out exact. This parser reads those ids and pairs each with the text of the
``<dd>`` that follows it, stopping at the first nested ``<dl>``.

Depth-1 keywords keep their plain name; deeper ones are prefixed ``kwd:``,
matching the convention already used across the corpus. Pages also carry a
second id namespace for shared modifier blocks (``kwd:component``,
``kwd:component.magnitude``, ``kwd:quantity.zz``, ``kwd:type.vector``); those
are the vocabulary the keywords accept rather than keywords of the command, so
they are kept under their own dotted ``kwd:`` path. The old parser lifted some
of their *values* (magnitude, zz, vector) into the top-level keyword list.

Names are cross-checked against ``out_commands.txt`` (the installed command
index) and any disagreement is reported.

Usage:
    uv run python scripts/corpus/reparse_mpoint_commands.py [--write]
"""

import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

MPM_DOC = Path("C:/Program Files/Itasca/Itasca Software Subscription/exe64/doc/mpm")
OUT_COMMANDS = Path("C:/Program Files/Itasca/Itasca Software Subscription/exe64/doc/out_commands.txt")
COMMANDS_DIR = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/mpoint/command_docs/commands/mpoint")

DT_RE = re.compile(r'<dt\b[^>]*\bid="(command|kwd):([^"]+)"[^>]*>(.*?)</dt>', re.S)


def text_of(fragment: str) -> str:
    """Flatten markup. Tags become nothing, not spaces: the MPM pages wrap every
    single character in its own <span>, so inserting spaces shreds every word."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def description_after(source: str, dt_end: int) -> str:
    """Text of the <dd> following a <dt>, truncated at the first nested <dl>."""
    dd = re.compile(r"<dd\b[^>]*>", re.S).search(source, dt_end)
    if not dd:
        return ""
    start = dd.end()
    nested = re.compile(r"<dl\b", re.S).search(source, start)
    close = re.compile(r"</dd>", re.S).search(source, start)
    end = min(x.start() for x in (nested, close) if x) if (nested or close) else start
    return text_of(source[start:end])


def parse_page(path: Path) -> dict | None:
    source = path.read_text(encoding="utf-8", errors="replace")
    command_name = ""
    command_syntax = ""
    command_id = ""
    keywords: list[dict] = []
    seen: set[str] = set()

    for m in DT_RE.finditer(source):
        kind, ident, body = m.group(1), m.group(2), m.group(3)
        label = text_of(body)
        if kind == "command":
            command_id = ident
            command_name = ident.replace(".", " ")
            command_syntax = label
            continue
        if not command_id:
            continue
        if ident.startswith(command_id + "."):
            segments = ident[len(command_id) + 1 :].split(".")
            name = segments[-1] if len(segments) == 1 else "kwd:" + segments[-1]
        else:
            # Shared modifier blocks live in their own id namespace on the same
            # page (kwd:component, kwd:component.magnitude, kwd:quantity.zz, ...).
            # They are not keywords of this command -- they are the vocabulary its
            # keywords accept -- so keep the dotted path and mark them kwd:.
            name = "kwd:" + ident
        if name in seen:
            continue
        seen.add(name)
        keywords.append({"name": name, "syntax": label, "description": description_after(source, m.end())})

    if not command_name:
        return None
    # page description: first paragraph after the command's own <dd>
    desc = description_after(source, source.find('id="command:' + command_id))
    return {"command": command_name, "syntax": command_syntax, "keywords": keywords, "description": desc}


def official_keywords() -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for line in OUT_COMMANDS.read_text(encoding="utf-8", errors="replace").splitlines():
        key = line.split(" ", 1)[0]
        if not key.startswith("mpoint."):
            continue
        parts = key.split(".")
        if parts[1] == "node":
            if len(parts) == 4:
                out["mpoint node " + parts[2]].add(parts[3])
        elif len(parts) == 3:
            out["mpoint " + parts[1]].add(parts[2])
    return out


def main() -> None:
    write = "--write" in sys.argv
    official = official_keywords()
    changed = 0
    mismatches = 0

    for page in sorted(MPM_DOC.rglob("cmd_mpoint*.html")):
        parsed = parse_page(page)
        if parsed is None or "." in parsed["command"]:
            continue
        command = parsed["command"]
        stem = command.replace("mpoint node ", "node-").replace("mpoint ", "")
        target = COMMANDS_DIR / f"{stem}.json"
        if not target.exists():
            print(f"  [NEW]  {stem}.json  ({command})")

        new_names = [k["name"] for k in parsed["keywords"] if not k["name"].startswith("kwd:")]
        ref = official.get(command)
        if ref is not None and set(new_names) != ref:
            mismatches += 1
            print(f"  [DIFF] {command}: parsed={sorted(new_names)} official={sorted(ref)}")

        old_names: list[str] = []
        if target.exists():
            old = json.loads(target.read_text(encoding="utf-8"))
            old_names = [
                k["name"] for k in old["versions"]["9.0"].get("keywords", []) if not k["name"].startswith("kwd:")
            ]

        if old_names != new_names:
            changed += 1
            print(f"  [FIX]  {command}")
            print(f"           was: {old_names}")
            print(f"           now: {new_names}")

        if write:
            # Only the parsed fields are regenerated. Anything a human or another
            # pipeline added (notes, figure_reference, examples) is carried over.
            doc = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
            block = doc.get("versions", {}).get("9.0", {})
            doc.update(
                {
                    "category": "mpoint",
                    "search_keywords": command.split(),
                    "description": parsed["description"],
                    "python_sdk_alternative": doc.get("python_sdk_alternative", {"available": False}),
                }
            )
            block.update({"command": command, "syntax": parsed["syntax"], "keywords": parsed["keywords"]})
            block.setdefault("examples", [])
            doc["versions"] = {"9.0": block}
            target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\ncommands with changed keyword names: {changed}")
    print(f"commands still disagreeing with out_commands.txt: {mismatches}")
    if not write:
        print("(dry run -- pass --write to apply)")


if __name__ == "__main__":
    main()
