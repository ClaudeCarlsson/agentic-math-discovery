"""Smart solver routing based on signature characteristics.

Inspects the incoming signature and routes model-finding to the best
available solver:

- Single-sorted + heavy equational axioms (self-distributivity, etc.)
  → Mace4 (if available), which has built-in symmetry breaking
  → Z3 with symmetry breaking + extended timeout (fallback)
- Everything else → Z3 (default, fast for small domains)

This prevents the O(n³) constraint explosion that causes Z3 to time out
on structures like Full-Self-Distributive Quasigroups, yielding false
"0 models" results.
"""

from __future__ import annotations

import logging

from src.core.signature import AxiomKind, Signature
from src.solvers.mace4 import Mace4Result, Mace4Solver, ModelSpectrum
from src.solvers.z3_solver import HEAVY_AXIOM_KINDS, Z3ModelFinder

log = logging.getLogger(__name__)


def _is_single_sorted(sig: Signature) -> bool:
    """Check if the signature uses only one sort."""
    return len(sig.sorts) <= 1


def _has_heavy_axioms(sig: Signature) -> bool:
    """Check if the signature contains O(n³) equational axioms."""
    return any(ax.kind in HEAVY_AXIOM_KINDS for ax in sig.axioms)


def _count_heavy_axioms(sig: Signature) -> int:
    """Count the number of heavy equational axioms."""
    return sum(1 for ax in sig.axioms if ax.kind in HEAVY_AXIOM_KINDS)


class SmartSolverRouter:
    """Routes model-finding to the best solver for each signature.

    Usage:
        router = SmartSolverRouter()
        spectrum = router.compute_spectrum(sig, min_size=2, max_size=8)
    """

    def __init__(
        self,
        z3_timeout_ms: int = 30000,
        mace4_timeout: int = 30,
        heavy_timeout_multiplier: float = 2.0,
    ):
        self.z3_timeout_ms = z3_timeout_ms
        self.mace4_timeout = mace4_timeout
        self.heavy_timeout_multiplier = heavy_timeout_multiplier

        # Probe Mace4 availability once at init
        self._mace4 = Mace4Solver(timeout=mace4_timeout)
        self._mace4_available = self._mace4.is_available()

        # Z3 solvers: normal and extended-timeout for heavy sigs
        self._z3_normal = Z3ModelFinder(timeout_ms=z3_timeout_ms)
        heavy_ms = int(z3_timeout_ms * heavy_timeout_multiplier)
        self._z3_heavy = Z3ModelFinder(timeout_ms=heavy_ms)

    def is_available(self) -> bool:
        """At least one solver must be available."""
        return self._mace4_available or self._z3_normal.is_available()

    def classify(self, sig: Signature) -> str:
        """Classify a signature for solver routing.

        Returns:
            "mace4_heavy" — route to Mace4 (heavy axioms, Mace4 available)
            "z3_heavy"    — route to Z3 with extended timeout (heavy axioms)
            "z3_normal"   — route to standard Z3
        """
        if _has_heavy_axioms(sig):
            if self._mace4_available:
                return "mace4_heavy"
            return "z3_heavy"
        return "z3_normal"

    def find_models(
        self,
        sig: Signature,
        domain_size: int,
        max_models: int = 10,
    ) -> Mace4Result:
        """Find models using the best solver for this signature."""
        route = self.classify(sig)

        if route == "mace4_heavy":
            log.debug(
                "Routing %s (size %d) to Mace4 (heavy axioms)",
                sig.name, domain_size,
            )
            return self._mace4.find_models(sig, domain_size, max_models)

        if route == "z3_heavy":
            log.debug(
                "Routing %s (size %d) to Z3 with symmetry breaking + extended timeout",
                sig.name, domain_size,
            )
            return self._z3_heavy.find_models(sig, domain_size, max_models)

        log.debug("Routing %s (size %d) to Z3 (standard)", sig.name, domain_size)
        return self._z3_normal.find_models(sig, domain_size, max_models)

    def compute_spectrum(
        self,
        sig: Signature,
        min_size: int = 2,
        max_size: int = 8,
        max_models_per_size: int = 10,
    ) -> ModelSpectrum:
        """Compute the model spectrum using the best solver for this signature."""
        spectrum = ModelSpectrum(signature_name=sig.name)

        for size in range(min_size, max_size + 1):
            result = self.find_models(sig, size, max_models_per_size)
            spectrum.spectrum[size] = len(result.models_found)
            spectrum.models_by_size[size] = result.models_found
            if result.timed_out:
                spectrum.timed_out_sizes.append(size)

        return spectrum
