"use client";

import { useEffect, useRef, useState } from "react";
import { useAppStore }                  from "@/store";
import type { ExchangeID, WidgetProps } from "@/types";
import { clsx }                         from "clsx";

const EXCHANGES: ExchangeID[] = ["binance", "kraken", "coinbase", "okx"];

const EX_META: Record<ExchangeID, { name: string; dot: string }> = {
  binance:  { name: "Binance",  dot: "#F0B90B" },
  kraken:   { name: "Kraken",   dot: "#5741D9" },
  coinbase: { name: "Coinbase", dot: "#0052FF" },
  okx:      { name: "OKX",      dot: "#00C5BF" },
};

function useFlash(value: number | undefined) {
  const [cls, setCls]  = useState("");
  const prevRef        = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (prevRef.current === undefined || value === undefined) {
      prevRef.current = value;
      return;
    }
    if (value > prevRef.current) {
      setCls("flash-up");
    } else if (value < prevRef.current) {
      setCls("flash-down");
    }
    prevRef.current = value;
    const t = setTimeout(() => setCls(""), 500);
    return () => clearTimeout(t);
  }, [value]);

  return cls;
}

function TickerRow({ exchange, symbol }: { exchange: ExchangeID; symbol: string }) {
  const ticker = useAppStore((s) => s.tickers[`${exchange}:${symbol}`]);
  const flash  = useFlash(ticker?.last);
  const meta   = EX_META[exchange];

  if (!ticker) {
    return (
      <tr>
        <td className="py-2.5 pl-4">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: meta.dot }} />
            <span className="text-blue-300/50 text-xs">{meta.name}</span>
          </div>
        </td>
        {[...Array(5)].map((_, i) => (
          <td key={i} className="py-2.5 px-3 text-center">
            <span className="text-blue-400/20 text-xs font-mono">—</span>
          </td>
        ))}
      </tr>
    );
  }

  const spread    = ticker.ask - ticker.bid;
  const spreadBps = (spread / ticker.last) * 10_000;

  return (
    <tr className={clsx("border-t border-navy-800/40 transition-colors", flash)}>
      {/* Exchange */}
      <td className="py-2.5 pl-4">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: meta.dot }} />
          <span className="text-blue-200/80 text-xs font-medium">{meta.name}</span>
        </div>
      </td>

      {/* Last price */}
      <td className="py-2.5 px-3 text-right">
        <span
          className="font-mono text-xs tabular font-semibold"
          style={{ color: "#E2E8F0" }}
        >
          ${ticker.last.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      </td>

      {/* Bid */}
      <td className="py-2.5 px-3 text-right">
        <span className="font-mono text-xs tabular text-emerald-400/80">
          {ticker.bid.toFixed(2)}
        </span>
      </td>

      {/* Ask */}
      <td className="py-2.5 px-3 text-right">
        <span className="font-mono text-xs tabular text-rose-400/80">
          {ticker.ask.toFixed(2)}
        </span>
      </td>

      {/* Spread (bps) */}
      <td className="py-2.5 px-3 text-right">
        <span
          className={clsx(
            "font-mono text-xs tabular px-1.5 py-0.5 rounded",
            spreadBps < 1
              ? "text-emerald-400 bg-emerald-400/10"
              : spreadBps < 3
              ? "text-amber-400 bg-amber-400/10"
              : "text-rose-400 bg-rose-400/10",
          )}
        >
          {spreadBps.toFixed(1)}
        </span>
      </td>

      {/* 24h volume */}
      <td className="py-2.5 pr-4 text-right">
        <span className="font-mono text-xs tabular text-blue-400/50">
          {(ticker.volume24h / 1000).toFixed(1)}K
        </span>
      </td>
    </tr>
  );
}

export function LiveTicker({ symbol = "BTC/USDT" }: WidgetProps) {
  const tickers = useAppStore((s) => s.tickers);

  // Best bid / ask across exchanges
  const allPrices = EXCHANGES
    .map((ex) => tickers[`${ex}:${symbol}`]?.last)
    .filter((v): v is number => v !== undefined);

  const bestBid = allPrices.length
    ? Math.max(...EXCHANGES.map((ex) => tickers[`${ex}:${symbol}`]?.bid ?? 0))
    : null;
  const bestAsk = allPrices.length
    ? Math.min(...EXCHANGES.map((ex) => tickers[`${ex}:${symbol}`]?.ask ?? Infinity))
    : null;

  return (
    <div className="card-glass rounded-xl h-full flex flex-col" style={{ minHeight: 300 }}>
      {/* Header */}
      <div className="px-5 pt-5 pb-4 flex items-start justify-between border-b border-navy-800/40">
        <div>
          <p className="text-[10px] text-blue-400/50 uppercase tracking-widest mb-1">
            Live Cross-Exchange Prices
          </p>
          <p className="text-white font-semibold text-sm">{symbol}</p>
        </div>

        {/* Best bid/ask */}
        {bestBid && bestAsk && (
          <div className="flex gap-3 text-right">
            <div>
              <p className="text-[9px] text-blue-400/40 uppercase tracking-wider">Best Bid</p>
              <p className="font-mono text-xs tabular text-emerald-400">${bestBid.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-[9px] text-blue-400/40 uppercase tracking-wider">Best Ask</p>
              <p className="font-mono text-xs tabular text-rose-400">${bestAsk.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-[9px] text-blue-400/40 uppercase tracking-wider">X-Spread</p>
              <p className="font-mono text-xs tabular text-amber-400">
                ${(bestAsk - bestBid).toFixed(2)}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead>
            <tr style={{ background: "rgba(18,37,64,0.5)" }}>
              {["Exchange", "Last", "Bid", "Ask", "Spread (bps)", "Vol 24h"].map((h, i) => (
                <th
                  key={h}
                  className={clsx(
                    "py-2 text-[9px] font-medium uppercase tracking-widest text-blue-400/40",
                    i === 0 ? "pl-4 text-left" : i === 5 ? "pr-4 text-right" : "px-3 text-right",
                  )}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {EXCHANGES.map((ex) => (
              <TickerRow key={ex} exchange={ex} symbol={symbol} />
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer note */}
      <div className="px-5 py-2 border-t border-navy-800/40">
        <p className="text-[10px] text-blue-400/25">
          Spread &lt;1bps = tight &nbsp;|&nbsp; cross-exchange spread = arb opportunity threshold
        </p>
      </div>
    </div>
  );
}
