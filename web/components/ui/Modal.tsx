"use client";
import type { ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

const SIZE: Record<string, string> = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

/**
 * Token-skinned dialog built on Radix — gives focus-trap, Escape, scroll-lock,
 * `aria-modal`, and focus restoration for free, so the app stops hand-rolling
 * these per modal. Visual layer stays 100% ours (tokens + tailwindcss-animate).
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  size = "md",
  children,
  footer,
  closeOnOutside = true,
  dismissable = true,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  size?: keyof typeof SIZE;
  children: ReactNode;
  footer?: ReactNode;
  /** allow closing by clicking the backdrop */
  closeOnOutside?: boolean;
  /** allow Escape / close button (set false while a blocking op runs) */
  dismissable?: boolean;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && dismissable && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[100] bg-ink/80 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0" />
        <Dialog.Content
          onInteractOutside={(e) => (!closeOnOutside || !dismissable) && e.preventDefault()}
          onEscapeKeyDown={(e) => !dismissable && e.preventDefault()}
          className={`fixed left-1/2 top-1/2 z-[101] w-[calc(100vw-2rem)] ${SIZE[size]} -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-2xl border border-edge bg-panel shadow-lg data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:fade-in-0 data-[state=closed]:fade-out-0 data-[state=open]:zoom-in-95 data-[state=closed]:zoom-out-95`}
        >
          <div className="flex items-start justify-between gap-3 border-b border-edge px-5 py-4">
            <div className="min-w-0">
              <Dialog.Title className="text-base font-semibold text-fg">{title}</Dialog.Title>
              {description && (
                <Dialog.Description className="mt-0.5 text-xs text-fg3">
                  {description}
                </Dialog.Description>
              )}
            </div>
            {dismissable && (
              <Dialog.Close
                className="btn-ghost -mr-1 shrink-0 px-2 py-1"
                aria-label="Close"
              >
                <X className="h-4 w-4" aria-hidden />
              </Dialog.Close>
            )}
          </div>

          <div className="max-h-[72vh] overflow-y-auto scroll-thin p-5">{children}</div>

          {footer && (
            <div className="flex justify-end gap-3 border-t border-edge px-5 py-4">{footer}</div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
