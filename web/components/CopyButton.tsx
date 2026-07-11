"use client";
import { useState } from "react";

// Small copy-to-clipboard button with transient "Copied" feedback. Takes a
// getter so it works for both message text and (via innerText) code blocks.
export function CopyButton({
  getText,
  className = "",
  label = "Copy",
}: {
  getText: () => string;
  className?: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(getText());
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard blocked (insecure context); silently ignore */
    }
  }
  return (
    <button
      type="button"
      onClick={copy}
      aria-label={copied ? "Copied" : label}
      className={`inline-flex items-center gap-1 text-xs text-slate-400 transition hover:text-brand ${className}`}
    >
      {copied ? "✓ Copied" : `⧉ ${label}`}
    </button>
  );
}
