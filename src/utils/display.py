"""Rich console display utilities for exploration results."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from src.core.signature import Signature
from src.scoring.engine import ScoreBreakdown
from src.solvers.mace4 import ModelSpectrum

console = Console()


def display_signature(sig: Signature) -> None:
    """Display a signature in a rich panel."""
    tree = Tree(f"[bold]{sig.name}[/bold]")

    sorts_branch = tree.add("[cyan]Sorts[/cyan]")
    for s in sig.sorts:
        sorts_branch.add(f"{s.name}: {s.description}")

    ops_branch = tree.add("[green]Operations[/green]")
    for op in sig.operations:
        domain = " × ".join(op.domain) if op.domain else "()"
        ops_branch.add(f"{op.name}: {domain} → {op.codomain}")

    axioms_branch = tree.add("[yellow]Axioms[/yellow]")
    for ax in sig.axioms:
        desc = ax.description or ax.kind.value
        axioms_branch.add(f"[{ax.kind.value}] {desc}")

    if sig.derivation_chain:
        chain_branch = tree.add("[magenta]Derivation[/magenta]")
        for step in sig.derivation_chain:
            chain_branch.add(step)

    console.print(Panel(tree, title=f"Signature: {sig.name}", border_style="blue"))


def display_score(name: str, score: ScoreBreakdown) -> None:
    """Display a score breakdown as a table."""
    table = Table(title=f"Interestingness Score: {name}")
    table.add_column("Dimension", style="cyan")
    table.add_column("Score", style="green", justify="right")

    for field_name, value in score.to_dict().items():
        style = "bold green" if field_name == "total" else ""
        bar = "█" * int(value * 20) + "░" * (20 - int(value * 20))
        table.add_row(field_name, f"{value:.3f} {bar}", style=style)

    console.print(table)


def display_spectrum(spectrum: ModelSpectrum) -> None:
    """Display a model spectrum."""
    table = Table(title=f"Model Spectrum: {spectrum.signature_name}")
    table.add_column("Size", style="cyan", justify="right")
    table.add_column("Models", style="green", justify="right")
    table.add_column("Visual", style="yellow")

    for size in sorted(spectrum.spectrum.keys()):
        count = spectrum.spectrum[size]
        bar = "█" * min(count, 40)
        table.add_row(str(size), str(count), bar)

    console.print(table)

    sizes = spectrum.sizes_with_models()
    if sizes:
        console.print(f"\n[bold]Sizes with models:[/bold] {sizes}")
        console.print(f"[bold]Total models:[/bold] {spectrum.total_models()}")


def display_exploration_results(results: list[dict[str, Any]], limit: int = 20) -> None:
    """Display exploration results as a table."""
    table = Table(title="Exploration Results")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Name", style="cyan")
    table.add_column("Move", style="green")
    table.add_column("Score", style="yellow", justify="right")
    table.add_column("S/O/A", style="blue", justify="right")

    for i, r in enumerate(results[:limit], 1):
        soa = f"{r.get('sorts', '?')}/{r.get('operations', '?')}/{r.get('axioms', '?')}"
        table.add_row(
            str(i),
            r["name"][:40],
            r.get("move", "?"),
            f"{r.get('score', 0):.3f}",
            soa,
        )

    console.print(table)
    if len(results) > limit:
        console.print(f"  ... and {len(results) - limit} more candidates")


def display_cycle_report(report: Any) -> None:
    """Display a cycle report."""
    console.print(Panel(
        f"[bold]Cycle {report.cycle_number}[/bold]\n"
        f"Goal: {report.goal}\n"
        f"Duration: {report.duration_seconds:.1f}s\n"
        f"Candidates: {report.candidates_generated} generated, "
        f"{report.candidates_with_models} with models\n"
        f"Discoveries: {len(report.discoveries)}",
        title="Cycle Report",
        border_style="green" if report.discoveries else "yellow",
    ))

    if report.top_candidates:
        display_exploration_results(report.top_candidates, limit=5)
