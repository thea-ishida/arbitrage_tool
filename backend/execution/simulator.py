"""
Execution Simulator & Performance Analytics.

Simulates the P&L impact of acting on GNN alpha signals, accounting for:
  • Maker / taker fees (configurable, default 0.1% each side).
  • Execution slippage modelled as a fixed basis-point cost on entry + exit.
  • Round-trip capital allocation per trade.

Metrics computed on the realised P&L series:
  • Annualised Sharpe Ratio  (risk-free rate configurable, default 0)
  • Maximum Drawdown (MDD)
  • Information Ratio        (alpha / tracking-error vs. a passive benchmark)
  • Win rate, average win/loss, profit factor
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import NamedTuple

import numpy as np

from backend.core.config import settings


# ── Trade record ──────────────────────────────────────────────────────────────

class Trade(NamedTuple):
    entry_price:   float
    exit_price:    float
    notional:      float    # USDT equivalent
    direction:     int      # +1 long, -1 short
    entry_ts:      float    # epoch seconds
    exit_ts:       float


# ── Performance report ────────────────────────────────────────────────────────

@dataclass
class PerformanceReport:
    n_trades:         int     = 0
    gross_pnl:        float   = 0.0
    net_pnl:          float   = 0.0
    total_fees:       float   = 0.0
    total_slippage:   float   = 0.0
    win_rate:         float   = 0.0
    profit_factor:    float   = 0.0
    sharpe_ratio:     float   = 0.0
    max_drawdown:     float   = 0.0
    information_ratio: float  = 0.0
    equity_curve:     list[float] = field(default_factory=list)


# ── Simulator ─────────────────────────────────────────────────────────────────

class ExecutionSimulator:
    """
    Stateful simulator.  Feed it Trade objects as the strategy fires, then
    call `report()` at any time for a snapshot of performance metrics.

    Usage:
        sim = ExecutionSimulator()
        sim.record_trade(Trade(...))
        report = sim.report()
    """

    def __init__(
        self,
        initial_capital: float | None = None,
        maker_fee:       float | None = None,
        taker_fee:       float | None = None,
        slippage_bps:    float | None = None,
        risk_free_rate:  float = 0.0,    # annualised, e.g. 0.05 for 5%
        periods_per_year: int = 252 * 24 * 12,  # 5-min bars default
    ) -> None:
        cfg = settings.execution
        self._capital      = initial_capital or cfg.capital_usdt
        self._maker_fee    = maker_fee    or cfg.maker_fee
        self._taker_fee    = taker_fee    or cfg.taker_fee
        self._slippage_bps = slippage_bps or cfg.slippage_bps
        self._rfr          = risk_free_rate
        self._ppy          = periods_per_year

        self._trades:         list[Trade] = []
        self._net_pnl_series: list[float] = []   # cumulative net P&L per trade
        self._equity:         float       = self._capital

    # ── Data ingestion ────────────────────────────────────────────────────────

    def record_trade(self, trade: Trade) -> None:
        gross, fees, slip = self._compute_pnl(trade)
        net = gross - fees - slip

        self._trades.append(trade)
        self._equity += net
        self._net_pnl_series.append(net)

    def simulate_signal(
        self,
        alpha:       float,
        entry_price: float,
        exit_price:  float,
        entry_ts:    float,
        exit_ts:     float,
        threshold:   float = 0.05,   # minimum |alpha| to trade
        fraction:    float = 0.10,   # fraction of capital per trade
    ) -> Trade | None:
        """
        Convert a GNN alpha scalar into a Trade if above threshold, then record it.
        Returns the Trade if executed, else None.
        """
        if abs(alpha) < threshold:
            return None

        direction  = 1 if alpha > 0 else -1
        notional   = self._equity * fraction
        trade      = Trade(
            entry_price=entry_price,
            exit_price=exit_price,
            notional=notional,
            direction=direction,
            entry_ts=entry_ts,
            exit_ts=exit_ts,
        )
        self.record_trade(trade)
        return trade

    # ── Analytics ─────────────────────────────────────────────────────────────

    def report(self, benchmark_returns: np.ndarray | None = None) -> PerformanceReport:
        if not self._trades:
            return PerformanceReport()

        gross_pnl_list, fee_list, slip_list, net_list = [], [], [], []
        for trade in self._trades:
            g, f, s = self._compute_pnl(trade)
            gross_pnl_list.append(g)
            fee_list.append(f)
            slip_list.append(s)
            net_list.append(g - f - s)

        net_arr   = np.array(net_list,       dtype=np.float64)
        gross_arr = np.array(gross_pnl_list, dtype=np.float64)

        wins  = net_arr[net_arr > 0]
        losses = net_arr[net_arr < 0]

        equity_curve = (self._capital + np.cumsum(net_arr)).tolist()

        return PerformanceReport(
            n_trades          = len(self._trades),
            gross_pnl         = float(gross_arr.sum()),
            net_pnl           = float(net_arr.sum()),
            total_fees        = float(sum(fee_list)),
            total_slippage    = float(sum(slip_list)),
            win_rate          = float(len(wins) / len(net_arr)),
            profit_factor     = float(wins.sum() / abs(losses.sum())) if losses.size else math.inf,
            sharpe_ratio      = self._sharpe(net_arr),
            max_drawdown      = self._max_drawdown(np.array(equity_curve)),
            information_ratio = self._information_ratio(net_arr, benchmark_returns),
            equity_curve      = equity_curve,
        )

    # ── Internal maths ────────────────────────────────────────────────────────

    def _compute_pnl(self, trade: Trade) -> tuple[float, float, float]:
        """Returns (gross_pnl, total_fees, total_slippage) in USDT."""
        gross = trade.direction * trade.notional * (
            trade.exit_price / trade.entry_price - 1.0
        )
        # Taker fee on entry, maker fee on exit (assumes limit order for exit)
        fees = trade.notional * (self._maker_fee + self._taker_fee)
        # Slippage: basis-point cost applied to round-trip notional
        slip = trade.notional * (self._slippage_bps / 10_000.0) * 2
        return gross, fees, slip

    def _sharpe(self, returns: np.ndarray) -> float:
        if returns.std() < 1e-9:
            return 0.0
        excess = returns - (self._rfr / self._ppy)
        return float(math.sqrt(self._ppy) * excess.mean() / excess.std())

    @staticmethod
    def _max_drawdown(equity: np.ndarray) -> float:
        peak = np.maximum.accumulate(equity)
        dd   = (equity - peak) / np.where(peak == 0, 1, peak)
        return float(dd.min())

    def _information_ratio(
        self,
        returns:    np.ndarray,
        benchmark:  np.ndarray | None,
    ) -> float:
        if benchmark is None or len(benchmark) != len(returns):
            return 0.0
        active = returns - benchmark
        std    = active.std()
        return float(math.sqrt(self._ppy) * active.mean() / std) if std > 1e-9 else 0.0
