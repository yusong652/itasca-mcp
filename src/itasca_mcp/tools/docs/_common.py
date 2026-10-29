"""Shared helpers for the two documentation tools (``itasca_browse_doc`` / ``itasca_query_doc``)."""

from __future__ import annotations

from typing import Any

from itasca_mcp.contracts import build_error
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


def stamp_summary(envelope: dict[str, Any], *, software: str, version: str) -> dict[str, Any]:
    """Make sure every successful docs payload states which engine/version it answered for."""
    if envelope.get("ok"):
        data = envelope.get("data")
        if isinstance(data, dict):
            summary = data.setdefault("summary", {})
            summary.setdefault("software", software)
            summary.setdefault("version", version)
    return envelope
