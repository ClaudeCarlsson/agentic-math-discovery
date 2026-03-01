"""Parallel model-checking via ProcessPoolExecutor.

Z3 is NOT thread-safe, so we use process-level parallelism.
Each worker creates its own SmartSolverRouter (and thus its own Z3/Mace4
instances) to avoid shared state.

Usage:
    from src.solvers.parallel import parallel_compute_spectra

    work_items = [
        (sig1, 2, 6, 10, 30000, 30),
        (sig2, 2, 6, 10, 30000, 30),
    ]
    spectra = parallel_compute_spectra(work_items, max_workers=8)
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.signature import Signature
    from src.solvers.mace4 import ModelSpectrum


# ── Worker function (top-level for pickling) ─────────────────────────

def _spectrum_worker(work_item: tuple) -> "ModelSpectrum":
    """Compute spectrum for a single signature in a worker process.

    Must be a top-level function so multiprocessing can pickle it.
    Each call creates a fresh SmartSolverRouter to avoid sharing Z3 state.
    """
    sig, min_size, max_size, max_models, z3_timeout, mace4_timeout = work_item
    from src.solvers.router import SmartSolverRouter

    router = SmartSolverRouter(
        z3_timeout_ms=z3_timeout,
        mace4_timeout=mace4_timeout,
    )
    return router.compute_spectrum(sig, min_size, max_size, max_models)


# ── Public API ───────────────────────────────────────────────────────

def parallel_compute_spectra(
    work_items: list[tuple],
    max_workers: int | None = None,
) -> list["ModelSpectrum"]:
    """Compute spectra in parallel using ProcessPoolExecutor.

    Args:
        work_items: List of tuples, each containing:
            (signature, min_size, max_size, max_models_per_size,
             z3_timeout_ms, mace4_timeout)
        max_workers: Maximum number of worker processes.
            Defaults to min(len(work_items), os.cpu_count() or 4).
            Pass 1 to force sequential execution.

    Returns:
        List of ModelSpectrum in the same order as work_items.
    """
    if not work_items:
        return []

    # Determine worker count
    if max_workers is None:
        max_workers = min(len(work_items), os.cpu_count() or 4)
    max_workers = max(1, max_workers)

    # Sequential fast path: single item or single worker
    if max_workers == 1 or len(work_items) == 1:
        return [_spectrum_worker(item) for item in work_items]

    # Parallel execution
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_spectrum_worker, work_items))

    return results
