"""
Abstract base for all exchange WebSocket adapters.

Each adapter owns exactly one concern: maintaining a live WS connection and
translating raw exchange messages into canonical Ticker / OrderBook objects.
It delegates publishing to the SignalBus — it does NOT process or store data.

Adding a new exchange = subclassing BaseAdapter and implementing four methods.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import time
from abc import ABC, abstractmethod

import certifi
import websockets
from websockets.exceptions import ConnectionClosed

# certifi bundle required on macOS Python 3.14+ where the system cert.pem is absent
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

from backend.core.bus import SignalBus
from backend.core.types import ExchangeID, OrderBook, Signal, SignalTopic, Ticker

log = logging.getLogger(__name__)


class BaseAdapter(ABC):
    """WebSocket adapter with exponential-backoff reconnection."""

    def __init__(
        self,
        exchange_id: ExchangeID,
        symbols: list[str],
        bus: SignalBus,
        reconnect_delay: float = 1.0,
        reconnect_max:   float = 60.0,
    ) -> None:
        self.exchange_id     = exchange_id
        self.symbols         = symbols
        self.bus             = bus
        self._reconnect_base = reconnect_delay
        self._reconnect_max  = reconnect_max
        self._running        = False

    # ── Interface ─────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def ws_url(self) -> str:
        """WebSocket endpoint URL."""

    @abstractmethod
    def build_subscribe_message(self, symbols: list[str]) -> dict:
        """JSON-serialisable subscription payload."""

    @abstractmethod
    def parse_ticker(self, raw: dict) -> Ticker | None:
        """Return a canonical Ticker or None if the message is not a ticker update."""

    @abstractmethod
    def parse_order_book(self, raw: dict) -> OrderBook | None:
        """Return a canonical OrderBook or None if not an order book update."""

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Connect, subscribe, and relay messages.  Reconnects on any failure."""
        self._running = True
        delay         = self._reconnect_base

        while self._running:
            try:
                async with websockets.connect(
                    self.ws_url,
                    ssl=_SSL_CTX,
                    ping_interval=20,
                    ping_timeout=10,
                    max_size=2**23,  # 8 MiB; L2 books can be large
                ) as ws:
                    # Some exchanges (e.g. Binance combined streams) subscribe via URL
                    # only; sending {} or other junk triggers a 1008 policy violation.
                    if subscribe := self.build_subscribe_message(self.symbols):
                        await ws.send(__import__("orjson").dumps(subscribe))
                    delay = self._reconnect_base  # reset on successful connect
                    log.info("%s: connected to %s", self.exchange_id, self.ws_url)

                    async for raw_bytes in ws:
                        if not self._running:
                            break
                        self._on_message(
                            __import__("orjson").loads(raw_bytes)
                        )

            except ConnectionClosed as exc:
                log.warning("%s: connection closed (%s), reconnecting in %.1fs", self.exchange_id, exc, delay)
            except Exception:
                log.exception("%s: unexpected error, reconnecting in %.1fs", self.exchange_id, delay)

            if self._running:
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._reconnect_max)

    def stop(self) -> None:
        self._running = False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_message(self, raw: dict) -> None:
        """Route parsed objects onto the bus.  Called synchronously on ingest task."""
        receipt_ts = time.time()

        if (ticker := self.parse_ticker(raw)) is not None:
            self.bus.publish(Signal(topic=SignalTopic.TICKER, payload=ticker, ts=receipt_ts))
            return

        if (book := self.parse_order_book(raw)) is not None:
            self.bus.publish(Signal(topic=SignalTopic.ORDER_BOOK, payload=book, ts=receipt_ts))
