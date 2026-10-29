"""Flag command docs that have reference figures the text corpus dropped.

The corpus is text-extracted from Itasca HTML `<dt>`/`<dd>` (see `parse_pfc*.py`);
`<img>` thumbnails are discarded. For figure-bearing commands the visual detail --
and for the primitive creators (`zone create`, `zone create2d`) the load-bearing
geometry (reference-point ordering, `size` -> direction mapping, `dimension`
meaning) -- is therefore missing from the text.

This pass annotates every affected command doc with a structured
`figure_reference` flag so the gap is visible to agents at query time (it flows
untouched through `CommandLoader._resolve_versioned_doc` into the `doc` payload of
`itasca_browse_doc(source='commands')`).

Two independent signals, deliberately kept separate:

* `figures` -- the actual reference figures, sourced from the ground truth
  (`extract_figure_refs.py` -> `figure_manifest.json`, each path verified on disk
  at extraction time). This is a neutral fact: "these figures exist at these
  paths; read them if you need them." Complete coverage, no judgement.
* `text_incomplete` / `deferrals` -- set only when the extracted *text* itself
  explicitly punts to a figure ("refer to the figures above"). This is the
  high-confidence "the spec is in the picture, do not guess" sub-signal.

Sourcing `figures` from the committed manifest (not the local install) keeps this
pass -- and its `--check` CI guard -- runnable anywhere. Re-run
`extract_figure_refs.py` to refresh the manifest against a new engine release.

Idempotent: re-running recomputes the flag from scratch.

Usage:
    uv run python scripts/corpus/flag_figure_defined.py
    uv run python scripts/corpus/flag_figure_defined.py --check   # exit 1 if stale (CI guard)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, cast

_HERE = Path(__file__).resolve().parent
RESOURCES = _HERE.parents[1] / "src" / "itasca_mcp" / "knowledge" / "resources"
MANIFEST_PATH = _HERE / "figure_manifest.json"

FLAG_KEY = "figure_reference"

# Phrases in the extracted text that explicitly defer to a figure/image. A hit
# means the text itself admits it is incomplete without the picture.
DEFERRAL_PATTERNS: tuple[str, ...] = (
    r"refer to the figures?\b",
    r"refer to figures?\b",
    r"see the figures?\b",
    r"\bfigures?\s+above\b",
    r"\breference images?\b",
    r"illustrated in the reference",
    r"shown in the reference image",
    r"click (?:on )?any thumbnail",
    r"\bthumbnails?\b",
)
_COMPILED = [re.compile(p, re.IGNORECASE) for p in DEFERRAL_PATTERNS]

# Where the figures live, so an agent can open them.
_DOC_ROOT_HINT = (
    "Figures are PNGs under <doc-root>/_images/ (doc-root sits beside the engine "
    "install, e.g. C:/Program Files/Itasca/<product>/exe64/doc); read them directly."
)
NOTE_NEUTRAL = "This command embeds reference figures that are not captured in this text corpus. " + _DOC_ROOT_HINT
NOTE_INCOMPLETE = (
    "The text below explicitly defers to figures that are not captured in this corpus, so "
    "load-bearing detail (reference-point ordering point 0..N, size -> direction mapping, "
    "dimension meaning) is missing here. Do not guess it: read the figure -- " + _DOC_ROOT_HINT + " "
    "Or confirm empirically: build one primitive and read back gridpoint coordinates via "
    "itasca_execute_code to deduce the convention."
)

MAX_DEFERRALS = 6


def load_manifest() -> dict[str, list[dict[str, str]]]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"figure manifest not found: {MANIFEST_PATH}. Run extract_figure_refs.py first.")
    return cast("dict[str, list[dict[str, str]]]", json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))


def _find_deferrals(text: str) -> list[str]:
    """Distinct sentences in ``text`` that defer to a figure."""
    hits: list[str] = []
    for sentence in re.split(r"(?<=[.;])\s+", text or ""):
        s = sentence.strip()
        if s and any(rx.search(s) for rx in _COMPILED):
            hits.append(s)
    return hits


def _collect_deferrals(doc: dict[str, Any], version_doc: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    if isinstance(doc.get("description"), str):
        texts.append(doc["description"])
    if isinstance(version_doc.get("description"), str):
        texts.append(version_doc["description"])
    for kw in version_doc.get("keywords", []) or []:
        if isinstance(kw, dict) and isinstance(kw.get("description"), str):
            texts.append(kw["description"])

    deferrals: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for hit in _find_deferrals(text):
            if hit not in seen:
                seen.add(hit)
                deferrals.append(hit)
    return deferrals


def _build_flag(
    figures: list[dict[str, str]] | None,
    deferrals: list[str],
) -> dict[str, Any] | None:
    """Assemble the figure_reference flag from the two signals, or None."""
    if not figures and not deferrals:
        return None
    flag: dict[str, Any] = {}
    if figures:
        flag["figures"] = figures
    if deferrals:
        flag["text_incomplete"] = True
        flag["deferrals"] = deferrals[:MAX_DEFERRALS]
    flag["note"] = NOTE_INCOMPLETE if deferrals else NOTE_NEUTRAL
    return flag


def _set_or_clear(target: dict[str, Any], flag: dict[str, Any] | None) -> bool:
    if flag is None:
        return target.pop(FLAG_KEY, None) is not None
    if target.get(FLAG_KEY) == flag:
        return False
    target[FLAG_KEY] = flag
    return True


def _apply_to_doc(doc: dict[str, Any], manifest: dict[str, list[dict[str, str]]]) -> bool:
    """Annotate ``doc`` in place. Return True if anything changed."""
    changed = False
    versions = doc.get("versions")

    if isinstance(versions, dict):
        for version_doc in versions.values():
            if not isinstance(version_doc, dict):
                continue
            if version_doc.get("available") is False:
                # No content for this version; never carries a flag.
                changed |= version_doc.pop(FLAG_KEY, None) is not None
                continue
            command = version_doc.get("command") or doc.get("command") or ""
            figures = manifest.get(command)
            deferrals = _collect_deferrals(doc, version_doc)
            changed |= _set_or_clear(version_doc, _build_flag(figures, deferrals))
    else:
        command = doc.get("command") or ""
        figures = manifest.get(command)
        deferrals = _collect_deferrals(doc, doc)
        changed |= _set_or_clear(doc, _build_flag(figures, deferrals))

    return changed


def _command_names(doc: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    versions = doc.get("versions")
    if isinstance(versions, dict):
        for vdoc in versions.values():
            if isinstance(vdoc, dict) and vdoc.get("command"):
                names.add(vdoc["command"])
    if doc.get("command"):
        names.add(doc["command"])
    return names


def iter_command_docs() -> list[Path]:
    return sorted(RESOURCES.glob("*/command_docs/commands/**/*.json"))


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    manifest = load_manifest()
    stale: list[Path] = []
    flagged = 0
    matched_commands: set[str] = set()

    for path in iter_command_docs():
        doc = json.loads(path.read_text(encoding="utf-8"))
        if _apply_to_doc(doc, manifest):
            stale.append(path)
            if not check_only:
                path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if _doc_is_flagged(doc):
            flagged += 1
        matched_commands |= _command_names(doc) & manifest.keys()

    unmatched = sorted(set(manifest) - matched_commands)

    if check_only:
        if stale:
            print(f"[STALE] {len(stale)} command doc(s) need re-flagging:")
            for p in stale:
                print(f"  {p.relative_to(RESOURCES.parents[0])}")
            print("Run: uv run python scripts/corpus/flag_figure_defined.py")
            return 1
        print(f"figure_reference flags up to date ({flagged} flagged docs).")
        return 0

    print(f"Updated {len(stale)} file(s); {flagged} command doc(s) now carry a figure_reference flag.")
    if unmatched:
        print(f"Note: {len(unmatched)} manifest command(s) have no corpus doc (figures unused): {unmatched}")
    return 0


def _doc_is_flagged(doc: dict[str, Any]) -> bool:
    versions = doc.get("versions")
    if isinstance(versions, dict):
        return any(isinstance(v, dict) and FLAG_KEY in v for v in versions.values())
    return FLAG_KEY in doc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
