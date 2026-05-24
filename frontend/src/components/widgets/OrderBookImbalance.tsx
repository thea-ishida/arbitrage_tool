"use client";

import { useAppStore }         from "@/store";
import type { WidgetProps, ExchangeID } from "@/types";

const EXCHANGES: ExchangeID[] = ["binance", "kraken", "coinbase", "okx"];

const EX_META: Record<ExchangeID, { abbr: string; color: string }> = {
  binance:  { abbr: "BIN", color: "#F0B90B" },
  kraken:   { abbr: "KRK", color: "#5741D9" },
  coinbase: { abbr: "CB",  color: "#0052FF" },
  okx:      { abbr: "OKX", color: "#00C5BF" },
};

function calcOBI(ob: { bids: { qty: number }[]; asks: { qty: number }[] } | undefined) {
  if (!ob) return null;
  const bv = ob.bids.slice(0, 5).reduce((s, l) => s + l.qty, 0);
  const av = ob.asks.slice(0, 5).reduce((s, l) => s + l.qty, 0);
  const d  = bv + av;
  return d ? (bv - av) / d : 0;
}

function DualBar({ value }: { value: number | null }) {
  if (value === null) {
    return (
      <div className="flex items-center justify-center h-6">
        <span className="text-[10px] text-blue-400/20">no data</span>
      </div>
    );
  }

  const bidPct = value >= 0 ? value * 100     : 0;
  const askPct = value < 0  ? -value * 100    : 0;
  const total  = bidPct + askPct;
  const netPct = Math.abs(value) * 100;

  return (
    <div className="flex items-center gap-2">
      {/* Bid side — grows left from center */}
      <div className="flex-1 flex justify-end">
        <div className="relative h-5 w-full rounded-l-sm overflow-hidden"
          style={{ background: "rgba(18,37,64,0.6)" }}>
          <div
            className="absolute top-0 right-0 h-full rounded-l-sm transition-all duration-300"
            style={{
              width:      `${bidPct}%`,
              background: `linear-gradient(90deg, rgba(52,211,153,0.3) 0%, rgba(52,211,153,0.7) 100%)`,
            }}
          />
        </div>
      </div>

      {/* Center divider + value */}
      <div
        className="w-14 flex-shrink-0 text-center font-mono text-xs tabular"
        style={{ color: value >= 0 ? "#34D399" : "#F87171" }}
      >
        {value >= 0 ? "+" : ""}{(value * 100).toFixed(1)}%
      </div>

      {/* Ask side — grows right from center */}
      <div className="flex-1">
        <div className="relative h-5 w-full rounded-r-sm overflow-hidden"
          style={{ background: "rgba(18,37,64,0.6)" }}>
          <div
            className="absolute top-0 left-0 h-full rounded-r-sm transition-all duration-300"
            style={{
              width:      `${askPct}%`,
              background: `linear-gradient(90deg, rgba(248,113,113,0.7) 0%, rgba(248,113,113,0.3) 100%)`,
            }}
          />
        </div>
      </div>
    </div>
  );
}

export function OrderBookImbalance({ symbol = "BTC/USDT" }: WidgetProps) {
  const orderBooks = useAppStore((s) => s.orderBooks);

  const rows = EXCHANGES.map((ex) => ({
    ex,
    obi: calcOBI(orderBooks[`${ex}:${symbol}`]),
    ts:  orderBooks[`${ex}:${symbol}`]?.ts,
  })).sort((a, b) => {
    if (a.obi === null) return 1;
    if (b.obi === null) return -1;
    return Math.abs(b.obi) - Math.abs(a.obi);
  });

  const maxOBI = Math.max(...rows.map((r) => (r.obi ? Math.abs(r.obi) : 0)), 0.01);

  return (
    <div className="card-glass rounded-xl h-full flex flex-col p-5 gap-4" style={{ minHeight: 320 }}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] text-blue-400/50 uppercase tracking-widest mb-1">
            Order Book Imbalance
          </p>
          <p className="text-white font-semibold text-sm">{symbol}</p>
        </div>
        <div className="text-[10px] text-blue-400/30 text-right">
          <p>Depth: top-5 levels</p>
          <p className="mt-0.5">+% = buy pressure</p>
        </div>
      </div>

      {/* Column headers */}
      <div className="flex items-center gap-2 text-[9px] text-blue-400/30 uppercase tracking-widest">
        <span className="w-14 flex-shrink-0">Exchange</span>
        <span className="flex-1 text-right">Bids</span>
        <span className="w-14 flex-shrink-0 text-center">OBI</span>
        <span className="flex-1">Asks</span>
      </div>

      {/* Rows */}
      <div className="flex flex-col gap-3 flex-1">
        {rows.map(({ ex, obi }) => {
          const meta      = EX_META[ex];
          const intensity = obi ? Math.abs(obi) / maxOBI : 0;
          return (
            <div key={ex} className="flex items-center gap-2">
              {/* Exchange badge */}
              <div
                className="w-14 flex-shrink-0 flex items-center gap-1.5"
              >
                <span
                  className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                  style={{ background: meta.color }}
                />
                <span className="text-[11px] font-mono text-blue-300/70">{meta.abbr}</span>
              </div>
              <div className="flex-1">
                <DualBar value={obi} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Aggregate pressure indicator */}
      {rows.some((r) => r.obi !== null) && (() => {
        const valid = rows.filter((r) => r.obi !== null);
        const avg   = valid.reduce((s, r) => s + r.obi!, 0) / valid.length;
        const col   = avg >= 0 ? "#34D399" : "#F87171";
        return (
          <div
            className="flex items-center justify-between px-3 py-2 rounded-lg text-xs"
            style={{ background: "rgba(18,37,64,0.7)", border: "1px solid rgba(30,58,138,0.3)" }}
          >
            <span className="text-blue-400/50">Cross-exchange avg OBI</span>
            <span className="font-mono font-bold tabular" style={{ color: col }}>
              {avg >= 0 ? "+" : ""}{(avg * 100).toFixed(2)}%
            </span>
          </div>
        );
      })()}
    </div>
  );
}
