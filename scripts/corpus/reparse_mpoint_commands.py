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
from html.parser import HTMLParser
from pathlib import Path

MPM_DOC = Path("C:/Program Files/Itasca/Itasca Software Subscription/exe64/doc/mpm")
OUT_COMMANDS = Path("C:/Program Files/Itasca/Itasca Software Subscription/exe64/doc/out_commands.txt")
COMMANDS_DIR = Path("C:/Dev/Han/itasca-mcp/src/itasca_mcp/knowledge/resources/mpoint/command_docs/commands/mpoint")

DT_RE = re.compile(r'<dt\b[^>]*\bid="(command|kwd):([^"]+)"[^>]*>(.*?)</dt>', re.S)


def text_of(fragment: str) -> str:
    """Flatten markup. Tags become nothing, not spaces: the MPM pages wrap every
    single character in its own <span>, so inserting spaces shreds every word."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


class _SyntaxLabel(HTMLParser):
    """Render a syntax <dt> fragment as corpus syntax.

    text_of() is wrong for syntax lines. On the MPM pages a placeholder is
    <span class="varint">i</span>, not the literal text '<i>' the PFC pages use, so
    flattening the markup drops its brackets ('mpoint extra i a'). An optional group is
    a literal '<' ... '>' pair inside <span class="cmdopt">, and the opening bracket is
    glued to the next tag ('<<a href=...>range</a>>'), so a tag-stripping regex eats it
    together with the tag and leaves 'range>'. This parser emits <i> for a var span and
    [...] for a cmdopt span, which is the bracket convention the rest of the corpus uses.
    """

    def __init__(self) -> None:
        super().__init__()
        self.frames: list[tuple[str | None, list[str]]] = [(None, [])]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "span":
            return
        cls = dict(attrs).get("class") or ""
        kind = "var" if cls.startswith("var") else "opt" if cls == "cmdopt" else None
        self.frames.append((kind, []))

    def handle_endtag(self, tag: str) -> None:
        if tag != "span" or len(self.frames) == 1:
            return
        kind, parts = self.frames.pop()
        text = "".join(parts)
        if kind == "var":
            text = f" <{text.strip()}> "
        elif kind == "opt":
            text = f" [{text.strip()}] "
        self.frames[-1][1].append(text)

    def handle_data(self, data: str) -> None:
        if data.strip() in ("<", ">") and any(kind == "opt" for kind, _ in self.frames):
            return  # the literal brackets of an optional group; [...] stands in for them
        self.frames[-1][1].append(data)

    def label(self) -> str:
        while len(self.frames) > 1:  # unclosed spans: flush as plain text
            _, parts = self.frames.pop()
            self.frames[-1][1].append("".join(parts))
        text = " ".join(html.unescape("".join(self.frames[0][1])).split())
        return re.sub(r"\[\s+", "[", re.sub(r"\s+\]", "]", text))


def label_of(fragment: str) -> str:
    parser = _SyntaxLabel()
    parser.feed(fragment)
    return parser.label()


def description_after(source: str, dt_end: int) -> str:
    """Text of the <dd> following a <dt>, truncated at the first nested <dl>."""
    dd = re.compile(r"<dd\b[^>]*>", re.S).search(source, dt_end)
    if not dd:
        return ""
    start = dd.end()
    nested = re.compile(r"<dl\b", re.S).search(source, start)
    close = re.compile(r"</dd>", re.S).search(source, start)
    end = min(x.start() for x in (nested, close) if x) if (nested or close) else start
    text = text_of(source[start:end])
    # The page opens the <dd> with a 'Primary keywords: a b c' rubric before the
    # prose; the keyword list is not the description.
    return re.sub(r"^Primary keywords:(?:\s+[a-z][\w-]*)+\s+(?=[A-Z])", "", text)


def parse_page(path: Path) -> dict | None:
    source = path.read_text(encoding="utf-8", errors="replace")
    command_name = ""
    command_syntax = ""
    command_id = ""
    keywords: list[dict] = []
    seen: set[str] = set()

    for m in DT_RE.finditer(source):
        kind, ident, body = m.group(1), m.group(2), m.group(3)
        label = label_of(body)
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
