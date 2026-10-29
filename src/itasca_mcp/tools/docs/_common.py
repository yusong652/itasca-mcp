"""Shared helpers for the two documentation tools (``itasca_browse_doc`` / ``itasca_query_doc``)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection, Iterable, Iterator
from functools import partial
from typing import Any

from itasca_mcp.contracts import build_error, fits_response
from itasca_mcp.utils import (
    CommandDocVersion,
    effective_doc_version,
    normalize_command_doc_version,
    supported_doc_versions,
)

VERSION_DESCRIPTION = (
    "Documentation version. Defaults to 9.0 (the current 9.x release); PFC also has 6.0 and 7.0, "
    "FLAC and 3DEC have 7.0; 9.0-only engines (MPoint, MassFlow) always resolve at 9.0. Gates "
    "commands, fish and reference entries by availability; python_api is a single 9.8 baseline "
    "whose docs carry their own availability notes."
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
SUMMARY_MAX = 240


def first_sentence(text: str | None, limit: int = SUMMARY_MAX) -> str:
    """The one-line summary listings and search hits show for an entry."""
    sentence = _SENTENCE_END.split(" ".join((text or "").split()), maxsplit=1)[0]
    if len(sentence) > limit:
        sentence = sentence[:limit].rsplit(" ", 1)[0] + " ..."
    return sentence


def resolve_doc_version(software: str, version: CommandDocVersion | str) -> tuple[str | None, dict[str, Any] | None]:
    """``(version, None)`` when the engine's corpus covers it, else ``(None, error envelope)``."""
    value = effective_doc_version(software, normalize_command_doc_version(version))
    supported = supported_doc_versions(software)
    if value not in supported:
        return None, build_error(
            code="unsupported_version",
            message=f"{software} documentation covers versions: {', '.join(sorted(supported))}.",
            details={"input": {"software": software, "version": value}},
        )
    return value, None


# (kind, field, apply): kind is "omit" (field dropped) or "compact" (field shortened).
Reduction = tuple[str, str, Callable[[], None]]


def trim_to_response(payload: dict[str, Any], reductions: Iterable[Reduction], hint: str) -> bool:
    """Apply ``reductions`` in order until ``payload`` fits one response; report them in its summary.

    A page that fits is left untouched. The caller's reductions must only rebind fields on
    copies, never mutate loader data, and whatever they drop must stay reachable by a deeper
    path, which ``hint`` names.
    """
    omitted: list[str] = []
    compacted: list[str] = []
    for kind, field, apply in reductions:
        if fits_response(payload):
            break
        apply()
        (omitted if kind == "omit" else compacted).append(field)
    if not (omitted or compacted):
        return False
    summary = payload.setdefault("summary", {})
    if omitted:
        summary["omitted_sections"] = omitted
    if compacted:
        summary["compacted"] = compacted
    summary["hint"] = hint
    return True


def omit_largest(doc: dict[str, Any], keep: Collection[str]) -> Iterator[Reduction]:
    """Reductions dropping ``doc``'s fields outside ``keep``, largest first.

    Lazy: sized when first consumed, so it sees what earlier reductions already removed.
    """
    sizes = {key: len(json.dumps(value, ensure_ascii=False)) for key, value in doc.items() if key not in keep}
    for key in sorted(sizes, key=sizes.__getitem__, reverse=True):
        yield ("omit", key, partial(doc.pop, key))


def compact_field(doc: dict[str, Any], field: str, shorten: Callable[[Any], Any]) -> Iterator[Reduction]:
    """A reduction replacing ``doc[field]`` with ``shorten(doc[field])``; none when the field is absent."""
    if field in doc:
        yield ("compact", field, lambda: doc.__setitem__(field, shorten(doc[field])))


def omit_entry_fields(entries: list[dict[str, Any]], *fields: str) -> Iterator[Reduction]:
    """Reductions dropping each named field from every entry of a listing, in the order given."""
    for field in fields:
        yield ("omit", field, partial(_pop_from_each, entries, field))


def _pop_from_each(entries: list[dict[str, Any]], field: str) -> None:
    for entry in entries:
        entry.pop(field, None)


def stamp_summary(envelope: dict[str, Any], *, software: str, version: str) -> dict[str, Any]:
    """Make sure every successful docs payload states which engine/version it answered for."""
    if envelope.get("ok"):
        data = envelope.get("data")
        if isinstance(data, dict):
            summary = data.setdefault("summary", {})
            summary.setdefault("software", software)
            summary.setdefault("version", version)
    return envelope
