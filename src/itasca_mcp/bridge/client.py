"""HTTP + SSE client for communicating with the itasca-mcp-bridge.

Commands are plain ``POST /<command>`` request/response. The one
server->client doorbell (``task_status_changed``) arrives on a single
long-lived ``GET /events`` Server-Sent Events stream consumed in the
background. The bridge speaks stdlib HTTP, so there is no third-party
dependency on the engine side.
"""

import asyncio
import json
import logging
from typing import Any
from uuid import uuid4

import httpx

from itasca_mcp.config import get_bridge_config

logger = logging.getLogger("itasca-mcp.bridge")


class ItascaBridgeClient:
    """Async request/response client for the itasca-mcp-bridge HTTP + SSE protocol."""

    def __init__(
        self,
        url: str,
        reconnect_interval_s: float,
        request_timeout_s: float,
    ) -> None:
        self.url = url
        self.reconnect_interval_s = reconnect_interval_s
        self.request_timeout_s = request_timeout_s

        self._client: httpx.AsyncClient | None = None
        self._sse_task: asyncio.Task[Any] | None = None
        self._task_events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._client is not None

    async def connect(self) -> None:
        async with self._lock:
            if self._client is not None:
                return
            # Per-request timeouts are set on each POST; the SSE stream uses an
            # unbounded read timeout because it stays open between doorbells.
            # trust_env=False: the bridge is reached directly (localhost by
            # default). With proxy env vars set (HTTP_PROXY etc., common with
            # Clash-style setups), httpx would otherwise route even localhost
            # requests through the proxy, surfacing as bridge_unavailable.
            self._client = httpx.AsyncClient(base_url=self.url, trust_env=False)
            self._sse_task = asyncio.create_task(self._sse_loop())
            logger.info("Connected to itasca-mcp-bridge at %s", self.url)

    async def disconnect(self) -> None:
        async with self._lock:
            sse_task = self._sse_task
            client = self._client
            self._sse_task = None
            self._client = None

        if sse_task is not None:
            sse_task.cancel()
            try:
                await sse_task
            except asyncio.CancelledError:
                pass

        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass

    async def _ensure_connected(self) -> None:
        if self.connected:
            return
        await self.connect()

    async def _sse_loop(self) -> None:
        """Consume the server's SSE doorbell stream.

        The only load-bearing event is ``task_status_changed`` -> wake any
        waiter registered via ``listen_for_task``. SSE is best-effort: a missed
        doorbell is covered by the caller's mandatory status re-poll, so the
        stream simply reconnects on drop.
        """
        sse_timeout = httpx.Timeout(self.request_timeout_s, read=None)
        while True:
            client = self._client
            if client is None:
                return
            try:
                async with client.stream("GET", "/events", timeout=sse_timeout) as response:
                    async for line in response.aiter_lines():
                        # SSE frames: "data: {json}" lines; ":" comment lines
                        # are keepalives; blank lines separate events.
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if not raw:
                            continue
                        try:
                            payload = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if payload.get("type") == "task_status_changed":
                            event = self._task_events.get(payload.get("task_id", ""))
                            if event is not None:
                                event.set()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Bridge SSE stream dropped: %s", exc)

            if self._client is None:
                return
            await asyncio.sleep(self.reconnect_interval_s)

    async def _send_request(self, message: dict[str, Any], timeout_s: float) -> dict[str, Any]:
        await self._ensure_connected()
        assert self._client is not None

        request_id = message.get("request_id") or str(uuid4())
        message["request_id"] = request_id
        command = message["type"]

        try:
            response = await self._client.post(f"/{command}", json=message, timeout=timeout_s)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Bridge request timed out after {timeout_s:.1f}s") from exc

        # The bridge returns 200 for every envelope, including ok:false
        # application errors. A non-2xx is a transport/protocol fault
        # (malformed request, unknown command, internal crash).
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        return payload

    async def _request(
        self,
        message: dict[str, Any],
        operation_name: str,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        # Single attempt, no transport-level retry: execute requests are not
        # idempotent (the bridge does not dedupe request_id), and the agent
        # driving this client can see the error and decide for itself.
        timeout = timeout_s if timeout_s is not None else self.request_timeout_s
        try:
            return await self._send_request(message, timeout)
        except Exception as exc:
            raise ConnectionError(f"{operation_name} failed: {exc}") from exc

    def listen_for_task(self, task_id: str) -> None:
        """Pre-register an event listener for task completion.

        Must be called BEFORE querying task status to avoid missing
        a push notification that arrives between the query and wait.
        """
        if task_id not in self._task_events:
            self._task_events[task_id] = asyncio.Event()

    def unlisten_task(self, task_id: str) -> None:
        """Remove a previously registered task listener."""
        self._task_events.pop(task_id, None)

    async def wait_for_task(self, task_id: str, timeout: float) -> bool:
        """Wait for a task to reach terminal state via push notification.

        Requires listen_for_task() to have been called first.
        Returns True if notified, False on timeout.
        """
        event = self._task_events.get(task_id)
        if event is None:
            return False
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            self._task_events.pop(task_id, None)

    async def execute_task(
        self,
        script_path: str,
        description: str,
        task_id: str,
        source: str = "agent",
    ) -> dict[str, Any]:
        return await self._request(
            {
                "type": "execute_task",
                "task_id": task_id,
                "script_path": script_path,
                "description": description,
                "source": source,
            },
            operation_name="execute_task",
            timeout_s=10.0,
        )

    async def check_task_status(
        self,
        task_id: str,
        skip_newest: int = 0,
        limit: int = 64,
        filter_text: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "check_task_status",
            "task_id": task_id,
            "skip_newest": skip_newest,
            "limit": limit,
        }
        if filter_text is not None:
            payload["filter_text"] = filter_text
        return await self._request(
            payload,
            operation_name="check_task_status",
        )

    async def list_tasks(self, offset: int, limit: int | None) -> dict[str, Any]:
        return await self._request(
            {
                "type": "list_tasks",
                "offset": offset,
                "limit": limit,
            },
            operation_name="list_tasks",
        )

    async def interrupt_task(self, task_id: str) -> dict[str, Any]:
        return await self._request(
            {"type": "interrupt_task", "task_id": task_id},
            operation_name="interrupt_task",
            timeout_s=5.0,
        )

    async def execute_code(self, code: str, timeout_ms: int = 10000) -> dict[str, Any]:
        timeout_s = max(self.request_timeout_s, timeout_ms / 1000.0 + 5.0)
        return await self._request(
            {
                "type": "execute_code",
                "code": code,
                "timeout_ms": timeout_ms,
            },
            operation_name="execute_code",
            timeout_s=timeout_s,
        )


_client: ItascaBridgeClient | None = None
_client_lock = asyncio.Lock()


async def get_bridge_client() -> ItascaBridgeClient:
    """Return the global bridge client instance with lazy initialization."""
    global _client
    async with _client_lock:
        if _client is None:
            config = get_bridge_config()
            _client = ItascaBridgeClient(
                url=config.url,
                reconnect_interval_s=config.reconnect_interval_s,
                request_timeout_s=config.request_timeout_s,
            )
        await _client.connect()
        return _client


async def close_bridge_client() -> None:
    """Close global bridge client connection."""
    global _client
    async with _client_lock:
        if _client is None:
            return
        client = _client
        _client = None
    await client.disconnect()
