"use client";

/**
 * Development mock data feed.
 * Seeds the Zustand store with realistic streaming data so the dashboard
 * renders live when the Python backend isn't running.
 * Remove the <MockDataProvider> from DashboardLayout when going to production.
 */

import { useEffect, useRef } from "react";
import { useAppStore } from "@/store";
import type { ExchangeID, GNNAlpha, OrderBook, PerformanceReport, Ticker } from "@/types";

const EXCHANGES: ExchangeID[] = ["binance", "kraken", "coinbase", "okx"];
const SYMBOLS  = ["BTC/USDT", "ETH/USDT"];

// Exchange-specific price offsets to simulate realistic cross-exchange spreads
const BASE_PRICES: Record<ExchangeID, Record<string, number>> = {
  binance:  { "BTC/USDT": 76_930, "ETH/USDT": 3_312 },
  kraken:   { "BTC/USDT": 76_935, "ETH/USDT": 3_313 },
  coinbase: { "BTC/USDT": 76_928, "ETH/USDT": 3_311 },
  okx:      { "BTC/USDT": 76_932, "ETH/USDT": 3_312 },
};

function randNorm(mean = 0, std = 1): number {
  // Box-Muller
  const u1 = Math.random(), u2 = Math.random();
  return mean + std * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

function clamp(v: number, min: number, max: number) { return Math.max(min, Math.min(max, v)); }

// Persistent random-walk state
const priceState: Record<string, number> = {};
const obiState:   Record<string, number> = {};
let   alphaState  = 0.0;

function initState() {
  for (const ex of EXCHANGES) {
    for (const sym of SYMBOLS) {
      const k = `${ex}:${sym}`;
      priceState[k] = BASE_PRICES[ex][sym];
      obiState[k]   = randNorm(0, 0.15);
    }
  }
}

export function useMockData(enabled = true): void {
  const { setTicker, setOrderBook, pushAlpha, setReport, setWsStatus } = useAppStore();
  const initialised = useRef(false);

  useEffect(() => {
    if (!enabled || initialised.current) return;
    initialised.current = true;

    initState();
    setWsStatus("connected");
    setReport(buildInitialReport());

    // Ticker feed — 250ms
    const tickerInterval = setInterval(() => {
      for (const sym of SYMBOLS) {
        for (const ex of EXCHANGES) {
          const k      = `${ex}:${sym}`;
          const drift  = randNorm(0, sym === "BTC/USDT" ? 8 : 2);
          priceState[k] = Math.max(priceState[k] + drift, 100);
          const last   = priceState[k];
          const spread = last * 0.00015;
          setTicker({
            exchange:  ex,
            symbol:    sym,
            last,
            bid:       last - spread / 2,
            ask:       last + spread / 2,
            volume24h: 120_000 + Math.random() * 2000,
            ts:        Date.now() / 1000,
          });
        }
      }
    }, 250);

    // Order book feed — 400ms
    const bookInterval = setInterval(() => {
      for (const sym of SYMBOLS) {
        for (const ex of EXCHANGES) {
          const k       = `${ex}:${sym}`;
          obiState[k]   = clamp(obiState[k] + randNorm(0, 0.04), -0.9, 0.9);
          const obi     = obiState[k];
          const mid     = priceState[k];
          setOrderBook(buildOrderBook(ex, sym, mid, obi));
        }
      }
    }, 400);

    // Alpha signal — 300ms with mean-reverting random walk
    const alphaInterval = setInterval(() => {
      alphaState = clamp(alphaState * 0.92 + randNorm(0, 0.06), -1, 1);
      const alpha: GNNAlpha = {
        symbol:   "BTC/USDT",
        alpha:    alphaState,
        exchange: "binance",
        ts:       Date.now() / 1000,
      };
      pushAlpha(alpha);
    }, 300);

    // Performance report refresh — 2s
    const perfInterval = setInterval(() => {
      setReport(buildDriftingReport());
    }, 2000);

    return () => {
      clearInterval(tickerInterval);
      clearInterval(bookInterval);
      clearInterval(alphaInterval);
      clearInterval(perfInterval);
    };
  }, [setTicker, setOrderBook, pushAlpha, setReport, setWsStatus]);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function buildOrderBook(ex: ExchangeID, sym: string, mid: number, obi: number): OrderBook {
  const depth = 20;
  const bids  = Array.from({ length: depth }, (_, i) => ({
    price: mid - (i + 0.5) * mid * 0.0001,
    qty:   Math.max(0.01, randNorm(1 + obi, 0.4)),
  }));
  const asks = Array.from({ length: depth }, (_, i) => ({
    price: mid + (i + 0.5) * mid * 0.0001,
    qty:   Math.max(0.01, randNorm(1 - obi, 0.4)),
  }));
  return { exchange: ex, symbol: sym, bids, asks, ts: Date.now() / 1000 };
}

let _equityCurve = (() => {
  let eq = 10_000;
  return Array.from({ length: 60 }, () => {
    eq += randNorm(15, 80);
    return Math.max(eq, 8_000);
  });
})();

function buildInitialReport(): PerformanceReport {
  return {
    nTrades: 142, netPnl: 1_247.83, grossPnl: 1_509.20, totalFees: 261.37,
    sharpeRatio: 1.87, maxDrawdown: -0.082, informationRatio: 1.42,
    winRate: 0.584, profitFactor: 2.31, equityCurve: [..._equityCurve],
  };
}

function buildDriftingReport(): PerformanceReport {
  _equityCurve = [..._equityCurve.slice(1), _equityCurve.at(-1)! + randNorm(15, 80)];
  return {
    nTrades: 142 + Math.floor(Math.random() * 3),
    netPnl:  _equityCurve.at(-1)! - 10_000,
    grossPnl: _equityCurve.at(-1)! - 10_000 + 261,
    totalFees: 261.37 + Math.random() * 2,
    sharpeRatio:      clamp(1.87 + randNorm(0, 0.03), 0, 5),
    maxDrawdown:      clamp(-0.082 - Math.random() * 0.002, -0.5, 0),
    informationRatio: clamp(1.42 + randNorm(0, 0.02), 0, 5),
    winRate:          clamp(0.584 + randNorm(0, 0.005), 0, 1),
    profitFactor:     clamp(2.31 + randNorm(0, 0.02), 0, 10),
    equityCurve:      [..._equityCurve],
  };
}
