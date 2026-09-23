"""Task status query tool backed by itasca-mcp-bridge."""

from typing import Any

from fastmcp import FastMCP

from itasca_mcp.bridge import get_bridge_client
from itasca_mcp.bridge.context import with_context
from itasca_mcp.contracts import build_ok
from itasca_mcp.formatting import (
    build_bridge_error,
    build_operation_error,
    format_elapsed_seconds,
    format_unix_timestamp,
    paginate_output,
)
from itasca_mcp.utils import FilterText, OutputLimit, SkipNewestLines, TaskId, WaitSeconds


def register(mcp: FastMCP) -> None:
    """Register itasca_check_task_status tool."""

    @mcp.tool()
    @with_context
    async def itasca_check_task_status(
        task_id: TaskId,
        skip_newest: SkipNewestLines = 0,
        limit: OutputLimit = 64,
        filter: FilterText = None,
        wait_seconds: WaitSeconds = 1,
    ) -> dict[str, Any]:
        """Check status and paginated output for a submitted Itasca task.

        Output combines Python prints and Itasca console output from
        itasca.command() calls (table dumps, list output, command
        summaries) interleaved in execution order. Use skip_newest /
        limit to paginate, or filter to keep only matching lines.
        """
        try:
            client = await get_bridge_client()
            terminal_states = {"completed", "failed", "interrupted", "not_found"}

            # Register listener BEFORE checking status to avoid missing
            # a push notification that arrives between check and wait.
            if wait_seconds > 0:
                client.listen_for_task(task_id)

            response = await client.check_task_status(
                task_id,
                skip_newest=skip_newest,
                limit=limit,
                filter_text=filter,
            )
            status = response.get("status", "unknown")

            if status not in terminal_states and wait_seconds > 0:
                await client.wait_for_task(task_id, timeout=wait_seconds)
                response = await client.check_task_status(
                    task_id,
                    skip_newest=skip_newest,
                    limit=limit,
                    filter_text=filter,
                )
            else:
                client.unlisten_task(task_id)
        except Exception as exc:
            return build_bridge_error(exc, task_id=task_id)

        status = response.get("status", "unknown")
        if status == "not_found":
            return build_operation_error(
                "not_found",
                "Task not found",
                task_id=task_id,
                action="Verify task_id or submit a new task",
            )

        data = response.get("data") or {}

        # Prefer bridge-side pagination when available: the bridge sees
        # the full log and reports accurate total_lines / line_range /
        # filter matches. Fall back to MCP-side paginate_output only for
        # legacy bridges that still send unpaginated output.
        bridge_output = data.get("output") or ""
        bridge_pagination = data.get("pagination")
        if isinstance(bridge_pagination, dict):
            output_text = bridge_output if bridge_output else "(no output)"
            # Normalize to the slim shape regardless of bridge version:
            # total_lines + line_range are self-describing, so the old
            # has_older / has_newer booleans (still emitted by pre-slim
            # bridges on PyPI) are dropped here for a consistent contract.
            pagination = {
                "total_lines": bridge_pagination.get("total_lines"),
                "line_range": bridge_pagination.get("line_range"),
            }
        else:
            output_text, pagination = paginate_output(
                output=bridge_output,
                skip_newest=skip_newest,
                limit=limit,
                filter_text=filter,
            )

        result: dict[str, Any] = {
            "task_id": task_id,
            "task_status": status,
            "start_time": format_unix_timestamp(data.get("start_time")),
            "end_time": format_unix_timestamp(data.get("end_time")),
            "elapsed_time": format_elapsed_seconds(data.get("elapsed_time")),
            "entry_script": data.get("entry_script") or data.get("script_path"),
            "description": data.get("description"),
            "output": output_text,
            "pagination": pagination,
        }

        if data.get("result") is not None:
            result["result"] = data["result"]
        if data.get("error"):
            result["error"] = data["error"]

        return build_ok(result)
