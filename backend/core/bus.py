"""
Asynchronous Pub/Sub signal bus.

Design goals
────────────
• Zero-copy dispatch: subscribers receive the same Signal object (immutable
  payloads prevent aliasing bugs).
• Non-blocking publish: each subscriber's queue is bounded; if a slow consumer
  falls behind, the oldest item is dropped rather than blocking the producer.
• Isolated failure: an exception in one subscriber never affects others.
• Plugin-ready: any module can call `bus.subscribe(topic, callback)` without
  touching the core engine.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Awaitable, Callable

from .types import Signal, SignalTopic

log = logging.getLogger(__name__)

Subscriber: type = Callable[[Signal], Awaitable[None]]

_QUEUE_MAXSIZE = 512   # per-subscriber; tune based on processing latency budget


class SignalBus:
    """Central broker for typed async signals."""

    def __init__(self) -> None:
        # topic → list of (subscriber_id, asyncio.Queue)
        self._queues: dict[SignalTopic, list[tuple[str, asyncio.Queue[Signal]]]] = (
            defaultdict(list)
        )
        self._tasks:  list[asyncio.Task] = []

    # ── Registration ──────────────────────────────────────────────────────────

    def subscribe(
        self,
        topic: SignalTopic,
        callback: Subscriber,
        subscriber_id: str = "",
    ) -> None:
        """Register `callback` to receive every Signal published on `topic`."""
        sid   = subscriber_id or callback.__qualname__
        queue: asyncio.Queue[Signal] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._queues[topic].append((sid, queue))

        task = asyncio.create_task(
            self._dispatch_loop(sid, queue, callback),
            name=f"bus-{topic}-{sid}",
        )
        self._tasks.append(task)
        log.info("bus: %s subscribed to %s", sid, topic)

    # ── Publishing ────────────────────────────────────────────────────────────

    def publish(self, signal: Signal) -> None:
        """Non-blocking publish.  Called from hot ingest path — must not await."""
        for sid, queue in self._queues.get(signal.topic, []):
            try:
                queue.put_nowait(signal)
            except asyncio.QueueFull:
                # Drop oldest item to make room, preserving liveness.
                try:
                    queue.get_nowait()
                    queue.put_nowait(signal)
                except asyncio.QueueEmpty:
                    pass
                log.warning("bus: queue full for subscriber %s — oldest item dropped", sid)

    # ── Internal dispatch loop (one per subscriber) ───────────────────────────

    @staticmethod
    async def _dispatch_loop(
        sid: str,
        queue: asyncio.Queue[Signal],
        callback: Subscriber,
    ) -> None:
        while True:
            signal = await queue.get()
            try:
                await callback(signal)
            except Exception:
                log.exception("bus: unhandled error in subscriber %s", sid)
            finally:
                queue.task_done()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        log.info("bus: shutdown complete")
