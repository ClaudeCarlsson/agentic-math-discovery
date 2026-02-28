"""Tests for solver integrations (FOL translator, Mace4, Z3, Prover9)."""

import pytest
import numpy as np
from src.core.signature import (
    Axiom, AxiomKind, Operation, Signature, Sort,
    make_assoc_equation, make_comm_equation, make_identity_equation,
    make_self_distrib_equation, make_right_self_distrib_equation,
)
from src.solvers.fol_translator import FOLTranslator
from src.solvers.mace4 import ModelSpectrum
from src.models.cayley import CayleyTable, models_are_isomorphic
from src.library.known_structures import semigroup, group, magma


class TestFOLTranslator:
    @pytest.fixture
    def translator(self):
        return FOLTranslator()

    def test_mace4_output_format(self, translator):
        sig = semigroup()
        output = translator.to_mace4(sig, domain_size=3)
        assert "assign(domain_size, 3)" in output
        assert "formulas(assumptions)" in output
        assert "end_of_list" in output

    def test_mace4_includes_axioms(self, translator):
        sig = semigroup()
        output = translator.to_mace4(sig, domain_size=3)
        # Should contain the associativity equation
        assert "mul" in output

    def test_prover9_output_format(self, translator):
        sig = semigroup()
        conj = make_comm_equation("mul")
        output = translator.to_prover9(sig, conj)
        assert "formulas(assumptions)" in output
        assert "formulas(goals)" in output

    def test_empty_axioms(self, translator):
        sig = magma()
        output = translator.to_mace4(sig, domain_size=2)
        assert "formulas(assumptions)" in output


class TestCayleyTable:
    def test_latin_square(self):
        # Z/3Z addition table is a Latin square
        table = np.array([
            [0, 1, 2],
            [1, 2, 0],
            [2, 0, 1],
        ])
        ct = CayleyTable(size=3, tables={"add": table})
        assert ct.is_latin_square("add")

    def test_not_latin_square(self):
        table = np.array([
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ])
        ct = CayleyTable(size=3, tables={"mul": table})
        assert not ct.is_latin_square("mul")

    def test_commutative(self):
        table = np.array([
            [0, 1, 2],
            [1, 2, 0],
            [2, 0, 1],
        ])
        ct = CayleyTable(size=3, tables={"add": table})
        assert ct.is_commutative("add")

    def test_has_identity(self):
        # Z/3Z addition: 0 is identity
        table = np.array([
            [0, 1, 2],
            [1, 2, 0],
            [2, 0, 1],
        ])
        ct = CayleyTable(size=3, tables={"add": table})
        assert ct.has_identity("add") == 0

    def test_no_identity(self):
        # Constant operation: everything maps to 0. No identity exists.
        table = np.array([
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ])
        ct = CayleyTable(size=3, tables={"mul": table})
        assert ct.has_identity("mul") is None

    def test_is_associative(self):
        # Z/3Z addition is associative
        table = np.array([
            [0, 1, 2],
            [1, 2, 0],
            [2, 0, 1],
        ])
        ct = CayleyTable(size=3, tables={"add": table})
        assert ct.is_associative("add")

    def test_symmetry_score_latin(self):
        table = np.array([
            [0, 1, 2],
            [1, 2, 0],
            [2, 0, 1],
        ])
        ct = CayleyTable(size=3, tables={"add": table})
        score = ct.symmetry_score("add")
        assert score == 1.0  # Perfect Latin square

    def test_row_entropy(self):
        # Latin square has maximum entropy per row
        table = np.array([
            [0, 1, 2],
            [1, 2, 0],
            [2, 0, 1],
        ])
        ct = CayleyTable(size=3, tables={"add": table})
        entropy = ct.row_entropy("add")
        assert entropy > 1.0  # High entropy

    def test_to_dict_roundtrip(self):
        table = np.array([[0, 1], [1, 0]])
        ct = CayleyTable(size=2, tables={"mul": table}, constants={"e": 0})
        d = ct.to_dict()
        ct2 = CayleyTable.from_dict(d)
        assert ct2.size == 2
        assert np.array_equal(ct2.tables["mul"], table)
        assert ct2.constants["e"] == 0


