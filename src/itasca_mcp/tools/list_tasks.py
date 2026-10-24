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
        """List tasks tracked by the bridge, newest first.

        Read-only. Each entry carries task_id, status (pending / running /
        completed / failed / interrupted), description, entry_script,
        start_time, end_time and elapsed_time; total_count gives the size
        of the full history for paging via skip_newest + limit.

        Task history is persisted in the engine working directory and
        survives GUI restarts. Use this to recover a task_id from an
        earlier session, to see what is running or recently finished, or
        as a cheap bridge-connectivity check. For a task's output and
        result use itasca_check_task_status; to submit a script use
        itasca_execute_task.
        """
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

        normalized_tasks: list[dict[str, Any]] = []

        for task in tasks:
            normalized_task = {
                "task_id": task.get("task_id"),
                "status": task.get("status", "unknown"),
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
                "tasks": normalized_tasks,
            }
        )
