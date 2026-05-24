"""
Kraken v2 WebSocket adapter (ticker + book).

Docs: https://docs.kraken.com/websockets-v2/
"""

from __future__ import annotations

import time

from backend.core.types import ExchangeID, OrderBook, PriceLevel, Ticker
from .base import BaseAdapter


class KrakenAdapter(BaseAdapter):

    WS_URL = "wss://ws.kraken.com/v2"

    def __init__(self, symbols: list[str], bus, book_depth: int = 10, **kwargs) -> None:
        super().__init__(ExchangeID.KRAKEN, symbols, bus, **kwargs)
        self._book_depth = book_depth

    @property
    def ws_url(self) -> str:
        return self.WS_URL

    def build_subscribe_message(self, symbols: list[str]) -> dict:
        # Kraken v2 uses a single subscribe frame per channel.
        # We send ticker first; book is sent as a second message after connect
        # (handled via a post-connect hook — see run() override below).
        return {
            "method": "subscribe",
            "params": {
                "channel": "ticker",
                "symbol": symbols,
            },
        }

    async def run(self) -> None:
        """Override to subscribe to both ticker and book channels on connect."""
        import orjson
        import websockets
        from websockets.exceptions import ConnectionClosed
        import asyncio
        import logging
        from .base import _SSL_CTX

        log = logging.getLogger(__name__)
        self._running = True
        delay = self._reconnect_base

        while self._running:
            try:
                async with websockets.connect(self.WS_URL, ssl=_SSL_CTX, ping_interval=20) as ws:
                    for channel in ("ticker", "book"):
                        msg = {
                            "method": "subscribe",
                            "params": {
                                "channel": channel,
                                "symbol": self.symbols,
                                **({"depth": self._book_depth} if channel == "book" else {}),
                            },
                        }
                        await ws.send(orjson.dumps(msg))

                    delay = self._reconnect_base
                    log.info("kraken: connected")

                    async for raw_bytes in ws:
                        if not self._running:
                            break
                        self._on_message(orjson.loads(raw_bytes))

            except ConnectionClosed as exc:
                log.warning("kraken: closed (%s), retry in %.1fs", exc, delay)
            except Exception:
                log.exception("kraken: error, retry in %.1fs", delay)

            if self._running:
                await asyncio.sleep(delay)
                delay = min(delay * 2, self._reconnect_max)

    # ── Parsers ───────────────────────────────────────────────────────────────

    def parse_ticker(self, raw: dict) -> Ticker | None:
        if raw.get("channel") != "ticker":
            return None
        try:
            data = raw["data"][0]
            return Ticker(
                exchange=ExchangeID.KRAKEN,
                symbol=data["symbol"],
                bid=float(data["bid"]),
                ask=float(data["ask"]),
                last=float(data["last"]),
                volume_24h=float(data.get("volume", 0.0)),
                ts=time.time(),
            )
        except (KeyError, IndexError, ValueError):
            return None

    def parse_order_book(self, raw: dict) -> OrderBook | None:
        if raw.get("channel") != "book":
            return None
        try:
            data = raw["data"][0]
            bids: tuple[PriceLevel, ...] = tuple(
                (float(lvl["price"]), float(lvl["qty"])) for lvl in data["bids"]
            )
            asks: tuple[PriceLevel, ...] = tuple(
                (float(lvl["price"]), float(lvl["qty"])) for lvl in data["asks"]
            )
            return OrderBook(
                exchange=ExchangeID.KRAKEN,
                symbol=data["symbol"],
                bids=bids,
                asks=asks,
                ts=time.time(),
            )
        except (KeyError, IndexError, ValueError):
            return None
