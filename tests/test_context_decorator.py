"""The with_context decorator and the shape of the context it attaches.

The decorator is the one place context injection happens, so success
envelopes and error envelopes must both come out with ``_context`` when
the bridge has fresh entries, and neither may be disturbed when it has
none or cannot be reached.
"""

from unittest.mock import AsyncMock, patch

from itasca_mcp.bridge import context as ctx_module
from itasca_mcp.bridge.context import fetch_bridge_context, with_context
from itasca_mcp.contracts import build_error, build_ok

FAKE_CONTEXT = {
    "user_console": {
        "description": "test",
        "entries": [{"source": "command", "input": "fish list"}],
    }
}


async def test_injects_on_success():
    @with_context
    async def tool():
        return build_ok({"msg": "hi"})

    with patch.object(ctx_module, "fetch_bridge_context", return_value=FAKE_CONTEXT):
        result = await tool()

    assert result["ok"] is True
    assert result["_context"] == FAKE_CONTEXT


async def test_injects_on_error():
    @with_context
    async def tool():
        return build_error("boom", "failed")

    with patch.object(ctx_module, "fetch_bridge_context", return_value=FAKE_CONTEXT):
        result = await tool()

    assert result["ok"] is False
    assert result["_context"] == FAKE_CONTEXT


async def test_omits_context_when_nothing_new():
    @with_context
    async def tool():
        return build_ok({"msg": "hi"})

    with patch.object(ctx_module, "fetch_bridge_context", return_value=None):
        result = await tool()

    assert "_context" not in result


async def test_fetch_failure_never_shadows_the_result():
    @with_context
    async def tool():
        return build_ok({"msg": "hi"})

    with patch.object(ctx_module, "fetch_bridge_context", side_effect=RuntimeError("bridge down")):
        result = await tool()

    assert result == build_ok({"msg": "hi"})


async def test_passes_arguments_through():
    @with_context
    async def tool(a, *, b):
        return build_ok({"sum": a + b})

    with patch.object(ctx_module, "fetch_bridge_context", return_value=None):
        result = await tool(1, b=2)

    assert result["data"]["sum"] == 3
    assert tool.__name__ == "tool"


def _client_returning(entries):
    client = AsyncMock()
    client.consume_console_history.return_value = {
        "status": "success",
        "data": {"entries": entries, "cursor": len(entries), "has_more": False},
    }
    return client


async def test_fetch_formats_entries_for_the_agent():
    entries = [
        {
            "id": 1,
            "source": "python",
            "input": "x = 6 * 7\nx",
            "output": "",
            "result": 42,
            "success": True,
            "timestamp": 1.0,
        },
        {
            "id": 2,
            "source": "command",
            "input": "foo bar",
            "output": "*** Bad conversion of parameter number 1 (foo).",
            "result": None,
            "success": False,
            "timestamp": 2.0,
        },
        {
            "id": 3,
            "source": "command",
            "input": "ball list",
            "output": "",
            "result": None,
            "success": True,
            "timestamp": 3.0,
            "status": "queued",
        },
    ]
    with patch.object(ctx_module, "get_bridge_client", return_value=_client_returning(entries)):
        context = await fetch_bridge_context()

    assert context is not None
    console = context["user_console"]
    assert "USER" in console["description"]
    assert console["entries"] == [
        {"source": "python", "input": "x = 6 * 7\nx", "result": 42},
        {
            "source": "command",
            "input": "foo bar",
            "output": "*** Bad conversion of parameter number 1 (foo).",
            "error": True,
        },
        {"source": "command", "input": "ball list", "status": "queued"},
    ]


async def test_fetch_returns_none_when_empty_or_unreachable():
    with patch.object(ctx_module, "get_bridge_client", return_value=_client_returning([])):
        assert await fetch_bridge_context() is None

    with patch.object(ctx_module, "get_bridge_client", side_effect=ConnectionError("no bridge")):
        assert await fetch_bridge_context() is None


async def test_fetch_tolerates_an_old_bridge_without_the_command():
    """A bridge that predates console_history answers 404; that is not an error for the tool."""
    client = AsyncMock()
    client.consume_console_history.side_effect = ConnectionError("console_history failed: 404")
    with patch.object(ctx_module, "get_bridge_client", return_value=client):
        assert await fetch_bridge_context() is None


async def test_fetch_splits_gui_entries_into_gui():
    entries = [
        {
            "id": 1,
            "source": "view",
            "input": "Plot01",
            "output": "",
            "result": None,
            "success": True,
            "timestamp": 1.0,
            "data": {"kind": "plot", "event": "open", "active": True, "items": ["Ball", "Legend"]},
        },
        {
            "id": 2,
            "source": "command",
            "input": "ball list",
            "output": "",
            "result": None,
            "success": True,
            "timestamp": 2.0,
        },
        {
            "id": 3,
            "source": "plot_item",
            "input": "Plot01",
            "output": "",
            "result": None,
            "success": True,
            "timestamp": 3.0,
            "data": {"items": ["Ball", "Wall", "Legend"], "added": ["Wall"]},
        },
        {
            "id": 4,
            "source": "view",
            "input": "consolidate.dat",
            "output": "",
            "result": None,
            "success": True,
            "timestamp": 4.0,
            "data": {"kind": "data_file", "event": "renamed", "previous": "script"},
        },
    ]
    with patch.object(ctx_module, "get_bridge_client", return_value=_client_returning(entries)):
        context = await fetch_bridge_context()

    assert context is not None
    assert context["user_console"]["entries"] == [{"source": "command", "input": "ball list"}]
    gui = context["gui"]
    assert "plot" in gui["description"] and "export" in gui["description"]
    assert gui["entries"] == [
        {"event": "open", "kind": "plot", "name": "Plot01", "active": True, "items": ["Ball", "Legend"]},
        {"plot": "Plot01", "added": ["Wall"], "items": ["Ball", "Wall", "Legend"]},
        {"event": "renamed", "kind": "data_file", "name": "consolidate.dat", "previous": "script"},
    ]


async def test_fetch_with_only_gui_entries_has_no_user_console():
    entries = [
        {
            "id": 1,
            "source": "view",
            "input": "script",
            "output": "",
            "result": None,
            "success": True,
            "timestamp": 1.0,
            "data": {"kind": "data_file", "event": "active"},
        },
    ]
    with patch.object(ctx_module, "get_bridge_client", return_value=_client_returning(entries)):
        context = await fetch_bridge_context()

    assert context == {
        "gui": {
            "description": ctx_module.GUI_DESCRIPTION,
            "entries": [{"event": "active", "kind": "data_file", "name": "script"}],
        }
    }


async def test_fetch_passes_changed_plot_items_through():
    entries = [
        {
            "id": 1,
            "source": "plot_item",
            "input": "Plot02",
            "output": "",
            "result": None,
            "success": True,
            "timestamp": 1.0,
            "data": {"items": ["Ball density", "Legend"], "changed": [["Ball", "Ball density"]]},
        },
    ]
    with patch.object(ctx_module, "get_bridge_client", return_value=_client_returning(entries)):
        context = await fetch_bridge_context()

    assert context is not None
    assert context["gui"]["entries"] == [
        {"plot": "Plot02", "changed": [["Ball", "Ball density"]], "items": ["Ball density", "Legend"]},
    ]
