"use client";
import { useRef, useState, useEffect, useCallback } from "react";
import { audioUrl, sendVoice } from "@/lib/api";

// The product promise is "Talk to Your Data" — voice is central, so this control
// is a prominent, polished mic with explicit, honest states.
type VoiceState = "idle" | "listening" | "transcribing" | "speaking" | "failed";

const STATE_META: Record<VoiceState, { label: string; hint: string }> = {
  idle: { label: "Hold to talk", hint: "Ask your data out loud" },
  listening: { label: "Listening…", hint: "Release to send" },
  transcribing: { label: "Transcribing & thinking…", hint: "Grounding your answer" },
  speaking: { label: "Speaking…", hint: "Playing the answer" },
  failed: { label: "Voice failed — try again", hint: "Check microphone access" },
};

const BAR_COUNT = 24;

function WaveformBars({ analyserRef }: { analyserRef: React.MutableRefObject<AnalyserNode | null> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const draw = () => {
      const analyser = analyserRef.current;
      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      if (!analyser) {
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      const buf = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(buf);

      const step = Math.floor(buf.length / BAR_COUNT);
      const barW = W / BAR_COUNT - 1;
      const style = getComputedStyle(canvas);
      const color = style.getPropertyValue("--color-bad").trim() || "#f87171";
      ctx.fillStyle = color;

      for (let i = 0; i < BAR_COUNT; i++) {
        const val = buf[i * step] / 255;
        const bh = Math.max(2, val * H);
        const x = i * (barW + 1);
        const y = (H - bh) / 2;
        ctx.beginPath();
        ctx.roundRect(x, y, barW, bh, 2);
        ctx.fill();
      }
      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(rafRef.current);
  }, [analyserRef]);

  return (
    <canvas
      ref={canvasRef}
      width={120}
      height={28}
      aria-hidden
      className="rounded"
      style={{ background: "transparent" }}
    />
  );
}

export function VoiceRecorder({
  onResult,
  compact = false,
}: {
  onResult: (r: any) => void;
  compact?: boolean;
}) {
  const [state, setState] = useState<VoiceState>("idle");
  const [partial, setPartial] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);

  const busy = state === "transcribing";

  async function start() {
    if (busy) return;
    setPartial("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Wire up the Web Audio analyser for the live waveform visualisation.
      try {
        const ctx = new AudioContext();
        audioCtxRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.7;
        source.connect(analyser);
        analyserRef.current = analyser;
      } catch {
        // Non-fatal: waveform degrades to nothing if WebAudio is unavailable.
        analyserRef.current = null;
      }

      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      rec.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        // Tear down the audio context; the canvas stops drawing on next frame.
        analyserRef.current = null;
        audioCtxRef.current?.close().catch(() => {});
        audioCtxRef.current = null;

        setState("transcribing");
        try {
          const blob = new Blob(chunksRef.current, { type: "audio/webm" });
          const r = await sendVoice(blob);
          setPartial(r.transcript || "");
          onResult(r);
          const a = new Audio(audioUrl());
          setState("speaking");
          a.onended = () => setState("idle");
          a.onerror = () => setState("idle");
          a.play().catch(() => setState("idle"));
        } catch (err) {
          setState("failed");
          onResult({ answer: `Voice error: ${(err as Error).message}`, citations: [] });
        }
      };
      rec.start();
      recorderRef.current = rec;
      setState("listening");
    } catch {
      setState("failed");
    }
  }

  function stop() {
    if (state !== "listening") return;
    recorderRef.current?.stop();
  }

  const meta = STATE_META[state];
  const active = state === "listening";

  return (
    <div className={`flex items-center gap-3 ${compact ? "" : "flex-wrap"}`}>
      <button
        type="button"
        onMouseDown={start}
        onMouseUp={stop}
        onMouseLeave={stop}
        onTouchStart={start}
        onTouchEnd={stop}
        disabled={busy}
        aria-label={meta.label}
        aria-pressed={active}
        title={meta.label}
        className={`relative inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border transition ${
          active
            ? "border-bad/50 bg-bad/15 text-bad"
            : state === "transcribing"
              ? "border-brand/50 bg-brand/15 text-brand"
              : state === "speaking"
                ? "border-accent/50 bg-accent/15 text-accent"
                : state === "failed"
                  ? "border-warn/50 bg-warn/15 text-warn"
                  : "border-edge bg-panel2 text-fg hover:border-brand/50 hover:text-brand"
        }`}
      >
        {active && (
          <span className="absolute inset-0 rounded-full border-2 border-bad/40 animate-pulse-ring" aria-hidden />
        )}
        <MicGlyph spinning={state === "transcribing"} />
      </button>

      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-fg">{meta.label}</span>
        </div>
        {active ? (
          <div className="mt-0.5" aria-hidden>
            <WaveformBars analyserRef={analyserRef} />
          </div>
        ) : partial ? (
          <p className="truncate text-xs text-fg3" title={partial}>
            "{partial}"
          </p>
        ) : (
          !compact && <p className="text-xs text-fg3">{meta.hint}</p>
        )}
      </div>
    </div>
  );
}

function MicGlyph({ spinning }: { spinning: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-5 w-5 ${spinning ? "animate-spin" : ""}`}
      aria-hidden
    >
      {spinning ? (
        <path d="M21 12a9 9 0 1 1-6.2-8.55" />
      ) : (
        <>
          <rect x="9" y="3" width="6" height="11" rx="3" />
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8" />
        </>
      )}
    </svg>
  );
}
