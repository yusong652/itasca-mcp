"""Unified tool response envelope contracts.

All tool business payloads should be wrapped by this module so response
shapes stay consistent across documentation and execution tools.

Includes automatic response size enforcement to prevent context window
exhaustion in LLM clients.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# Maximum serialized response size in characters.
# MCP responses go into the LLM context window — large payloads waste tokens.
# 8000 chars ≈ 2000 tokens, leaving plenty of room for conversation.
MAX_RESPONSE_CHARS = 8000


class ToolError(BaseModel):
    """Structured business error for tool payloads."""

    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable error summary")
    details: dict[str, Any] | None = Field(default=None, description="Optional structured error details")


class ToolEnvelope(BaseModel):
    """Unified response shape for all tool business results."""

    ok: bool = Field(description="Business-level success flag")
    data: Any | None = Field(default=None, description="Tool-specific payload")
    error: ToolError | None = Field(default=None, description="Structured error payload")

    @model_validator(mode="after")
    def _validate_coherence(self) -> ToolEnvelope:
        if self.ok and self.error is not None:
            raise ValueError("ok=true responses must not include error")
        if not self.ok and self.error is None:
            raise ValueError("ok=false responses must include error")
        return self


DocsSource = Literal["commands", "python_api", "fish", "reference", "all"]


class DocsData(BaseModel):
    """Unified inner `data` schema for documentation tools."""

    source: DocsSource
    action: Literal["browse", "query"]
    entries: list[dict[str, Any]]
    summary: dict[str, Any] = Field(default_factory=dict)


def _truncate_strings_in_data(data: Any, budget: int) -> Any:
    """Recursively truncate long string values to fit within budget.

    Targets the most common oversized fields: 'output', 'doc', 'description'.
    """
    if isinstance(data, str):
        if len(data) > budget:
            cut = data[:budget].rsplit("\n", 1)[0]
            return cut + f"\n... (truncated, {len(data)} total chars. Use pagination or filter to see more.)"
        return data
    if isinstance(data, dict):
        return {k: _truncate_strings_in_data(v, budget) for k, v in data.items()}
    if isinstance(data, list):
        return [_truncate_strings_in_data(item, budget) for item in data]
    return data


def _enforce_size(envelope: dict[str, Any], max_chars: int = MAX_RESPONSE_CHARS) -> dict[str, Any]:
    """Enforce response size limit. If over budget, truncate large string fields."""
    serialized = json.dumps(envelope, ensure_ascii=False)
    if len(serialized) <= max_chars:
        return envelope

    # Truncate string fields in data, keeping structure intact
    per_field_budget = max_chars // 2
    envelope["data"] = _truncate_strings_in_data(envelope.get("data"), per_field_budget)

    # Final check — if still too large, replace data with summary
    serialized = json.dumps(envelope, ensure_ascii=False)
    if len(serialized) > max_chars * 2:
        envelope["data"] = {
            "_truncated": True,
            "_message": f"Response too large ({len(serialized)} chars). Use more specific queries or pagination.",
            "_original_size": len(serialized),
        }
    return envelope


def fits_response(data: Any, margin: int = 512) -> bool:
    """True when a success envelope around ``data`` stays clear of the size that blanks it.

    ``_enforce_size`` replaces ``data`` wholesale past ``2 * MAX_RESPONSE_CHARS``; documentation
    pages trim themselves below that first. ``margin`` leaves room for summary fields added later.
    """
    return len(json.dumps({"ok": True, "data": data}, ensure_ascii=False)) <= MAX_RESPONSE_CHARS * 2 - margin


def build_ok(data: Any) -> dict[str, Any]:
    """Build, validate, and size-enforce a success envelope."""
    envelope = ToolEnvelope(ok=True, data=data).model_dump(exclude_none=True)
    return _enforce_size(envelope)


def build_error(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    *,
    data: Any | None = None,
) -> dict[str, Any]:
    """Build and validate an error envelope."""
    return ToolEnvelope(
        ok=False,
        data=data,
        error=ToolError(code=code, message=message, details=details),
    ).model_dump(exclude_none=True)


def build_docs_data(
    *,
    source: Literal["commands", "python_api", "fish", "reference", "all"],
    action: Literal["browse", "query"],
    entries: list[dict[str, Any]],
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate documentation tool `data` payloads."""
    return DocsData(
        source=source,
        action=action,
        entries=entries,
        summary=summary or {},
    ).model_dump(exclude_none=True)
