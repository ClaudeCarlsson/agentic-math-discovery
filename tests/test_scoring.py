"""Tests for the interestingness scoring engine."""

import pytest
from src.scoring.engine import ScoringEngine, ScoreBreakdown
from src.core.signature import (
    Axiom, AxiomKind, Operation, Signature, Sort,
    make_assoc_equation, make_self_distrib_equation,
    make_right_self_distrib_equation, make_idempotent_equation,
)
from src.solvers.mace4 import ModelSpectrum


@pytest.fixture
def scorer():
    return ScoringEngine()


class TestStructuralScores:
    def test_economy_small_is_good(self, scorer):
        """Small signatures should score well on economy."""
        small = Signature(
            name="Small",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"])],
        )
        score = scorer.score(small)
        assert score.economy > 0.5

    def test_economy_large_is_penalized(self, scorer):
        """Large signatures should score poorly on economy."""
        large = Signature(
            name="Large",
            sorts=[Sort(f"S{i}") for i in range(5)],
            operations=[Operation(f"op{i}", ["S0", "S0"], "S0") for i in range(10)],
            axioms=[Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation(f"op{i}"), [f"op{i}"])
                    for i in range(10)],
        )
        score = scorer.score(large)
        assert score.economy < 0.5

    def test_richness_balanced(self, scorer):
        """A signature with equal ops and axioms should score well on richness."""
        balanced = Signature(
            name="Balanced",
            sorts=[Sort("S")],
            operations=[
                Operation("mul", ["S", "S"], "S"),
                Operation("add", ["S", "S"], "S"),
            ],
            axioms=[
                Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"]),
                Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("add"), ["add"]),
            ],
        )
        score = scorer.score(balanced)
        assert score.richness > 0.9

    def test_tension_diverse_axioms(self, scorer):
        """Diverse axiom kinds should score well on tension."""
        from src.core.signature import make_comm_equation
        diverse = Signature(
            name="Diverse",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"]),
                Axiom(AxiomKind.COMMUTATIVITY, make_comm_equation("mul"), ["mul"]),
            ],
        )
        single = Signature(
            name="Single",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"]),
            ],
        )
        diverse_score = scorer.score(diverse)
        single_score = scorer.score(single)
        assert diverse_score.tension > single_score.tension


class TestNovelty:
    def test_novel_when_fingerprint_unknown(self, scorer):
        sig = Signature(
            name="Novel",
            sorts=[Sort("S"), Sort("T")],
            operations=[Operation("mul", ["S", "T"], "S")],
            axioms=[],
        )
        score = scorer.score(sig, known_fingerprints=set())
        assert score.is_novel == 1.0

    def test_not_novel_when_fingerprint_known(self, scorer):
        sig = Signature(
            name="Known",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[],
        )
        fp = sig.fingerprint()
        score = scorer.score(sig, known_fingerprints={fp})
        assert score.is_novel == 0.0


