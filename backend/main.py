"""
Application entrypoint.

Startup order
─────────────
  1. Resolve config.
  2. Instantiate the SignalBus.
  3. Wire GNNAlphaEngine → bus.
  4. Wire PerformanceReporter → bus.
  5. Start WSBroadcastServer (subscribes to bus, opens port 8000).
  6. Register optional plugins.
  7. Start IngestionManager (blocks via asyncio.TaskGroup).
  8. Graceful shutdown on SIGINT / SIGTERM.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time

import structlog

from backend.core.bus import SignalBus
from backend.core.config import settings
from backend.core.types import ExchangeID, Signal, SignalTopic, Ticker
from backend.ingestion import IngestionManager
from backend.models import FeatureBuilder, LeadLagGNN
from backend.execution import ExecutionSimulator, PerformanceReport
from backend.plugins import PluginRegistry
from backend.server import WSBroadcastServer

# ── Logging ──────────────────────────────────────────────────────────────────

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        logging.getLevelName(settings.log_level)
    )
)
log = structlog.get_logger()


# ── GNN alpha engine ─────────────────────────────────────────────────────────

class GNNAlphaEngine:
    """
    Subscribes to ORDER_BOOK signals, builds the 7-dim feature matrix,
    runs a GATv2 forward pass, and publishes the scalar alpha on GNN_ALPHA.
    """

    def __init__(self, bus: SignalBus) -> None:
        self._bus      = bus
        self._features = FeatureBuilder(
            exchanges=list(ExchangeID),
            symbols=settings.ingestion.symbols,
        )
        self._model = LeadLagGNN(
            num_nodes=len(list(ExchangeID)),
            in_channels=7,
            hidden_channels=settings.model.hidden_channels,
            num_layers=settings.model.num_layers,
            dropout=settings.model.dropout,
        )

    def subscribe(self) -> None:
        self._bus.subscribe(SignalTopic.ORDER_BOOK, self._on_book,   "gnn-engine:book")
        self._bus.subscribe(SignalTopic.TICKER,     self._on_ticker, "gnn-engine:ticker")

    async def _on_ticker(self, signal: Signal) -> None:
        self._features.update_ticker(signal.payload)  # type: ignore[arg-type]

    async def _on_book(self, signal: Signal) -> None:
        import torch
        book = signal.payload
        self._features.update_book(book)              # type: ignore[arg-type]

        mat = self._features.build_feature_matrix(book.symbol)
        if mat is None:
            return

        x     = torch.from_numpy(mat)
        alpha = self._model.predict(x)

        self._bus.publish(Signal(
            topic=SignalTopic.GNN_ALPHA,
            payload={"symbol": book.symbol, "alpha": alpha, "exchange": str(book.exchange)},
            ts=time.time(),
        ))


# ── Performance reporter ──────────────────────────────────────────────────────

class PerformanceReporter:
    """
    Listens to GNN_ALPHA signals, runs each through the ExecutionSimulator,
    and broadcasts a fresh PerformanceReport on the EXECUTION topic every
    REPORT_INTERVAL_S seconds so the dashboard stays current.
    """

    REPORT_INTERVAL_S = 5.0

    def __init__(self, bus: SignalBus) -> None:
        self._bus            = bus
        self._sim            = ExecutionSimulator()
        self._last_report    = 0.0
        self._prev_alpha:    dict[str, float] = {}
        self._latest_prices: dict[str, float] = {}

    def subscribe(self) -> None:
        self._bus.subscribe(SignalTopic.GNN_ALPHA, self._on_alpha,  "perf-reporter")
        self._bus.subscribe(SignalTopic.TICKER,    self._on_ticker, "perf-reporter:ticker")

    async def _on_ticker(self, signal: Signal) -> None:
        ticker: Ticker = signal.payload
        self._latest_prices[ticker.symbol] = (ticker.bid + ticker.ask) / 2.0

    async def _on_alpha(self, signal: Signal) -> None:
        payload = signal.payload
        symbol  = payload.get("symbol", "BTC/USDT")
        alpha   = float(payload.get("alpha", 0.0))

        # Simulate a round-trip trade whenever we have a previous alpha to
        # pair with (entry at previous mid, exit at current mid).
        if symbol in self._prev_alpha:
            prev = self._prev_alpha[symbol]
            mid  = self._latest_prices.get(symbol, 0.0)
            if mid == 0.0:
                # No ticker received yet — store alpha and wait
                self._prev_alpha[symbol] = alpha
                return
            self._sim.simulate_signal(
                alpha=prev,
                entry_price=mid,
                exit_price=mid * (1 + alpha * 0.0001),
                entry_ts=signal.ts - 0.3,
                exit_ts=signal.ts,
            )

        self._prev_alpha[symbol] = alpha

        # Rate-limit the broadcast to avoid flooding the bus
        now = time.time()
        if now - self._last_report >= self.REPORT_INTERVAL_S:
            self._last_report = now
            report = self._sim.report()
            self._bus.publish(Signal(
                topic=SignalTopic.EXECUTION,
                payload=report,
                ts=now,
            ))


# ── Main ──────────────────────────────────────────────────────────────────────

async def _main() -> None:
    log.info("starting arbi-calculator", log_level=settings.log_level)

    bus       = SignalBus()
    ingestion = IngestionManager(bus)
    registry  = PluginRegistry(bus)

    # Core engine
    engine   = GNNAlphaEngine(bus)
    reporter = PerformanceReporter(bus)
    engine.subscribe()
    reporter.subscribe()

    # WebSocket broadcast server — must start before ingestion so the first
    # signals have a server ready to receive them
    ws_server = WSBroadcastServer(
        bus=bus,
        host="0.0.0.0",
        port=settings.ws_port,
    )
    await ws_server.start()

    # ── Register custom plugins here ──────────────────────────────────────
    # from backend.plugins.my_plugin import MyPlugin
    # registry.register(MyPlugin())
    # ──────────────────────────────────────────────────────────────────────

    await registry.startup_all()
    log.info("plugin registry ready", n_plugins=len(registry))

    # Shutdown coordination
    loop           = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def _handle_signal(*_) -> None:
        log.info("shutdown signal received")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    ingest_task = asyncio.create_task(ingestion.run(), name="ingestion")
    log.info("arbi-calculator: running — ws://localhost:%d/ws", settings.ws_port)

    await shutdown_event.wait()

    log.info("shutting down …")
    ingest_task.cancel()
    await asyncio.gather(ingest_task, return_exceptions=True)
    await ingestion.shutdown()
    await registry.shutdown_all()
    await ws_server.stop()
    await bus.shutdown()
    log.info("shutdown complete")


if __name__ == "__main__":
    asyncio.run(_main())
