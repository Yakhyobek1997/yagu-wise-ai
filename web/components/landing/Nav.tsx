"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";

const REPO = "https://github.com/MHHamdan/Auralynq";

const LINKS = [
  { href: "#features", label: "Features" },
  { href: "#how", label: "How it works" },
  { href: "#why", label: "Why" },
  { href: "#stack", label: "Architecture" },
  { href: REPO, label: "GitHub", external: true },
];

export function Nav() {
  const [open, setOpen] = useState(false);

  // Close the mobile menu on Escape and lock body scroll while open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className="sticky top-0 z-50 border-b border-edge bg-ink/80 backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 md:px-6">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold tracking-tight text-fg">
          <span aria-hidden>🎙️</span>
          <span>
            <span className="text-brand">Aura</span>
            <span className="text-brand2">lynq</span>
          </span>
        </Link>

        <div className="hidden items-center gap-7 text-sm font-medium text-fg2 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              target={l.external ? "_blank" : undefined}
              rel={l.external ? "noopener noreferrer" : undefined}
              className="transition hover:text-fg"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle compact />
          <Link href="/chat" className="btn-cta hidden text-sm sm:inline-flex">
            Launch app →
          </Link>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            className="btn-ghost px-2.5 py-2 md:hidden"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5" aria-hidden>
              {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </div>
      </nav>

      {/* Mobile disclosure menu */}
      {open && (
        <div className="border-t border-edge bg-ink/95 backdrop-blur-xl md:hidden">
          <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-3">
            {LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                target={l.external ? "_blank" : undefined}
                rel={l.external ? "noopener noreferrer" : undefined}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2.5 text-sm font-medium text-fg2 transition hover:bg-panel2 hover:text-fg"
              >
                {l.label}
              </a>
            ))}
            <Link
              href="/chat"
              onClick={() => setOpen(false)}
              className="btn-cta mt-2 justify-center text-sm"
            >
              Launch app →
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