class TestModelScores:
    def test_has_models(self, scorer):
        sig = Signature(name="Test", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Test",
            spectrum={2: 1, 3: 2, 4: 3},
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert score.has_models == 1.0

    def test_no_models(self, scorer):
        sig = Signature(name="Test", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Test",
            spectrum={2: 0, 3: 0, 4: 0},
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert score.has_models == 0.0

    def test_spectrum_pattern_primes(self, scorer):
        sig = Signature(name="Test", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Test",
            spectrum={2: 1, 3: 1, 4: 0, 5: 1, 6: 0, 7: 1},
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert score.spectrum_pattern > 0.7  # Prime pattern detected


class TestSolverDifficulty:
    def test_no_timeouts_scores_high(self, scorer):
        """A clean spectrum with no timeouts should score well."""
        sig = Signature(name="Test", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Test",
            spectrum={2: 1, 3: 2, 4: 3},
            timed_out_sizes=[],
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert score.solver_difficulty == 1.0

    def test_all_timeouts_scores_zero(self, scorer):
        """If all sizes timed out, solver_difficulty should be 0."""
        sig = Signature(name="Test", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Test",
            spectrum={2: 0, 3: 0, 4: 0},
            timed_out_sizes=[2, 3, 4],
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert score.solver_difficulty == 0.0

    def test_partial_timeouts_penalized(self, scorer):
        """Partial timeouts should reduce solver_difficulty proportionally."""
        sig = Signature(name="Test", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Test",
            spectrum={2: 1, 3: 2, 4: 0, 5: 0},
            timed_out_sizes=[4, 5],
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert 0.0 < score.solver_difficulty < 1.0

    def test_flat_spectrum_penalized(self, scorer):
        """A trivially flat spectrum (same count at every size) should be penalized."""
        sig = Signature(name="Test", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Test",
            spectrum={2: 5, 3: 5, 4: 5, 5: 5},
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert score.solver_difficulty < 1.0  # Flatness penalty applied

    def test_varied_spectrum_not_penalized(self, scorer):
        """A spectrum with varied counts should not get flatness penalty."""
        sig = Signature(name="Test", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Test",
            spectrum={2: 1, 3: 2, 4: 5},
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert score.solver_difficulty == 1.0


class TestSpectrumPatternRefined:
    def test_consecutive_sizes_score_low(self, scorer):
        """Consecutive sizes {2,3,4,5} should score lower than non-trivial gap."""
        sig = Signature(name="Test", sorts=[Sort("S")], operations=[], axioms=[])
        consecutive = ModelSpectrum(
            signature_name="Test",
            spectrum={2: 1, 3: 1, 4: 1, 5: 1},
        )
        gapped = ModelSpectrum(
            signature_name="Test",
            spectrum={2: 1, 4: 1, 6: 1, 8: 1},
        )
        consec_score = scorer.score(sig, spectrum=consecutive)
        gapped_score = scorer.score(sig, spectrum=gapped)
        assert gapped_score.spectrum_pattern > consec_score.spectrum_pattern


class TestTotalScore:
    def test_total_is_weighted_sum(self, scorer):
        sig = Signature(
            name="Test",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"])],
        )
        score = scorer.score(sig)
        # Total should be between 0 and 1
        assert 0 <= score.total <= 1.0

    def test_score_breakdown_to_dict(self):
        breakdown = ScoreBreakdown(connectivity=0.5, richness=0.8, total=0.65)
        d = breakdown.to_dict()
        assert d["connectivity"] == 0.5
        assert d["richness"] == 0.8
        assert d["total"] == 0.65


class TestEconomySteeper:
    def test_economy_steeper_past_8(self, scorer):
        """11 components should score ~0.52 with steeper penalty."""
        # 2 sorts + 5 ops + 4 axioms = 11 components
        sig = Signature(
            name="Bloated",
            sorts=[Sort("S"), Sort("T")],
            operations=[Operation(f"op{i}", ["S", "S"], "S") for i in range(5)],
            axioms=[Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation(f"op{i}"), [f"op{i}"])
                    for i in range(4)],
        )
        score = scorer.score(sig)
        # 11 components: 1.0 - (11-5)*0.08 = 1.0 - 0.48 = 0.52
        assert abs(score.economy - 0.52) < 0.01


class TestAxiomSynergy:
    def test_synergy_quandle_instinct(self, scorer):
        """IDEMPOTENCE + SELF_DISTRIBUTIVITY on same op -> 0.9."""
        sig = Signature(
            name="QuandleLike",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.IDEMPOTENCE, make_idempotent_equation("mul"), ["mul"]),
                Axiom(AxiomKind.SELF_DISTRIBUTIVITY, make_self_distrib_equation("mul"), ["mul"]),
            ],
        )
        score = scorer.score(sig)
        assert score.axiom_synergy == 0.9

    def test_synergy_full_distrib(self, scorer):
        """Left + right self-distributivity on same op -> 1.0."""
        sig = Signature(
            name="FullSD",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.SELF_DISTRIBUTIVITY, make_self_distrib_equation("mul"), ["mul"]),
                Axiom(AxiomKind.RIGHT_SELF_DISTRIBUTIVITY, make_right_self_distrib_equation("mul"), ["mul"]),
            ],
        )
        score = scorer.score(sig)
        assert score.axiom_synergy == 1.0

    def test_synergy_none(self, scorer):
        """Just ASSOCIATIVITY -> 0.0 synergy."""
        sig = Signature(
            name="JustAssoc",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.ASSOCIATIVITY, make_assoc_equation("mul"), ["mul"]),
            ],
        )
        score = scorer.score(sig)
        assert score.axiom_synergy == 0.0

    def test_synergy_in_to_dict(self):
        """axiom_synergy should appear in to_dict()."""
        breakdown = ScoreBreakdown(axiom_synergy=0.9)
        d = breakdown.to_dict()
        assert "axiom_synergy" in d
        assert d["axiom_synergy"] == 0.9
