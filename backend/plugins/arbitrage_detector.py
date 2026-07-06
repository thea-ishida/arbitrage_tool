"""
Cross-exchange arbitrage opportunity detector.

Tracks the best bid/ask per symbol across all exchanges currently sending
ticker data and flags a "crossed" market whenever the best bid on one
exchange exceeds the best ask on another — i.e. you could buy on the ask
exchange and immediately sell on the bid exchange for a positive spread.

Detection is edge-triggered: a symbol only counts as a *new* opportunity
when it transitions from non-crossed to crossed, so a spread that persists
across many ticks isn't double-counted once per tick.

Reports two figures per event, since "opportunity" is ambiguous without them:
  spread_bps      — raw (sell_bid - buy_ask) / buy_ask, before costs.
  net_spread_bps  — spread_bps minus round-trip taker fees + slippage
                     (from ExecutionConfig), i.e. what's left to actually
                     capture after crossing both books.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field

import structlog

from backend.core.config import settings
from backend.core.types import ExchangeID, Signal, SignalTopic, Ticker
from .base import BasePlugin

log = structlog.get_logger()


@dataclass
class _SymbolState:
    quotes:  dict[ExchangeID, Ticker] = field(default_factory=dict)
    crossed: bool = False


@dataclass(frozen=True, slots=True)
class ArbEvent:
    symbol:         str
    buy_exchange:   ExchangeID
    sell_exchange:  ExchangeID
    buy_price:      float
    sell_price:     float
    spread_bps:     float
    net_spread_bps: float
    latency_ms:     float   # tick receipt (Signal.ts) -> opportunity flagged
    ts:             float


class ArbitrageDetectorPlugin(BasePlugin):
    """Detects cross-exchange price discrepancies from live ticker data."""

    def __init__(self) -> None:
        self._state:  dict[str, _SymbolState] = {}
        self._events: list[ArbEvent] = []

        cfg = settings.execution
        # Round-trip cost: taker fee to buy + taker fee to sell + slippage on both legs.
        self._cost_bps = (cfg.taker_fee * 2 * 10_000) + (cfg.slippage_bps * 2)

    @property
    def name(self) -> str:
        return "arbitrage-detector"

    @property
    def subscribed_topics(self) -> list[SignalTopic]:
        return [SignalTopic.TICKER]

    @property
    def events(self) -> list[ArbEvent]:
        return self._events

    async def on_signal(self, signal: Signal) -> None:
        ticker: Ticker = signal.payload
        state = self._state.setdefault(ticker.symbol, _SymbolState())
        state.quotes[ticker.exchange] = ticker

        if len(state.quotes) < 2:
            return

        best_ask_ex = min(state.quotes, key=lambda ex: state.quotes[ex].ask)
        best_bid_ex = max(state.quotes, key=lambda ex: state.quotes[ex].bid)

        if best_ask_ex == best_bid_ex:
            state.crossed = False
            return

        best_ask = state.quotes[best_ask_ex].ask
        best_bid = state.quotes[best_bid_ex].bid
        spread_bps = (best_bid - best_ask) / best_ask * 10_000

        is_crossed = spread_bps > 0.0
        if is_crossed and not state.crossed:
            flag_ts    = time.time()
            latency_ms = (flag_ts - signal.ts) * 1000.0
            event = ArbEvent(
                symbol=ticker.symbol,
                buy_exchange=best_ask_ex,
                sell_exchange=best_bid_ex,
                buy_price=best_ask,
                sell_price=best_bid,
                spread_bps=spread_bps,
                net_spread_bps=spread_bps - self._cost_bps,
                latency_ms=latency_ms,
                ts=flag_ts,
            )
            self._events.append(event)
            log.info(
                "arb-detector: opportunity flagged",
                symbol=event.symbol,
                buy=str(event.buy_exchange), sell=str(event.sell_exchange),
                buy_price=event.buy_price, sell_price=event.sell_price,
                spread_bps=round(event.spread_bps, 3),
                net_spread_bps=round(event.net_spread_bps, 3),
                latency_ms=round(event.latency_ms, 3),
            )

        state.crossed = is_crossed

    async def shutdown(self) -> None:
        if not self._events:
            log.info("arb-detector: shutdown — zero opportunities detected this run")
            return

        latencies       = [e.latency_ms for e in self._events]
        net_spreads     = [e.net_spread_bps for e in self._events]
        gross_spreads   = [e.spread_bps for e in self._events]
        profitable      = [e for e in self._events if e.net_spread_bps > 0]

        log.info(
            "arb-detector: run summary",
            n_opportunities=len(self._events),
            n_profitable_after_cost=len(profitable),
            cost_bps_assumed=round(self._cost_bps, 3),
            avg_gross_spread_bps=round(statistics.mean(gross_spreads), 3),
            avg_net_spread_bps=round(statistics.mean(net_spreads), 3),
            avg_latency_ms=round(statistics.mean(latencies), 3),
            p95_latency_ms=round(
                statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies), 3
            ),
            max_latency_ms=round(max(latencies), 3),
        )
