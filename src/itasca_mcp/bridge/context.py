"""Bridge context: what happened in the engine GUI between the agent's calls.

Two pieces live here:

* ``fetch_bridge_context`` pulls the runtime signals the bridge keeps for
  the client (today: what the person typed into the product's consoles)
  and returns them as one dict.
* ``with_context`` is applied at the tool boundary. It awaits the tool's
  envelope, success or error alike, and attaches ``_context`` in one
  place, so the contract layer stays pure and both branches get the same
  treatment.

Context is best-effort: a bridge that cannot be reached, or has nothing
new, leaves the tool's own result untouched.
"""

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from itasca_mcp.bridge.client import get_bridge_client

logger = logging.getLogger("itasca-mcp.context")

USER_CONSOLE_DESCRIPTION = (
    "What the USER typed into the Itasca product GUI since the last tool call, "
    "not from this session: 'python' entries are cells run in the IPython pane, "
    "'command' entries are lines entered at the product's command prompt."
)


async def fetch_bridge_context() -> dict[str, Any] | None:
    """Fetch context from the bridge, or None when there is nothing to add."""
    context: dict[str, Any] = {}

    try:
        client = await get_bridge_client()
        response = await client.consume_console_history()
        data = response.get("data") or {}
        entries = data.get("entries") or []
        if entries:
            context["user_console"] = {
                "description": USER_CONSOLE_DESCRIPTION,
                "entries": [_format_entry(e) for e in entries],
            }
    except Exception as exc:
        logger.debug("Console context unavailable: %s", exc)

    return context or None


def with_context(
    func: Callable[..., Awaitable[dict[str, Any]]],
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Attach ``_context`` to a tool's envelope, on success and on error alike.

    Fetch failures are swallowed: the tool's own result is always returned.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        envelope = await func(*args, **kwargs)
        try:
            context = await fetch_bridge_context()
            if context and isinstance(envelope, dict):
                envelope["_context"] = context
        except Exception:
            logger.debug("Context injection skipped", exc_info=True)
        return envelope

    return wrapper


def _format_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """The entry as the agent should read it: no ids, no timestamps, no empties."""
    formatted: dict[str, Any] = {
        "source": entry.get("source", "python"),
        "input": entry.get("input", ""),
    }
    output = entry.get("output", "")
    if output:
        formatted["output"] = output
    result = entry.get("result")
    if result is not None:
        formatted["result"] = result
    if not entry.get("success", True):
        formatted["error"] = True
    return formatted
