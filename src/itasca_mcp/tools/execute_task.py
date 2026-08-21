"""Itasca task execution tool backed by itasca-mcp-bridge."""

import uuid
from typing import Any

from fastmcp import FastMCP

from itasca_mcp.bridge import get_bridge_client
from itasca_mcp.contracts import build_ok
from itasca_mcp.formatting import build_bridge_error, build_operation_error
from itasca_mcp.utils import ScriptPath, TaskDescription


def register(mcp: FastMCP) -> None:
    """Register itasca_execute_task tool."""

    @mcp.tool()
    async def itasca_execute_task(
        entry_script: ScriptPath,
        description: TaskDescription,
    ) -> dict[str, Any]:
        """Submit a Python script file for asynchronous execution in the Itasca engine.

        Returns a task_id immediately; the script runs in the background.
        Companion tools manage the lifecycle:
        - itasca_check_task_status: poll output, progress, and final status
        - itasca_interrupt_task: cancel a running task
        - itasca_list_tasks: browse task history
        For synchronous, inline execution, use itasca_execute_code instead.

        While the task is cycling, itasca_execute_code shares the same
        __main__ namespace in the engine's main thread, so you can
        inspect or modify simulation state live — probe progress, tune
        parameters mid-run, swap callbacks, or trigger early termination
        via a sentinel variable. Submit with reasonable starting values
        and refine as the task runs.

        Console output from itasca.command() inside the script (table
        dumps, list output, command summaries) is captured into the task
        log alongside Python prints, visible through
        itasca_check_task_status.

        Script-writing rules:
        - Multi-line itasca.command(\"\"\"...\"\"\") batches are normalized
          to one engine call per command, keeping the task interruptible
          mid-batch. Normalization recognizes itasca.command through its
          import name; call it through that name directly — rebinding
          via intermediate variables (`_it = itasca`) bypasses it and
          logs a bridge warning.
        - Pass each FISH definition block (`fish define` /
          `fish operator` / legacy bare `define`, through its
          terminating standalone `end`) whole, in ONE itasca.command()
          string; feeding one line-by-line leaves the engine blocked in
          interactive FISH mode until completed manually in the GUI
          console. Per-line loops are fine for ordinary commands.
        - `program call '<file>.p3dat'` (or .p2dat / .dat) keeps the
          bridge responsive only on engine 9.7+; on 6/7 and unverified
          versions (including 9.0-9.6) it blocks the bridge for the
          script's entire duration, so never emit it there. Even on
          9.7+, prefer translating the file's commands into
          itasca.command(...) calls — that keeps per-command output,
          error locality, and mid-script control.
        """
        try:
            client = await get_bridge_client()
        except Exception as exc:
            # Connection failed — no task_id generated, nothing to track
            return build_bridge_error(exc)

        task_id = uuid.uuid4().hex[:6]

        try:
            response = await client.execute_task(
                script_path=entry_script,
                description=description,
                task_id=task_id,
            )
        except Exception as exc:
            # Connected but request failed — task may or may not exist on bridge
            return build_bridge_error(exc, task_id=task_id)

        status = response.get("status", "unknown")
        message = response.get("message", "")

        if status != "pending":
            return build_operation_error(
                status or "submission_failed",
                message or "Task submission rejected by bridge",
                task_id=task_id,
                action="Check script path and bridge logs, then retry",
            )

        return build_ok(
            {
                "task_id": task_id,
                "entry_script": entry_script,
                "description": description,
                "task_status": "pending",
                "message": message or "submitted",
            }
        )
