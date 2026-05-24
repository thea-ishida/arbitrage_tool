import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#060D18",
          900: "#0B192C",
          850: "#0E2038",
          800: "#122540",
          750: "#162D4E",
          700: "#1A3360",
          600: "#1E3A8A",   // matches #1E3A8A requirement exactly
        },
      },
      backgroundImage: {
        "grid-navy": `
          linear-gradient(rgba(30,58,138,0.07) 1px, transparent 1px),
          linear-gradient(90deg, rgba(30,58,138,0.07) 1px, transparent 1px)
        `,
      },
      backgroundSize: {
        "grid-sm": "32px 32px",
      },
      boxShadow: {
        "glow-blue":  "0 0 20px -4px rgba(59,130,246,0.35)",
        "glow-green": "0 0 20px -4px rgba(16,185,129,0.35)",
        "glow-red":   "0 0 20px -4px rgba(239,68,68,0.35)",
        "card":       "0 4px 24px rgba(6,13,24,0.6), inset 0 1px 0 rgba(30,58,138,0.2)",
      },
      animation: {
        "flash-green": "flash-green 0.4s ease-out",
        "flash-red":   "flash-red 0.4s ease-out",
        "pulse-dot":   "pulse-dot 2s cubic-bezier(0.4,0,0.6,1) infinite",
      },
      keyframes: {
        "flash-green": {
          "0%":   { backgroundColor: "rgba(16,185,129,0.25)" },
          "100%": { backgroundColor: "transparent" },
        },
        "flash-red": {
          "0%":   { backgroundColor: "rgba(239,68,68,0.25)" },
          "100%": { backgroundColor: "transparent" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0.3" },
        },
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
