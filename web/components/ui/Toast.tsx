"use client";
import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

/**
 * Dismissible toast. Auto-dismisses after `duration` ms, but pauses the timer
 * while hovered and offers a manual close — so a user can actually read (or
 * re-read) it instead of racing a 2.2s timeout. Re-arms whenever `message`
 * changes (keyed by the caller).
 */
export function Toast({
  message,
  onClose,
  duration = 3500,
}: {
  message: string;
  onClose: () => void;
  duration?: number;
}) {
  const [paused, setPaused] = useState(false);
  const startedAt = useRef(Date.now());
  const remaining = useRef(duration);

  useEffect(() => {
    if (paused) return;
    startedAt.current = Date.now();
    const id = setTimeout(onClose, remaining.current);
    return () => {
      clearTimeout(id);
      remaining.current -= Date.now() - startedAt.current;
    };
  }, [paused, onClose]);

  return (
    <div
      role="status"
      aria-live="polite"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className="fixed bottom-24 left-1/2 z-[120] flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-3 rounded-xl border border-edge bg-panel px-4 py-2.5 text-sm text-fg shadow-lg data-[state=open]:animate-in fade-in-0 slide-in-from-bottom-2"
      data-state="open"
    >
      <span className="min-w-0">{message}</span>
      <button
        type="button"
        onClick={onClose}
        aria-label="Dismiss"
        className="-mr-1 shrink-0 rounded-md p-1 text-fg3 transition hover:bg-panel2 hover:text-fg"
      >
        <X className="h-3.5 w-3.5" aria-hidden />
      </button>
    </div>
  );
}
