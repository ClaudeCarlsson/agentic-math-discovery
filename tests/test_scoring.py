"""Tests for the interestingness scoring engine."""

import pytest
from src.scoring.engine import ScoringEngine, ScoreBreakdown
from src.core.signature import Axiom, AxiomKind, Operation, Signature, Sort, make_assoc_equation
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
