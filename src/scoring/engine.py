"""Interestingness scoring engine for candidate algebraic structures.

Scores candidates across multiple dimensions:
- Structural quality (connectivity, richness, tension, economy, fertility)
- Model-theoretic quality (has_models, model_diversity, spectrum_pattern)
- Novelty (is_novel, distance from known structures)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from src.core.signature import AxiomKind, Signature
from src.models.cayley import CayleyTable
from src.solvers.mace4 import ModelSpectrum


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of interestingness scores."""

    # Structural quality
    connectivity: float = 0.0       # How well sorts interact (0-1)
    richness: float = 0.0           # Axiom/operation ratio near 1.0 (0-1)
    tension: float = 0.0            # Diversity of axiom kinds (0-1)
    economy: float = 0.0            # Occam's razor: smaller = better (0-1)
    fertility: float = 0.0          # Can further constructions be built? (0-1)

    # Model-theoretic quality
    has_models: float = 0.0         # Does it have non-trivial finite models? (0/1)
    model_diversity: float = 0.0    # How many non-isomorphic models per size? (0-1)
    spectrum_pattern: float = 0.0   # Is the model spectrum structured? (0-1)
    solver_difficulty: float = 0.0  # Penalizes timeout-heavy / trivially-saturated spectra (0-1)

    # Novelty
    is_novel: float = 0.0           # Not isomorphic to anything known? (0/1)
    distance: float = 0.0           # How far from nearest known structure? (0-1)

    # Total
    total: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "connectivity": self.connectivity,
            "richness": self.richness,
            "tension": self.tension,
            "economy": self.economy,
            "fertility": self.fertility,
            "has_models": self.has_models,
            "model_diversity": self.model_diversity,
            "spectrum_pattern": self.spectrum_pattern,
            "solver_difficulty": self.solver_difficulty,
            "is_novel": self.is_novel,
            "distance": self.distance,
            "total": self.total,
        }


# Default scoring weights
DEFAULT_WEIGHTS = {
    "connectivity": 0.08,
    "richness": 0.08,
    "tension": 0.08,
    "economy": 0.10,
    "fertility": 0.06,
    "has_models": 0.15,
    "model_diversity": 0.10,
    "spectrum_pattern": 0.10,
    "solver_difficulty": 0.05,
    "is_novel": 0.15,
    "distance": 0.05,
}


