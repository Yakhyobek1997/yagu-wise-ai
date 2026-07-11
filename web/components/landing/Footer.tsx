import Link from "next/link";

const REPO = "https://github.com/MHHamdan/Auralynq";

export function Footer() {
  return (
    <footer className="border-t border-edge">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 text-sm text-fg2 md:flex-row md:px-6">
        <div className="flex items-center gap-2 font-semibold text-fg">
          <span aria-hidden>🎙️</span>
          <span>
            <span className="text-brand">Aura</span>
            <span className="text-brand2">lynq</span>
          </span>
          <span className="ml-2 font-normal text-fg3">Talk to Your Data</span>
        </div>
        <div className="flex items-center gap-6">
          <Link href="/chat" className="transition hover:text-fg">
            Launch app
          </Link>
          <a href="#features" className="transition hover:text-fg">
            Features
          </a>
          <a href={REPO} target="_blank" rel="noopener noreferrer" className="transition hover:text-fg">
            GitHub
          </a>
        </div>
        <div className="text-xs text-fg3">Local-first · $0 default · Open source</div>
      </div>
    </footer>
  );
}
