#!/usr/bin/env python3
"""Reproducible end-to-end Auralynq demo (`make demo`).

Runs the full pipeline locally at $0 with only HUGGINGFACE_TOKEN (optional):
  1. ensure sample data exists (download_data)
  2. build the vector index + knowledge graph
  3. answer a typed question  → grounded, cited answer (fast path)
  4. answer a relational question → routed to PathRAG with evidence paths
  5. run a voice turn on the synthetic audio → speaker/timestamp citations
"""

from __future__ import annotations

from auralynq.config import get_settings
from auralynq.telemetry import configure_logging
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _print_answer(title: str, res) -> None:
    console.print(Panel(res.answer or "(no answer)", title=title, border_style="cyan"))
    meta = Table.grid(padding=(0, 2))
    meta.add_row("route", f"[bold]{res.route}[/] ({res.route_confidence})")
    meta.add_row("rationale", res.route_rationale)
    meta.add_row("iterations", str(res.iterations))
    meta.add_row("elapsed_ms", str(res.elapsed_ms))
    console.print(meta)
    if res.citations:
        t = Table(title="Citations", show_lines=False)
        t.add_column("#")
        t.add_column("source")
        t.add_column("locator / timestamp")
        for c in res.citations:
            t.add_row(
                str(c.get("marker", "?")), str(c.get("source", "?")), str(c.get("locator", ""))
            )
        console.print(t)
    if res.path_evidence:
        console.print("[bold]PathRAG evidence paths:[/]")
        for ev in res.path_evidence[:4]:
            console.print(f"  • {' → '.join(ev['nodes'])}  (reliability {ev['reliability']})")


def main() -> None:
    s = get_settings()
    configure_logging(level="WARNING")
    s.ensure_dirs()
    console.rule("[bold cyan]Auralynq — Talk to Your Data[/]")

    # 1-2. data + index
    from auralynq.pipeline import build_index

    from scripts.download_data import download

    corpus = s.data_dir / "corpus"
    if not corpus.exists() or not any(corpus.iterdir()):
        console.print("→ downloading sample data …")
        download(sample=True)
    console.print("→ building index (vector + knowledge graph) …")
    stats = build_index(corpus)
    st = Table(title="Index")
    st.add_column("metric")
    st.add_column("value", justify="right")
    for k, v in stats.items():
        st.add_row(k, str(v))
    console.print(st)

    from auralynq.agent import runner
    from auralynq.agent.runner import answer_question

    runner._CACHE.clear()

    # 3. simple typed question → fast path
    _print_answer("Q1 — typed (fast path)", answer_question("What is the capital of France?"))

    # 4. relational question → PathRAG
    _print_answer(
        "Q2 — relational (PathRAG)", answer_question("How are Paris, France and Europe related?")
    )

    # 5. voice turn on the synthetic lecture audio
    audio = corpus / "lecture_pathrag.wav"
    if audio.exists():
        from auralynq.voice.loop import run_voice_turn

        console.rule("[bold magenta]Voice turn[/]")
        v = run_voice_turn(audio_path=audio, speak=True)
        console.print(
            Panel(v.transcript or "(no speech)", title="Heard (ASR)", border_style="magenta")
        )
        console.print(Panel(v.answer, title="Spoken answer", border_style="cyan"))
        if v.audio_out_path:
            console.print(f"[green]✓[/] TTS audio → {v.audio_out_path} ({v.tts_provider})")

    console.rule("[bold green]Demo complete[/]")


if __name__ == "__main__":
    main()
