"""Contract tests for itasca-mcp tool response structures.

Verifies that each tool returns the expected field structure,
ensuring the API contract between itasca-mcp and its consumers is stable.
"""

import http.server
import json
import os
import socketserver
import threading
import time
from pathlib import Path

import pytest

from itasca_mcp.bridge.client import close_bridge_client
from itasca_mcp.server import mcp
from itasca_mcp.utils import HARNESS_TIMEOUT_FLOOR_S

# ── Mock Bridge ──────────────────────────────────────────


TASK_STORE = {}


def _build_response(msg_type, req):
    """Build the mock bridge response for a single request (transport-agnostic)."""
    req_id = req.get("request_id", "unknown")

    if msg_type == "execute_task":
        task_id = req.get("task_id", "000000")
        TASK_STORE[task_id] = {
            "status": "running",
            "start_time": time.time(),
            "script_path": req.get("script_path", ""),
            "description": req.get("description", ""),
        }
        return {
            "type": "result",
            "request_id": req_id,
            "status": "pending",
            "message": f"Script submitted: {Path(req.get('script_path', '')).name}",
        }

    if msg_type == "check_task_status":
        task_id = req.get("task_id", "")
        stored = TASK_STORE.get(task_id)
        if stored:
            return {
                "type": "result",
                "request_id": req_id,
                "status": stored["status"],
                "message": "ok",
                "data": {
                    "task_id": task_id,
                    "status": stored["status"],
                    "start_time": stored["start_time"],
                    "end_time": None,
                    "elapsed_time": "5.0s",
                    "script_path": stored["script_path"],
                    "description": stored["description"],
                    "output": "Cycle 100: unbalanced=1e-3\nCycle 200: unbalanced=5e-4\n",
                    "result": None,
                    "error": None,
                },
            }
        return {
            "type": "result",
            "request_id": req_id,
            "status": "not_found",
            "message": f"Task not found: {task_id}",
            "data": None,
        }

    if msg_type == "list_tasks":
        tasks = [
            {
                "task_id": tid,
                "status": t["status"],
                "elapsed_time": "5.0s",
                "entry_script": t["script_path"],
                "description": t["description"],
            }
            for tid, t in TASK_STORE.items()
        ]
        return {
            "type": "result",
            "request_id": req_id,
            "status": "success",
            "message": f"Found {len(tasks)} task(s)",
            "data": tasks,
            "pagination": {
                "total_count": len(tasks),
                "displayed_count": len(tasks),
                "offset": 0,
                "limit": 32,
                "has_more": False,
            },
        }

    if msg_type == "interrupt_task":
        return {
            "type": "result",
            "request_id": req_id,
            "status": "success",
            "message": f"Interrupt requested for task: {req.get('task_id')}",
            "data": {"task_id": req.get("task_id"), "interrupt_requested": True},
        }

    if msg_type == "execute_code":
        return {
            "type": "execute_code_result",
            "request_id": req_id,
            "status": "success",
            "message": "Code executed",
            "data": {
                "output": "42\n",
                "result": 42,
            },
        }

    return {
        "type": "result",
        "request_id": req_id,
        "status": "error",
        "message": f"unsupported: {msg_type}",
    }


class _MockBridgeHandler(http.server.BaseHTTPRequestHandler):
    """Mock itasca-mcp-bridge over HTTP + SSE, mirroring the real transport.

    ``POST /<command>`` dispatches to ``_build_response``; ``GET /events``
    serves a keepalive-only SSE stream (no doorbells needed: the contract
    tests re-poll status directly).
    """

    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.split("?", 1)[0] != "/events":
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while not self.server.stop_event.is_set():
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError, ValueError, OSError):
            pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        req = json.loads(raw.decode("utf-8")) if raw else {}
        command = self.path.split("?", 1)[0].strip("/")
        resp = _build_response(command, req)
        body = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


@pytest.fixture()
async def mock_bridge(tmp_path):
    """Start mock bridge and configure environment."""
    TASK_STORE.clear()

    server = _ThreadingHTTPServer(("127.0.0.1", 0), _MockBridgeHandler)
    server.stop_event = threading.Event()
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    prev = os.environ.get("ITASCA_MCP_BRIDGE_URL")
    os.environ["ITASCA_MCP_BRIDGE_URL"] = f"http://127.0.0.1:{port}"

    await close_bridge_client()

    yield tmp_path

    await close_bridge_client()
    if prev is None:
        os.environ.pop("ITASCA_MCP_BRIDGE_URL", None)
    else:
        os.environ["ITASCA_MCP_BRIDGE_URL"] = prev
    server.stop_event.set()
    server.shutdown()
    server.server_close()


# ── itasca_execute_task ─────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_task_success_fields(mock_bridge, tmp_path):
    script = tmp_path / "run.py"
    script.write_text("print('hello')")

    result = await mcp.call_tool(
        "itasca_execute_task",
        {"entry_script": str(script), "description": "test task"},
    )

    data = result.content[0].text if hasattr(result.content[0], "text") else json.loads(result.content[0].text)
    # For fastmcp, the tool returns a dict which gets serialized
    # Just verify the raw result has the right structure
    assert result is not None
    assert len(result.content) > 0

    # Parse the structured content
    text = result.content[0].text
    parsed = json.loads(text) if text.startswith("{") else None

    if parsed:
        assert parsed["ok"] is True
        data = parsed["data"]
        assert "task_id" in data
        assert len(data["task_id"]) == 6
        assert "entry_script" in data
        assert "description" in data
        assert "message" in data


# ── itasca_check_task_status ────────────────────────────────


