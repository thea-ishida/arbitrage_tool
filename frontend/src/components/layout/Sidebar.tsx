"use client";

import { WIDGET_REGISTRY } from "@/components/widgets/registry";
import { useAppStore }     from "@/store";
import { clsx }            from "clsx";

// ── Inline SVG icons ──────────────────────────────────────────────────────────

const Icons: Record<string, JSX.Element> = {
  overview: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
      <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
  ),
  "gnn-alpha-chart": (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
      <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.5V12l3 3-3 1v2l-2-1-2 1v-2l-3-1 3-3V9.5A4 4 0 0 1 8 6a4 4 0 0 1 4-4z"/>
      <path d="M3 20h18"/>
    </svg>
  ),
  "order-book-imbalance": (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
      <path d="M3 6h4v12H3zM10 10h4v8h-4zM17 3h4v15h-4z"/>
    </svg>
  ),
  "performance-metrics": (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>
    </svg>
  ),
  "live-ticker": (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
};

const WS_BADGE = {
  connected:    { dot: "bg-emerald-400", label: "Live", ring: "shadow-[0_0_8px_2px_rgba(52,211,153,0.3)]" },
  connecting:   { dot: "bg-amber-400 animate-pulse-dot", label: "Connecting…", ring: "" },
  disconnected: { dot: "bg-rose-500", label: "Offline", ring: "" },
};

export function Sidebar() {
  const {
    activeWidgetId, wsStatus, latencyMs, activeSymbol,
    sidebarCollapsed,
    setActiveWidget, setActiveSymbol, toggleSidebar,
  } = useAppStore();

  const collapsed = sidebarCollapsed;

  return (
    <aside
      className={clsx(
        "flex-shrink-0 flex flex-col border-r transition-all duration-300 ease-in-out",
        "bg-navy-900 border-navy-700",
        collapsed ? "w-[60px]" : "w-[220px]",
      )}
    >
      {/* ── Brand + collapse toggle ── */}
      <div
        className={clsx(
          "flex items-center border-b border-navy-700 h-14 px-3 flex-shrink-0",
          collapsed ? "justify-center" : "justify-between",
        )}
      >
        {!collapsed && (
          <div>
            <p className="text-white font-bold text-xs tracking-[0.12em] uppercase">
              Arbi Calc
            </p>
            <p className="text-blue-400 text-[10px] tracking-wide opacity-70">
              GNN Lead-Lag
            </p>
          </div>
        )}
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded text-navy-600/80 hover:text-blue-400 hover:bg-navy-800 transition-colors"
          aria-label="Toggle sidebar"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
            {collapsed
              ? <path d="M9 18l6-6-6-6"/>
              : <path d="M15 18l-6-6 6-6"/>}
          </svg>
        </button>
      </div>

      {/* ── Symbol selector ── */}
      {!collapsed && (
        <div className="px-3 py-2.5 border-b border-navy-700">
          <p className="text-[10px] text-blue-400/50 uppercase tracking-widest mb-1.5">
            Symbol
          </p>
          <div className="flex gap-1.5">
            {["BTC/USDT", "ETH/USDT"].map((s) => (
              <button
                key={s}
                onClick={() => setActiveSymbol(s)}
                className={clsx(
                  "flex-1 text-[10px] font-mono py-1 rounded transition-all",
                  activeSymbol === s
                    ? "bg-navy-600 text-blue-300 border border-navy-600 shadow-glow-blue"
                    : "bg-navy-800 text-blue-400/50 border border-navy-700 hover:text-blue-300",
                )}
              >
                {s.split("/")[0]}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Navigation ── */}
      <nav className="flex-1 overflow-y-auto py-2">
        {!collapsed && (
          <p className="px-3 pt-1 pb-2 text-[9px] text-blue-400/40 uppercase tracking-[0.2em]">
            Tools
          </p>
        )}
        {WIDGET_REGISTRY.map((widget) => {
          const active = activeWidgetId === widget.id;
          return (
            <button
              key={widget.id}
              onClick={() => setActiveWidget(widget.id)}
              title={collapsed ? widget.label : undefined}
              className={clsx(
                "w-full flex items-center gap-3 transition-all duration-150",
                "border-l-2",
                collapsed ? "justify-center px-0 py-3" : "px-3 py-2.5",
                active
                  ? "bg-navy-700/60 text-blue-300 border-blue-500 shadow-[inset_0_0_12px_rgba(59,130,246,0.08)]"
                  : "text-blue-400/50 border-transparent hover:text-blue-200 hover:bg-navy-800/60",
              )}
            >
              <span className={clsx("flex-shrink-0", active && "text-blue-400")}>
                {Icons[widget.id] ?? Icons["live-ticker"]}
              </span>
              {!collapsed && (
                <span className="text-xs font-medium truncate">{widget.label}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* ── WS status footer ── */}
      <div className={clsx(
        "border-t border-navy-700 flex items-center gap-2 px-3 py-2.5",
        collapsed && "justify-center px-0",
      )}>
        {(() => {
          const b = WS_BADGE[wsStatus];
          return (
            <>
              <span className={clsx("w-2 h-2 rounded-full flex-shrink-0", b.dot, b.ring)} />
              {!collapsed && (
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] text-blue-300/60">{b.label}</p>
                  {latencyMs !== null && wsStatus === "connected" && (
                    <p className="text-[10px] font-mono text-emerald-400/70">{latencyMs}ms</p>
                  )}
                </div>
              )}
            </>
          );
        })()}
      </div>
    </aside>
  );
}
