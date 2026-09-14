import asyncio

from itasca_mcp.formatting import build_bridge_error
from itasca_mcp.server import mcp
from itasca_mcp.tools.task_formatting import paginate_output
from itasca_mcp.utils import validate_script_path


def test_phase2_tools_registered() -> None:
    tools = asyncio.run(mcp.list_tools())
    tool_names = {tool.name for tool in tools}
    expected = {
        "itasca_execute_task",
        "itasca_check_task_status",
        "itasca_list_tasks",
        "itasca_interrupt_task",
    }
    assert expected.issubset(tool_names)
    assert "itasca_execute_code" in tool_names


def test_pagination() -> None:
    text, page = paginate_output(
        output="a\nb\nc\nd",
        skip_newest=0,
        limit=2,
        filter_text=None,
    )

    assert text == "c\nd"
    assert page["line_range"] == "3-4"
    assert page["total_lines"] == 4


def test_validate_script_path_requires_absolute() -> None:
    assert validate_script_path("/tmp/run.py") == "/tmp/run.py"

    try:
        validate_script_path("relative/run.py")
    except ValueError as exc:
        assert "absolute path" in str(exc)
    else:
        raise AssertionError("relative path should raise ValueError")


def test_bridge_error_message_is_friendly() -> None:
    err = OSError("Multiple exceptions: [Errno 61] Connect call failed")
    envelope = build_bridge_error(err)

    assert envelope["ok"] is False
    error = envelope["error"]
    assert error["code"] == "bridge_unavailable"
    assert error["message"] == "Itasca bridge unavailable"
    assert error["details"]["reason"] == "cannot connect to bridge service"
    action = error["details"]["action"]
    assert action.startswith("start itasca-mcp-bridge in the Itasca engine GUI, then retry")
    # The GUI stays the recommended path; the console build is offered as a
    # fallback for when nobody is there to run it, not as the default.
    assert "console.exe can start it unattended" in action
