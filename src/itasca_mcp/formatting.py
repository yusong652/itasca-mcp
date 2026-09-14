"""Formatting and error rendering helpers for MCP tool outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from itasca_mcp.config import get_bridge_config
from itasca_mcp.contracts import build_error

# =============================================================================
# Task status / output formatting
# =============================================================================


def format_unix_timestamp(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return str(value)
    try:
        return datetime.fromtimestamp(timestamp).isoformat(sep=" ", timespec="seconds")
    except Exception:
        return str(value)


def format_elapsed_seconds(value: Any) -> float | None:
    """Round a bridge-supplied elapsed-time float to 2 decimals for display.

    The bridge reports elapsed wall-clock at full float precision (e.g.
    0.010000944137573242); sub-millisecond digits are noise for a task
    duration. Kept numeric (not stringified) so the field stays
    machine-readable. None and unparseable values pass through as None.
    """
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def paginate_output(
    output: str,
    skip_newest: int,
    limit: int,
    filter_text: str | None,
) -> tuple[str, dict[str, Any]]:
    lines = output.splitlines() if output else []
    if filter_text:
        lines = [line for line in lines if filter_text in line]

    total_lines = len(lines)
    start_idx = max(0, total_lines - limit - skip_newest)
    end_idx = max(0, total_lines - skip_newest)
    selected = lines[start_idx:end_idx]

    pagination = {
        "total_lines": total_lines,
        "line_range": f"{start_idx + 1}-{end_idx}" if selected else "0-0",
    }

    return "\n".join(selected) if selected else "(no output)", pagination


# =============================================================================
# Bridge error formatting
# =============================================================================


def is_bridge_connectivity_error(exc: Exception) -> bool:
    """Best-effort detection for bridge connectivity failures."""
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True

    lowered = str(exc).strip().lower()
    return (
        "connect call failed" in lowered
        or "connection refused" in lowered
        or "connection lost" in lowered
        or "connection closed" in lowered
        or "bridge" in lowered
        and "unavailable" in lowered
        or "[errno 61]" in lowered
    )


def _summarize_bridge_error(exc: Exception) -> str:
    text = str(exc).strip()
    lowered = text.lower()

    if "connect call failed" in lowered or "connection refused" in lowered or "[errno 61]" in lowered:
        return "cannot connect to bridge service"
    if "timed out" in lowered:
        return "bridge request timed out"
    if "connection closed" in lowered or "connection lost" in lowered:
        return "bridge connection closed"
    if not text:
        return "unknown bridge error"
    return text.splitlines()[0]


def build_bridge_error(exc: Exception, *, task_id: str | None = None) -> dict[str, Any]:
    """Build a unified error envelope for bridge connectivity failures."""
    cfg = get_bridge_config()
    reason = _summarize_bridge_error(exc)
    details: dict[str, Any] = {
        "bridge_url": cfg.url,
        "reason": reason,
        "action": (
            "start itasca-mcp-bridge in the Itasca engine GUI, then retry; "
            "if needed, the engine's console.exe can start it unattended"
        ),
    }
    if task_id:
        details["task_id"] = task_id
    return build_error("bridge_unavailable", "Itasca bridge unavailable", details)


def build_operation_error(
    code: str,
    message: str,
    *,
    reason: str | None = None,
    task_id: str | None = None,
    action: str | None = None,
    output: str | None = None,
) -> dict[str, Any]:
    """Build a unified error envelope for operation failures.

    `output` lets callers attach captured stdout/console output produced
    before the failure — invaluable when an LLM-issued batch of commands
    fails partway through and the agent needs to see which command broke.
    """
    details: dict[str, Any] = {}
    if reason:
        details["reason"] = reason
    if task_id:
        details["task_id"] = task_id
    if action:
        details["action"] = action
    if output:
        details["output"] = output
    return build_error(code, message, details or None)
