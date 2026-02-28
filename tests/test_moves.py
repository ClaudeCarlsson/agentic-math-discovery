"""Tests for the 7 structural moves."""

import pytest
from src.moves.engine import MoveEngine, MoveKind
from src.library.known_structures import (
    group, ring, lattice, semigroup, monoid, magma, quasigroup,
    load_all_known,
)


@pytest.fixture
def engine():
    return MoveEngine()


class TestDualize:
    def test_dualize_semigroup(self, engine):
        """Dualizing a semigroup should add commutativity to 'mul'."""
        results = engine.dualize(semigroup())
        assert len(results) >= 1
        for r in results:
            assert r.move == MoveKind.DUALIZE
            assert any(a.kind.value == "COMMUTATIVITY" for a in r.signature.axioms)

    def test_dualize_commutative_noop(self, engine):
        """Dualizing a commutative operation should produce nothing."""
        from src.library.known_structures import abelian_group
        results = engine.dualize(abelian_group())
        # mul is already commutative, so no results for it
        mul_duals = [r for r in results if "mul" in r.signature.name]
        assert len(mul_duals) == 0


class TestComplete:
    def test_complete_magma_adds_identity(self, engine):
        """Completing a magma should offer adding an identity."""
        results = engine.complete(magma())
        identity_results = [r for r in results if "id" in r.signature.name.lower()]
        assert len(identity_results) >= 1

    def test_complete_semigroup_adds_identity(self, engine):
        results = engine.complete(semigroup())
        names = [r.signature.name for r in results]
        assert any("id" in n for n in names)

    def test_complete_adds_second_op(self, engine):
        """Completing should offer adding a second binary operation."""
        results = engine.complete(semigroup())
        op2_results = [r for r in results if "op2" in r.signature.name]
        assert len(op2_results) >= 1
        for r in op2_results:
            assert any(a.kind.value == "DISTRIBUTIVITY" for a in r.signature.axioms)


class TestQuotient:
    def test_quotient_adds_commutativity(self, engine):
        results = engine.quotient(semigroup())
        comm_results = [
            r for r in results
            if any(a.kind.value == "COMMUTATIVITY" for a in r.signature.axioms)
        ]
        assert len(comm_results) >= 1

    def test_quotient_adds_idempotence(self, engine):
        results = engine.quotient(semigroup())
        idem_results = [
            r for r in results
            if any(a.kind.value == "IDEMPOTENCE" for a in r.signature.axioms)
        ]
        assert len(idem_results) >= 1


class TestAbstract:
    def test_abstract_group_ring(self, engine):
        """Abstracting Group and Ring should find shared axiom kinds."""
        results = engine.abstract(group(), ring())
        assert len(results) >= 1
        # Both have associativity, identity, inverse
        for r in results:
            axiom_kinds = {a.kind for a in r.signature.axioms}
            assert any(k.value == "ASSOCIATIVITY" for k in axiom_kinds)

    def test_abstract_no_shared(self, engine):
        """Two structures with no shared axiom kinds produce nothing."""
        # Magma has no axioms
        results = engine.abstract(magma(), group())
        assert len(results) == 0


class TestInternalize:
    def test_internalize_creates_hom_sort(self, engine):
        results = engine.internalize(semigroup())
        assert len(results) >= 1
        for r in results:
            sort_names = [s.name for s in r.signature.sorts]
            assert any("Hom" in s for s in sort_names)

    def test_internalize_has_eval_and_curry(self, engine):
        results = engine.internalize(semigroup())
        for r in results:
            op_names = [op.name for op in r.signature.operations]
            assert any("eval" in n for n in op_names)
            assert any("curry" in n for n in op_names)


class TestTransfer:
    def test_transfer_creates_morphism(self, engine):
        results = engine.transfer(group(), ring())
        assert len(results) >= 1
        for r in results:
            op_names = [op.name for op in r.signature.operations]
            assert "transfer" in op_names

    def test_transfer_has_functoriality(self, engine):
        results = engine.transfer(group(), ring())
        for r in results:
            assert any(a.kind.value == "FUNCTORIALITY" for a in r.signature.axioms)


class TestDeform:
    def test_deform_creates_parameter(self, engine):
        results = engine.deform(semigroup())
        assert len(results) >= 1
        for r in results:
            sort_names = [s.name for s in r.signature.sorts]
            assert any("Param" in s for s in sort_names)

    def test_deform_removes_original_axiom(self, engine):
        original = semigroup()
        n_axioms = len(original.axioms)
        results = engine.deform(original)
        for r in results:
            # Should have the same number of axioms (one removed, one deformed added)
            # or more if deformation adds extra operations
            assert len(r.signature.axioms) >= n_axioms - 1


class TestApplyAll:
    def test_apply_all_produces_candidates(self, engine):
        results = engine.apply_all_moves([semigroup(), group()])
        assert len(results) > 0

    def test_depth2_produces_more(self, engine):
        depth1 = engine.apply_all_moves([magma()])
        depth2_inputs = [r.signature for r in depth1]
        depth2 = engine.apply_all_moves(depth2_inputs)
        assert len(depth2) > len(depth1)


class TestPerformance:
    def test_all_known_depth1(self, engine):
        """Depth-1 on all known structures should complete quickly."""
        import time
        structures = load_all_known()
        start = time.time()
        results = engine.apply_all_moves(structures)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Depth-1 took {elapsed:.2f}s (should be <5s)"
        assert len(results) > 50
