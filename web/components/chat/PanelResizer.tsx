"use client";
import { useCallback, useRef } from "react";
import { INSPECTOR_OVERRIDE_KEY as KEY, applySettings, loadSettings } from "./SettingsPanel";

const MIN_PX = 300;
const MAX_VW = 0.72; // inspector may take up to 72% of the viewport

/**
 * Draggable divider between the chat column and the inspector. Drag left to grow
 * the inspector (right side), drag right to grow the chat (left side) — the chat
 * is `1fr`, so one handle flexes both. Writes `--inspector-width` live (the grid
 * template reads it) and persists it. Double-click resets to the default.
 */
export function PanelResizer() {
  const dragging = useRef(false);

  const apply = (px: number): number => {
    const max = Math.round(window.innerWidth * MAX_VW);
    const w = Math.max(MIN_PX, Math.min(max, Math.round(px)));
    document.documentElement.style.setProperty("--inspector-width", `${w}px`);
    return w;
  };

  // Note: the persisted override is restored on load by `applySettings`
  // (SettingsPanel owns `--inspector-width`), so no restore effect is needed here.

  const onDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  const onMove = useCallback((e: React.PointerEvent) => {
    if (!dragging.current) return;
    apply(window.innerWidth - e.clientX); // inspector hugs the right edge
  }, []);

  const onUp = useCallback((e: React.PointerEvent) => {
    if (!dragging.current) return;
    dragging.current = false;
    (e.target as HTMLElement).releasePointerCapture?.(e.pointerId);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    const cur = parseInt(
      getComputedStyle(document.documentElement).getPropertyValue("--inspector-width"),
      10,
    );
    try {
      if (cur > 0) localStorage.setItem(KEY, String(cur));
    } catch {}
  }, []);

  const reset = useCallback(() => {
    try {
      localStorage.removeItem(KEY);
    } catch {}
    // Drop the manual override and fall back to the chosen size preset.
    applySettings(loadSettings());
  }, []);

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize inspector — drag, or double-click to reset"
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onDoubleClick={reset}
      title="Drag to resize · double-click to reset"
      className="group relative hidden w-1.5 shrink-0 cursor-col-resize touch-none select-none lg:block"
    >
      {/* visible hairline that thickens/tints on hover+drag */}
      <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-edge transition-colors group-hover:bg-brand group-active:bg-brand" />
      {/* wider invisible hit area */}
      <span className="absolute inset-y-0 -left-1 -right-1" />
    </div>
  );
}
