"""
Feature engineering from raw market data.

Converts streams of Ticker / OrderBook signals into the per-node feature
vectors fed into the GNN on each forward pass.

Node feature vector (per exchange, per symbol) — shape [N_exchanges, F_dim]:
  [0] mid_price_norm     — mid price z-scored over rolling window
  [1] spread_norm        — spread normalised by mid
  [2] obi                — order book imbalance ∈ (-1, 1)
  [3] log_return         — log(mid_t / mid_{t-1})
  [4] volume_z           — 24h volume z-scored
  [5] bid_ask_slope      — linear slope of top-5 bid levels (depth proxy)
  [6] ask_bid_slope      — linear slope of top-5 ask levels
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from backend.core.types import ExchangeID, OrderBook, Ticker

_WINDOW = 60     # rolling window length for normalisation
_F_DIM  = 7     # must match the feature vector description above


@dataclass
class _NodeState:
    """Sliding-window statistics for one (exchange, symbol) node."""
    mid_prices:  deque[float] = field(default_factory=lambda: deque(maxlen=_WINDOW))
    volumes:     deque[float] = field(default_factory=lambda: deque(maxlen=_WINDOW))
    last_ob:     OrderBook | None = None

    def update_ticker(self, t: Ticker) -> None:
        self.mid_prices.append((t.bid + t.ask) / 2.0)
        self.volumes.append(t.volume_24h)

    def update_book(self, ob: OrderBook) -> None:
        self.last_ob = ob


class FeatureBuilder:
    """
    Stateful accumulator.  Call `update_ticker` / `update_book` on ingest,
    then `build_feature_matrix` before each GNN forward pass.
    """

    def __init__(self, exchanges: list[ExchangeID], symbols: list[str]) -> None:
        self.exchanges = exchanges
        self.symbols   = symbols
        # keyed by (exchange_id, symbol)
        self._state: dict[tuple[ExchangeID, str], _NodeState] = {
            (ex, sym): _NodeState()
            for ex in exchanges
            for sym in symbols
        }

    # ── Update methods ────────────────────────────────────────────────────────

    def update_ticker(self, ticker: Ticker) -> None:
        key = (ticker.exchange, ticker.symbol)
        if key in self._state:
            self._state[key].update_ticker(ticker)

    def update_book(self, book: OrderBook) -> None:
        key = (book.exchange, book.symbol)
        if key in self._state:
            self._state[key].update_book(book)

    # ── Feature matrix ────────────────────────────────────────────────────────

    def build_feature_matrix(self, symbol: str) -> np.ndarray:
        """
        Returns shape [N_exchanges, F_DIM] for a single symbol.
        Returns None if any node has insufficient history.
        """
        rows = []
        for ex in self.exchanges:
            vec = self._node_features(ex, symbol)
            if vec is None:
                return None
            rows.append(vec)
        return np.stack(rows, axis=0).astype(np.float32)

    def _node_features(self, exchange: ExchangeID, symbol: str) -> np.ndarray | None:
        state = self._state.get((exchange, symbol))
        if state is None or len(state.mid_prices) < 2:
            return None

        mids   = np.array(state.mid_prices, dtype=np.float64)
        vols   = np.array(state.volumes,    dtype=np.float64)
        mid    = mids[-1]

        mid_z   = _zscore(mids)[-1]
        vol_z   = _zscore(vols)[-1]
        log_ret = math.log(mids[-1] / mids[-2]) if mids[-2] != 0 else 0.0

        if state.last_ob and len(state.last_ob.bids) >= 5 and len(state.last_ob.asks) >= 5:
            ob      = state.last_ob
            spread  = ob.spread / mid if mid else 0.0
            obi     = ob.order_book_imbalance(depth=5)
            b_slope = _price_slope([lvl[0] for lvl in ob.bids[:5]])
            a_slope = _price_slope([lvl[0] for lvl in ob.asks[:5]])
        else:
            spread = obi = b_slope = a_slope = 0.0

        return np.array([mid_z, spread, obi, log_ret, vol_z, b_slope, a_slope])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _zscore(arr: np.ndarray) -> np.ndarray:
    std = arr.std()
    return (arr - arr.mean()) / std if std > 1e-9 else arr - arr.mean()


def _price_slope(prices: list[float]) -> float:
    """Normalised linear regression slope over N price levels."""
    n  = len(prices)
    xs = np.arange(n, dtype=np.float64)
    ys = np.array(prices, dtype=np.float64)
    if ys.mean() == 0:
        return 0.0
    slope = np.polyfit(xs, ys, 1)[0]
    return float(slope / ys.mean())   # normalise by mid for scale-invariance
