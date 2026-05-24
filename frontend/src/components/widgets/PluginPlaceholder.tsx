"use client";

import type { WidgetProps } from "@/types";

export function PluginPlaceholder(_props: WidgetProps) {
  return (
    <div
      className="card-glass rounded-xl h-full flex flex-col items-center justify-center gap-5 text-center p-8"
      style={{ minHeight: 300 }}
    >
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center"
        style={{
          background: "rgba(30,58,138,0.3)",
          border:     "1px dashed rgba(59,130,246,0.3)",
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth={1.5} className="w-6 h-6">
          <path d="M12 5v14M5 12h14" strokeLinecap="round"/>
        </svg>
      </div>
      <div>
        <p className="text-blue-200 font-semibold text-sm">New Analytical Module</p>
        <p className="text-blue-400/40 text-xs mt-2 max-w-xs leading-relaxed">
          Add an entry to{" "}
          <code
            className="px-1 py-0.5 rounded text-blue-300"
            style={{ background: "rgba(30,58,138,0.4)" }}
          >
            widgets/registry.ts
          </code>
          {" "}to register a new tool here. No layout code required.
        </p>
      </div>
    </div>
  );
}
