"use client";

import type { WidgetProps } from "@/types";
import { GNNAlphaChart }      from "./GNNAlphaChart";
import { OrderBookImbalance } from "./OrderBookImbalance";
import { PerformanceMetrics } from "./PerformanceMetrics";
import { LiveTicker }         from "./LiveTicker";

/**
 * Overview — renders all 4 panels simultaneously in a responsive grid.
 * This is the default view; selecting a panel from the sidebar shows it
 * full-screen instead.
 */
export function DashboardOverview({ symbol = "BTC/USDT" }: WidgetProps) {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 h-full auto-rows-fr">
      {/* Top-left: GNN Alpha (primary signal) */}
      <div className="min-h-[320px]">
        <GNNAlphaChart symbol={symbol} />
      </div>

      {/* Top-right: Live Ticker */}
      <div className="min-h-[320px]">
        <LiveTicker symbol={symbol} />
      </div>

      {/* Bottom-left: Order Book Imbalance */}
      <div className="min-h-[320px]">
        <OrderBookImbalance symbol={symbol} />
      </div>

      {/* Bottom-right: Performance Metrics */}
      <div className="min-h-[320px]">
        <PerformanceMetrics symbol={symbol} />
      </div>
    </div>
  );
}
