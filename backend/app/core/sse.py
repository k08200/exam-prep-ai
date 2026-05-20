import asyncio
import contextlib
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import settings


def sse_event(data: dict[str, Any]) -> str:
    """Format a dict as a Server-Sent Events data frame."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def iter_with_heartbeat(
    events: AsyncIterator[dict[str, Any]],
    *,
    heartbeat_seconds: float | None = None,
    event_timeout_seconds: float | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield upstream events, heartbeat frames while waiting, and one timeout error."""
    heartbeat = heartbeat_seconds or settings.AI_STREAM_HEARTBEAT_SECONDS
    timeout = event_timeout_seconds or settings.AI_STREAM_EVENT_TIMEOUT_SECONDS
    iterator = events.__aiter__()
    next_event = asyncio.create_task(iterator.__anext__())
    last_event_at = time.monotonic()

    try:
        while True:
            done, _ = await asyncio.wait({next_event}, timeout=min(heartbeat, timeout))

            if next_event in done:
                try:
                    event = next_event.result()
                except StopAsyncIteration:
                    return

                last_event_at = time.monotonic()
                yield event
                next_event = asyncio.create_task(iterator.__anext__())
                continue

            elapsed = time.monotonic() - last_event_at
            if elapsed >= timeout:
                next_event.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await next_event
                yield {
                    "type": "error",
                    "content": "AI stream timed out. Please try again.",
                    "retryable": True,
                }
                return

            yield {"type": "heartbeat"}
    finally:
        if not next_event.done():
            next_event.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await next_event
