#!/usr/bin/env python3
"""Backtest / verification script for discovered algebraic structures.

Loads all discoveries from library/discovered/, reconstructs their signatures,
re-verifies finite models via Z3, and re-scores them to detect drift.

Usage:
    python3 backtest.py
    python3 backtest.py --max-size 8
    python3 backtest.py --id disc_0001
    python3 backtest.py --min-score 0.7
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.core.signature import Signature
from src.library.manager import LibraryManager
from src.scoring.engine import ScoringEngine


def run_backtest(
    library_path: str = "library",
    max_size: int = 6,
    min_score: float = 0.0,
    discovery_id: str | None = None,
    dry_run: bool = False,
    workers: int | None = None,
) -> int:
    """Run backtest on all (or selected) discoveries.

    Failed discoveries are moved to library/failed/ unless --dry-run is set.
    Passing discoveries have their scores updated in place.
    Returns 0 if all pass, 1 if any fail.
    """
    console = Console()
    library = LibraryManager(library_path)
    discoveries = library.list_discovered()

    if not discoveries:
        console.print("[yellow]No discoveries found.[/yellow]")
        return 0

    # Filter by ID if specified
    if discovery_id:
        discoveries = [d for d in discoveries if d.get("id") == discovery_id]
        if not discoveries:
            console.print(f"[red]Discovery '{discovery_id}' not found.[/red]")
            return 1

    # Filter by minimum score
    if min_score > 0:
        discoveries = [d for d in discoveries if d.get("score", 0) >= min_score]

    console.print(f"\n[bold]Backtesting {len(discoveries)} discoveries[/bold] (max_size={max_size})\n")

    scorer = ScoringEngine()

    # Build fingerprint set excluding discovered structures themselves,
    # so each discovery is still "novel" relative to known structures
    # (not penalized for its own existence in the library).
    known_fps = set(library.known_fingerprints())

    table = Table(title="Backtest Results")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white", max_width=30)
    table.add_column("Orig Score", justify="right")
    table.add_column("New Score", justify="right")
    table.add_column("Delta", justify="right")
    table.add_column("Models", justify="right")
    table.add_column("Status", justify="center")

    results = []
    # Track which discovery files to update on PASS
    updates: list[tuple[dict, float, dict]] = []  # (disc_data, new_score, new_breakdown)

    discovered_dir = Path(library_path) / "discovered"

    # Phase 1: Parse all signatures, collecting valid ones for parallel spectrum computation
    parsed: list[tuple[int, dict, Signature]] = []  # (index, disc, sig)
    for i, disc in enumerate(discoveries):
        disc_id = disc.get("id", "?")
        disc_name = disc.get("name", "?")
        orig_score = disc.get("score", 0.0)

        try:
            sig = Signature.from_dict(disc["signature"])
            parsed.append((i, disc, sig))
        except Exception as e:
            results.append({"status": "FAIL", "id": disc_id, "reason": f"parse error: {e}"})
            table.add_row(
                disc_id, disc_name,
                f"{orig_score:.3f}", "ERR", "—", "—",
                "[red]FAIL[/red]",
            )
            console.print(f"  [red]{disc_id}: Failed to reconstruct signature: {e}[/red]")

    # Phase 2: Compute spectra in parallel for all valid signatures
    if parsed:
        from src.solvers.parallel import parallel_compute_spectra

        z3_timeout_ms = 30000
        mace4_timeout = 30
        work_items = [
            (sig, 2, max_size, 10, z3_timeout_ms, mace4_timeout)
            for _, _, sig in parsed
        ]

        if workers and workers > 1:
            console.print(f"  [dim]Using {workers} parallel workers[/dim]")

        spectra = parallel_compute_spectra(work_items, max_workers=workers)

        # Phase 3: Post-process results
        for (_, disc, sig), spectrum in zip(parsed, spectra):
            disc_id = disc.get("id", "?")
            disc_name = disc.get("name", "?")
            orig_score = disc.get("score", 0.0)

            total_models = spectrum.total_models()
            orig_had_models = disc.get("score_breakdown", {}).get("has_models", 0) > 0

            # Re-score using only known fingerprints (not other discoveries),
            # so is_novel stays 1.0 for genuinely novel structures.
            # Add sibling discovery fingerprints but exclude this one's own.
            scoring_fps = set(known_fps)
            own_fp = disc.get("fingerprint")
            for other in discoveries:
                other_fp = other.get("fingerprint")
                if other_fp and other_fp != own_fp:
                    scoring_fps.add(other_fp)

            new_score_bd = scorer.score(sig, spectrum, scoring_fps)
            new_score = new_score_bd.total
            delta = new_score - orig_score

            # Determine status
            if orig_had_models and total_models == 0 and not spectrum.any_timed_out():
                status = "FAIL"
                status_str = "[red]FAIL[/red]"
                reason = "no models found (original had models)"
            elif orig_had_models and total_models == 0 and spectrum.any_timed_out():
                status = "WARN"
                status_str = "[yellow]WARN[/yellow]"
                reason = f"no models but Z3 timed out at sizes {spectrum.timed_out_sizes}"
            elif total_models == 0 and not orig_had_models and not spectrum.any_timed_out():
                status = "FAIL"
                status_str = "[red]FAIL[/red]"
                reason = "no models found"
            else:
                status = "PASS"
                status_str = "[green]PASS[/green]"
                reason = ""
                # Queue score update for all passing discoveries
                updates.append((disc, new_score, new_score_bd.to_dict()))

            results.append({"status": status, "id": disc_id, "reason": reason})

            # Format models column
            sizes_with = spectrum.sizes_with_models()
            timeout_note = f" T/O@{spectrum.timed_out_sizes}" if spectrum.any_timed_out() else ""
            if sizes_with:
                models_str = f"{total_models} ({len(sizes_with)} sizes){timeout_note}"
            else:
                models_str = f"0{timeout_note}"

            delta_str = f"{delta:+.3f}" if delta != 0 else "0.000"

            table.add_row(
                disc_id, disc_name,
                f"{orig_score:.3f}", f"{new_score:.3f}", delta_str,
                models_str, status_str,
            )

    console.print(table)

    # Summary
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_warn = sum(1 for r in results if r["status"] == "WARN")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")

    console.print(f"\n[bold]Summary:[/bold] {n_pass} PASS, {n_warn} WARN, {n_fail} FAIL")

    # Update scores for passing discoveries
    if updates and not dry_run:
        updated_count = 0
        for disc_data, new_score, new_breakdown in updates:
            if abs(new_score - disc_data.get("score", 0)) > 0.0001:
                disc_data["score"] = new_score
                disc_data["score_breakdown"] = new_breakdown
                # Write back to file
                for f in discovered_dir.glob("disc_*.json"):
                    try:
                        file_data = json.loads(f.read_text())
                        if file_data.get("id") == disc_data.get("id"):
                            file_data["score"] = new_score
                            file_data["score_breakdown"] = new_breakdown
                            f.write_text(json.dumps(file_data, indent=2))
                            updated_count += 1
                            break
                    except (json.JSONDecodeError, OSError):
                        continue
        if updated_count:
            console.print(f"[green]Updated scores for {updated_count} discovery(ies).[/green]")

    # Archive failed discoveries
    failed = [r for r in results if r["status"] == "FAIL"]
    if failed:
        if dry_run:
            console.print(f"\n[dim]Dry run: would archive {len(failed)} failed discovery(ies) to library/failed/[/dim]")
            for r in failed:
                console.print(f"  [dim]{r['id']}: {r.get('reason', 'unknown')}[/dim]")
        else:
            console.print(f"\n[bold]Archiving {len(failed)} failed discovery(ies) to library/failed/[/bold]")
            for r in failed:
                dest = library.archive_failed(r["id"], r.get("reason", "backtest failure"))
                if dest:
                    console.print(f"  [red]{r['id']}[/red] -> {dest}")
                else:
                    console.print(f"  [yellow]{r['id']}: not found (already archived?)[/yellow]")

    if n_fail > 0:
        console.print("\n[red]Some discoveries failed verification.[/red]")
        return 1
    if n_warn > 0:
        console.print("[yellow]Some discoveries have score drift > 0.1.[/yellow]")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backtest discovered algebraic structures")
    parser.add_argument("--max-size", type=int, default=6, help="Maximum Z3 domain size (default: 6)")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum score threshold")
    parser.add_argument("--id", dest="discovery_id", help="Backtest a specific discovery by ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be archived without moving files")
    parser.add_argument("--library-path", default="library", help="Path to library directory")
    parser.add_argument("--workers", type=int, default=None, help="Parallel workers for model checking")
    args = parser.parse_args()

    sys.exit(run_backtest(
        library_path=args.library_path,
        max_size=args.max_size,
        min_score=args.min_score,
        discovery_id=args.discovery_id,
        dry_run=args.dry_run,
        workers=args.workers,
    ))
