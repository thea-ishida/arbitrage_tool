"use client";

import {
  LineChart, Line, ResponsiveContainer, Tooltip, ReferenceLine,
} from "recharts";
import { useAppStore }    from "@/store";
import type { WidgetProps } from "@/types";

// ── Metric card ───────────────────────────────────────────────────────────────

function MetricCard({
  label, value, unit = "", fmt, thresholds, description,
}: {
  label:       string;
  value:       number | null;
  unit?:       string;
  fmt:         (v: number) => string;
  thresholds:  { good: number; warn: number; flip?: boolean };
  description: string;
}) {
  const isGood = value === null
    ? false
    : thresholds.flip
      ? value <= thresholds.good
      : value >= thresholds.good;
  const isWarn = value === null
    ? false
    : thresholds.flip
      ? value > thresholds.good && value <= thresholds.warn
      : value < thresholds.good && value >= thresholds.warn;

  const color = value === null
    ? "#4B5563"
    : isGood ? "#34D399"
    : isWarn ? "#FBBF24"
    : "#F87171";

  return (
    <div
      className="rounded-xl p-4 flex flex-col gap-2"
      style={{
        background: "rgba(18,37,64,0.7)",
        border:     `1px solid ${color}22`,
        boxShadow:  `0 0 20px -8px ${color}40`,
      }}
    >
      <p className="text-[10px] text-blue-400/50 uppercase tracking-widest">{label}</p>
      <div className="flex items-end gap-1.5">
        <span
          className="text-2xl font-mono font-bold tabular leading-none"
          style={{ color }}
        >
          {value === null ? "—" : fmt(value)}
        </span>
        {unit && (
          <span className="text-xs text-blue-400/40 mb-0.5">{unit}</span>
        )}
      </div>
      <p className="text-[10px] text-blue-400/30 leading-tight">{description}</p>

      {/* Threshold bar */}
      <div className="h-0.5 rounded-full mt-1" style={{ background: "rgba(30,58,138,0.3)" }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width:      value === null ? "0%" : `${Math.min(Math.abs(value) / (thresholds.flip ? Math.abs(thresholds.warn) : thresholds.good) * 60, 100)}%`,
            background: color,
          }}
        />
      </div>
    </div>
  );
}

// ── Equity curve mini chart ───────────────────────────────────────────────────

function EquityCurve({ curve }: { curve: number[] }) {
  if (!curve.length) return null;
  const data     = curve.map((v, i) => ({ i, v }));
  const baseline = curve[0];
  const latest   = curve.at(-1)!;
  const pnl      = latest - baseline;
  const pct      = ((pnl / baseline) * 100).toFixed(2);
  const color    = pnl >= 0 ? "#34D399" : "#F87171";

  return (
    <div
      className="rounded-xl p-4"
      style={{ background: "rgba(18,37,64,0.7)", border: "1px solid rgba(30,58,138,0.25)" }}
    >
      <div className="flex items-center justify-between mb-3">
        <p className="text-[10px] text-blue-400/50 uppercase tracking-widest">Equity Curve</p>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs tabular" style={{ color }}>
            {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}
          </span>
          <span
            className="text-xs font-mono tabular px-1.5 py-0.5 rounded"
            style={{ color, background: `${color}18` }}
          >
            {pct}%
          </span>
        </div>
      </div>
      <div className="h-24">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <ReferenceLine
              y={baseline}
              stroke="rgba(96,165,250,0.2)"
              strokeDasharray="3 3"
            />
            <Line
              type="monotone"
              dataKey="v"
              stroke={color}
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
            <Tooltip
              contentStyle={{
                background:  "rgba(11,25,44,0.95)",
                border:      "1px solid rgba(30,58,138,0.4)",
                borderRadius: 6,
                fontSize:    11,
              }}
              formatter={(v: number) => [`$${v.toFixed(2)}`, "Equity"]}
              labelFormatter={() => ""}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────

export function PerformanceMetrics(_props: WidgetProps) {
  const report = useAppStore((s) => s.report);

  return (
    <div className="card-glass rounded-xl h-full flex flex-col p-5 gap-4" style={{ minHeight: 380 }}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] text-blue-400/50 uppercase tracking-widest mb-1">
            Execution Simulator
          </p>
          <p className="text-white font-semibold text-sm">Performance Metrics</p>
        </div>
        {report && (
          <div className="text-right">
            <p className="text-[10px] text-blue-400/40">Total Trades</p>
            <p className="font-mono text-blue-200 text-lg tabular">{report.nTrades}</p>
          </div>
        )}
      </div>

      {/* Fees strip */}
      {report && (
        <div
          className="flex gap-4 px-3 py-2 rounded-lg text-xs"
          style={{ background: "rgba(18,37,64,0.6)", border: "1px solid rgba(30,58,138,0.2)" }}
        >
          {[
            { label: "Net P&L",  value: `${report.netPnl >= 0 ? "+" : ""}$${report.netPnl.toFixed(2)}`,   color: report.netPnl >= 0 ? "#34D399" : "#F87171" },
            { label: "Gross",    value: `$${report.grossPnl.toFixed(2)}`,  color: "#60A5FA" },
            { label: "Fees",     value: `-$${report.totalFees.toFixed(2)}`, color: "#F87171" },
            { label: "PF",       value: report.profitFactor.toFixed(2),     color: "#FBBF24" },
          ].map(({ label, value, color }) => (
            <div key={label} className="flex-1 text-center">
              <p className="text-[9px] text-blue-400/40 uppercase tracking-wider">{label}</p>
              <p className="font-mono tabular mt-0.5 text-xs" style={{ color }}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* 4 metric cards */}
      <div className="grid grid-cols-2 gap-3">
        <MetricCard
          label="Sharpe Ratio"
          value={report?.sharpeRatio ?? null}
          fmt={(v) => v.toFixed(2)}
          thresholds={{ good: 1.5, warn: 0.5 }}
          description="Annualised risk-adjusted return. ≥1.5 is strong."
        />
        <MetricCard
          label="Max Drawdown"
          value={report?.maxDrawdown ?? null}
          unit="%"
          fmt={(v) => `${(v * 100).toFixed(2)}`}
          thresholds={{ good: -0.05, warn: -0.15, flip: true }}
          description="Peak-to-trough equity decline. Closer to 0 is better."
        />
        <MetricCard
          label="Information Ratio"
          value={report?.informationRatio ?? null}
          fmt={(v) => v.toFixed(2)}
          thresholds={{ good: 1.0, warn: 0.3 }}
          description="Alpha per unit of tracking error vs. benchmark."
        />
        <MetricCard
          label="Win Rate"
          value={report ? report.winRate * 100 : null}
          unit="%"
          fmt={(v) => v.toFixed(1)}
          thresholds={{ good: 55, warn: 45 }}
          description="% of trades that closed in profit."
        />
      </div>

      {/* Equity curve */}
      {report?.equityCurve?.length ? (
        <EquityCurve curve={report.equityCurve} />
      ) : (
        <div className="flex items-center justify-center flex-1 text-blue-400/20 text-sm">
          Waiting for simulation data…
        </div>
      )}
    </div>
  );
}