class TestIsomorphism:
    def test_identical_models(self):
        table = np.array([[0, 1], [1, 0]])
        m1 = CayleyTable(size=2, tables={"mul": table})
        m2 = CayleyTable(size=2, tables={"mul": table.copy()})
        assert models_are_isomorphic(m1, m2, "mul")

    def test_different_size(self):
        m1 = CayleyTable(size=2, tables={"mul": np.array([[0, 1], [1, 0]])})
        m2 = CayleyTable(size=3, tables={"mul": np.zeros((3, 3), dtype=int)})
        assert not models_are_isomorphic(m1, m2, "mul")

    def test_isomorphic_by_relabeling(self):
        # Z/2Z: 0+0=0, 0+1=1, 1+0=1, 1+1=0
        t1 = np.array([[0, 1], [1, 0]])
        # Same but with 0,1 swapped: 1+1=1, 1+0=0, 0+1=0, 0+0=1
        t2 = np.array([[1, 0], [0, 1]])
        m1 = CayleyTable(size=2, tables={"mul": t1})
        m2 = CayleyTable(size=2, tables={"mul": t2})
        assert models_are_isomorphic(m1, m2, "mul")


class TestZ3Solver:
    """Tests for Z3-based model finding."""

    @pytest.fixture
    def z3_finder(self):
        from src.solvers.z3_solver import Z3ModelFinder
        finder = Z3ModelFinder(timeout_ms=10000)
        if not finder.is_available():
            pytest.skip("z3-solver not installed")
        return finder

    def test_magma_has_models(self, z3_finder):
        """A magma (no axioms) should have models at every size."""
        result = z3_finder.find_models(magma(), domain_size=2, max_models=1)
        assert len(result.models_found) >= 1

    def test_semigroup_has_models(self, z3_finder):
        """A semigroup should have models at small sizes."""
        result = z3_finder.find_models(semigroup(), domain_size=2, max_models=1)
        assert len(result.models_found) >= 1

    def test_semigroup_model_is_associative(self, z3_finder):
        """Models found for semigroup should satisfy associativity."""
        result = z3_finder.find_models(semigroup(), domain_size=3, max_models=1)
        if result.models_found:
            model = result.models_found[0]
            assert model.is_associative("mul")

    def test_group_size2(self, z3_finder):
        """There's exactly one group of order 2 (Z/2Z)."""
        result = z3_finder.find_models(group(), domain_size=2, max_models=5)
        assert len(result.models_found) >= 1
        # Check that the model has an identity
        for m in result.models_found:
            assert m.has_identity("mul") is not None

    def test_spectrum_computation(self, z3_finder):
        """Test computing model spectrum for a semigroup."""
        spectrum = z3_finder.compute_spectrum(semigroup(), min_size=2, max_size=3)
        assert 2 in spectrum.spectrum
        assert 3 in spectrum.spectrum
        assert spectrum.spectrum[2] >= 1

    def test_timeout_sets_timed_out_flag(self):
        """When Z3 times out, the result should have timed_out=True."""
        from src.solvers.z3_solver import Z3ModelFinder
        finder = Z3ModelFinder(timeout_ms=1)
        if not finder.is_available():
            pytest.skip("z3-solver not installed")
        # Group at size 10 is complex enough to not finish in 1ms
        result = finder.find_models(group(), domain_size=10, max_models=1)
        assert result.timed_out is True


