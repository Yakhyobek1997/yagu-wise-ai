"use client";
import type { ReactNode } from "react";
import { Upload, Globe, FolderSync, Cloud, Mic, CheckCircle2 } from "lucide-react";

type Status = "available" | "planned";

interface SourceTile {
  id: string;
  label: string;
  desc: string;
  icon: ReactNode;
  status: Status;
}

const TILES: SourceTile[] = [
  { id: "upload", label: "Upload files", desc: "PDF · DOCX · HTML · MD · TXT · audio", icon: <Upload className="h-4 w-4" />, status: "available" },
  { id: "voice", label: "Voice note", desc: "WAV · MP3 · M4A — transcribed + diarized", icon: <Mic className="h-4 w-4" />, status: "available" },
  { id: "folder", label: "Watch folder", desc: "Auto-reindex a local directory", icon: <FolderSync className="h-4 w-4" />, status: "available" },
  { id: "url", label: "Web URL", desc: "Scrape + index a page", icon: <Globe className="h-4 w-4" />, status: "planned" },
  { id: "cloud", label: "Cloud connectors", desc: "Drive · Slack · Notion", icon: <Cloud className="h-4 w-4" />, status: "planned" },
];

/**
 * Ingest source tile-grid (Onyx pattern, adapted honestly to a local-first RAG):
 * available sources are actionable; not-yet-built ones are shown as disabled
 * "Planned" tiles — the same available/planned discipline the RAG strategy
 * selector uses — rather than faking connectors that don't exist.
 */
export function IngestSources({ onUpload }: { onUpload: () => void }) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-fg">Add a source</h3>
        <span className="text-[10px] text-fg3">3 available · 2 planned</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {TILES.map((t) => {
          const available = t.status === "available";
          const Tag = available ? "button" : "div";
          // The folder tile jumps to the Watch Folder manager below; others open upload.
          const onClick =
            t.id === "folder"
              ? () =>
                  document
                    .getElementById("watch-panel")
                    ?.scrollIntoView({ behavior: "smooth", block: "start" })
              : onUpload;
          return (
            <Tag
              key={t.id}
              {...(available ? { type: "button" as const, onClick } : { "aria-disabled": true })}
              className={`flex flex-col gap-1 rounded-xl border p-2.5 text-left transition ${
                available
                  ? "border-edge bg-panel2 hover:border-brand/50 hover:bg-panel"
                  : "cursor-not-allowed border-edge/60 bg-panel2/40 opacity-60"
              }`}
            >
              <span className="flex items-center justify-between">
                <span className={available ? "text-brand" : "text-fg3"}>{t.icon}</span>
                {available ? (
                  <span className="inline-flex items-center gap-1 text-[10px] font-medium text-ok">
                    <CheckCircle2 className="h-3 w-3" aria-hidden /> Available
                  </span>
                ) : (
                  <span className="text-[10px] font-medium text-fg3">Planned</span>
                )}
              </span>
              <span className="text-xs font-medium text-fg">{t.label}</span>
              <span className="text-[10px] leading-snug text-fg3">{t.desc}</span>
            </Tag>
          );
        })}
      </div>
    </div>
  );
}
