"""execute_code tool — synchronous code execution in the Itasca engine process."""

from typing import Any

from fastmcp import FastMCP

from itasca_mcp.bridge import get_bridge_client
from itasca_mcp.contracts import build_ok
from itasca_mcp.formatting import build_bridge_error, build_operation_error, is_bridge_connectivity_error
from itasca_mcp.utils import ConsoleCode, ConsoleTimeoutSeconds


def register(mcp: FastMCP) -> None:
    """Register itasca_execute_code tool."""

    @mcp.tool()
    async def itasca_execute_code(
        code: ConsoleCode,
        timeout: ConsoleTimeoutSeconds = 10,
    ) -> dict[str, Any]:
        """Execute Python code synchronously in the running Itasca engine process.

        Returns stdout and an optional result variable immediately.
        Code runs in the engine's main thread, sharing the same __main__
        namespace as any running task — side effects persist and are
        immediately visible to the task on its next cycle.

        This tool remains responsive EVEN WHILE a simulation task is
        running (submitted via itasca_execute_task), as long as the task
        is actively cycling — execute_code interleaves at cycle gaps.
        Use it as a live REPL to inspect simulation state in real
        time — no need to pre-script print statements, and parameter
        sweeps or sentinel-based control don't have to be baked into
        the task script up front.

        Environment: the Itasca engine's embedded Python interpreter.
        The version is bundled with the engine (Itasca 6/7 → Python 3.6,
        Itasca 9 → 3.10); the product+version is encoded in sys.executable
        (e.g. PFC900, FLAC900). When unsure, write code compatible with
        Python 3.6+.

        Typical uses:
        - Query model state: ball/wall/contact counts, current cycle
        - Issue Itasca commands and read their console output:
          itasca.command('ball list'), itasca.command('model list
          information'). Table dumps, list output, and command
          summaries are captured and interleaved with Python prints
          in execution order — no need to re-implement queries via
          the SDK just to see what a command would print
        - Live inspection during a running task: check forces,
          energy, coordination number, contact statistics
        - Live tuning during a running task: modify parameters,
          swap callbacks, or set sentinel variables that the task
          reads each cycle (e.g. change a servo target, adjust
          damping, signal early termination)
        - Create and export plots: itasca.command('plot ...')
        - Development and REPL-style testing

        Multi-line itasca.command(\"\"\"...\"\"\") batches are normalized to
        one engine call per command, which keeps the bridge reachable
        while the batch runs — including after a `model new`/
        `model restore`, which reset the engine's cycle-callback
        registry mid-batch. The normalization applies when
        itasca.command is reached through its import name
        (`import itasca` / `import itasca as x` / `from itasca import
        command`); rebinding through intermediate variables
        (`_it = itasca`) bypasses it, and the output then carries a
        bridge warning.

        `program call '<file>.p3dat'` (or .p2dat / .dat) through this
        tool is engine-version-gated. On 6/7 the command-script
        interpreter blocks the bridge for the script's entire
        duration with no cycle-gap interleaving — any long
        `model cycle` inside the file leaves the bridge unreachable
        until the engine is stopped manually. Never emit it there, and
        treat unknown or unverified versions (including 9.0-9.6) the
        same way. On 9.7+ the bridge stays fully
        responsive during a `program call` (verified on 9.7: status
        polling, cycle-gap interleaving, and interrupt all work
        mid-call). Even where it is safe, prefer reading the file
        and translating its commands into a sequence of
        `itasca.command(...)` calls in Python — that keeps
        per-command output, error locality, and mid-script control
        that a single opaque `program call` cannot give.

        This is a synchronous tool: the request blocks until the code
        finishes or hits the timeout (default 10s, max 600s). Output
        is returned in full; the call is NOT tracked by itasca_list_tasks
        and cannot be interrupted mid-execution. For cancellable,
        pollable, or background work, submit it via itasca_execute_task
        instead — and you can still call itasca_execute_code against the
        task while it cycles.
        """
        try:
            client = await get_bridge_client()
            response = await client.execute_code(
                code=code,
                timeout_ms=timeout * 1000,
            )
        except Exception as exc:
            if is_bridge_connectivity_error(exc):
                return build_bridge_error(exc)
            return build_operation_error(
                "execute_code_failed",
                "Code execution failed",
                reason=str(exc),
            )

        status = response.get("status", "unknown")
        message = response.get("message", "")
        partial_output = ((response.get("data") or {}).get("output")) or None
        error_block = response.get("error") or {}
        error_details = error_block.get("details") or {}
        termination_method = error_details.get("method")

        if status == "terminated":
            # Bridge aborted the snippet at the timeout deadline and the
            # worker thread settled. Engine state may be partially modified.
            return build_operation_error(
                "terminated",
                "Execution aborted by bridge timeout",
                reason=message,
                action="Engine state may be partially modified; verify with itasca_execute_code before retrying",
                output=partial_output,
            )

        if status == "timeout":
            if termination_method == "stuck_in_c":
                action = (
                    "Bridge could not terminate the code (likely stuck "
                    "in a C extension). It may recover when the C call "
                    "returns; otherwise restart the Itasca bridge."
                )
            else:
                action = "Reduce code complexity or increase timeout"
            return build_operation_error(
                "timeout",
                "Execution timed out",
                reason=message,
                action=action,
                output=partial_output,
            )

        if status == "interrupted":
            return build_operation_error(
                "interrupted",
                "Execution interrupted",
                reason=message,
                output=partial_output,
            )

        if status == "error":
            return build_operation_error(
                error_block.get("code", "execute_code_error"),
                error_block.get("message", message),
                reason=message,
                output=partial_output,
            )

        data = response.get("data") or {}
        result_data: dict[str, Any] = {
            "output": data.get("output") or "(no output)",
        }
        if data.get("result") is not None:
            result_data["result"] = data["result"]

        return build_ok(result_data)
