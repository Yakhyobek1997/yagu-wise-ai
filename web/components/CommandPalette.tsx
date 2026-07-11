"use client";
import { useEffect } from "react";
import { Command } from "cmdk";
import type { LucideIcon } from "lucide-react";

export interface Cmd {
  id: string;
  label: string;
  hint?: string;
  group: string;
  icon?: LucideIcon;
  keywords?: string[];
  run: () => void;
}

/**
 * Token-styled command palette (cmdk). Cmd/Ctrl-K opens it; type to filter,
 * Enter to run. No competitor in the teardown ships one — a fast keyboard
 * surface across our multi-tab workspace. cmdk uses Radix Dialog underneath, so
 * focus-trap / Escape / scroll-lock come for free.
 */
export function CommandPalette({
  open,
  onClose,
  commands,
}: {
  open: boolean;
  onClose: () => void;
  commands: Cmd[];
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const groups = Array.from(new Set(commands.map((c) => c.group)));

  return (
    <Command.Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      label="Command palette"
      className="fixed left-1/2 top-[18%] z-[130] w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-2xl border border-edge bg-panel shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
      overlayClassName="fixed inset-0 z-[129] bg-ink/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0"
    >
      <Command.Input
        placeholder="Type a command or search…"
        className="w-full border-b border-edge bg-transparent px-4 py-3.5 text-sm text-fg placeholder:text-fg3 focus:outline-none"
      />
      <Command.List className="max-h-[min(60vh,380px)] overflow-y-auto scroll-thin p-2">
        <Command.Empty className="px-3 py-6 text-center text-sm text-fg3">
          No matching commands.
        </Command.Empty>
        {groups.map((g) => (
          <Command.Group
            key={g}
            heading={g}
            className="px-1 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-fg3 [&_[cmdk-group-items]]:mt-1 [&_[cmdk-group-items]]:space-y-0.5"
          >
            {commands
              .filter((c) => c.group === g)
              .map((c) => {
                const Icon = c.icon;
                return (
                  <Command.Item
                    key={c.id}
                    value={`${c.label} ${c.keywords?.join(" ") ?? ""}`}
                    onSelect={() => {
                      c.run();
                      onClose();
                    }}
                    className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-fg2 data-[selected=true]:bg-panel2 data-[selected=true]:text-fg"
                  >
                    {Icon && <Icon className="h-4 w-4 shrink-0 text-fg3" aria-hidden />}
                    <span className="flex-1 truncate">{c.label}</span>
                    {c.hint && <span className="shrink-0 font-mono text-[10px] text-fg3">{c.hint}</span>}
                  </Command.Item>
                );
              })}
          </Command.Group>
        ))}
      </Command.List>
    </Command.Dialog>
  );
}
