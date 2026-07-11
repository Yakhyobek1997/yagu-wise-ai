"""auralynq-modelfit CLI — hardware profiling, model scoring, and benchmarking.

Usage:
  auralynq-modelfit hardware
  auralynq-modelfit score --model ollama:llama3.1:8b
  auralynq-modelfit recommend --task rag
  auralynq-modelfit benchmark --model llama3.1:8b --task rag --examples 10
  auralynq-modelfit estimate --model llama3.1:8b --params 8 --quant q4_k
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="auralynq-modelfit", help="Auralynq ModelFit Index CLI")
console = Console()


@app.command()
def hardware() -> None:
    """Probe and display local hardware profile."""
    from auralynq.modelfit.hardware import probe_hardware

    hw = probe_hardware()
    d = hw.to_dict()

    console.print("\n[bold cyan]Auralynq ModelFit — Hardware Profile[/bold cyan]")
    console.print(f"  OS:           {d['os']['name']}")
    console.print(f"  CPU:          {d['cpu']['model']}")
    console.print(f"  Cores:        {d['cpu']['cores_physical']}P / {d['cpu']['cores_logical']}L")
    console.print(f"  RAM:          {d['ram_gb']} GB")
    console.print(f"  Best backend: [green]{d['best_backend'].upper()}[/green]")

    if d["gpus"]:
        for g in d["gpus"]:
            console.print(f"  GPU[{g['device_index']}]:       {g['name']} — {g['vram_gb']} GB VRAM")
    else:
        console.print("  GPU:          [yellow]none detected[/yellow]")

    console.print(f"  Disk free:    {d['disk_free_gb']} GB")
    ollama_status = "[green]yes[/green]" if d["ollama_available"] else "[dim]no[/dim]"
    ollama_ver = f" ({d['ollama_version']})" if d.get("ollama_version") else ""
    console.print(f"  Ollama:       {ollama_status}{ollama_ver}")
    hf_status = "[green]yes[/green]" if d["hf_available"] else "[dim]no[/dim]"
    console.print(f"  HF cache:     {hf_status}")
    if d["warnings"]:
        for w in d["warnings"]:
            console.print(f"  [yellow]⚠ {w}[/yellow]")
    console.print()


@app.command()
def estimate(
    model: str = typer.Option(..., "--model", help="Model ID (e.g. ollama:llama3.1:8b)"),
    params: float = typer.Option(..., "--params", help="Parameter count in billions"),
    quant: str = typer.Option("q4_k", "--quant", help="Quantization level"),
    context: int = typer.Option(4096, "--context", help="Context tokens"),
) -> None:
    """Estimate VRAM/RAM/disk for a model+quantization on current hardware."""
    from auralynq.modelfit.hardware import probe_hardware
    from auralynq.modelfit.resource_estimator import estimate_resources

    hw = probe_hardware()
    result = estimate_resources(
        model_id=model,
        params_b=params,
        quantization=quant,
        available_vram_gb=hw.total_vram_gb,
        available_ram_gb=hw.ram_gb,
        context_tokens=context,
    )
    d = result.to_dict()

    _fit_colors = {
        "comfortable": "green",
        "tight": "yellow",
        "not_recommended": "red",
        "impossible": "bold red",
    }
    color = _fit_colors.get(d["fit_level"], "white")
    console.print("\n[bold cyan]Resource Estimate[/bold cyan] (is_estimate=true)")
    console.print(f"  Model:        {model}")
    console.print(f"  Quantization: {quant}")
    console.print(f"  Est. VRAM:    {d['estimated_vram_gb']} GB")
    console.print(f"  Est. RAM:     {d['estimated_ram_gb']} GB")
    console.print(f"  Est. disk:    {d['estimated_disk_gb']} GB")
    console.print(f"  Fit:          [{color}]{d['fit_level'].replace('_', ' ')}[/{color}]")
    console.print(f"  Rec. context: {d['recommended_context']:,} tokens")
    for w in d["warnings"]:
        console.print(f"  [yellow]⚠ {w}[/yellow]")
    console.print()


@app.command()
def score(
    model: str = typer.Option(..., "--model", help="Model ID from registry"),
    quant: str | None = typer.Option(None, "--quant"),
    task: str | None = typer.Option(None, "--task", help="e.g. rag, coding, agents"),
) -> None:
    """Compute ModelFit Score for a model on current hardware."""
    from auralynq.modelfit.hardware import probe_hardware
    from auralynq.modelfit.model_registry import get_registry
    from auralynq.modelfit.scoring import score_model

    registry = get_registry()
    m = registry.get(model)
    if m is None:
        console.print(f"[red]Model '{model}' not found in registry.[/red]")
        raise typer.Exit(1)

    hw = probe_hardware()
    s = score_model(m, hw, quantization=quant, requested_tasks=[task] if task else [])
    d = s.to_dict()

    label_color = {
        "Excellent fit": "bold green",
        "Recommended": "green",
        "Usable with limits": "yellow",
        "Not recommended": "red",
        "Does not fit": "bold red",
    }.get(d["label"], "white")

    console.print("\n[bold cyan]ModelFit Score[/bold cyan]")
    console.print(f"  Model:        {model}")
    overall_line = (
        f"  Overall:      [bold]{d['overall_score']:.0f}/100[/bold]"
        f"  [{label_color}]{d['label']}[/{label_color}]"
    )
    console.print(overall_line)
    console.print(f"  Hardware fit: {d['hardware_fit']:.0f}")
    speed_note = "(estimated)" if d["estimate_used"] else "(measured)"
    console.print(f"  Speed fit:    {d['speed_fit']:.0f}  {speed_note}")
    console.print(f"  RAG fit:      {d['rag_fit']:.0f}")
    console.print(f"  Task fit:     {d['task_fit']:.0f}")
    console.print(f"  Deployment:   {d['deployment_fit']:.0f}")
    console.print(f"  Best quant:   {d['best_quantization']}")
    console.print(f"  Reason:       {d['reason']}")
    if d["estimate_used"]:
        console.print("  [dim]Speed score is estimated. Run 'benchmark' for measured tok/s.[/dim]")
    for w in d["warnings"][:3]:
        console.print(f"  [yellow]⚠ {w}[/yellow]")
    console.print()


@app.command()
def recommend(
    task: str | None = typer.Option(None, "--task", help="e.g. rag, coding, summarization"),
    limit: int = typer.Option(5, "--limit"),
) -> None:
    """Show top model recommendations for current hardware."""
    from auralynq.modelfit.hardware import probe_hardware
    from auralynq.modelfit.model_registry import get_registry
    from auralynq.modelfit.scoring import score_model

    hw = probe_hardware()
    registry = get_registry()
    candidates = [m for m in registry.list_all() if not m.embedding and not m.reranker]
    if task:
        candidates = [m for m in candidates if task in m.tasks or not m.tasks]

    scored = sorted(
        [score_model(m, hw, requested_tasks=[task] if task else []) for m in candidates],
        key=lambda s: s.overall_score,
        reverse=True,
    )[:limit]

    vram_or_ram = hw.total_vram_gb or hw.ram_gb
    table = Table(title=f"Top {limit} models for {hw.best_backend.upper()} / {vram_or_ram:.0f}GB")
    table.add_column("Model", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Label")
    table.add_column("Quant")
    table.add_column("VRAM est.")
    table.add_column("Notes")

    for s in scored:
        re = s.resource_estimate
        table.add_row(
            s.model_id.replace("ollama:", "").replace("hf:", ""),
            f"{s.overall_score:.0f}",
            s.label,
            s.best_quantization,
            f"{re.estimated_vram_gb:.1f} GB" if re else "—",
            "(est.)" if s.estimate_used else "(meas.)",
        )
    console.print(table)
    console.print()


@app.command()
def benchmark(
    model: str = typer.Option(..., "--model", help="Ollama tag or model ID"),
    quant: str = typer.Option("q4_k", "--quantization"),
    task: str = typer.Option("latency", "--task"),
    examples: int = typer.Option(10, "--examples"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview only; do not run"),
    output: str | None = typer.Option(None, "--output", help="Output directory"),
) -> None:
    """Run a local benchmark against an installed Ollama model.

    Always previews the plan first. Requires --no-dry-run to actually execute.
    """
    from auralynq.modelfit.benchmark_runner import preview_benchmark, run_benchmark

    model_id = model if model.startswith("ollama:") else f"ollama:{model}"
    plan = preview_benchmark(model_id, quant, task, examples)

    console.print("\n[bold cyan]Benchmark Plan[/bold cyan]")
    console.print(f"  Model:         {plan.model_id}")
    console.print(f"  Quantization:  {plan.quantization}")
    console.print(f"  Task:          {plan.task}")
    console.print(f"  Examples:      {plan.num_examples}")
    console.print(f"  Est. duration: {plan.estimated_duration_min} min")
    console.print("  Auto-download: [bold green]never[/bold green]")
    for w in plan.warnings:
        console.print(f"  [yellow]⚠ {w}[/yellow]")

    if dry_run:
        console.print("\n[dim]Dry run — use without --dry-run to execute.[/dim]\n")
        return

    if not typer.confirm("\nRun benchmark now?"):
        console.print("[dim]Cancelled.[/dim]")
        return

    console.print("[cyan]Running benchmark…[/cyan]")
    result = asyncio.run(run_benchmark(model_id, quant, task, examples, output))

    if result.status == "failed":
        console.print(f"[red]Benchmark failed: {result.error}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold green]Benchmark completed[/bold green] — run/{result.run_id}")
    if result.avg_tok_per_sec is not None:
        console.print(f"  Avg tok/s:  [green]{result.avg_tok_per_sec} (measured)[/green]")
    if result.p50_latency_ms is not None:
        console.print(f"  p50 latency: {result.p50_latency_ms} ms")
    if result.p95_latency_ms is not None:
        console.print(f"  p95 latency: {result.p95_latency_ms} ms")
    console.print()


def main() -> None:
    app()
