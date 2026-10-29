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

    The doc's ``command`` field is trusted when, separators aside, it ends with the key and
    has at least one word in front of it: it may spell the key's dashes as spaces, or as
    nothing ('model largestrain' where a manual writes it so), but it may not drop the
    category word ('cmat add') or add words ('zone geometry update-interval' for
    'geometry-update'). Otherwise the name falls back to ``'<prefix> <key>'``, dashes kept.
    """
    spoken = str(cmd_doc.get("command") or "").lower().split()
    flat = key.replace("-", "")
    if any("".join(spoken[i:]).replace("-", "") == flat for i in range(1, len(spoken))):
        return " ".join(spoken)
    return f"{prefix} {key}"


def group_of(name: str) -> str | None:
    """'block contact' for 'block contact apply'; None for a two-word name such as 'block merge-start'.

    The manuals nest commands one level below the category ('block contact commands',
    'structure beam commands'), so a three-word name's first two words are that heading.
    """
    words = name.split()
    return " ".join(words[:2]) if len(words) >= 3 else None
