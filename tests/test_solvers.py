"""Tests for solver integrations (FOL translator, Mace4, Z3, Prover9)."""

import pytest
import numpy as np
from src.core.signature import (
    Axiom, AxiomKind, Operation, Signature, Sort,
    make_assoc_equation, make_comm_equation, make_identity_equation,
)
from src.solvers.fol_translator import FOLTranslator
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
