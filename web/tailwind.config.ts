import type { Config } from "tailwindcss";
import tailwindcssAnimate from "tailwindcss-animate";

/* Surface + text + status tokens are theme-driven CSS variables (see
   app/globals.css :root / [data-theme]). Everything is an `R G B` triplet so
   Tailwind's `/<alpha-value>` opacity modifier works on every token. Brand
   identity colors stay fixed across themes. */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // surfaces
        ink: "rgb(var(--c-ink) / <alpha-value>)",
        ink2: "rgb(var(--c-ink-2) / <alpha-value>)",
        panel: "rgb(var(--c-panel) / <alpha-value>)",
        panel2: "rgb(var(--c-panel-2) / <alpha-value>)",
        edge: "rgb(var(--c-edge) / <alpha-value>)",
        edge2: "rgb(var(--c-edge-strong) / <alpha-value>)",
        // text scale (token-driven, contrast-checked per theme)
        fg: "rgb(var(--c-text) / <alpha-value>)",
        fg2: "rgb(var(--c-text-2) / <alpha-value>)",
        fg3: "rgb(var(--c-text-3) / <alpha-value>)",
        muted: "rgb(var(--c-muted) / <alpha-value>)",
        // semantic status (dot/bar colors)
        ok: "rgb(var(--c-ok) / <alpha-value>)",
        warn: "rgb(var(--c-warn) / <alpha-value>)",
        bad: "rgb(var(--c-bad) / <alpha-value>)",
        info: "rgb(var(--c-info) / <alpha-value>)",
        // brand identity (fixed)
        brand: "#5eead4", // teal
        brand2: "#a5b4fc", // indigo
        accent: "#c084fc", // violet
        accent2: "#f472b6", // pink
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      fontSize: {
        // tightened display scale for confident hero hierarchy
        display: ["clamp(2.75rem, 6vw, 4.5rem)", { lineHeight: "1.04", letterSpacing: "-0.025em" }],
        overline: ["0.72rem", { lineHeight: "1", letterSpacing: "0.14em" }],
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        DEFAULT: "var(--shadow-md)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        glow: "var(--shadow-glow)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        float: {
          "0%,100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-12px)" },
        },
        "orb-drift": {
          "0%,100%": { transform: "translate(0,0) scale(1)" },
          "50%": { transform: "translate(20px,-20px) scale(1.08)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        "pulse-soft": {
          "0%,100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.9)", opacity: "0.7" },
          "70%,100%": { transform: "scale(1.6)", opacity: "0" },
        },
        "dash-flow": {
          to: { strokeDashoffset: "-16" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.6s ease-out both",
        float: "float 6s ease-in-out infinite",
        "orb-drift": "orb-drift 14s ease-in-out infinite",
        shimmer: "shimmer 6s linear infinite",
        "pulse-soft": "pulse-soft 2.4s ease-in-out infinite",
        "pulse-ring": "pulse-ring 1.6s ease-out infinite",
        "dash-flow": "dash-flow 0.9s linear infinite",
      },
    },
  },
  plugins: [tailwindcssAnimate],
};
export default config;
