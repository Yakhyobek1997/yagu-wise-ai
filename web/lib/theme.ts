// Pure theme helpers — kept framework-free so they're unit-testable in node.
export type Theme = "light" | "dark" | "comfort";

export const THEME_KEY = "auralynq.theme";
export const THEME_ORDER: Theme[] = ["dark", "light", "comfort"];
export const THEME_META: Record<Theme, { icon: string; label: string }> = {
  dark: { icon: "🌙", label: "Dark" },
  light: { icon: "☀️", label: "Light" },
  comfort: { icon: "📖", label: "Comfort" },
};

export function isTheme(v: unknown): v is Theme {
  return v === "light" || v === "dark" || v === "comfort";
}

/** Normalize any stored/garbage value to a valid theme (defaults to dark). */
export function coerceTheme(v: unknown): Theme {
  return isTheme(v) ? v : "dark";
}

/** Next theme in the cycle, wrapping around. */
export function nextTheme(cur: Theme): Theme {
  return THEME_ORDER[(THEME_ORDER.indexOf(cur) + 1) % THEME_ORDER.length];
}