class TestTimeoutPropagation:
    """Ensure timed_out_sizes is populated by all solver compute_spectrum paths."""

    def test_z3_spectrum_propagates_timeout(self):
        """Z3 compute_spectrum should record timed-out sizes."""
        from src.solvers.z3_solver import Z3ModelFinder
        finder = Z3ModelFinder(timeout_ms=1)
        if not finder.is_available():
            pytest.skip("z3-solver not installed")
        spectrum = finder.compute_spectrum(group(), min_size=8, max_size=10)
        # With 1ms timeout, sizes 8-10 should time out
        assert len(spectrum.timed_out_sizes) > 0

    def test_mace4_fallback_propagates_timeout(self):
        """Mace4Fallback compute_spectrum should record timed-out sizes."""
        from src.solvers.mace4 import Mace4Fallback
        # Use 1ms Z3 timeout (timeout=1 means 1 sec → 1000ms, but we
        # need sub-second; construct directly via find_models instead)
        from src.solvers.z3_solver import Z3ModelFinder
        if not Z3ModelFinder().is_available():
            pytest.skip("z3-solver not installed")
        # Create a fallback that wraps a very short Z3 timeout
        fallback = Mace4Fallback(timeout=1)  # 1 second
        # Group at size 20 should timeout in 1 second
        result = fallback.find_models(group(), domain_size=20, max_models=1)
        # Verify the timed_out flag is set on the result
        assert result.timed_out is True
        # Now verify compute_spectrum propagates it
        spectrum = fallback.compute_spectrum(group(), min_size=10, max_size=10)
        assert len(spectrum.timed_out_sizes) > 0


class TestSymmetryBreaking:
    """Test that symmetry breaking is applied to heavy signatures."""

    def test_heavy_sig_detected(self):
        """Single-sorted + SD + no CUSTOM → detected as heavy."""
        from src.solvers.z3_solver import Z3ModelFinder
        sig = Signature(
            name="HeavyTest",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.SELF_DISTRIBUTIVITY,
                      make_self_distrib_equation("mul"), ["mul"]),
            ],
        )
        assert Z3ModelFinder._is_heavy_signature(sig)

    def test_light_sig_not_detected(self):
        """A plain semigroup should NOT be detected as heavy."""
        from src.solvers.z3_solver import Z3ModelFinder
        assert not Z3ModelFinder._is_heavy_signature(semigroup())

    def test_heavy_with_custom_not_detected(self):
        """Single-sorted + SD + CUSTOM axioms → NOT heavy (quasigroup-like)."""
        from src.solvers.z3_solver import Z3ModelFinder
        from src.core.ast_nodes import Equation, Var, App
        a, b = Var("a"), Var("b")
        sig = Signature(
            name="QuasigroupSD",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.SELF_DISTRIBUTIVITY,
                      make_self_distrib_equation("mul"), ["mul"]),
                Axiom(AxiomKind.CUSTOM,
                      Equation(App("mul", [a, b]), App("mul", [a, b])),
                      ["mul"], "cancellation"),
            ],
        )
        assert not Z3ModelFinder._is_heavy_signature(sig)

    def test_multi_sorted_not_detected(self):
        """Multi-sorted + SD → NOT heavy (cross-sort risk)."""
        from src.solvers.z3_solver import Z3ModelFinder
        sig = Signature(
            name="MultiSortSD",
            sorts=[Sort("S"), Sort("T")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.SELF_DISTRIBUTIVITY,
                      make_self_distrib_equation("mul"), ["mul"]),
            ],
        )
        assert not Z3ModelFinder._is_heavy_signature(sig)

    def test_symmetry_breaking_still_finds_models(self):
        """Heavy sig with symmetry breaking should still find valid models."""
        from src.solvers.z3_solver import Z3ModelFinder
        finder = Z3ModelFinder(timeout_ms=10000)
        if not finder.is_available():
            pytest.skip("z3-solver not installed")
        # Build a self-distributive magma (no associativity, just SD)
        sig = Signature(
            name="SDMagma",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.SELF_DISTRIBUTIVITY,
                      make_self_distrib_equation("mul"), ["mul"]),
            ],
        )
        result = finder.find_models(sig, domain_size=3, max_models=1)
        assert len(result.models_found) >= 1
        assert not result.timed_out

    def test_full_sd_finds_models(self):
        """Full self-distributivity (left + right) should find models with symmetry breaking."""
        from src.solvers.z3_solver import Z3ModelFinder
        finder = Z3ModelFinder(timeout_ms=15000)
        if not finder.is_available():
            pytest.skip("z3-solver not installed")
        sig = Signature(
            name="FullSD",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.SELF_DISTRIBUTIVITY,
                      make_self_distrib_equation("mul"), ["mul"]),
                Axiom(AxiomKind.RIGHT_SELF_DISTRIBUTIVITY,
                      make_right_self_distrib_equation("mul"), ["mul"]),
            ],
        )
        result = finder.find_models(sig, domain_size=2, max_models=1)
        # Size 2 with full SD should be solvable
        assert not result.timed_out


