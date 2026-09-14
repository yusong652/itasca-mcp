"""Itasca MCP Server - ITASCA simulation tools exposed over MCP."""

import argparse
import asyncio
import logging
import os
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from fastmcp import FastMCP

from itasca_mcp import __version__
from itasca_mcp.bridge import close_bridge_client
from itasca_mcp.tools import (
    browse_commands,
    browse_python_api,
    browse_reference,
    check_task_status,
    execute_code,
    execute_task,
    interrupt_task,
    list_tasks,
    query_command,
    query_python_api,
)

mcp = FastMCP(
    "Itasca MCP Server",
    instructions=(
        "ITASCA MCP server for PFC, FLAC, 3DEC, MPoint, and MassFlow. "
        "Provides tools for browsing/searching engine documentation (select the "
        "engine via the required 'software' parameter) and for executing simulation "
        "tasks and managing runs through an itasca-mcp-bridge service running inside "
        "the Itasca engine GUI, or in a console build started unattended."
    ),
)

logger = logging.getLogger("itasca-mcp.server")

# Register documentation tools
browse_commands.register(mcp)
browse_python_api.register(mcp)
browse_reference.register(mcp)
query_command.register(mcp)
query_python_api.register(mcp)

# Register execution tools
execute_task.register(mcp)
check_task_status.register(mcp)
list_tasks.register(mcp)
interrupt_task.register(mcp)
execute_code.register(mcp)


DEFAULT_BRIDGE_URL = "http://localhost:9001"


def _override_bridge_port(url: str, port: int) -> str:
    """Return ``url`` with its port replaced, preserving scheme/host/path."""
    parts = urlsplit(url)
    host = parts.hostname or "localhost"
    return urlunsplit((parts.scheme or "http", f"{host}:{port}", parts.path, parts.query, parts.fragment))


def main() -> None:
    """Entry point for the Itasca MCP server."""
    parser = argparse.ArgumentParser(
        prog="itasca-mcp",
        description="Itasca MCP Server - ITASCA simulation tools exposed over MCP",
    )
    parser.add_argument("--version", "-v", action="version", version=f"itasca-mcp {__version__}")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind when using http/sse transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind when using http/sse transport (default: 8000)",
    )
    parser.add_argument(
        "--bridge-url",
        default=None,
        help="Bridge HTTP URL (default: http://localhost:9001, or ITASCA_MCP_BRIDGE_URL env)",
    )
    parser.add_argument(
        "--bridge-port",
        type=int,
        default=None,
        help=(
            "Bridge HTTP port; shorthand for --bridge-url http://localhost:PORT. "
            "Overrides only the port of --bridge-url / ITASCA_MCP_BRIDGE_URL when both "
            "are given (default: 9001)"
        ),
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="warning",
        help="Log level for itasca-mcp (default: warning)",
    )
    args = parser.parse_args()

    # Resolve the bridge URL from (in order of precedence) --bridge-url,
    # the ITASCA_MCP_BRIDGE_URL env, then the default. --bridge-port then
    # overrides just the port, so users can point at a non-default bridge
    # port without spelling out the whole http:// URL.
    bridge_url = args.bridge_url or os.environ.get("ITASCA_MCP_BRIDGE_URL")
    if args.bridge_port is not None:
        if not 1 <= args.bridge_port <= 65535:
            parser.error("--bridge-port must be between 1 and 65535")
        bridge_url = _override_bridge_port(bridge_url or DEFAULT_BRIDGE_URL, args.bridge_port)
    if bridge_url:
        os.environ["ITASCA_MCP_BRIDGE_URL"] = bridge_url

    # Configure logging
    level = getattr(logging, args.log_level.upper())
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("itasca-mcp").setLevel(level)
    # Keep uvicorn quiet unless user asks for debug/info
    uvicorn_level = level if level <= logging.INFO else logging.CRITICAL
    logging.getLogger("uvicorn").setLevel(uvicorn_level)
    logging.getLogger("uvicorn.error").setLevel(uvicorn_level)

    run_kwargs: dict[str, Any] = {"transport": args.transport, "show_banner": False}
    if args.transport in ("http", "sse"):
        run_kwargs["host"] = args.host
        run_kwargs["port"] = args.port

    try:
        mcp.run(**run_kwargs)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            asyncio.run(close_bridge_client())
        except Exception as exc:
            logger.debug("Bridge client cleanup skipped: %s", exc)


if __name__ == "__main__":
    main()
