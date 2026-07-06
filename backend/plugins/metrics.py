"""
Throughput instrumentation — logs messages/sec across all ingest topics
every REPORT_INTERVAL_S seconds, and a run-total summary on shutdown.
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter

import structlog

from backend.core.types import Signal, SignalTopic
from .base import BasePlugin

log = structlog.get_logger()


class ThroughputMetricsPlugin(BasePlugin):

    REPORT_INTERVAL_S = 10.0

    def __init__(self) -> None:
        self._interval_counts: Counter[SignalTopic] = Counter()
        self._total_counts:    Counter[SignalTopic] = Counter()
        self._start_ts = time.time()
        self._task: asyncio.Task | None = None

    @property
    def name(self) -> str:
        return "throughput-metrics"

    @property
    def subscribed_topics(self) -> list[SignalTopic]:
        return [SignalTopic.TICKER, SignalTopic.ORDER_BOOK]

    async def on_signal(self, signal: Signal) -> None:
        self._interval_counts[signal.topic] += 1
        self._total_counts[signal.topic] += 1

    async def startup(self) -> None:
        self._task = asyncio.create_task(self._report_loop(), name="throughput-metrics-loop")

    async def shutdown(self) -> None:
        if self._task:
            self._task.cancel()

        elapsed = time.time() - self._start_ts
        total   = sum(self._total_counts.values())
        log.info(
            "metrics: run summary",
            elapsed_s=round(elapsed, 1),
            total_messages=total,
            avg_msgs_per_sec=round(total / elapsed, 2) if elapsed > 0 else 0.0,
            ticker_total=self._total_counts[SignalTopic.TICKER],
            order_book_total=self._total_counts[SignalTopic.ORDER_BOOK],
        )

    async def _report_loop(self) -> None:
        while True:
            await asyncio.sleep(self.REPORT_INTERVAL_S)
            total = sum(self._interval_counts.values())
            rate  = total / self.REPORT_INTERVAL_S
            log.info(
                "metrics: throughput",
                interval_s=self.REPORT_INTERVAL_S,
                msgs=total,
                msgs_per_sec=round(rate, 2),
                ticker=self._interval_counts[SignalTopic.TICKER],
                order_book=self._interval_counts[SignalTopic.ORDER_BOOK],
            )
            self._interval_counts.clear()