class TestSmartSolverRouter:
    """Test the SmartSolverRouter routing logic."""

    def test_router_classifies_heavy_as_z3_heavy(self):
        """Single-sorted + heavy axioms should route to z3_heavy (Mace4 not available)."""
        from src.solvers.router import SmartSolverRouter
        router = SmartSolverRouter()
        sig = Signature(
            name="HeavySig",
            sorts=[Sort("S")],
            operations=[Operation("mul", ["S", "S"], "S")],
            axioms=[
                Axiom(AxiomKind.SELF_DISTRIBUTIVITY,
                      make_self_distrib_equation("mul"), ["mul"]),
            ],
        )
        route = router.classify(sig)
        # Mace4 is likely not installed in test env; should be z3_heavy
        assert route in ("z3_heavy", "mace4_heavy")

    def test_router_classifies_normal(self):
        """A plain semigroup should route to z3_normal."""
        from src.solvers.router import SmartSolverRouter
        router = SmartSolverRouter()
        assert router.classify(semigroup()) == "z3_normal"

    def test_router_finds_models(self):
        """Router should find models for a semigroup."""
        from src.solvers.router import SmartSolverRouter
        router = SmartSolverRouter()
        if not router.is_available():
            pytest.skip("No solvers available")
        result = router.find_models(semigroup(), domain_size=2, max_models=1)
        assert len(result.models_found) >= 1

    def test_router_spectrum_has_timeout_tracking(self):
        """Router compute_spectrum should track timed-out sizes."""
        from src.solvers.router import SmartSolverRouter
        router = SmartSolverRouter(z3_timeout_ms=1)
        if not router.is_available():
            pytest.skip("No solvers available")
        spectrum = router.compute_spectrum(group(), min_size=10, max_size=10)
        assert len(spectrum.timed_out_sizes) > 0


class TestScoringTimeoutAwareness:
    """Test that the scoring engine distinguishes timeout from proven-0."""

    def test_has_models_proven_zero(self):
        """Proven 0 models (no timeouts) should score has_models=0.0."""
        from src.scoring.engine import ScoringEngine
        scorer = ScoringEngine()
        sig = Signature(name="Empty", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Empty",
            spectrum={2: 0, 3: 0, 4: 0},
            timed_out_sizes=[],
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert score.has_models == 0.0

    def test_has_models_timed_out_is_inconclusive(self):
        """0 models with timeouts should score has_models=0.5 (inconclusive)."""
        from src.scoring.engine import ScoringEngine
        scorer = ScoringEngine()
        sig = Signature(name="Hard", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Hard",
            spectrum={2: 0, 3: 0, 4: 0},
            timed_out_sizes=[3, 4],
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert score.has_models == 0.5

    def test_has_models_with_actual_models(self):
        """Spectrum with real models should still score has_models=1.0."""
        from src.scoring.engine import ScoringEngine
        scorer = ScoringEngine()
        sig = Signature(name="Good", sorts=[Sort("S")], operations=[], axioms=[])
        spectrum = ModelSpectrum(
            signature_name="Good",
            spectrum={2: 1, 3: 0, 4: 0},
            timed_out_sizes=[4],
        )
        score = scorer.score(sig, spectrum=spectrum)
        assert score.has_models == 1.0
