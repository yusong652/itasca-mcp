"""Watch the Itasca v9 subscription release notes for revisions we have not seen.

Itasca ships point releases through one installer page whose "Software Update
Revisions" table lists every revision with a date and a description (new
features, bug fixes, each item optionally tagged with a product or FISH). The
corpus and the bridge follow those notes: a new FISH intrinsic or Python
binding means corpus work, a save/restore or scripting fix may change what the
bridge has to work around.

The script fetches the page, parses the table, and diffs it against the
snapshot checked into this repo. New revisions are printed in full, with the
items that mention scripting, commands, documentation, saving or crashes
marked so they are not missed in a long list. ``--update`` rewrites the
snapshot so the next run reports only what changed after it.

Usage:
    uv run python scripts/releases/itasca_release_watch.py            # report only
    uv run python scripts/releases/itasca_release_watch.py --update   # report and refresh the snapshot
    uv run python scripts/releases/itasca_release_watch.py --since 50 # print revisions newer than 50

Only stdlib is used so the script runs anywhere the repo is checked out.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

PAGE_URL = "https://www.itascacg.com/software/downloads/v9-subscription-installer"
SNAPSHOT = Path(__file__).resolve().parent / "itasca_subscription_revisions.json"
USER_AGENT = "Mozilla/5.0 (itasca-mcp release watch)"

# Products Itasca tags items with, as they appear inside <strong> in the notes.
PRODUCTS = (
    "FLAC3D",
    "FLAC2D",
    "FLAC",
    "3DEC",
    "PFC3D",
    "PFC2D",
    "PFC",
    "MPoint",
    "Massflow",
    "MassFlow",
    "FISH",
    "Python",
)

# An item mentioning any of these touches what itasca-mcp or the bridge documents or works around.
WATCH_TERMS = (
    "python",
    "fish",
    "intrinsic",
    "command",
    "keyword",
    "documentation",
    "docs",
    "save",
    "restore",
    "crash",
    "callback",
    "scripting",
    "api",
    "deprecat",
    "rename",
    "remove",
)

_ROW_RE = re.compile(r"<tr>\s*<td>(\d+)</td>\s*<td[^>]*>([^<]*)</td>\s*<td>(.*?)</td>\s*</tr>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def fetch(url: str = PAGE_URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - fixed https URL
        return resp.read().decode("utf-8", errors="replace")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", fragment))).strip()


def _item(fragment: str) -> dict[str, object]:
    """One <li>: the product tag it opens with (if any), the text, and whether it is worth a look."""
    text = _text(fragment)
    product = None
    for name in PRODUCTS:
        if text.startswith(name + " "):
            product = name
            text = text[len(name) + 1 :]
            break
    lowered = text.lower()
    flags = [term for term in WATCH_TERMS if term in lowered]
    item: dict[str, object] = {"text": text}
    if product:
        item["product"] = product
    if flags:
        item["watch"] = flags
    return item


_HEADING_LINE_RE = re.compile(r"^(?:<p>)?\s*<strong>(?:<em>)?([^<]+)(?:</em>)?</strong>\s*(?:</p>)?$")


def _lines(body: str) -> list[str]:
    """The description cell as raw lines: one per heading or item, whatever the markup.

    Revisions up to 53 are one <p> with <br>-separated "- item" lines under
    <strong>Heading</strong><br>; from 54 on each heading is its own <p> and the
    items are <li>. Both reduce to lines once <li>, <br>, </p> and </li> break them.
    """
    text = re.sub(r"<li>\s*(?:<p>)?", "\n- ", body)
    text = re.sub(r"</li>|<br\s*/?>|</p>|</?ul>", "\n", text)
    return [line.strip() for line in text.split("\n") if _text(line)]


def parse_revisions(page: str) -> list[dict[str, object]]:
    """Every row of the revisions table, newest first, as it appears on the page."""
    start = page.find('<a name="notes">')
    table = page[start:] if start >= 0 else page
    revisions = []
    for number, date, body in _ROW_RE.findall(table):
        sections: dict[str, list[dict[str, object]]] = {}
        heading = "Notes"
        for line in _lines(body):
            found = _HEADING_LINE_RE.match(line)
            if found:
                heading = _text(found.group(1))
                continue
            text_line = line
            if _text(text_line).startswith("- "):
                text_line = re.sub(r"^(?:<p>)?\s*-\s*", "", text_line)
            sections.setdefault(heading, []).append(_item(text_line))
        revisions.append({"revision": int(number), "date": date.strip(), "sections": sections})
    return revisions


def parse_latest(page: str) -> dict[str, str]:
    version = re.search(r"Latest Version:\s*<b>([^<]+)</b>", page)
    released = re.search(r"Released On:\s*<b>([^<]+)</b>", page)
    return {
        "version": version.group(1).strip() if version else "",
        "released": released.group(1).strip() if released else "",
    }


def load_snapshot() -> dict[str, object]:
    if SNAPSHOT.exists():
        return json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return {"latest": {}, "revisions": []}


def print_revision(rev: dict[str, object]) -> None:
    print(f"--- Revision {rev['revision']} ({rev['date']})")
    for heading, items in rev["sections"].items():  # type: ignore[union-attr]
        print(f"  {heading}")
        for item in items:
            mark = "*" if item.get("watch") else " "
            product = f"[{item['product']}] " if item.get("product") else ""
            print(f"   {mark} {product}{item['text']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--update", action="store_true", help="rewrite the snapshot after reporting")
    parser.add_argument("--since", type=int, help="print every revision newer than this number, ignoring the snapshot")
    parser.add_argument("--all", action="store_true", help="print every revision on the page")
    args = parser.parse_args()

    page = fetch()
    latest = parse_latest(page)
    revisions = parse_revisions(page)
    if not revisions:
        print("No revisions parsed; the page layout may have changed.", file=sys.stderr)
        return 2

    snapshot = load_snapshot()
    known = {r["revision"] for r in snapshot.get("revisions", [])}
    if args.all:
        new = revisions
    elif args.since is not None:
        new = [r for r in revisions if r["revision"] > args.since]
    else:
        new = [r for r in revisions if r["revision"] not in known]

    print(f"Latest: {latest['version']} ({latest['released']}); {len(revisions)} revisions on the page")
    if snapshot.get("latest"):
        print(
            f"Snapshot: {snapshot['latest'].get('version')} ({snapshot['latest'].get('released')}); {len(known)} revisions"
        )
    if not new:
        print("Nothing new.")
    else:
        flagged = sum(1 for r in new for items in r["sections"].values() for i in items if i.get("watch"))  # type: ignore[union-attr]
        print(
            f"{len(new)} new revision(s); {flagged} item(s) marked * mention scripting, commands, docs, save/restore or crashes\n"
        )
        for rev in new:
            print_revision(rev)

    if args.update:
        SNAPSHOT.write_text(
            json.dumps({"source": PAGE_URL, "latest": latest, "revisions": revisions}, indent=2, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        print(
            f"\nSnapshot written: {SNAPSHOT.relative_to(Path.cwd()) if SNAPSHOT.is_relative_to(Path.cwd()) else SNAPSHOT}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
