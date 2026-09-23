"""Task listing tool backed by itasca-mcp-bridge."""

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
)
from itasca_mcp.utils import SkipNewestTasks, TaskListLimit


def register(mcp: FastMCP) -> None:
    """Register itasca_list_tasks tool."""

    @mcp.tool()
    @with_context
    async def itasca_list_tasks(
        skip_newest: SkipNewestTasks = 0,
        limit: TaskListLimit = 32,
    ) -> dict[str, Any]:
        """List tracked Itasca tasks with pagination."""
        try:
            client = await get_bridge_client()
            response = await client.list_tasks(
                offset=skip_newest,
                limit=limit,
            )
        except Exception as exc:
            return build_bridge_error(exc)

        status = response.get("status", "unknown")
        if status != "success":
            return build_operation_error(
                status or "list_failed",
                response.get("message", "Failed to list tasks"),
                action="Check bridge state and retry",
            )

        tasks = response.get("data") or []
        pagination = response.get("pagination") or {}
        total_count = pagination.get("total_count", len(tasks))
        displayed_count = pagination.get("displayed_count", len(tasks))
        has_more = pagination.get("has_more", False)

        normalized_tasks: list[dict[str, Any]] = []

        for task in tasks:
            normalized_task = {
                "task_id": task.get("task_id"),
                "status": task.get("status", "unknown"),
                "source": task.get("source", "agent"),
                "start_time": format_unix_timestamp(task.get("start_time")),
                "end_time": format_unix_timestamp(task.get("end_time")),
                "elapsed_time": format_elapsed_seconds(task.get("elapsed_time")),
                "entry_script": task.get("entry_script") or task.get("name"),
                "description": task.get("description"),
            }
            normalized_tasks.append(normalized_task)

        return build_ok(
            {
                "total_count": total_count,
                "displayed_count": displayed_count,
                "has_more": has_more,
                "tasks": normalized_tasks,
            }
        )
