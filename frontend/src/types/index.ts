// ── Market data ───────────────────────────────────────────────────────────────

export type ExchangeID = "binance" | "kraken" | "coinbase" | "okx";

export interface Ticker {
  exchange:   ExchangeID;
  symbol:     string;
  bid:        number;
  ask:        number;
  last:       number;
  volume24h:  number;
  ts:         number;   // epoch seconds
}

export interface PriceLevel {
  price: number;
  qty:   number;
}

export interface OrderBook {
  exchange: ExchangeID;
  symbol:   string;
  bids:     PriceLevel[];
  asks:     PriceLevel[];
  ts:       number;
}

// ── GNN output ────────────────────────────────────────────────────────────────

export interface GNNAlpha {
  symbol:   string;
  alpha:    number;     // sign = direction, magnitude = conviction
  exchange: ExchangeID;
  ts:       number;
}

// ── Execution / performance ───────────────────────────────────────────────────

export interface PerformanceReport {
  nTrades:          number;
  netPnl:           number;
  grossPnl:         number;
  totalFees:        number;
  sharpeRatio:      number;
  maxDrawdown:      number;    // ≤ 0, expressed as fraction
  informationRatio: number;
  winRate:          number;    // 0–1
  profitFactor:     number;
  equityCurve:      number[];  // cumulative equity values
}

// ── Widget system ─────────────────────────────────────────────────────────────

export type WidgetID = string;

export interface WidgetMeta {
  id:          WidgetID;
  label:       string;
  description: string;
  icon:        string;   // SVG path data
  component:   React.ComponentType<WidgetProps>;
}

export interface WidgetProps {
  symbol?: string;
}

// ── WebSocket messages ────────────────────────────────────────────────────────

export type SignalTopic = "ticker" | "order_book" | "gnn_alpha" | "execution";

export interface WsMessage<T = unknown> {
  topic:   SignalTopic;
  payload: T;
  ts:      number;
}
