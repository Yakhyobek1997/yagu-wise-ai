"use client";
import { useEffect, useState } from "react";
import {
  THEME_KEY,
  THEME_META as META,
  THEME_ORDER as ORDER,
  type Theme,
  coerceTheme,
  nextTheme,
} from "@/lib/theme";

export type { Theme };

export function applyTheme(t: Theme) {
  document.documentElement.dataset.theme = t;
  try {
    localStorage.setItem(THEME_KEY, t);
  } catch {
    /* private mode — non-fatal */
  }
}

/** Inline, runs before paint to avoid a theme flash. Injected in <head>. */
export const themeBootScript = `(function(){try{var t=localStorage.getItem(${JSON.stringify(
  THEME_KEY,
)})||'dark';document.documentElement.dataset.theme=t;}catch(e){document.documentElement.dataset.theme='dark';}})();`;

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    setTheme(coerceTheme(document.documentElement.dataset.theme));
  }, []);

  function pick(t: Theme) {
    setTheme(t);
    applyTheme(t);
  }

  if (compact) {
    // Cycle button for tight headers.
    const next = nextTheme(theme);
    return (
      <button
        onClick={() => pick(next)}
        className="btn-ghost text-sm"
        aria-label={`Theme: ${META[theme].label}. Switch to ${META[next].label}`}
        title={`Theme: ${META[theme].label} — click for ${META[next].label}`}
      >
        <span aria-hidden>{META[theme].icon}</span>
        <span className="ml-1 hidden sm:inline">{META[theme].label}</span>
      </button>
    );
  }

  return (
    <div
      role="radiogroup"
      aria-label="Color theme"
      className="inline-flex items-center gap-0.5 rounded-xl border border-edge bg-panel/60 p-0.5"
    >
      {ORDER.map((t) => (
        <button
          key={t}
          role="radio"
          aria-checked={theme === t}
          onClick={() => pick(t)}
          title={META[t].label}
          className={`rounded-lg px-2.5 py-1 text-sm transition ${
            theme === t ? "bg-brand text-[#06231e]" : "hover:bg-edge/40"
          }`}
        >
          <span aria-hidden>{META[t].icon}</span>
          <span className="ml-1 hidden md:inline">{META[t].label}</span>
        </button>
      ))}
    </div>
  );
}
