"use client";
import { useCallback, useEffect, useState } from "react";
import { FolderSync, RefreshCw, FileText, CheckCircle2, AlertTriangle } from "lucide-react";
import { watchStatus, watchSync, type WatchStatus, type WatchSyncResult } from "@/lib/api";

/**
 * Watch Folder inspector: shows the auto-reindexed local directories, their file
 * counts, and a "Sync now" trigger. Adds/edits/deletes in a watched folder are
 * reflected in the index automatically by the worker; this surfaces + forces it.
 */
export function WatchPanel({ onSynced }: { onSynced?: () => void }) {
  const [status, setStatus] = useState<WatchStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [last, setLast] = useState<WatchSyncResult | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    watchStatus()
      .then(setStatus)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const sync = () => {
    setSyncing(true);
    watchSync()
      .then((r) => {
        setLast(r);
        if (r.added || r.updated || r.removed) onSynced?.();
      })
      .catch(() => {})
      .finally(() => {
        setSyncing(false);
        load();
      });
  };

  return (
    <div id="watch-panel" className="space-y-2 scroll-mt-4">
      <div className="flex items-center justify-between">
        <h3 className="inline-flex items-center gap-1.5 text-sm font-semibold text-fg">
          <FolderSync className="h-4 w-4 text-brand" aria-hidden /> Watch Folder
          {status?.enabled && status.tracked > 0 && (
            <span className="font-mono text-xs text-fg3">{status.tracked}</span>
          )}
        </h3>
        <button
          type="button"
          onClick={load}
          aria-label="Refresh watch status"
          className="text-fg3 transition hover:text-fg"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} aria-hidden />
        </button>
      </div>

      {!status?.enabled ? (
        <div className="card-inset text-xs text-fg3">
          Auto-reindex is off. Enable it with{" "}
          <code className="rounded bg-ink/60 px-1 py-0.5 font-mono text-fg2">AURALYNQ_WATCH__ENABLED=true</code>{" "}
          — then drop files into a watched folder and Auralynq keeps the index in sync automatically
          (adds, edits and deletes).
        </div>
      ) : (
        <>
          <ul className="space-y-1">
            {status.directories.map((d) => (
              <li
                key={d.path}
                className="flex items-center gap-2 rounded-lg border border-edge bg-panel2 px-2.5 py-1.5"
              >
                <FileText className="h-3.5 w-3.5 shrink-0 text-fg3" aria-hidden />
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-fg" title={d.path}>
                  {d.path}
                </span>
                {d.exists ? (
                  <span className="shrink-0 font-mono text-[10px] text-fg3">{d.files} file{d.files === 1 ? "" : "s"}</span>
                ) : (
                  <span className="shrink-0 text-[10px] text-warn">missing</span>
                )}
              </li>
            ))}
          </ul>

          <div className="flex items-center gap-2 text-[10px] text-fg3">
            <span className="tag">every {status.poll_seconds}s</span>
            {status.recursive && <span className="tag">recursive</span>}
            {status.delete_missing && <span className="tag">prunes deletes</span>}
          </div>

          <button
            type="button"
            onClick={sync}
            disabled={syncing}
            className="btn-outline inline-flex w-full items-center justify-center gap-1.5 text-xs disabled:opacity-60"
          >
            <FolderSync className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} aria-hidden />
            {syncing ? "Syncing…" : "Sync now"}
          </button>

          {last && (
            <div className="card-inset text-xs">
              {last.errors.length > 0 ? (
                <span className="inline-flex items-center gap-1.5 text-warn">
                  <AlertTriangle className="h-3.5 w-3.5" aria-hidden /> {last.errors[0]}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-fg2">
                  <CheckCircle2 className="h-3.5 w-3.5 text-ok" aria-hidden />
                  {last.added + last.updated + last.removed === 0
                    ? "Already up to date"
                    : `+${last.added} added · ${last.updated} updated · ${last.removed} removed`}
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
