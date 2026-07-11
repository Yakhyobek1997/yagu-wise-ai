"use client";
import { useCallback, useEffect, useState } from "react";
import {
  CorpusClearPreview,
  CorpusDeleteDocumentPreview,
  CorpusDeleteReport,
  DocumentMeta,
  corpusClearConfirm,
  corpusClearPreview,
  corpusDeleteDocumentConfirm,
  corpusDeleteDocumentPreview,
  corpusDeleteLastConfirm,
  corpusDeleteLastPreview,
} from "@/lib/api";
import { displaySource } from "@/lib/format";
import { Modal } from "@/components/ui/Modal";

type ModalStep = "idle" | "previewing" | "confirming" | "done" | "error";
type DeleteAction = "clear_all" | "delete_last" | "delete_doc";

interface Props {
  onClose: () => void;
  onDeleted: () => void;
  initialAction?: DeleteAction;
}

export function CorpusManageModal({ onClose, onDeleted, initialAction }: Props) {
  const [step, setStep] = useState<ModalStep>("idle");
  const [action, setAction] = useState<DeleteAction>(initialAction ?? "clear_all");
  const [clearPreview, setClearPreview] = useState<CorpusClearPreview | null>(null);
  const [docPreview, setDocPreview] = useState<CorpusDeleteDocumentPreview | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<DocumentMeta | null>(null);
  const [phrase, setPhrase] = useState("");
  const [report, setReport] = useState<CorpusDeleteReport | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const startPreview = useCallback(async (act: DeleteAction, doc?: DocumentMeta) => {
    setAction(act);
    setStep("previewing");
    setBusy(true);
    setPhrase("");
    setErrorMsg("");
    try {
      if (act === "clear_all") {
        const prev = await corpusClearPreview();
        setClearPreview(prev);
      } else if (act === "delete_last") {
        const prev = await corpusDeleteLastPreview();
        setDocPreview(prev);
      } else if (act === "delete_doc" && doc) {
        setSelectedDoc(doc);
        const prev = await corpusDeleteDocumentPreview(doc.doc_id);
        setDocPreview(prev);
      }
      setStep("confirming");
    } catch (e) {
      setErrorMsg((e as Error).message);
      setStep("error");
    } finally {
      setBusy(false);
    }
  }, []);

  // Auto-start preview when a specific action was requested from outside the modal.
  useEffect(() => {
    if (initialAction) {
      void startPreview(initialAction);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runConfirm = useCallback(async () => {
    setBusy(true);
    setErrorMsg("");
    try {
      let result: CorpusDeleteReport;
      if (action === "clear_all") {
        result = await corpusClearConfirm(phrase);
      } else if (action === "delete_last") {
        result = await corpusDeleteLastConfirm(phrase);
      } else {
        result = await corpusDeleteDocumentConfirm(selectedDoc!.doc_id, phrase);
      }
      setReport(result);
      setStep("done");
      onDeleted();
    } catch (e) {
      setErrorMsg((e as Error).message);
      setStep("error");
    } finally {
      setBusy(false);
    }
  }, [action, phrase, selectedDoc, onDeleted]);

  const expectedPhrase =
    action === "clear_all"
      ? "CLEAR CORPUS"
      : action === "delete_last"
        ? "DELETE LAST DOCUMENT"
        : "DELETE DOCUMENT";

  const phraseMatch = phrase.trim().toUpperCase() === expectedPhrase;

  return (
    <Modal open onClose={onClose} title="Manage Corpus" size="md" dismissable={!busy}>
      <>
          {step === "idle" && (
            <div className="space-y-3">
              <p className="text-sm text-fg2">
                Select an action. Deletions are permanent and cannot be undone.
              </p>
              <div className="space-y-2">
                <ActionCard
                  title="Delete last document"
                  desc="Remove the most recently indexed file from the corpus."
                  danger={false}
                  onClick={() => startPreview("delete_last")}
                  busy={busy}
                />
                <ActionCard
                  title="Clear all corpus"
                  desc="Remove all documents, vectors, entities, and the knowledge graph."
                  danger
                  onClick={() => startPreview("clear_all")}
                  busy={busy}
                />
              </div>
            </div>
          )}

          {step === "confirming" && action === "clear_all" && clearPreview && (
            <ConfirmClearAll
              preview={clearPreview}
              phrase={phrase}
              setPhrase={setPhrase}
              phraseMatch={phraseMatch}
              onConfirm={runConfirm}
              onBack={() => setStep("idle")}
              busy={busy}
            />
          )}

          {step === "confirming" && action !== "clear_all" && docPreview && (
            <ConfirmDeleteDoc
              preview={docPreview}
              phrase={phrase}
              setPhrase={setPhrase}
              phraseMatch={phraseMatch}
              expectedPhrase={expectedPhrase}
              onConfirm={runConfirm}
              onBack={() => setStep("idle")}
              busy={busy}
            />
          )}

          {step === "previewing" && (
            <div className="flex items-center gap-2 py-4 text-sm text-fg3">
              <span className="animate-spin">⏳</span> Loading preview…
            </div>
          )}

          {step === "done" && report && (
            <DeletionReport report={report} onClose={onClose} />
          )}

          {step === "error" && (
            <div className="space-y-3">
              <p className="rounded-lg border border-bad/30 bg-bad/10 p-3 text-sm text-bad">
                {errorMsg || "An error occurred."}
              </p>
              <button className="btn-ghost text-sm" onClick={() => setStep("idle")}>
                ← Back
              </button>
            </div>
          )}
      </>
    </Modal>
  );
}

function ActionCard({
  title,
  desc,
  danger,
  onClick,
  busy,
}: {
  title: string;
  desc: string;
  danger: boolean;
  onClick: () => void;
  busy: boolean;
}) {
  return (
    <button
      className={`w-full rounded-xl border p-4 text-left transition hover:bg-panel2 disabled:opacity-50 ${
        danger ? "border-bad/30 hover:border-bad/60" : "border-edge hover:border-edge-strong"
      }`}
      onClick={onClick}
      disabled={busy}
    >
      <p className={`text-sm font-medium ${danger ? "text-bad" : "text-fg"}`}>{title}</p>
      <p className="mt-0.5 text-xs text-fg3">{desc}</p>
    </button>
  );
}

function ConfirmClearAll({
  preview,
  phrase,
  setPhrase,
  phraseMatch,
  onConfirm,
  onBack,
  busy,
}: {
  preview: CorpusClearPreview;
  phrase: string;
  setPhrase: (v: string) => void;
  phraseMatch: boolean;
  onConfirm: () => void;
  onBack: () => void;
  busy: boolean;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-bad/30 bg-bad/10 p-4">
        <p className="text-sm font-semibold text-bad">This will permanently delete:</p>
        <ul className="mt-2 space-y-1 text-xs text-fg2">
          <li>• {preview.document_count} document(s)</li>
          <li>• {preview.vector_count} vectors</li>
          <li>• {preview.entity_count} entities</li>
          <li>• Knowledge graph</li>
          <li>• Ingest manifest</li>
        </ul>
        {preview.files.length > 0 && (
          <div className="mt-3">
            <p className="text-xs text-fg3 mb-1">Files to remove:</p>
            <ul className="space-y-0.5 text-xs text-fg2">
              {preview.files.slice(0, 8).map((f) => (
                <li key={f} className="truncate">• {displaySource(f)}</li>
              ))}
              {preview.files.length > 8 && (
                <li className="text-fg3">… and {preview.files.length - 8} more</li>
              )}
            </ul>
          </div>
        )}
      </div>
      <div className="space-y-2">
        <p className="text-xs text-fg2">
          Type <span className="font-mono font-semibold text-bad">CLEAR CORPUS</span> to confirm:
        </p>
        <input
          type="text"
          className="w-full rounded-lg border border-edge bg-panel2 px-3 py-2 text-sm text-fg placeholder:text-fg3 focus:border-bad focus:outline-none"
          placeholder="CLEAR CORPUS"
          value={phrase}
          onChange={(e) => setPhrase(e.target.value)}
          autoFocus
          spellCheck={false}
        />
      </div>
      <div className="flex gap-2">
        <button className="btn-ghost flex-1 text-sm" onClick={onBack} disabled={busy}>
          Cancel
        </button>
        <button
          className="flex-1 rounded-xl bg-bad px-4 py-2 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          onClick={onConfirm}
          disabled={!phraseMatch || busy}
        >
          {busy ? "Deleting…" : "Clear corpus"}
        </button>
      </div>
    </div>
  );
}

function ConfirmDeleteDoc({
  preview,
  phrase,
  setPhrase,
  phraseMatch,
  expectedPhrase,
  onConfirm,
  onBack,
  busy,
}: {
  preview: CorpusDeleteDocumentPreview;
  phrase: string;
  setPhrase: (v: string) => void;
  phraseMatch: boolean;
  expectedPhrase: string;
  onConfirm: () => void;
  onBack: () => void;
  busy: boolean;
}) {
  if (!preview.found || !preview.document) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-fg3">No document found to delete.</p>
        <button className="btn-ghost text-sm" onClick={onBack}>← Back</button>
      </div>
    );
  }
  const doc = preview.document;
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-warn/30 bg-warn/10 p-4">
        <p className="text-sm font-semibold text-warn">Permanently delete this document?</p>
        <div className="mt-2 space-y-1 text-xs text-fg2">
          <p><span className="text-fg3">Title:</span> {displaySource(doc.title || doc.source)}</p>
          <p><span className="text-fg3">Type:</span> {doc.source_type}</p>
          {doc.chunks && <p><span className="text-fg3">Chunks/vectors:</span> {doc.chunks}</p>}
        </div>
      </div>
      <div className="space-y-2">
        <p className="text-xs text-fg2">
          Type{" "}
          <span className="font-mono font-semibold text-warn">{expectedPhrase}</span> to confirm:
        </p>
        <input
          type="text"
          className="w-full rounded-lg border border-edge bg-panel2 px-3 py-2 text-sm text-fg placeholder:text-fg3 focus:border-warn focus:outline-none"
          placeholder={expectedPhrase}
          value={phrase}
          onChange={(e) => setPhrase(e.target.value)}
          autoFocus
          spellCheck={false}
        />
      </div>
      <div className="flex gap-2">
        <button className="btn-ghost flex-1 text-sm" onClick={onBack} disabled={busy}>
          Cancel
        </button>
        <button
          className="flex-1 rounded-xl bg-warn px-4 py-2 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          onClick={onConfirm}
          disabled={!phraseMatch || busy}
        >
          {busy ? "Deleting…" : "Delete document"}
        </button>
      </div>
    </div>
  );
}

