/**
 * Widget Registry — the frontend plugin system.
 *
 * To add a new widget:
 *   1. Create its component in this directory.
 *   2. Add a WidgetMeta entry below with a unique `id` and an icon path.
 *   3. It will appear automatically in the sidebar and DashboardOverview.
 */

import type { WidgetMeta } from "@/types";
import { DashboardOverview }   from "./DashboardOverview";
import { GNNAlphaChart }       from "./GNNAlphaChart";
import { OrderBookImbalance }  from "./OrderBookImbalance";
import { PerformanceMetrics }  from "./PerformanceMetrics";
import { LiveTicker }          from "./LiveTicker";
import { PluginPlaceholder }   from "./PluginPlaceholder";

export const WIDGET_REGISTRY: WidgetMeta[] = [
  {
    id:          "overview",
    label:       "Overview",
    description: "All panels — Bloomberg-style multi-feed view",
    icon:        "",
    component:   DashboardOverview,
  },
  {
    id:          "gnn-alpha-chart",
    label:       "GNN Alpha",
    description: "Real-time lead-lag alpha signal from the GATv2 model",
    icon:        "",
    component:   GNNAlphaChart,
  },
  {
    id:          "order-book-imbalance",
    label:       "Order Book",
    description: "Cross-exchange top-5 order book imbalance (OBI)",
    icon:        "",
    component:   OrderBookImbalance,
  },
  {
    id:          "performance-metrics",
    label:       "Performance",
    description: "Sharpe, Max Drawdown, Information Ratio, Win Rate",
    icon:        "",
    component:   PerformanceMetrics,
  },
  {
    id:          "live-ticker",
    label:       "Live Ticker",
    description: "Real-time bid / ask / spread across all exchanges",
    icon:        "",
    component:   LiveTicker,
  },
  {
    id:          "plugin-placeholder",
    label:       "New Module",
    description: "Drop your next analytical tool here",
    icon:        "",
    component:   PluginPlaceholder,
  },
];

export function getWidget(id: string): WidgetMeta | undefined {
  return WIDGET_REGISTRY.find((w) => w.id === id);
}
