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

        The tool stays responsive while a task submitted via
        itasca_execute_task is cycling (calls interleave at cycle
        gaps), so use it as a live REPL — nothing has to be
        pre-scripted into the task up front. Typical uses:
        - Query model state and read Itasca command output:
          itasca.command('ball list') etc. — table dumps, list output,
          and command summaries are captured and interleaved with
          Python prints in execution order
        - Live inspection and tuning during a running task: check
          forces or contact statistics, modify parameters, swap
          callbacks, set sentinel variables the task reads each cycle
        - Create and export plots: itasca.command('plot ...')

        Environment: the engine's embedded Python interpreter
        (Itasca 9+ → Python 3.10, pre-9 → Python 3.6 or older; the
        product+version is encoded in sys.executable, e.g. PFC900).
        When unsure, check sys.version_info before relying on newer
        syntax.

        Code-writing rules (shared with itasca_execute_task):
        - Multi-line itasca.command(\"\"\"...\"\"\") batches are normalized
          to one engine call per command, keeping the bridge reachable
          mid-batch. Normalization recognizes itasca.command through
          its import name; call it through that name directly —
          rebinding via intermediate variables (`_it = itasca`)
          bypasses it and the output carries a bridge warning.
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

        Synchronous semantics: the request blocks until the code
        finishes or hits the timeout (default 10s, max 600s), and
        output is returned in full. The call is not tracked by
        itasca_list_tasks and cannot be interrupted mid-execution.
        For cancellable, pollable, or background work, submit via
        itasca_execute_task instead.
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
