"use client";
import { useEffect, useState } from "react";

export interface UISettings {
  fontSize: "small" | "default" | "large" | "xl";
  density: "compact" | "comfortable" | "spacious";
  inspectorSize: "compact" | "standard" | "wide";
  traceVisibility: "always" | "auto" | "tab";
  newChatMode: "chat_only" | "new_workspace" | "clear_corpus";
}

export const DEFAULT_SETTINGS: UISettings = {
  fontSize: "large",
  density: "comfortable",
  inspectorSize: "standard",
  traceVisibility: "always",
  newChatMode: "chat_only",
};

const LS_KEY = "auralynq.ui_settings.v1";

export function loadSettings(): UISettings {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    /* ignore */
  }
  return DEFAULT_SETTINGS;
}

export function saveSettings(s: UISettings) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

const FONT_SCALE: Record<UISettings["fontSize"], string> = {
  small: "0.85",
  default: "1",
  large: "1.1",
  xl: "1.2",
};

const DENSITY_SCALE: Record<UISettings["density"], string> = {
  compact: "0.85",
  comfortable: "1",
  spacious: "1.15",
};

const INSPECTOR_WIDTH: Record<UISettings["inspectorSize"], string> = {
  compact: "clamp(280px,24vw,380px)",
  standard: "clamp(360px,30vw,560px)",
  wide: "clamp(420px,36vw,680px)",
};

// A free drag on the panel divider (PanelResizer) writes a pixel override here.
// It wins over the size preset until the user picks a preset or resets the divider.
export const INSPECTOR_OVERRIDE_KEY = "auralynq.inspectorWidth";

export function applySettings(s: UISettings) {
  const root = document.documentElement;
  root.style.setProperty("--font-scale", FONT_SCALE[s.fontSize]);
  root.style.setProperty("--density-scale", DENSITY_SCALE[s.density]);
  // Respect a manual drag override if present, else fall back to the preset.
  let override = 0;
  try {
    override = Number(localStorage.getItem(INSPECTOR_OVERRIDE_KEY));
  } catch {
    /* ignore */
  }
  root.style.setProperty(
    "--inspector-width",
    override > 0 ? `${override}px` : INSPECTOR_WIDTH[s.inspectorSize],
  );
}

function OptionGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { id: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold text-fg2">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => (
          <button
            key={o.id}
            type="button"
            onClick={() => onChange(o.id)}
            className={`rounded-full border px-3 py-1 text-xs transition ${
              value === o.id
                ? "border-brand/50 bg-brand/15 text-brand"
                : "border-edge bg-panel2 text-fg3 hover:text-fg"
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SettingsPanel({
  settings,
  onChange,
  onClose,
}: {
  settings: UISettings;
  onChange: (s: UISettings) => void;
  onClose: () => void;
}) {
  function update<K extends keyof UISettings>(key: K, value: UISettings[K]) {
    const next = { ...settings, [key]: value };
    // Picking a size preset discards any manual divider-drag override.
    if (key === "inspectorSize") {
      try {
        localStorage.removeItem(INSPECTOR_OVERRIDE_KEY);
      } catch {
        /* ignore */
      }
    }
    onChange(next);
    saveSettings(next);
    applySettings(next);
  }

  return (
    <div className="space-y-4 p-1">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-fg">Display Settings</h3>
        <button onClick={onClose} className="btn-ghost text-xs px-2 py-1" aria-label="Close settings">
          ✕
        </button>
      </div>

      <OptionGroup
        label="Font Size"
        value={settings.fontSize}
        onChange={(v) => update("fontSize", v)}
        options={[
          { id: "small", label: "Small" },
          { id: "default", label: "Default" },
          { id: "large", label: "Large" },
          { id: "xl", label: "Extra large" },
        ]}
      />

      <OptionGroup
        label="Density"
        value={settings.density}
        onChange={(v) => update("density", v)}
        options={[
          { id: "compact", label: "Compact" },
          { id: "comfortable", label: "Comfortable" },
          { id: "spacious", label: "Spacious" },
        ]}
      />

      <OptionGroup
        label="Inspector Width"
        value={settings.inspectorSize}
        onChange={(v) => update("inspectorSize", v)}
        options={[
          { id: "compact", label: "Compact" },
          { id: "standard", label: "Standard" },
          { id: "wide", label: "Wide" },
        ]}
      />

      <OptionGroup
        label="Trace Visibility"
        value={settings.traceVisibility}
        onChange={(v) => update("traceVisibility", v)}
        options={[
          { id: "always", label: "Always visible" },
          { id: "auto", label: "Auto" },
          { id: "tab", label: "Tab only" },
        ]}
      />

      <div className="space-y-1.5">
        <p className="text-xs font-semibold text-fg2">New Chat Behavior</p>
        <div className="flex flex-col gap-1.5">
          {[
            { id: "chat_only" as const, label: "Clear chat only", hint: "Corpus stays indexed" },
            { id: "new_workspace" as const, label: "New workspace", hint: "Prompts about corpus" },
            { id: "clear_corpus" as const, label: "Clear corpus + chat", hint: "Requires confirmation" },
          ].map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => update("newChatMode", o.id)}
              className={`flex items-center justify-between rounded-lg border px-3 py-2 text-left text-xs transition ${
                settings.newChatMode === o.id
                  ? "border-brand/50 bg-brand/10 text-brand"
                  : "border-edge bg-panel2 text-fg3 hover:text-fg"
              }`}
            >
              <span>{o.label}</span>
              <span className="text-fg3">{o.hint}</span>
            </button>
          ))}
        </div>
      </div>

      <p className="text-[10px] text-fg3">Settings are saved to your browser.</p>
    </div>
  );
}

export function useUISettings() {
  const [settings, setSettings] = useState<UISettings>(DEFAULT_SETTINGS);

  useEffect(() => {
    const s = loadSettings();
    setSettings(s);
    applySettings(s);
  }, []);

  function update(next: UISettings) {
    setSettings(next);
    saveSettings(next);
    applySettings(next);
  }

  return { settings, update };
}
