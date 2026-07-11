"use client";
import { useEffect, useState } from "react";
import type { DeploymentMode } from "@/lib/api";

const DISMISS_KEY = "auralynq.demoBanner.dismissed.v1";

/**
 * A compact, dismissible banner that tells a public/demo visitor what kind of
 * deployment they're looking at: demo mode, a Hugging Face Space with ephemeral
 * storage, uploads disabled, and/or the offline $0 fallback providers. Renders
 * nothing when none of those apply (a fully-configured local/private run), so
 * it's invisible for the normal self-hosted case.
 *
 * Presentational: it takes an already-derived DeploymentMode (see
 * deploymentMode() in lib/api.ts) so it's trivial to reason about and the
 * detection logic stays unit-testable without a DOM.
 */
export function DemoBanner({ mode }: { mode: DeploymentMode | null }) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    try {
      setDismissed(sessionStorage.getItem(DISMISS_KEY) === "1");
    } catch {
      /* private mode — just show it */
    }
  }, []);

  if (!mode) return null;
  const show =
    mode.demo || mode.publicDemo || mode.hfSpace || mode.uploadsDisabled || mode.offlineFallback;
  if (!show || dismissed) return null;

  const parts: string[] = [];
  if (mode.demo || mode.publicDemo) parts.push("Running in demo mode");
  if (mode.offlineFallback)
    parts.push(`offline fallback (${mode.offlineProviders.join(" + ")}) — answers verify the pipeline, not model quality`);
  if (mode.uploadsDisabled) parts.push("document uploads are disabled");
  if (mode.hfSpace) parts.push("on a Hugging Face Space — storage is ephemeral and resets on restart");

  const dismiss = () => {
    setDismissed(true);
    try {
      sessionStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* ignore */
    }
  };

  return (
    <div
      role="status"
      aria-label="Deployment mode notice"
      className="flex items-start gap-2 border-b border-warn/30 bg-warn/[0.06] px-4 py-2 text-xs text-fg2"
    >
      <span aria-hidden className="mt-0.5 shrink-0 text-warn">
        ◐
      </span>
      <p className="min-w-0 flex-1 leading-relaxed">
        {parts.map((p, i) => (
          <span key={i}>
            {i > 0 && <span className="text-fg3"> · </span>}
            <span className={i === 0 ? "font-medium text-fg" : ""}>{p}</span>
          </span>
        ))}
        {(mode.hfSpace || mode.demo) && (
          <>
            {" "}
            <a
              href="https://github.com/MHHamdan/Auralynq/blob/main/docs/getting-started/huggingface-space.md"
              target="_blank"
              rel="noreferrer"
              className="underline decoration-dotted hover:text-brand"
            >
              What&apos;s this?
            </a>
          </>
        )}
      </p>
      <button
        onClick={dismiss}
        aria-label="Dismiss deployment notice"
        className="shrink-0 rounded px-1.5 text-fg3 hover:text-fg focus-visible:outline focus-visible:outline-1 focus-visible:outline-ring"
      >
        ✕
      </button>
    </div>
  );
}
