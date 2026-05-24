"""
IngestionManager — owns the lifecycle of all exchange adapter tasks.

Responsibilities:
  • Start / stop all adapters concurrently via asyncio.TaskGroup.
  • Expose a `register_adapter` hook so future exchanges can be dropped in
    without touching the core engine (plugin pattern).
  • Propagate structured cancellation on shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from backend.core.bus import SignalBus
from backend.core.config import settings
from .adapters.base import BaseAdapter
from .adapters.binance import BinanceAdapter
from .adapters.kraken import KrakenAdapter

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class IngestionManager:

    def __init__(self, bus: SignalBus) -> None:
        self._bus      = bus
        self._adapters: list[BaseAdapter] = []

    # ── Plugin registration ───────────────────────────────────────────────────

    def register_adapter(self, adapter: BaseAdapter) -> None:
        """Add an adapter before calling `run()`.  Idiomatic extension point."""
        self._adapters.append(adapter)
        log.info("ingestion: registered adapter %s", adapter.exchange_id)

    # ── Default factory ───────────────────────────────────────────────────────

    def _register_defaults(self) -> None:
        cfg = settings.ingestion
        self.register_adapter(
            BinanceAdapter(
                symbols=cfg.symbols,
                bus=self._bus,
                reconnect_delay=cfg.reconnect_delay_s,
                reconnect_max=cfg.reconnect_max_s,
            )
        )
        self.register_adapter(
            KrakenAdapter(
                symbols=cfg.symbols,
                bus=self._bus,
                book_depth=cfg.book_depth,
                reconnect_delay=cfg.reconnect_delay_s,
                reconnect_max=cfg.reconnect_max_s,
            )
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Run all registered adapters concurrently.  Blocks until cancelled."""
        if not self._adapters:
            self._register_defaults()

        log.info("ingestion: starting %d adapters", len(self._adapters))

        # TaskGroup propagates the first exception and cancels siblings —
        # exactly the semantics we want: one crashed adapter tears down the
        # group so the supervisor (main.py) can restart the whole ingestion layer.
        async with asyncio.TaskGroup() as tg:
            for adapter in self._adapters:
                tg.create_task(adapter.run(), name=f"adapter-{adapter.exchange_id}")

    async def shutdown(self) -> None:
        for adapter in self._adapters:
            adapter.stop()
