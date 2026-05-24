import { create } from "zustand";
import type {
  ExchangeID, GNNAlpha, OrderBook, PerformanceReport,
  Ticker, WidgetID,
} from "@/types";

const ALPHA_HISTORY_LEN = 200;

// ── Market slice ──────────────────────────────────────────────────────────────

interface MarketState {
  tickers:      Record<string, Ticker>;      // "exchange:symbol"
  orderBooks:   Record<string, OrderBook>;   // "exchange:symbol"
  prevTickers:  Record<string, number>;      // last known `last` price (for flash)
  setTicker:    (t: Ticker) => void;
  setOrderBook: (ob: OrderBook) => void;
}

// ── GNN slice ─────────────────────────────────────────────────────────────────

interface GNNState {
  alphaHistory: Record<string, GNNAlpha[]>;  // keyed by symbol
  pushAlpha:    (a: GNNAlpha) => void;
}

// ── Performance slice ─────────────────────────────────────────────────────────

interface PerformanceState {
  report:    PerformanceReport | null;
  setReport: (r: PerformanceReport) => void;
}

// ── UI slice ──────────────────────────────────────────────────────────────────

interface UIState {
  activeWidgetId:   WidgetID;
  activeSymbol:     string;
  activeExchange:   ExchangeID;
  wsStatus:         "connecting" | "connected" | "disconnected";
  latencyMs:        number | null;
  sidebarCollapsed: boolean;
  setActiveWidget:    (id: WidgetID) => void;
  setActiveSymbol:    (s: string) => void;
  setActiveExchange:  (e: ExchangeID) => void;
  setWsStatus:        (s: UIState["wsStatus"]) => void;
  setLatency:         (ms: number) => void;
  toggleSidebar:      () => void;
}

// ── Combined store ────────────────────────────────────────────────────────────

type AppStore = MarketState & GNNState & PerformanceState & UIState;

export const useAppStore = create<AppStore>()((set) => ({
  // Market
  tickers:     {},
  orderBooks:  {},
  prevTickers: {},
  setTicker: (t) =>
    set((s) => ({
      prevTickers: {
        ...s.prevTickers,
        [`${t.exchange}:${t.symbol}`]: s.tickers[`${t.exchange}:${t.symbol}`]?.last ?? t.last,
      },
      tickers: { ...s.tickers, [`${t.exchange}:${t.symbol}`]: t },
    })),
  setOrderBook: (ob) =>
    set((s) => ({
      orderBooks: { ...s.orderBooks, [`${ob.exchange}:${ob.symbol}`]: ob },
    })),

  // GNN
  alphaHistory: {},
  pushAlpha: (a) =>
    set((s) => {
      const prev = s.alphaHistory[a.symbol] ?? [];
      return { alphaHistory: { ...s.alphaHistory, [a.symbol]: [...prev, a].slice(-ALPHA_HISTORY_LEN) } };
    }),

  // Performance
  report:    null,
  setReport: (r) => set({ report: r }),

  // UI
  activeWidgetId:   "overview",
  activeSymbol:     "BTC/USDT",
  activeExchange:   "binance",
  wsStatus:         "disconnected",
  latencyMs:        null,
  sidebarCollapsed: false,
  setActiveWidget:   (id) => set({ activeWidgetId: id }),
  setActiveSymbol:   (s)  => set({ activeSymbol: s }),
  setActiveExchange: (e)  => set({ activeExchange: e }),
  setWsStatus:       (st) => set({ wsStatus: st }),
  setLatency:        (ms) => set({ latencyMs: ms }),
  toggleSidebar:     ()   => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}));
