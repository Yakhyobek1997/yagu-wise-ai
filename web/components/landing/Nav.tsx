"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Menu, Mic2, X } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";

const REPO = "https://github.com/MHHamdan/YaguWiseAi";

const LINKS = [
  { href: "#features", label: "Features" },
  { href: "#how", label: "How it works" },
  { href: "#why", label: "Why" },
  { href: "#stack", label: "Architecture" },
  { href: REPO, label: "GitHub", external: true },
];

export function Nav() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className="sticky top-0 z-50 border-b border-edge bg-ink/85 backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-[1536px] items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-2.5 text-lg font-bold tracking-tight text-fg">
          <span className="grid h-8 w-8 place-items-center rounded-lg border border-edge bg-panel text-brand shadow-sm">
            <Mic2 className="h-4 w-4" aria-hidden />
          </span>
          <span>
            <span className="text-brand">Yagu</span>
            <span className="text-brand2">Wise AI</span>
          </span>
        </Link>

        <div className="hidden items-center gap-7 text-sm font-medium text-fg2 md:flex">
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              target={link.external ? "_blank" : undefined}
              rel={link.external ? "noopener noreferrer" : undefined}
              className="transition hover:text-fg"
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <ThemeToggle compact />
          <Link href="/chat" className="btn-cta hidden text-sm sm:inline-flex">
            Launch app <ArrowRight className="h-4 w-4" />
          </Link>
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            className="btn-ghost px-2.5 py-2 md:hidden"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </nav>

      {open && (
        <div className="border-t border-edge bg-ink/95 backdrop-blur-xl md:hidden">
          <div className="mx-auto flex max-w-[1536px] flex-col gap-1 px-4 py-3 sm:px-6">
            {LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                target={link.external ? "_blank" : undefined}
                rel={link.external ? "noopener noreferrer" : undefined}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2.5 text-sm font-medium text-fg2 transition hover:bg-panel2 hover:text-fg"
              >
                {link.label}
              </a>
            ))}
            <Link href="/chat" onClick={() => setOpen(false)} className="btn-cta mt-2 justify-center text-sm">
              Launch app <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
