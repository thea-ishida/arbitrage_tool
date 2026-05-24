"""
Binance combined stream adapter (ticker + partial depth).

Docs: https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams
"""

from __future__ import annotations

from backend.core.types import ExchangeID, OrderBook, PriceLevel, Ticker
from .base import BaseAdapter


def _symbol_to_binance(symbol: str) -> str:
    """'BTC/USDT' → 'btcusdt'"""
    return symbol.replace("/", "").lower()


class BinanceAdapter(BaseAdapter):

    WS_BASE = "wss://stream.binance.com:9443/stream?streams="

    def __init__(self, symbols: list[str], bus, **kwargs) -> None:
        super().__init__(ExchangeID.BINANCE, symbols, bus, **kwargs)

    @property
    def ws_url(self) -> str:
        streams = "/".join(
            f"{_symbol_to_binance(s)}@bookTicker/{_symbol_to_binance(s)}@depth20@100ms"
            for s in self.symbols
        )
        return f"{self.WS_BASE}{streams}"

    def build_subscribe_message(self, symbols: list[str]) -> dict:
        # Combined streams use URL-based subscription; no JSON payload needed.
        return {}

    # ── Parsers ───────────────────────────────────────────────────────────────

    def parse_ticker(self, raw: dict) -> Ticker | None:
        data = raw.get("data", {})
        # bookTicker frame has keys: u, s, b, B, a, A
        if "b" not in data or "a" not in data or "depth" in raw.get("stream", ""):
            return None
        try:
            return Ticker(
                exchange=ExchangeID.BINANCE,
                symbol=self._normalise_symbol(data["s"]),
                bid=float(data["b"]),
                ask=float(data["a"]),
                last=float(data.get("c", data["b"])),  # 'c' absent in bookTicker
                volume_24h=float(data.get("v", 0.0)),
                ts=float(data.get("T", data.get("E", 0))) / 1000.0,
            )
        except (KeyError, ValueError):
            return None

    def parse_order_book(self, raw: dict) -> OrderBook | None:
        stream = raw.get("stream", "")
        if "depth" not in stream:
            return None
        data = raw.get("data", {})
        try:
            bids: tuple[PriceLevel, ...] = tuple(
                (float(p), float(q)) for p, q in data["bids"]
            )
            asks: tuple[PriceLevel, ...] = tuple(
                (float(p), float(q)) for p, q in data["asks"]
            )
            symbol = stream.split("@")[0].upper()
            return OrderBook(
                exchange=ExchangeID.BINANCE,
                symbol=self._normalise_symbol(symbol),
                bids=bids,
                asks=asks,
                ts=float(data.get("T", data.get("E", 0))) / 1000.0,
            )
        except (KeyError, ValueError, IndexError):
            return None

    @staticmethod
    def _normalise_symbol(raw: str) -> str:
        """'BTCUSDT' → 'BTC/USDT'  (handles the 4- or 3-char quote asset)."""
        for quote in ("USDT", "USDC", "BTC", "ETH", "BNB"):
            if raw.endswith(quote):
                base = raw[: -len(quote)]
                return f"{base}/{quote}"
        return raw