@pytest.mark.asyncio
async def test_check_task_status_running_fields(mock_bridge, tmp_path):
    # First submit a task so we have something to check
    script = tmp_path / "sim.py"
    script.write_text("print('running')")

    exec_result = await mcp.call_tool(
        "itasca_execute_task",
        {"entry_script": str(script), "description": "simulation"},
    )
    exec_text = exec_result.content[0].text
    exec_data = json.loads(exec_text) if exec_text.startswith("{") else {}
    task_id = exec_data.get("data", {}).get("task_id", list(TASK_STORE.keys())[0])

    result = await mcp.call_tool(
        "itasca_check_task_status",
        {"task_id": task_id, "wait_seconds": 1},
    )

    text = result.content[0].text
    parsed = json.loads(text) if text.startswith("{") else None

    if parsed:
        assert parsed["ok"] is True
        data = parsed["data"]
        assert data["task_status"] in ("pending", "running", "completed", "failed", "interrupted")
        assert data["task_id"] == task_id
        assert "output" in data
        # Pagination
        assert "pagination" in data
        pag = data["pagination"]
        assert "total_lines" in pag
        assert "line_range" in pag


@pytest.mark.asyncio
async def test_check_task_status_passes_through_bridge_pagination(mock_bridge, tmp_path, monkeypatch):
    """When bridge returns data.pagination, tool should use it directly
    (not re-paginate the output string locally)."""
    from itasca_mcp.bridge import get_bridge_client

    client = await get_bridge_client()

    async def fake_check(task_id, skip_newest=0, limit=64, filter_text=None):
        return {
            "type": "result",
            "status": "completed",  # terminal → skips wait_for_task
            "message": "ok",
            "data": {
                "task_id": task_id,
                "status": "completed",
                "start_time": time.time(),
                "end_time": time.time(),
                "elapsed_time": "1.0s",
                "script_path": "/tmp/fake.py",
                "description": "fake",
                "output": "paginated-window-line",
                "pagination": {
                    "total_lines": 12345,
                    "line_range": "12281-12345",
                    "has_older": True,
                    "has_newer": False,
                },
            },
        }

    monkeypatch.setattr(client, "check_task_status", fake_check)

    result = await mcp.call_tool(
        "itasca_check_task_status",
        {"task_id": "abc123", "wait_seconds": 1},
    )
    parsed = json.loads(result.content[0].text)
    assert parsed["ok"] is True
    data = parsed["data"]
    # Bridge pagination values are used (total_lines + line_range)
    assert data["pagination"]["total_lines"] == 12345
    assert data["pagination"]["line_range"] == "12281-12345"
    # Output should come from bridge verbatim (not re-split/joined)
    assert data["output"] == "paginated-window-line"


@pytest.mark.asyncio
async def test_check_task_status_not_found(mock_bridge):
    result = await mcp.call_tool(
        "itasca_check_task_status",
        {"task_id": "nonexistent", "wait_seconds": 1},
    )

    text = result.content[0].text
    parsed = json.loads(text) if text.startswith("{") else None

    if parsed:
        assert parsed["ok"] is False
        assert parsed["error"]["code"] == "not_found"


# ── itasca_list_tasks ───────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tasks_with_tasks(mock_bridge, tmp_path):
    # Submit a task first
    script = tmp_path / "job.py"
    script.write_text("print('done')")
    await mcp.call_tool(
        "itasca_execute_task",
        {"entry_script": str(script), "description": "list test"},
    )

    result = await mcp.call_tool("itasca_list_tasks", {})

    text = result.content[0].text
    parsed = json.loads(text) if text.startswith("{") else None

    if parsed:
        assert parsed["ok"] is True
        data = parsed["data"]
        assert isinstance(data["total_count"], int)
        assert data["total_count"] >= 1
        assert isinstance(data["tasks"], list)
        assert len(data["tasks"]) >= 1
        # Task fields
        task = data["tasks"][0]
        assert "task_id" in task
        assert "status" in task
        assert "entry_script" in task
        assert "start_time" in task
        assert "end_time" in task


# ── itasca_execute_code ──────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_code_success_fields(mock_bridge):
    result = await mcp.call_tool(
        "itasca_execute_code",
        {"code": "print(42)"},
    )

    text = result.content[0].text
    parsed = json.loads(text) if text.startswith("{") else None

    if parsed:
        assert parsed["ok"] is True
        data = parsed["data"]
        assert "output" in data
        assert "result" in data
        assert data["result"] == 42


# ── itasca_list_tasks (continued) ──────────────────────────


@pytest.mark.asyncio
async def test_list_tasks_empty(mock_bridge):
    # No tasks submitted — TASK_STORE is cleared by fixture
    result = await mcp.call_tool("itasca_list_tasks", {})

    text = result.content[0].text
    parsed = json.loads(text) if text.startswith("{") else None

    if parsed:
        assert parsed["ok"] is True
        data = parsed["data"]
        assert data["total_count"] == 0
        assert data["tasks"] == []


# ── Advertised parameter bounds ──────────────────────────


@pytest.mark.asyncio
async def test_wait_seconds_capped_below_harness_timeout():
    """wait_seconds stays under the shortest MCP client timeout (OpenCode 30 s)."""
    tool = await mcp.get_tool("itasca_check_task_status")
    wait = tool.parameters["properties"]["wait_seconds"]
    assert wait["maximum"] == HARNESS_TIMEOUT_FLOOR_S
    assert wait["maximum"] < 30


@pytest.mark.asyncio
async def test_execute_code_timeout_capped_below_harness_timeout():
    """execute_code timeout stays under the shortest MCP client timeout (OpenCode 30 s)."""
    tool = await mcp.get_tool("itasca_execute_code")
    timeout = tool.parameters["properties"]["timeout"]
    assert timeout["maximum"] == HARNESS_TIMEOUT_FLOOR_S
    assert timeout["maximum"] < 30
