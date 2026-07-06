"""
Historical data capture — persists every TICKER / ORDER_BOOK signal to
date-partitioned Parquet files under `backend/data/captures/`, so a replay
harness can later feed the same signals back through the bus for backtesting.

Layout
──────
  backend/data/captures/<UTC date>/ticker.parquet
  backend/data/captures/<UTC date>/order_book.parquet

Order-book levels are stored as orjson-encoded strings (list of [price, qty]
pairs) rather than nested Arrow types — keeps the schema simple and portable,
and round-trips exactly through `orjson.loads` on replay. Top-of-book price
is duplicated into flat columns for fast filtering without decoding JSON.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

import orjson
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from backend.core.types import OrderBook, Signal, SignalTopic, Ticker
from .base import BasePlugin

log = structlog.get_logger()

_TICKER_SCHEMA = pa.schema([
    ("ts",         pa.float64()),   # Signal.ts — local receipt time of the raw WS frame
    ("exchange",   pa.string()),
    ("symbol",     pa.string()),
    ("bid",        pa.float64()),
    ("ask",        pa.float64()),
    ("last",       pa.float64()),
    ("volume_24h", pa.float64()),
])

_ORDER_BOOK_SCHEMA = pa.schema([
    ("ts",       pa.float64()),
    ("exchange", pa.string()),
    ("symbol",   pa.string()),
    ("best_bid", pa.float64()),
    ("best_ask", pa.float64()),
    ("bids",     pa.string()),   # orjson-encoded [[price, qty], ...], sorted desc
    ("asks",     pa.string()),   # orjson-encoded [[price, qty], ...], sorted asc
])


class CapturePlugin(BasePlugin):
    """Streams raw market data to disk for later backtest replay."""

    FLUSH_INTERVAL_S = 15.0

    def __init__(self, output_dir: str = "backend/data/captures") -> None:
        self._root = Path(output_dir)
        self._buffers: dict[SignalTopic, list[dict]] = {
            SignalTopic.TICKER:     [],
            SignalTopic.ORDER_BOOK: [],
        }
        self._writers: dict[SignalTopic, pq.ParquetWriter] = {}
        self._rows_written: dict[SignalTopic, int] = {
            SignalTopic.TICKER: 0, SignalTopic.ORDER_BOOK: 0,
        }
        self._current_date: str | None = None
        self._task: asyncio.Task | None = None

    @property
    def name(self) -> str:
        return "capture"

    @property
    def subscribed_topics(self) -> list[SignalTopic]:
        return [SignalTopic.TICKER, SignalTopic.ORDER_BOOK]

    # ── Ingest ────────────────────────────────────────────────────────────────

    async def on_signal(self, signal: Signal) -> None:
        if signal.topic == SignalTopic.TICKER:
            t: Ticker = signal.payload
            self._buffers[SignalTopic.TICKER].append({
                "ts":         signal.ts,
                "exchange":   str(t.exchange),
                "symbol":     t.symbol,
                "bid":        t.bid,
                "ask":        t.ask,
                "last":       t.last,
                "volume_24h": t.volume_24h,
            })
        elif signal.topic == SignalTopic.ORDER_BOOK:
            ob: OrderBook = signal.payload
            self._buffers[SignalTopic.ORDER_BOOK].append({
                "ts":       signal.ts,
                "exchange": str(ob.exchange),
                "symbol":   ob.symbol,
                "best_bid": ob.bids[0][0] if ob.bids else None,
                "best_ask": ob.asks[0][0] if ob.asks else None,
                "bids":     orjson.dumps(ob.bids).decode(),
                "asks":     orjson.dumps(ob.asks).decode(),
            })

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def startup(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self._task = asyncio.create_task(self._flush_loop(), name="capture-flush-loop")

    async def shutdown(self) -> None:
        if self._task:
            self._task.cancel()
        self._flush()
        for writer in self._writers.values():
            writer.close()
        log.info("capture: shutdown", rows_written=dict(self._rows_written))

    # ── Flush / rotation ──────────────────────────────────────────────────────

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(self.FLUSH_INTERVAL_S)
            self._flush()

    def _flush(self) -> None:
        today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        if today != self._current_date:
            self._rotate(today)

        for topic, schema in (
            (SignalTopic.TICKER, _TICKER_SCHEMA),
            (SignalTopic.ORDER_BOOK, _ORDER_BOOK_SCHEMA),
        ):
            rows = self._buffers[topic]
            if not rows:
                continue
            table = pa.Table.from_pylist(rows, schema=schema)
            self._writers[topic].write_table(table)
            self._rows_written[topic] += len(rows)
            rows.clear()

    def _rotate(self, date_str: str) -> None:
        """Close the current day's writers (if any) and open fresh ones."""
        for writer in self._writers.values():
            writer.close()
        self._writers.clear()

        day_dir = self._root / date_str
        day_dir.mkdir(parents=True, exist_ok=True)
        self._writers[SignalTopic.TICKER]     = pq.ParquetWriter(day_dir / "ticker.parquet", _TICKER_SCHEMA)
        self._writers[SignalTopic.ORDER_BOOK] = pq.ParquetWriter(day_dir / "order_book.parquet", _ORDER_BOOK_SCHEMA)
        self._current_date = date_str
        log.info("capture: rotated to new date partition", date=date_str, path=str(day_dir))