class ScoringEngine:
    """Score candidate signatures for mathematical interestingness."""

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or DEFAULT_WEIGHTS

    def score(
        self,
        sig: Signature,
        spectrum: ModelSpectrum | None = None,
        known_fingerprints: set[str] | None = None,
    ) -> ScoreBreakdown:
        """Compute the full interestingness score for a candidate."""
        breakdown = ScoreBreakdown()

        # Structural scores
        breakdown.connectivity = self._connectivity(sig)
        breakdown.richness = self._richness(sig)
        breakdown.tension = self._tension(sig)
        breakdown.economy = self._economy(sig)
        breakdown.fertility = self._fertility(sig)

        # Model-theoretic scores
        if spectrum:
            breakdown.has_models = 1.0 if not spectrum.is_empty() else 0.0
            breakdown.model_diversity = self._model_diversity(spectrum)
            breakdown.spectrum_pattern = self._spectrum_pattern(spectrum)
            breakdown.solver_difficulty = self._solver_difficulty(spectrum)

        # Novelty scores
        if known_fingerprints is not None:
            fp = sig.fingerprint()
            breakdown.is_novel = 0.0 if fp in known_fingerprints else 1.0

        breakdown.distance = self._distance_from_known(sig)

        # Weighted total
        breakdown.total = sum(
            self.weights.get(field, 0) * getattr(breakdown, field)
            for field in self.weights
        )

        return breakdown

    def _connectivity(self, sig: Signature) -> float:
        """How well do the operations connect the sorts?

        An operation connects sorts if its domain/codomain span multiple sorts.
        A signature with all operations on the same sort scores lower.
        """
        if len(sig.sorts) <= 1:
            return 0.5  # Single-sorted: neutral

        all_sorts = set(s.name for s in sig.sorts)
        touched_sorts: set[str] = set()

        for op in sig.operations:
            for s in op.domain:
                touched_sorts.add(s)
            touched_sorts.add(op.codomain)

        # Cross-sort operations
        cross_sort_ops = 0
        for op in sig.operations:
            sorts_in_op = set(op.domain) | {op.codomain}
            if len(sorts_in_op) > 1:
                cross_sort_ops += 1

        coverage = len(touched_sorts) / len(all_sorts) if all_sorts else 0
        cross_ratio = cross_sort_ops / len(sig.operations) if sig.operations else 0

        return (coverage + cross_ratio) / 2

    def _richness(self, sig: Signature) -> float:
        """Axiom/operation ratio. Best when close to 1.0.

        Too few axioms = underconstrained (boring). Too many = overconstrained (likely trivial).
        """
        n_ops = len(sig.operations) or 1
        n_axioms = len(sig.axioms)

        ratio = n_axioms / n_ops
        # Peak at ratio=1.0, decay on either side
        return math.exp(-((ratio - 1.0) ** 2))

    def _tension(self, sig: Signature) -> float:
        """Diversity of axiom kinds. More diverse = more interesting.

        A structure with only associativity axioms is less interesting than
        one combining associativity, distributivity, and positivity.
        """
        if not sig.axioms:
            return 0.0

        kinds = set(a.kind for a in sig.axioms)
        all_kinds = set(AxiomKind)
        diversity = len(kinds) / min(len(all_kinds), 6)  # cap at 6 for normalization
        return min(diversity, 1.0)

    def _economy(self, sig: Signature) -> float:
        """Occam's razor: simpler signatures that constrain heavily are better.

        Penalizes signatures with many sorts, operations, or complex axioms.
        """
        total_size = len(sig.sorts) + len(sig.operations) + len(sig.axioms)
        # Ideal size range: 3-12 components
        if total_size <= 2:
            return 0.4
        if total_size <= 12:
            return 1.0 - max(0, total_size - 5) * 0.04
        return max(0.1, 1.0 - total_size * 0.04)

    def _fertility(self, sig: Signature) -> float:
        """Can further constructions be built on this?

        Signatures with more sorts and binary operations can support more moves.
        """
        n_binary = len(sig.get_ops_by_arity(2))
        n_sorts = len(sig.sorts)

        # More sorts and binary ops = more fertile
        sort_score = min(n_sorts / 3, 1.0)
        op_score = min(n_binary / 3, 1.0)

        return (sort_score + op_score) / 2

    def _model_diversity(self, spectrum: ModelSpectrum) -> float:
        """How many non-isomorphic models exist across sizes?"""
        total = spectrum.total_models()
        if total == 0:
            return 0.0
        sizes_with = len(spectrum.sizes_with_models())
        size_range = max(spectrum.spectrum.keys()) - min(spectrum.spectrum.keys()) + 1

        # Reward having models at multiple sizes
        coverage = sizes_with / size_range if size_range > 0 else 0

        # Reward having multiple models per size (but not too many)
        avg_per_size = total / sizes_with if sizes_with > 0 else 0
        count_score = 1.0 - math.exp(-avg_per_size / 3)

        return (coverage + count_score) / 2

    def _spectrum_pattern(self, spectrum: ModelSpectrum) -> float:
        """Is the model spectrum structured (not random)?

        Detects patterns like:
        - Only prime sizes
        - Only powers of 2
        - Arithmetic/geometric progressions
        - Regular gaps
        """
        sizes = spectrum.sizes_with_models()
        if len(sizes) < 2:
            return 0.0

        score = 0.0

        # Check for prime-only pattern
        primes = {2, 3, 5, 7, 11, 13, 17, 19, 23}
        if all(s in primes for s in sizes):
            score = max(score, 0.9)

        # Check for power-of-2 pattern
        pow2 = {1, 2, 4, 8, 16, 32}
        if all(s in pow2 for s in sizes):
            score = max(score, 0.8)

        # Check for arithmetic progression (require gap > 1 to be interesting;
        # consecutive sizes {2,3,4,5} are uninteresting, but {2,4,6,8} is)
        diffs = [sizes[i + 1] - sizes[i] for i in range(len(sizes) - 1)]
        if len(set(diffs)) == 1:
            gap = diffs[0]
            if gap > 1:
                score = max(score, 0.7)  # Non-trivial arithmetic progression
            else:
                score = max(score, 0.3)  # Consecutive sizes — less interesting

        # Check for a ratio pattern (geometric-ish)
        if all(s > 0 for s in sizes) and len(sizes) >= 3:
            ratios = [sizes[i + 1] / sizes[i] for i in range(len(sizes) - 1)]
            ratio_spread = max(ratios) - min(ratios) if ratios else 0
            if ratio_spread < 0.1:
                score = max(score, 0.7)

        # Model counts at each size form a pattern?
        counts = [spectrum.spectrum.get(s, 0) for s in sizes]
        if len(counts) >= 3:
            # Check if counts form a monotone sequence
            increasing = all(counts[i] <= counts[i + 1] for i in range(len(counts) - 1))
            if increasing:
                score = max(score, 0.5)

        return score

    def _solver_difficulty(self, spectrum: ModelSpectrum) -> float:
        """Penalize spectra with heavy timeouts or trivial saturation.

        High score (1.0) = solver completed cleanly with a non-trivial spectrum.
        Low score (0.0) = solver timed out everywhere or spectrum is trivially flat.

        This captures "solver difficulty" — structures that are either too hard
        for the solver (all timeouts) or too easy (trivially many models at
        every size with identical counts) score poorly.
        """
        sizes_checked = len(spectrum.spectrum)
        if sizes_checked == 0:
            return 0.0

        n_timed_out = len(spectrum.timed_out_sizes)

        # Penalty for timeouts: proportional to fraction of sizes that timed out
        if n_timed_out == sizes_checked:
            return 0.0  # All sizes timed out — no useful information
        timeout_ratio = n_timed_out / sizes_checked
        timeout_penalty = 1.0 - timeout_ratio  # 1.0 if no timeouts, 0.0 if all

        # Penalty for trivially flat spectra (same non-zero count at every size)
        counts = [v for v in spectrum.spectrum.values() if v > 0]
        if len(counts) >= 3 and len(set(counts)) == 1:
            # All non-zero counts are identical — likely trivially saturated
            flatness_penalty = 0.7
        else:
            flatness_penalty = 1.0

        return timeout_penalty * flatness_penalty

    def _distance_from_known(self, sig: Signature) -> float:
        """How structurally different is this from known structures?

        Based on the derivation chain length and move diversity.
        """
        chain = sig.derivation_chain
        if not chain:
            return 0.0

        # Longer derivation chain = more distant
        length_score = min(len(chain) / 5, 1.0)

        # Diverse moves = more creative exploration
        move_kinds = set()
        for step in chain:
            for kind in ["Abstract", "Dualize", "Complete", "Quotient",
                         "Internalize", "Transfer", "Deform"]:
                if kind in step:
                    move_kinds.add(kind)

        diversity_score = len(move_kinds) / 7

        return (length_score + diversity_score) / 2
