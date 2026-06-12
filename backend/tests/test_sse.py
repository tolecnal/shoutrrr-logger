"""Tests for SSE subscriber queue bounding (slow-consumer protection)."""

import asyncio

from services.sse import _QUEUE_MAXSIZE, SSEService


def test_slow_consumer_queue_is_bounded_and_drops_oldest():
    service = SSEService()
    queue: asyncio.Queue = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    service.queues.add(queue)

    for i in range(_QUEUE_MAXSIZE + 50):
        service._on_notify(None, None, "shoutrrr_updates", f"ping-{i}")

    assert queue.qsize() == _QUEUE_MAXSIZE
    # The oldest 50 pings were dropped; the newest one survived.
    items = [queue.get_nowait() for _ in range(queue.qsize())]
    assert items[0] == "ping-50"
    assert items[-1] == f"ping-{_QUEUE_MAXSIZE + 49}"
