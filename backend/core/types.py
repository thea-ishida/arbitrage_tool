"""
Shared domain types.  All timestamps are Unix epoch seconds (float) so we
avoid datetime allocation overhead on the hot ingest path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

# ── Exchange identity ──────────────────────────────────────────────────────────

class ExchangeID(StrEnum):
    BINANCE  = "binance"
    KRAKEN   = "kraken"
    COINBASE = "coinbase"
    OKX      = "okx"


# ── Market data primitives ─────────────────────────────────────────────────────

PriceLevel: TypeAlias = tuple[float, float]   # (price, quantity)


@dataclass(slots=True, frozen=True)
class Ticker:
    exchange:   ExchangeID
    symbol:     str          # e.g. "BTC/USDT"
    bid:        float
    ask:        float
    last:       float
    volume_24h: float
    ts:         float        # exchange-reported epoch seconds


@dataclass(slots=True, frozen=True)
class OrderBook:
    """Snapshot or incremental update of the top-N order book levels."""
    exchange: ExchangeID
    symbol:   str
    bids:     tuple[PriceLevel, ...]  # sorted descending by price
    asks:     tuple[PriceLevel, ...]  # sorted ascending  by price
    ts:       float

    @property
    def mid_price(self) -> float:
        return (self.bids[0][0] + self.asks[0][0]) / 2.0

    @property
    def spread(self) -> float:
        return self.asks[0][0] - self.bids[0][0]

    def order_book_imbalance(self, depth: int = 5) -> float:
        """OBI ∈ (-1, 1).  Positive → buy pressure; negative → sell pressure."""
        bid_vol = sum(qty for _, qty in self.bids[:depth])
        ask_vol = sum(qty for _, qty in self.asks[:depth])
        denom   = bid_vol + ask_vol
        return (bid_vol - ask_vol) / denom if denom else 0.0


# ── Signal types emitted on the bus ───────────────────────────────────────────

class SignalTopic(StrEnum):
    TICKER     = "ticker"
    ORDER_BOOK = "order_book"
    GNN_ALPHA  = "gnn_alpha"     # model output: predicted lead-lag signal
    EXECUTION  = "execution"     # fill / order event


@dataclass(slots=True)
class Signal:
    topic:   SignalTopic
    payload: Ticker | OrderBook | dict  # extend union as new payload types arrive
    ts:      float                      # local receipt epoch seconds
