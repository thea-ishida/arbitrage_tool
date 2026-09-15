"""
Rule-based cross-exchange arbitrage backtest.

What this does
──────────────
Runs the real ingestion layer (BinanceAdapter + KrakenAdapter) against live
markets for a fixed window, feeds every crossed-book event detected by
`ArbitrageDetectorPlugin` into `ExecutionSimulator` as a completed round-trip
trade, and prints Sharpe ratio / max drawdown / win rate / profit factor
computed from those real fills.

This is NOT a backtest against months of historical data — no tick-level
historical order-book data source is wired into this project yet (see
README "Known Limitations"). It is a genuine backtest in the sense that
every trade comes from real, live bid/ask quotes rather than synthetic
prices; the sample window is just short. `CapturePlugin` persists the raw
ticks to backend/data/captures/ so this window can be replayed later
without hitting the exchanges again.

Usage:
    python -m backend.scripts.run_backtest --duration-s 300
"""

from __future__ import annotations

import argparse
import asyncio
import time

import structlog

from backend.core.bus import SignalBus
from backend.core.config import settings
from backend.core.types import Signal, SignalTopic
from backend.execution import ExecutionSimulator, Trade
from backend.ingestion import IngestionManager
from backend.plugins import PluginRegistry
from backend.plugins.arbitrage_detector import ArbitrageDetectorPlugin
from backend.plugins.capture import CapturePlugin

log = structlog.get_logger()

SECONDS_PER_YEAR = 365 * 24 * 3600
CAPITAL_FRACTION_PER_TRADE = 0.10  # matches ExecutionSimulator.simulate_signal default


async def _run(duration_s: float) -> None:
    bus = SignalBus()
    ingestion = IngestionManager(bus)
    registry = PluginRegistry(bus)

    detector = ArbitrageDetectorPlugin()
    registry.register(detector)
    registry.register(CapturePlugin())

    tick_counts: dict[str, int] = {}

    async def _count_tick(signal: Signal) -> None:
        exch = str(signal.payload.exchange)
        tick_counts[exch] = tick_counts.get(exch, 0) + 1

    bus.subscribe(SignalTopic.TICKER, _count_tick, "backtest:tick-counter")

    await registry.startup_all()

    print(f"Capturing live ticks for {duration_s:.0f}s "
          f"(symbols={settings.ingestion.symbols}) ...")
    start = time.time()
    ingest_task = asyncio.create_task(ingestion.run(), name="ingestion")
    try:
        await asyncio.sleep(duration_s)
    finally:
        ingest_task.cancel()
        await asyncio.gather(ingest_task, return_exceptions=True)
        await ingestion.shutdown()
        await registry.shutdown_all()
        await bus.shutdown()
    elapsed = time.time() - start

    events = detector.events
    print(f"\nCapture window complete: {elapsed:.1f}s elapsed, "
          f"ticks received: {tick_counts or 'none'}")
    print(f"Crossed-book opportunities detected: {len(events)}")

    if not events:
        print("\nNo crossed-book opportunities occurred during this window — "
              "cross-exchange spot arbitrage on liquid pairs is rare and "
              "usually closes in milliseconds. Re-run with a longer "
              "--duration-s, or point the replay harness at a captured "
              "window from backend/data/captures/ once you have more data.")
        return

    # Per-trade (unannualised) Sharpe is the honest primary figure with a
    # handful of trades: periods_per_year=1 means _sharpe() reduces to
    # mean(net pnl) / std(net pnl) over the realised trade series, with no
    # extrapolation baked in.
    sim = ExecutionSimulator(periods_per_year=1)
    notional = settings.execution.capital_usdt * CAPITAL_FRACTION_PER_TRADE
    for event in events:
        sim.record_trade(Trade(
            entry_price=event.buy_price,
            exit_price=event.sell_price,
            notional=notional,
            direction=1,
            entry_ts=event.ts,
            exit_ts=event.ts,
        ))

    report = sim.report()

    print("\n=== Backtest report (real live fills, rule-based detector) ===")
    print(f"Capital (USDT):        {settings.execution.capital_usdt:,.2f}")
    print(f"Fees (maker/taker):    {settings.execution.maker_fee:.3%} / {settings.execution.taker_fee:.3%}")
    print(f"Slippage assumption:   {settings.execution.slippage_bps:.1f} bps")
    print(f"Trades:                {report.n_trades}")
    print(f"Win rate:              {report.win_rate:.1%}")
    print(f"Profit factor:         {report.profit_factor:.3f}")
    print(f"Gross P&L (USDT):      {report.gross_pnl:.4f}")
    print(f"Net P&L (USDT):        {report.net_pnl:.4f}")
    print(f"Total fees (USDT):     {report.total_fees:.4f}")
    print(f"Total slippage (USDT): {report.total_slippage:.4f}")
    print(f"Max drawdown:          {report.max_drawdown:.4%}")
    print(f"Sharpe (per-trade, unannualised): {report.sharpe_ratio:.3f}  "
          f"(mean/std of net P&L across the {report.n_trades} realised trades — "
          f"not scaled to a yearly figure)")

    trades_per_second = len(events) / elapsed if elapsed > 0 else 0.0
    if len(events) >= 5:
        periods_per_year = max(1, round(trades_per_second * SECONDS_PER_YEAR))
        # Recompute with a fresh simulator using the observed-rate periods_per_year
        # so the annualisation is explicit and separate from the per-trade figure.
        ann_sim = ExecutionSimulator(periods_per_year=periods_per_year)
        for event in events:
            ann_sim.record_trade(Trade(
                entry_price=event.buy_price, exit_price=event.sell_price,
                notional=notional, direction=1, entry_ts=event.ts, exit_ts=event.ts,
            ))
        ann_report = ann_sim.report()
        print(f"Sharpe (annualised, extrapolated): {ann_report.sharpe_ratio:.3f}  "
              f"(scaled from an observed rate of {trades_per_second * 3600:.2f} "
              f"opportunities/hr over this {elapsed:.0f}s window — a small-sample "
              f"extrapolation, not a robust long-run estimate; treat as illustrative only)")
    else:
        print(f"Sharpe (annualised): skipped — only {len(events)} trade(s) observed, "
              f"too few to extrapolate a yearly rate without a misleading result")

    print(f"\nn_profitable_after_cost (from detector's own spread accounting): "
          f"{len([e for e in events if e.net_spread_bps > 0])}/{len(events)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-s", type=float, default=300.0,
                         help="How long to capture live data before reporting (default: 300s)")
    args = parser.parse_args()
    asyncio.run(_run(args.duration_s))


if __name__ == "__main__":
    main()
