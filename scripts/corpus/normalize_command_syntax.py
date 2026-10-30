"""Normalize command syntax strings to the corpus bracket convention.

The parsers assembled syntax from the manual's italic/placeholder spans and
dropped the spaces between them ('<i><a>[range]', '<fx><fy><fz>', 'id <i>keyword'),
doubled the shared-block markers ('[[faceapplyblock]]'), and the FLAC parser kept
the manual's own conventions: bare placeholder letters ('dip f', 'slot s') and
optional groups in angle brackets ('<range>', '<slot <s> >', '<[faceapplyblock]>').
The rest of the corpus writes placeholders as <f>/<v>/<s> and optional parts in
[...], so a reader cannot tell '<range>' (optional range) from '<s>' (a string)
without knowing which engine the file came from.

Rules, all engines: collapse [[x]] to [x]; '<f >' to '<f>'; '<i>a' (a lost <a>) to
'<i> <a>'; '<keyword>' / '<keyword...>' / '<range>' to the bracket form; a space
after '>' or ']' when a letter, '[', '<' or '...' follows.

Rules, FLAC only (the engine whose blocks carry the manual convention): an angle
group that is not a single placeholder token becomes [...], recursively; a bare
f/i/v/s/b token (optionally numbered) becomes <f>/<i>/...; a handful of optional
keywords the manual wrote as <remove>, <nodes>, <local>, <mass>, ... become [remove].
Anything else inside <...> (sgroup, prop, nplane, R) is a placeholder and stays.

Usage:
    uv run python scripts/corpus/normalize_command_syntax.py [--write] [--engine flac]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RESOURCES = Path(__file__).resolve().parents[2] / "src" / "itasca_mcp" / "knowledge" / "resources"

ANGLE_OPTIONAL_ENGINES = {"flac"}
# Optional keywords the FLAC manual writes in angle brackets; single tokens, so the
# placeholder rule would otherwise keep them as <remove>.
OPTIONAL_WORDS = {
    "range", "keyword", "keyword...", "remove", "nodes", "local", "mass", "stiffness",
    "novalidate", "no-edges-cp", "alternate", "binary", "invalid", "path",
}  # fmt: skip
BARE_PLACEHOLDER = re.compile(r"(?<![\w<>\[\]./-])([fivsb]\d?)(\.\.\.)?(?![\w>./-])")
SINGLE_TOKEN = re.compile(r"^[^\s<>\[\]|{}]+$")


def _matching(s: str, start: int) -> int:
    """Index of the '>' closing the '<' at ``start``; -1 when unbalanced."""
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "<":
            depth += 1
        elif s[i] == ">":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _angle_groups_to_brackets(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] != "<":
            out.append(s[i])
            i += 1
            continue
        j = _matching(s, i)
        if j < 0:
            out.append(s[i:])
            break
        inner = _angle_groups_to_brackets(s[i + 1 : j]).strip()
        if SINGLE_TOKEN.match(inner) and inner not in OPTIONAL_WORDS:
            out.append(f"<{inner}>")
        elif inner.startswith("[") and inner.endswith("]") and _balanced(inner[1:-1], "[", "]"):
            out.append(inner)  # '<[faceapplyblock]>' is just the marker
        else:
            out.append(f"[{inner}]")
        i = j + 1
    return "".join(out)


def _balanced(s: str, open_: str, close: str) -> bool:
    depth = 0
    for ch in s:
        if ch == open_:
            depth += 1
        elif ch == close:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def normalize_syntax(s: str, *, angle_optional: bool = False) -> str:
    s = s.rstrip("\\").strip()
    while re.search(r"\[\[([^\[\]]*)\]\]", s):
        s = re.sub(r"\[\[([^\[\]]*)\]\]", r"[\1]", s)
    s = re.sub(r"<\s*([^<>\s]+)\s*>", r"<\1>", s)
    s = re.sub(r"<i>a\b", "<i> <a>", s)
    s = s.replace("<keyword...>", "[keyword ...]").replace("<keyword>", "[keyword]").replace("<range>", "[range]")
    if angle_optional:
        s = _angle_groups_to_brackets(s)
        s = BARE_PLACEHOLDER.sub(lambda m: f"<{m.group(1)}>" + (" ..." if m.group(2) else ""), s)
    s = re.sub(r"([>\]])(?=[A-Za-z\[<]|\.\.\.|[23]D)", r"\1 ", s)
    s = re.sub(r"\[\s+", "[", s)
    s = re.sub(r"\s+\]", "]", s)
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    write = "--write" in sys.argv
    only = sys.argv[sys.argv.index("--engine") + 1] if "--engine" in sys.argv else None
    changed_files = 0
    changed_strings = 0
    samples: list[str] = []
    for path in sorted(RESOURCES.rglob("command_docs/commands/*/*.json")):
        engine = path.relative_to(RESOURCES).parts[0]
        if only and engine != only:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        touched = False
        for version, block in (doc.get("versions") or {}).items():
            if not isinstance(block, dict):
                continue
            holders = [block] + [k for k in block.get("keywords") or [] if isinstance(k, dict)]
            for holder in holders:
                old = holder.get("syntax")
                if not isinstance(old, str) or not old:
                    continue
                new = normalize_syntax(old, angle_optional=engine in ANGLE_OPTIONAL_ENGINES)
                if new != old:
                    touched = True
                    changed_strings += 1
                    if len(samples) < 400:
                        samples.append(f"{engine} {version} {path.parent.name}/{path.stem}\n      {old}\n   -> {new}")
                    holder["syntax"] = new
        if touched:
            changed_files += 1
            if write:
                path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # The per-engine index.json repeats each command's syntax; keep it in step.
    index_strings = 0
    for index_path in sorted(RESOURCES.glob("*/command_docs/index.json")):
        engine = index_path.parent.parent.name
        if only and engine != only:
            continue
        index = json.loads(index_path.read_text(encoding="utf-8"))
        touched = False
        for category in index.get("categories", {}).values():
            for command in category.get("commands", []):
                old = command.get("syntax")
                if not isinstance(old, str) or not old:
                    continue
                new = normalize_syntax(old, angle_optional=engine in ANGLE_OPTIONAL_ENGINES)
                if new != old:
                    command["syntax"] = new
                    touched = True
                    index_strings += 1
        if touched and write:
            index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n".join(samples))
    print(
        f"\nchanged strings: {changed_strings} in {changed_files} files; index entries: {index_strings}"
        + ("" if write else " (dry run)")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
