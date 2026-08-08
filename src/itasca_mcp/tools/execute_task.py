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
        Use the companion tools to manage the task lifecycle:
        - itasca_check_task_status: poll output, progress, and final status
        - itasca_interrupt_task: cancel a running task
        - itasca_list_tasks: browse task history

        While the task is cycling, you can call itasca_execute_code at any
        time to inspect or modify simulation state — including variables
        the task depends on. This is the standard way to probe progress,
        tune parameters mid-run, swap callbacks, or trigger early
        termination via a sentinel variable. Both tools share the same
        __main__ namespace in the engine's main thread.

        Console output from itasca.command() inside the script —
        table dumps, list output, command summaries — is captured
        and interleaved with Python prints in the task log, visible
        through itasca_check_task_status.

        Multi-line itasca.command(\"\"\"...\"\"\") batches are normalized to
        one engine call per command, which keeps the bridge reachable
        and the task interruptible while the batch runs — including
        after a `model new`/`model restore`, which reset the engine's
        cycle-callback registry mid-batch. The normalization applies
        when itasca.command is reached through its import name
        (`import itasca` / `import itasca as x` / `from itasca import
        command`); rebinding through intermediate variables
        (`_it = itasca`) bypasses it, and the task log then carries a
        bridge warning.

        FISH definition blocks (`fish define` / `fish operator` /
        legacy bare `define` ... `end`) must arrive at the engine
        whole: pass the complete block, header through its
        terminating standalone `end`, in ONE itasca.command() string —
        on its own or inside a multi-line batch (normalization keeps
        definition blocks intact as a single engine call). Never feed
        a definition line-by-line (e.g. looping with one
        itasca.command(line) per line): the `fish define` header alone
        drops the console into interactive FISH mode and that engine
        call blocks waiting for body input that can never arrive over
        the bridge, leaving the engine stuck until someone completes
        the definition manually in the GUI console. Per-line loops
        are fine for ordinary commands; only definition blocks must
        stay in one string.

        Having the script invoke `program call '<file>.p3dat'` (or
        .p2dat / .dat) is engine-version-gated. On 6/7 the
        command-script interpreter blocks the bridge for the
        script's entire duration with no cycle-gap interleaving,
        leaving the bridge unreachable until the engine is stopped
        manually. Never emit it there, and treat unknown or
        unverified versions (including 9.0-9.6) the same way.
        On 9.7+ the bridge stays fully responsive during a
        `program call` (verified on 9.7: status polling, cycle-gap
        interleaving, and interrupt all work mid-call). Even where
        it is safe, prefer reading the file and translating its
        commands into a sequence of `itasca.command(...)` calls in
        the Python script — that keeps per-command output, error
        locality, and mid-script control that a single opaque
        `program call` cannot give.

        This is the async / background execution path: pollable via
        itasca_check_task_status, cancellable via itasca_interrupt_task.
        Submission does not lock parameters — start with reasonable
        values and refine live via itasca_execute_code as the task
        cycles. For synchronous, inline execution, use
        itasca_execute_code directly.

        Submission uses the bridge's `execute_task` protocol message. If
        a submission times out, the connected bridge may predate it —
        confirm its version with itasca_execute_code (`import
        itasca_mcp_bridge; print(itasca_mcp_bridge.__version__)`). To
        upgrade, fetch and follow the bootstrap guide, then resubmit:
        https://raw.githubusercontent.com/yusong652/itasca-mcp/main/docs/agentic/itasca-mcp-bootstrap.md
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
