"use client";

import { useState, useEffect }  from "react";
import { useWebSocket }         from "@/hooks/useWebSocket";
import { useMockData }          from "@/hooks/useMockData";
import { useAppStore }          from "@/store";
import { getWidget }            from "@/components/widgets/registry";
import { Sidebar }              from "./Sidebar";
import { clsx }                 from "clsx";

// Set to true to use generated mock data instead of the live backend.
// Automatically falls back to mock when NEXT_PUBLIC_USE_MOCK_DATA=true.
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK_DATA === "true";

function LiveClock() {
  const [time, setTime] = useState("");
  useEffect(() => {
    const tick = () => setTime(new Date().toLocaleTimeString("en-US", { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="font-mono text-xs text-blue-400/60 tabular">{time} UTC</span>;
}

export function DashboardLayout() {
  useWebSocket();
  useMockData(USE_MOCK);

  const { activeWidgetId, activeSymbol, wsStatus, latencyMs, setActiveSymbol } = useAppStore();
  const widget          = getWidget(activeWidgetId);
  const WidgetComponent = widget?.component;

  const statusColor = {
    connected:    "text-emerald-400",
    connecting:   "text-amber-400",
    disconnected: "text-rose-500",
  }[wsStatus];

  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ background: "var(--navy-900)" }}
    >
      {/* ── Global header ───────────────────────────────────────────────── */}
      <header
        className="h-14 flex-shrink-0 flex items-center justify-between px-4 border-b"
        style={{
          borderColor:    "rgba(30,58,138,0.4)",
          background:     "linear-gradient(90deg, rgba(11,25,44,0.98) 0%, rgba(18,37,64,0.98) 100%)",
          backdropFilter: "blur(16px)",
        }}
      >
        {/* Left: mobile sidebar toggle + logo */}
        <div className="flex items-center gap-3">
          {/* Mobile only */}
          <button
            className="md:hidden p-1.5 rounded text-blue-400/50 hover:text-blue-300 hover:bg-navy-800"
            onClick={() => useAppStore.getState().toggleSidebar()}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-5 h-5">
              <path d="M3 12h18M3 6h18M3 18h18"/>
            </svg>
          </button>

          <div className="flex items-center gap-2">
            {/* Brand mark */}
            <div className="w-7 h-7 rounded-md flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%)" }}>
              <svg viewBox="0 0 16 16" fill="none" className="w-4 h-4">
                <path d="M3 13 L8 3 L13 13" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M5 9.5h6" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </div>
            <div className="hidden sm:block">
              <p className="text-white font-semibold text-sm tracking-tight leading-none">
                Arbi Calculator
              </p>
              <p className="text-blue-400/50 text-[10px] tracking-wide">Cross-Exchange GNN</p>
            </div>
          </div>
        </div>

        {/* Center: symbol tabs */}
        <div className="flex items-center gap-1 p-0.5 rounded-lg"
          style={{ background: "rgba(18,37,64,0.8)", border: "1px solid rgba(30,58,138,0.3)" }}>
          {["BTC/USDT", "ETH/USDT"].map((s) => (
            <button
              key={s}
              onClick={() => setActiveSymbol(s)}
              className={clsx(
                "px-3 py-1 rounded-md text-xs font-mono font-medium transition-all",
                activeSymbol === s
                  ? "bg-navy-600 text-blue-200 shadow-glow-blue"
                  : "text-blue-400/50 hover:text-blue-300",
              )}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Right: latency + clock */}
        <div className="flex items-center gap-3">
          {wsStatus === "connected" && latencyMs !== null && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-md"
              style={{ background: "rgba(18,37,64,0.8)", border: "1px solid rgba(30,58,138,0.3)" }}>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-glow-green" />
              <span className="font-mono text-xs text-emerald-400/80 tabular">{latencyMs}ms</span>
            </div>
          )}
          {wsStatus !== "connected" && (
            <span className={clsx("text-xs font-medium", statusColor)}>
              {wsStatus === "connecting" ? "Connecting…" : "Offline"}
            </span>
          )}
          <LiveClock />
        </div>
      </header>

      {/* ── Body ──────────────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />

        {/* Main canvas */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Widget breadcrumb */}
          <div
            className="h-9 flex-shrink-0 flex items-center px-5 border-b"
            style={{ borderColor: "rgba(30,58,138,0.25)", background: "rgba(11,25,44,0.6)" }}
          >
            <span className="text-[11px] text-blue-400/40 uppercase tracking-widest">
              {widget?.label ?? "Dashboard"}
            </span>
            <span className="mx-2 text-blue-400/20">›</span>
            <span className="text-[11px] text-blue-400/60">{activeSymbol}</span>
          </div>

          {/* Widget canvas — bg grid */}
          <div
            className="flex-1 overflow-auto p-5"
            style={{
              backgroundImage: `
                linear-gradient(rgba(30,58,138,0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(30,58,138,0.05) 1px, transparent 1px)
              `,
              backgroundSize: "32px 32px",
            }}
          >
            {WidgetComponent ? (
              <WidgetComponent symbol={activeSymbol} />
            ) : (
              <div className="flex items-center justify-center h-full text-blue-400/20 text-sm">
                Select a tool from the sidebar
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
