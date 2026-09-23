"""Task interruption tool backed by itasca-mcp-bridge."""

from typing import Any

from fastmcp import FastMCP

from itasca_mcp.bridge import get_bridge_client
from itasca_mcp.bridge.context import with_context
from itasca_mcp.contracts import build_ok
from itasca_mcp.formatting import build_bridge_error, build_operation_error
from itasca_mcp.utils import TaskId


def register(mcp: FastMCP) -> None:
    """Register itasca_interrupt_task tool."""

    @mcp.tool()
    @with_context
    async def itasca_interrupt_task(task_id: TaskId) -> dict[str, Any]:
        """Request graceful interruption of a running Itasca task."""
        try:
            client = await get_bridge_client()
            response = await client.interrupt_task(task_id)
        except Exception as exc:
            return build_bridge_error(exc, task_id=task_id)

        status = response.get("status", "unknown")
        message = response.get("message", "")

        if status == "success":
            return build_ok(
                {
                    "task_id": task_id,
                    "interrupt_requested": True,
                    "message": message or "signal sent",
                    "next_action": f'call itasca_check_task_status(task_id="{task_id}")',
                }
            )

        return build_operation_error(
            status or "interrupt_failed",
            message or "Interrupt request failed",
            task_id=task_id,
            action="Check task status and bridge logs",
        )
