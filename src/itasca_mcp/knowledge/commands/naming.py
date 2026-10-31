"""The engine's spelling of a command, recovered from its corpus file key.

Command files are keyed by category directory and a dashed name: ``block/contact-apply.json``.
The dash stands in for the engine's space, so the key alone cannot tell
``block contact apply`` (a 'contact' command) from ``block merge-start`` (one hyphenated word).
The doc's ``command`` field is the manual's page title and keeps the real spelling.
"""

from __future__ import annotations

from typing import Any


def full_name(prefix: str, key: str, cmd_doc: dict[str, Any]) -> str:
    """'block contact apply' for key 'contact-apply' under prefix 'block'.

    The doc's ``command`` field is the name: the manual's page title, corrected where a live
    run disagreed ('wall conveyor' for the file keyed velocity-conveyor, 'rblock results' for
    result.json), and it may stand without the category word ('inlet create' is filed under
    brick but is its own command). The key is not checked against it; a scan of the corpus
    against the manual page stems is what keeps the field honest. Only a block without the
    field falls back to ``'<prefix> <key>'``, dashes kept.
    """
    spoken = " ".join(str(cmd_doc.get("command") or "").lower().split())
    return spoken or f"{prefix} {key}"


def group_of(name: str) -> str | None:
    """'block contact' for 'block contact apply'; None for a two-word name such as 'block merge-start'.

    The manuals nest commands one level below the category ('block contact commands',
    'structure beam commands'), so a three-word name's first two words are that heading.
    """
    words = name.split()
    return " ".join(words[:2]) if len(words) >= 3 else None
