"""Bridge context: what happened in the engine GUI between the agent's calls.

Two pieces live here:

* ``fetch_bridge_context`` pulls the runtime signals the bridge keeps for
  the client (what the person typed into the product's consoles, and which
  plots and data files they have open) and returns them as one dict.
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
    "Typed by the USER in the Itasca GUI since the last call: 'python' = IPython "
    "pane, 'command' = command prompt. 'queued' = not run yet (engine busy); its "
    "output follows as 'ran'."
)

GUI_DESCRIPTION = (
    "Plots and data files opened or switched to in the Itasca GUI since the last "
    "call, by the user or by your own code ('active' = the one in front), and plot "
    "items added, removed or changed. To see one, read the file or export the plot as an image."
)

# Console entries are what the person typed; GUI entries are what changed in
# the product's windows, whoever changed it.
_CONSOLE_SOURCES = ("python", "command")
_GUI_SOURCES = ("view", "plot_item")

# One console entry's output, at most. A table dump typed at the prompt would
# otherwise land in the agent's context whole; the head and the tail are kept.
MAX_CONSOLE_OUTPUT_CHARS = 2000


async def fetch_bridge_context() -> dict[str, Any] | None:
    """Fetch context from the bridge, or None when there is nothing to add."""
    context: dict[str, Any] = {}

    try:
        client = await get_bridge_client()
        response = await client.consume_console_history()
        data = response.get("data") or {}
        entries = data.get("entries") or []
        console = [_format_entry(e) for e in entries if e.get("source", "python") in _CONSOLE_SOURCES]
        gui = _coalesce_gui([_format_gui_entry(e) for e in entries if e.get("source") in _GUI_SOURCES])
        if console:
            context["user_console"] = {
                "description": USER_CONSOLE_DESCRIPTION,
                "entries": console,
            }
        if gui:
            context["gui"] = {
                "description": GUI_DESCRIPTION,
                "entries": gui,
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
        formatted["output"] = _clip(output)
    result = entry.get("result")
    if result is not None:
        formatted["result"] = _clip(result) if isinstance(result, str) else result
    if not entry.get("success", True):
        formatted["error"] = True
    status = entry.get("status")
    if status:
        formatted["status"] = status
    return formatted


def _format_gui_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """A view or plot-item entry as the agent should read it.

    The bridge puts the plot or file name in ``input`` and the structured
    fields in ``data``; the agent gets them flattened under a name that
    says which is which.
    """
    data = entry.get("data") or {}
    if entry.get("source") == "plot_item":
        formatted: dict[str, Any] = {"plot": entry.get("input", "")}
        for key in ("added", "removed", "changed", "items"):
            if data.get(key):
                formatted[key] = data[key]
        return formatted
    formatted = {
        "event": data.get("event", ""),
        "kind": data.get("kind", ""),
        "name": entry.get("input", ""),
    }
    for key in ("active", "previous", "items"):
        if data.get(key):
            formatted[key] = data[key]
    return formatted


def _clip(text: str, max_chars: int = MAX_CONSOLE_OUTPUT_CHARS) -> str:
    """``text`` cut to its head and tail when longer than ``max_chars``."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    omitted = len(text) - 2 * half
    return f"{text[:half]}\n... [{omitted} chars omitted] ...\n{text[-half:]}"


def _coalesce_gui(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The GUI entries reduced to where things ended up, not every click.

    The agent needs the view now in front and what each plot holds now. So
    only the last view brought to the front stays marked as such, and the
    item changes of one plot become a single entry carrying the net change,
    placed where the last of them was -- or nothing, when they cancel out.
    """
    last_active = max(
        (i for i, e in enumerate(entries) if e.get("event") == "active" or e.get("active")),
        default=-1,
    )
    item_changes: dict[str, list[int]] = {}
    for i, entry in enumerate(entries):
        if "plot" in entry:
            item_changes.setdefault(entry["plot"], []).append(i)

    merged: dict[int, dict[str, Any] | None] = {}
    for plot, indices in item_changes.items():
        if len(indices) < 2:
            continue
        for i in indices[:-1]:
            merged[i] = None
        merged[indices[-1]] = _net_item_change(plot, entries[indices[0]], entries[indices[-1]])

    result = []
    for i, entry in enumerate(entries):
        if i in merged:
            replacement = merged[i]
            if replacement is not None:
                result.append(replacement)
            continue
        if "event" in entry and i < last_active:
            if entry["event"] == "active":
                continue
            entry = {k: v for k, v in entry.items() if k != "active"}
        result.append(entry)
    return result


def _net_item_change(plot: str, first: dict[str, Any], last: dict[str, Any]) -> dict[str, Any] | None:
    """One entry for everything between ``first`` and ``last``, or None if nothing is left."""
    # The plot's items before the first change: that change, undone.
    before = list(first.get("items", []))
    for name in first.get("added", []):
        if name in before:
            before.remove(name)
    for old, new in first.get("changed", []):
        if new in before:
            before[before.index(new)] = old
    before.extend(first.get("removed", []))
    items = list(last.get("items", []))

    removed = list(before)
    added = []
    for name in items:
        if name in removed:
            removed.remove(name)
        else:
            added.append(name)
    changed = []
    if len(before) == len(items):
        for old, new in zip(before, items, strict=True):
            if old != new and old in removed and new in added:
                removed.remove(old)
                added.remove(new)
                changed.append([old, new])
    if not (added or removed or changed):
        return None

    net: dict[str, Any] = {"plot": plot}
    for key, value in (("added", added), ("removed", removed), ("changed", changed), ("items", items)):
        if value:
            net[key] = value
    return net
