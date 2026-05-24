"use client";

import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, defs,
} from "recharts";
import { useAppStore }    from "@/store";
import type { WidgetProps } from "@/types";
import { clsx }           from "clsx";

// ── Conviction classifier ─────────────────────────────────────────────────────

function convictionLabel(alpha: number): { label: string; color: string; bg: string } {
  const a = Math.abs(alpha);
  if (a < 0.08) return { label: "NEUTRAL",  color: "#94A3B8", bg: "rgba(148,163,184,0.12)" };
  if (a < 0.25) return { label: "WEAK",     color: "#FBBF24", bg: "rgba(251,191,36,0.12)"  };
  if (a < 0.55) return { label: "MODERATE", color: "#60A5FA", bg: "rgba(96,165,250,0.12)"  };
  return              { label: "STRONG",    color: alpha > 0 ? "#34D399" : "#F87171",
                                            bg:    alpha > 0 ? "rgba(52,211,153,0.12)" : "rgba(248,113,113,0.12)" };
}

// ── Custom tooltip ────────────────────────────────────────────────────────────

function AlphaTooltip({ active, payload }: { active?: boolean; payload?: { value: number }[] }) {
  if (!active || !payload?.length) return null;
  const v   = payload[0].value;
  const col = v >= 0 ? "#34D399" : "#F87171";
  return (
    <div
      className="px-3 py-2 rounded-lg text-xs font-mono"
      style={{
        background:   "rgba(11,25,44,0.95)",
        border:       "1px solid rgba(30,58,138,0.5)",
        backdropFilter: "blur(8px)",
      }}
    >
      <span style={{ color: col }}>{v >= 0 ? "+" : ""}{v.toFixed(5)}</span>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function GNNAlphaChart({ symbol = "BTC/USDT" }: WidgetProps) {
  const history = useAppStore((s) => s.alphaHistory[symbol] ?? []);
  const latest  = history.at(-1);
  const alpha   = latest?.alpha ?? 0;
  const conv    = convictionLabel(alpha);

  const data = history.map((a, i) => ({
    i,
    alpha: parseFloat(a.alpha.toFixed(5)),
    pos:   a.alpha >= 0 ? a.alpha : 0,
    neg:   a.alpha < 0  ? a.alpha : 0,
  }));

  // Dynamic y-axis domain with symmetric padding
  const values = data.map((d) => d.alpha);
  const yMax   = Math.max(Math.abs(Math.min(...values, 0)), Math.abs(Math.max(...values, 0)), 0.1);
  const yDomain: [number, number] = [-yMax * 1.15, yMax * 1.15];

  return (
    <div
      className="card-glass rounded-xl h-full flex flex-col p-5 gap-4"
      style={{ minHeight: 340 }}
    >
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] text-blue-400/50 uppercase tracking-widest mb-1">
            GNN Alpha Signal
          </p>
          <p className="text-white font-semibold text-sm">{symbol}</p>
        </div>

        <div className="flex items-center gap-3">
          {/* Conviction badge */}
          <span
            className="text-[10px] font-bold tracking-widest px-2 py-0.5 rounded-full uppercase"
            style={{ color: conv.color, background: conv.bg, border: `1px solid ${conv.color}30` }}
          >
            {conv.label}
          </span>

          {/* Alpha readout */}
          <div className="text-right">
            <p
              className="text-2xl font-mono font-bold tabular leading-none"
              style={{ color: alpha >= 0 ? "#34D399" : "#F87171" }}
            >
              {alpha >= 0 ? "+" : ""}{alpha.toFixed(4)}
            </p>
            <p className="text-[10px] text-blue-400/40 mt-0.5">α</p>
          </div>
        </div>
      </div>

      {/* ── Stats row ── */}
      {history.length > 1 && (
        <div className="flex gap-4">
          {[
            { label: "1m High", value: Math.max(...history.slice(-20).map((h) => h.alpha)).toFixed(4) },
            { label: "1m Low",  value: Math.min(...history.slice(-20).map((h) => h.alpha)).toFixed(4) },
            { label: "Exchange", value: latest?.exchange ?? "—" },
          ].map(({ label, value }) => (
            <div key={label}
              className="px-3 py-1.5 rounded-lg text-xs"
              style={{ background: "rgba(18,37,64,0.6)", border: "1px solid rgba(30,58,138,0.25)" }}
            >
              <p className="text-blue-400/40 text-[10px] uppercase tracking-wider">{label}</p>
              <p className="text-blue-200 font-mono mt-0.5 tabular capitalize">{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Chart ── */}
      <div className="flex-1 min-h-0">
        {data.length < 2 ? (
          <div className="flex items-center justify-center h-full text-blue-400/20 text-sm">
            Waiting for signal…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="gradPos" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#34D399" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#34D399" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradNeg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#F87171" stopOpacity={0.02} />
                  <stop offset="95%" stopColor="#F87171" stopOpacity={0.3} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="2 6"
                stroke="rgba(30,58,138,0.25)"
                vertical={false}
              />
              <XAxis dataKey="i" hide />
              <YAxis
                domain={yDomain}
                tick={{ fill: "rgba(96,165,250,0.4)", fontSize: 10, fontFamily: "monospace" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) => v.toFixed(2)}
                width={40}
              />
              <Tooltip content={<AlphaTooltip />} />
              <ReferenceLine
                y={0}
                stroke="rgba(96,165,250,0.35)"
                strokeDasharray="4 3"
                strokeWidth={1}
              />
              <Area
                type="monotone"
                dataKey="pos"
                stroke="#34D399"
                strokeWidth={2}
                fill="url(#gradPos)"
                dot={false}
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="neg"
                stroke="#F87171"
                strokeWidth={2}
                fill="url(#gradNeg)"
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* ── Legend ── */}
      <div className="flex gap-4 text-[10px] text-blue-400/40">
        <span><span className="text-emerald-400">▲</span> α &gt; 0 → lag exchange rises</span>
        <span><span className="text-rose-400">▼</span> α &lt; 0 → lag exchange falls</span>
      </div>
    </div>
  );
}
