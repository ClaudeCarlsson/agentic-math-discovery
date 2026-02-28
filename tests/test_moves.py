"""Tests for the 8 structural moves."""

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


class TestSelfDistrib:
    def test_self_distrib_basic(self, engine):
        """Applying self-distrib to Semigroup should produce 2 results (left + full)."""
        results = engine.self_distrib(semigroup())
        assert len(results) == 2
        # First: left-only
        assert results[0].move == MoveKind.SELF_DISTRIB
        assert any(a.kind.value == "SELF_DISTRIBUTIVITY" for a in results[0].signature.axioms)
        assert not any(a.kind.value == "RIGHT_SELF_DISTRIBUTIVITY" for a in results[0].signature.axioms)
        # Second: full (left + right)
        assert any(a.kind.value == "SELF_DISTRIBUTIVITY" for a in results[1].signature.axioms)
        assert any(a.kind.value == "RIGHT_SELF_DISTRIBUTIVITY" for a in results[1].signature.axioms)

    def test_self_distrib_skip_existing(self, engine):
        """Left already present -> 1 result (full only, adding right)."""
        from src.core.signature import (
            Axiom, AxiomKind, make_self_distrib_equation,
        )
        sig = semigroup()
        sig.axioms.append(
            Axiom(AxiomKind.SELF_DISTRIBUTIVITY, make_self_distrib_equation("mul"), ["mul"])
        )
        results = engine.self_distrib(sig)
        assert len(results) == 1
        # Should be the full variant (adding right)
        assert any(a.kind.value == "RIGHT_SELF_DISTRIBUTIVITY" for a in results[0].signature.axioms)

    def test_self_distrib_skip_both_existing(self, engine):
        """Both left and right already present -> 0 results."""
        from src.core.signature import (
            Axiom, AxiomKind, make_self_distrib_equation,
            make_right_self_distrib_equation,
        )
        sig = semigroup()
        sig.axioms.append(
            Axiom(AxiomKind.SELF_DISTRIBUTIVITY, make_self_distrib_equation("mul"), ["mul"])
        )
        sig.axioms.append(
            Axiom(AxiomKind.RIGHT_SELF_DISTRIBUTIVITY, make_right_self_distrib_equation("mul"), ["mul"])
        )
        results = engine.self_distrib(sig)
        assert len(results) == 0

    def test_self_distrib_multi_op(self, engine):
        """Ring has 2 binary ops (add, mul) → should produce 4 results (2 per op)."""
        results = engine.self_distrib(ring())
        assert len(results) == 4
        names = [r.signature.name for r in results]
        assert any("add" in n for n in names)
        assert any("mul" in n for n in names)

    def test_right_self_distrib_equation(self):
        """Verify right self-distributivity equation shape: (a*b)*c = (a*c)*(b*c)."""
        from src.core.signature import make_right_self_distrib_equation
        from src.core.ast_nodes import App, Var
        eq = make_right_self_distrib_equation("mul")
        # LHS: mul(mul(a, b), c)
        assert isinstance(eq.lhs, App)
        assert eq.lhs.op_name == "mul"
        assert isinstance(eq.lhs.args[0], App)
        assert eq.lhs.args[0].op_name == "mul"
        # RHS: mul(mul(a, c), mul(b, c))
        assert isinstance(eq.rhs, App)
        assert eq.rhs.op_name == "mul"
        assert isinstance(eq.rhs.args[0], App)
        assert isinstance(eq.rhs.args[1], App)


class TestDeformRestricted:
    def test_deform_skips_idempotence(self, engine):
        """DEFORM should skip IDEMPOTENCE axioms."""
        from src.core.signature import Axiom, AxiomKind, make_idempotent_equation
        sig = semigroup()
        sig.axioms.append(
            Axiom(AxiomKind.IDEMPOTENCE, make_idempotent_equation("mul"), ["mul"])
        )
        results = engine.deform(sig)
        # Should only deform ASSOCIATIVITY, not IDEMPOTENCE
        for r in results:
            assert "IDEMPOTENCE" not in r.description

    def test_deform_skips_absorption(self, engine):
        """DEFORM should skip ABSORPTION axioms."""
        results = engine.deform(lattice())
        # Lattice has ABSORPTION axioms — those should be skipped
        for r in results:
            assert "ABSORPTION" not in r.description

    def test_deform_still_handles_associativity(self, engine):
        """DEFORM should still deform ASSOCIATIVITY."""
        results = engine.deform(semigroup())
        assert len(results) >= 1
        assert any("ASSOCIATIVITY" in r.description for r in results)


class TestExcludeMoves:
    def test_apply_move_respects_kinds(self, engine):
        """apply_move with specific kind should only apply that move."""
        results = engine.apply_move(MoveKind.DUALIZE, [semigroup()])
        for r in results:
            assert r.move == MoveKind.DUALIZE

    def test_excluded_deform_reduces_output(self, engine):
        """Excluding DEFORM from apply_all_moves should reduce candidate count."""
        all_results = engine.apply_all_moves([semigroup()])
        deform_count = sum(1 for r in all_results if r.move == MoveKind.DEFORM)
        assert deform_count > 0  # DEFORM does produce results for semigroup

        # Simulate exclusion by applying all non-DEFORM moves
        excluded = {MoveKind.DEFORM}
        filtered_results = []
        for kind in MoveKind:
            if kind not in excluded:
                filtered_results.extend(engine.apply_move(kind, [semigroup()]))
        assert len(filtered_results) < len(all_results)


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
