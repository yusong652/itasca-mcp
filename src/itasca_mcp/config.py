"""Runtime configuration for Itasca MCP server."""

import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class BridgeConfig:
    url: str
    reconnect_interval_s: float
    request_timeout_s: float


def get_bridge_config() -> BridgeConfig:
    """Load bridge config from environment variables."""
    return BridgeConfig(
        url=os.getenv("ITASCA_MCP_BRIDGE_URL", "http://localhost:9001"),
        reconnect_interval_s=_env_float("ITASCA_MCP_RECONNECT_INTERVAL_S", 0.5),
        request_timeout_s=max(1.0, _env_float("ITASCA_MCP_REQUEST_TIMEOUT_S", 10.0)),
    )
