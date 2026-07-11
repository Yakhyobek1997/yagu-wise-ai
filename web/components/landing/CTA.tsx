import Link from "next/link";

const REPO = "https://github.com/MHHamdan/Auralynq";

export function CTA() {
  return (
    <section className="relative mx-auto max-w-7xl px-4 py-14 md:px-6">
      <div className="glass relative overflow-hidden p-10 text-center md:p-16">
        <div className="orb left-1/2 top-[-4rem] h-72 w-72 -translate-x-1/2 bg-brand2/25" aria-hidden />
        <div className="orb right-10 bottom-[-4rem] h-56 w-56 bg-brand/20" aria-hidden />
        <div className="relative">
          <span className="chip mb-5 border-brand/30">
            <span className="h-1.5 w-1.5 rounded-full bg-brand animate-pulse-soft" />
            Ready in minutes
          </span>
          <h2 className="text-3xl font-bold tracking-tight sm:text-5xl">
            Ready to <span className="gradient-text">talk to your data?</span>
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-lg text-fg2">
            Launch the app and ask your first question — no signup, no bill. Grounded, cited answers
            that run on your machine.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/chat" className="btn-cta">
              Launch Auralynq →
            </Link>
            <a href={REPO} target="_blank" rel="noopener noreferrer" className="btn-outline">
              Read the docs
            </a>
          </div>
          <p className="mt-6 text-sm text-fg3">
            Runs locally with Podman, or a lightweight dev mode — your documents never leave the box.
          </p>
        </div>
      </div>
    </section>
  );
}
