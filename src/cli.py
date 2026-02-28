"""CLI interface for the mathematical discovery system.

Usage:
    mathdisc explore --depth 2 --check-models --max-size 6
    mathdisc agent --model claude-sonnet-4-6 --cycles 10 --goal "explore broadly"
    mathdisc report --cycle latest
    mathdisc list-structures
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
@click.option("--library-path", default="library", help="Path to the library directory")
@click.pass_context
def main(ctx: click.Context, library_path: str) -> None:
    """Agentic AI for Mathematical Structure Discovery."""
    ctx.ensure_object(dict)
    ctx.obj["library_path"] = library_path


@main.command()
@click.option("--depth", default=1, help="Search depth (1-3)")
@click.option("--moves", multiple=True, help="Specific moves to apply")
@click.option("--base", multiple=True, help="Base structures to start from")
@click.option("--check-models", is_flag=True, help="Check candidates for finite models")
@click.option("--max-size", default=6, help="Maximum model size to search")
@click.option("--threshold", default=0.0, help="Minimum score threshold")
@click.option("--top", default=20, help="Number of top candidates to display")
@click.pass_context
def explore(
    ctx: click.Context,
    depth: int,
    moves: tuple[str, ...],
    base: tuple[str, ...],
    check_models: bool,
    max_size: int,
    threshold: float,
    top: int,
) -> None:
    """Explore the space of algebraic structures using structural moves."""
    from src.library.known_structures import load_all_known, load_by_name
    from src.moves.engine import MoveEngine, MoveKind
    from src.scoring.engine import ScoringEngine
    from src.utils.display import (
        display_exploration_results, display_score, display_signature, display_spectrum,
    )

    # Load base structures
    if base:
        bases = [load_by_name(name) for name in base]
        bases = [b for b in bases if b is not None]
        if not bases:
            console.print("[red]No valid base structures found.[/red]")
            console.print(f"Available: {', '.join(s.name for s in load_all_known())}")
            return
    else:
        bases = load_all_known()

    console.print(f"\n[bold]Starting exploration[/bold]")
    console.print(f"  Base structures: {[b.name for b in bases]}")
    console.print(f"  Depth: {depth}")
    console.print(f"  Threshold: {threshold}")

    engine = MoveEngine()
    scorer = ScoringEngine()

    # Parse moves
    if moves:
        move_kinds = [MoveKind(m) for m in moves]
    else:
        move_kinds = None

    # Iterative deepening
    current = bases
    all_results = []

    for d in range(depth):
        console.print(f"\n[cyan]Depth {d + 1}...[/cyan]")
        if move_kinds:
            results = []
            for mk in move_kinds:
                results.extend(engine.apply_move(mk, current))
        else:
            results = engine.apply_all_moves(current)

        all_results.extend(results)
        current = [r.signature for r in results]
        console.print(f"  Generated {len(results)} candidates (total: {len(all_results)})")

    # Score all candidates
    from src.library.manager import LibraryManager
    library = LibraryManager(ctx.obj["library_path"])
    known_fps = set(library.known_fingerprints())

    scored = []
    for r in all_results:
        score = scorer.score(r.signature, known_fingerprints=known_fps)
        if score.total >= threshold:
            scored.append({
                "name": r.signature.name,
                "move": r.move.value,
                "parents": r.parents,
                "description": r.description,
                "score": round(score.total, 4),
                "sorts": len(r.signature.sorts),
                "operations": len(r.signature.operations),
                "axioms": len(r.signature.axioms),
                "_sig": r.signature,
                "_score": score,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)

    console.print(f"\n[bold green]{len(scored)} candidates above threshold {threshold}[/bold green]")
    display_exploration_results(scored, limit=top)

    # Check models for top candidates
    if check_models:
        console.print(f"\n[bold]Checking models for top {min(top, len(scored))} candidates...[/bold]")

        from src.solvers.mace4 import Mace4Solver, Mace4Fallback
        from src.solvers.z3_solver import Z3ModelFinder

        solver = Mace4Solver()
        if not solver.is_available():
            console.print("[yellow]Mace4 not found, falling back to Z3...[/yellow]")
            z3_finder = Z3ModelFinder()
            if not z3_finder.is_available():
                console.print("[red]Neither Mace4 nor Z3 available. Install z3-solver: pip install z3-solver[/red]")
                return
            solver = Mace4Fallback()

        for item in scored[:top]:
            sig = item["_sig"]
            console.print(f"\n  Checking [cyan]{sig.name}[/cyan]...")
            spectrum = solver.compute_spectrum(sig, min_size=2, max_size=max_size)

            if not spectrum.is_empty():
                console.print(f"    [green]Models found![/green] Spectrum: {spectrum.spectrum}")
                display_spectrum(spectrum)

                # Re-score with model information
                score = scorer.score(sig, spectrum, known_fps)
                display_score(sig.name, score)
            else:
                console.print(f"    [dim]No models found up to size {max_size}[/dim]")

    # Show details of top 3
    console.print(f"\n[bold]Top 3 candidates:[/bold]")
    for item in scored[:3]:
        display_signature(item["_sig"])
        display_score(item["name"], item["_score"])


@main.command()
@click.option("--model", default="claude-opus-4-6", help="Claude model (e.g. claude-opus-4-6, opus, sonnet)")
@click.option("--effort", default="high", type=click.Choice(["low", "medium", "high"]), help="Thinking effort level")
@click.option("--cycles", default=5, help="Number of research cycles")
@click.option("--goal", default="Explore broadly: find novel algebraic structures", help="Research goal")
@click.option("--depth", default=2, help="Exploration depth per cycle")
@click.option("--max-size", default=6, help="Maximum model size")
@click.option("--base", multiple=True, help="Base structures")
@click.pass_context
def agent(
    ctx: click.Context,
    model: str,
    effort: str,
    cycles: int,
    goal: str,
    depth: int,
    max_size: int,
    base: tuple[str, ...],
) -> None:
    """Run the Claude CLI-driven research agent.

    Requires: claude CLI (npm install -g @anthropic-ai/claude-code)
    """
    from src.agent.controller import AgentConfig, AgentController
    from src.library.manager import LibraryManager
    from src.utils.display import display_cycle_report

    library = LibraryManager(ctx.obj["library_path"])

    config = AgentConfig(
        model=model,
        effort=effort,
        max_cycles=cycles,
        goal=goal,
        explore_depth=depth,
        max_model_size=max_size,
        base_structures=list(base) if base else ["Group", "Ring", "Lattice", "Quasigroup"],
    )

    console.print(Panel(
        f"[bold]Mathematical Discovery Agent[/bold]\n\n"
        f"Model: {config.model}\n"
        f"Effort: {config.effort}\n"
        f"Goal: {config.goal}\n"
        f"Cycles: {cycles}\n"
        f"Base structures: {config.base_structures}\n"
        f"Explore depth: {depth}\n"
        f"Max model size: {max_size}",
        title="Agent Configuration",
        border_style="blue",
    ))

    controller = AgentController(config, library)

    try:
        reports = controller.run(cycles)
        for report in reports:
            display_cycle_report(report)
    except KeyboardInterrupt:
        console.print("\n[yellow]Agent interrupted by user.[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Agent error: {e}[/red]")
        raise


@main.command("list-structures")
def list_structures() -> None:
    """List all known algebraic structures in the library."""
    from src.library.known_structures import load_all_known
    from src.utils.display import display_signature

    structures = load_all_known()
    console.print(f"\n[bold]{len(structures)} known structures:[/bold]\n")
    for sig in structures:
        display_signature(sig)


@main.command()
@click.option("--cycle", default="latest", help="Cycle number or 'latest'")
@click.option("--top", default=20, help="Number of top discoveries to show")
@click.option("--sort-by", default="score", help="Sort by: score, cycle, name")
@click.pass_context
def report(ctx: click.Context, cycle: str, top: int, sort_by: str) -> None:
    """View discovery reports."""
    from src.library.manager import LibraryManager

    library = LibraryManager(ctx.obj["library_path"])

    reports_dir = library.base_path / "reports"
    if not reports_dir.exists():
        console.print("[yellow]No reports found yet. Run 'explore' or 'agent' first.[/yellow]")
        return

    report_files = sorted(reports_dir.glob("cycle_*_report.md"))
    if not report_files:
        console.print("[yellow]No cycle reports found.[/yellow]")
        return

    if cycle == "latest":
        target = report_files[-1]
    else:
        target = reports_dir / f"cycle_{int(cycle):03d}_report.md"

    if target.exists():
        content = target.read_text()
        from rich.markdown import Markdown
        console.print(Markdown(content))
    else:
        console.print(f"[red]Report not found: {target}[/red]")

    # Also show discovered structures
    discovered = library.list_discovered()
    if discovered:
        discovered.sort(key=lambda x: x.get("score", 0), reverse=True)
        console.print(f"\n[bold]Discovered Structures ({len(discovered)}):[/bold]")
        for d in discovered[:top]:
            console.print(f"  [{d['id']}] {d['name']} — score: {d.get('score', '?'):.3f}")


@main.command()
@click.argument("name")
@click.option("--max-size", default=6, help="Maximum model size")
@click.pass_context
def inspect(ctx: click.Context, name: str, max_size: int) -> None:
    """Inspect a specific structure in detail."""
    from src.library.known_structures import load_by_name
    from src.utils.display import display_signature, display_score, display_spectrum
    from src.scoring.engine import ScoringEngine
    from src.solvers.mace4 import Mace4Solver, Mace4Fallback

    sig = load_by_name(name)
    if not sig:
        console.print(f"[red]Structure '{name}' not found.[/red]")
        from src.library.known_structures import KNOWN_STRUCTURES
        console.print(f"Available: {', '.join(KNOWN_STRUCTURES.keys())}")
        return

    display_signature(sig)

    # Score it
    scorer = ScoringEngine()
    score = scorer.score(sig)
    display_score(name, score)

    # Check models
    console.print(f"\n[bold]Checking models up to size {max_size}...[/bold]")
    solver = Mace4Solver()
    if not solver.is_available():
        solver = Mace4Fallback()

    spectrum = solver.compute_spectrum(sig, min_size=2, max_size=max_size)
    display_spectrum(spectrum)

    # Re-score with model info
    score = scorer.score(sig, spectrum)
    display_score(f"{name} (with models)", score)


# Need to import Panel for the agent command
from rich.panel import Panel


if __name__ == "__main__":
    main()