function DeletionReport({ report, onClose }: { report: CorpusDeleteReport; onClose: () => void }) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-ok/30 bg-ok/10 p-4">
        <p className="text-sm font-semibold text-ok">Deletion complete</p>
        <ul className="mt-2 space-y-1 text-xs text-fg2">
          {report.deleted_vectors > 0 && <li>✓ {report.deleted_vectors} vectors removed</li>}
          {report.deleted_documents > 0 && <li>✓ {report.deleted_documents} documents removed</li>}
          {report.deleted_entities > 0 && <li>✓ {report.deleted_entities} entities removed</li>}
          {report.deleted_chunks > 0 && <li>✓ {report.deleted_chunks} chunks removed</li>}
        </ul>
      </div>
      {report.errors.length > 0 && (
        <div className="rounded-xl border border-warn/30 bg-warn/10 p-3">
          <p className="text-xs font-medium text-warn mb-1">Partial errors ({report.errors.length}):</p>
          <ul className="space-y-0.5 text-xs text-fg2">
            {report.errors.map((e, i) => <li key={i}>⚠ {e}</li>)}
          </ul>
        </div>
      )}
      <button className="w-full rounded-xl bg-panel2 py-2 text-sm text-fg hover:bg-panel transition" onClick={onClose}>
        Close
      </button>
    </div>
  );
}
