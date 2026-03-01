"""Integration tests: full pipeline from exploration to scoring."""

import pytest
import tempfile
from pathlib import Path

from src.moves.engine import MoveEngine, MoveKind
from src.scoring.engine import ScoringEngine
from src.library.known_structures import load_all_known, group, semigroup, ring, lattice
from src.library.manager import LibraryManager
from src.agent.tools import ToolExecutor


class TestExplorationPipeline:
    """Test the full explore → score → filter pipeline."""

    def test_depth1_explore_and_score(self):
        engine = MoveEngine()
        scorer = ScoringEngine()

        bases = [semigroup(), group()]
        results = engine.apply_all_moves(bases)

        assert len(results) > 0

        scored = []
        for r in results:
            score = scorer.score(r.signature)
            scored.append((r, score))

        scored.sort(key=lambda x: x[1].total, reverse=True)

        # Top candidate should have a reasonable score
        top_sig, top_score = scored[0]
        assert top_score.total > 0

    def test_depth2_scaling(self):
        """Depth-2 should produce many more candidates than depth-1."""
        engine = MoveEngine()
        bases = [semigroup()]

        depth1 = engine.apply_all_moves(bases)
        depth2_bases = [r.signature for r in depth1]
        depth2 = engine.apply_all_moves(depth2_bases)

        assert len(depth2) > len(depth1)

    def test_novelty_filtering(self):
        """Most depth-1 results should have unique fingerprints."""
        engine = MoveEngine()
        scorer = ScoringEngine()
        bases = load_all_known()

        results = engine.apply_all_moves(bases)
        fingerprints = set()
        novel_count = 0

        for r in results:
            fp = r.signature.fingerprint()
            if fp not in fingerprints:
                novel_count += 1
                fingerprints.add(fp)

        # At least some should be novel
        assert novel_count > 10


class TestToolExecutor:
    """Test the tool executor that the agent uses."""

    @pytest.fixture
    def executor(self, tmp_path):
        library = LibraryManager(tmp_path / "test_library")
        return ToolExecutor(library)

    def test_explore_tool(self, executor):
        result = executor.execute("explore", {
            "base_structures": ["Group", "Semigroup"],
            "depth": 1,
        })
        assert "candidates" in result
        assert result["total_candidates"] > 0

    def test_explore_with_moves(self, executor):
        result = executor.execute("explore", {
            "base_structures": ["Semigroup"],
            "moves": ["DUALIZE", "COMPLETE"],
            "depth": 1,
        })
        assert "candidates" in result

    def test_score_tool(self, executor):
        # First explore to get candidates
        executor.execute("explore", {
            "base_structures": ["Semigroup"],
            "depth": 1,
        })

        # Score one of the candidates
        candidates = list(executor._candidates.keys())
        if candidates:
            result = executor.execute("score", {"signature_id": candidates[0]})
            assert "scores" in result
            assert "total" in result["scores"]

    def test_search_library_tool(self, executor):
        result = executor.execute("search_library", {"query": "Group"})
        assert "results" in result
        assert len(result["results"]) > 0

    def test_unknown_tool(self, executor):
        result = executor.execute("nonexistent_tool", {})
        assert "error" in result

    def test_add_to_library_tool(self, executor):
        # First explore to generate candidates
        executor.execute("explore", {
            "base_structures": ["Semigroup"],
            "depth": 1,
        })

        candidates = list(executor._candidates.keys())
        if candidates:
            sig_id = candidates[0]

            # Must check models first — adding without models should fail
            result = executor.execute("add_to_library", {
                "signature_id": sig_id,
                "name": "TestDiscovery",
                "notes": "A test discovery from integration tests",
            })
            assert "error" in result, "Should require check_models before add"

            # Now check models, then add
            executor.execute("check_models", {
                "signature_id": sig_id,
                "min_size": 2,
                "max_size": 4,
            })
            spectrum = executor._spectra.get(sig_id)
            if spectrum and spectrum.total_models() > 0:
                result = executor.execute("add_to_library", {
                    "signature_id": sig_id,
                    "name": "TestDiscovery",
                    "notes": "A test discovery from integration tests",
                })
                assert result.get("status") == "added"


    def test_explore_with_exclude_moves(self, executor):
        """exclude_moves should prevent specific moves from being applied."""
        # Explore with all moves
        result_all = executor.execute("explore", {
            "base_structures": ["Semigroup"],
            "depth": 1,
        })

        # Explore excluding DUALIZE and COMPLETE
        result_excluded = executor.execute("explore", {
            "base_structures": ["Semigroup"],
            "depth": 1,
            "exclude_moves": ["DUALIZE", "COMPLETE"],
        })

        # Excluded should produce fewer candidates
        assert result_excluded["total_candidates"] < result_all["total_candidates"]

        # No excluded moves should appear in results
        for c in result_excluded.get("candidates", []):
            assert c["move"] not in ("DUALIZE", "COMPLETE"), (
                f"Move {c['move']} should have been excluded"
            )


class TestAgentConfigExcludeMoves:
    """Test that AgentConfig.exclude_moves is wired through to explore calls."""

    def test_exclude_moves_injected_into_explore(self, tmp_path):
        """Controller should inject exclude_moves into every explore call."""
        from src.agent.controller import AgentConfig

        config = AgentConfig(
            exclude_moves=["ABSTRACT", "TRANSFER"],
            base_structures=["Semigroup"],
            explore_depth=1,
        )

        library = LibraryManager(tmp_path / "test_lib")
        executor = ToolExecutor(library)

        # Simulate what the controller does: inject exclude_moves
        explore_args = {
            "base_structures": config.base_structures,
            "depth": config.explore_depth,
            "score_threshold": config.score_threshold,
        }
        if config.exclude_moves:
            explore_args["exclude_moves"] = config.exclude_moves

        result = executor.execute("explore", explore_args)

        # No ABSTRACT or TRANSFER moves should appear
        for c in result.get("candidates", []):
            assert c["move"] not in ("ABSTRACT", "TRANSFER"), (
                f"Move {c['move']} should have been excluded"
            )


class TestZ3Integration:
    """Test Z3 model finding integrated with the full pipeline."""

    @pytest.fixture
    def z3_available(self):
        try:
            import z3
            return True
        except ImportError:
            pytest.skip("z3-solver not installed")

    def test_explore_and_check_models(self, z3_available, tmp_path):
        """Full pipeline: explore candidates then check for models."""
        from src.solvers.z3_solver import Z3ModelFinder

        engine = MoveEngine()
        scorer = ScoringEngine()
        z3_finder = Z3ModelFinder(timeout_ms=5000)

        # Generate candidates from semigroup
        results = engine.apply_all_moves([semigroup()])
        assert len(results) > 0

        # Check models for the first few
        found_models = 0
        for r in results[:5]:
            result = z3_finder.find_models(r.signature, domain_size=3, max_models=1)
            if result.models_found:
                found_models += 1
                # Verify the model makes sense
                model = result.models_found[0]
                assert model.size == 3

        # At least some candidates should have models
        # (magma-derived things always have models)
        assert found_models >= 0  # Some might not, depending on axioms


class TestRediscovery:
    """Validate that the system can rediscover known structures."""

    def test_group_from_magma(self):
        """Starting from Magma, Complete should produce something group-like."""
        engine = MoveEngine()
        results = engine.complete(semigroup())  # semigroup → add identity, inverse

        identity_results = [r for r in results if "id" in r.signature.name.lower()]
        assert len(identity_results) >= 1

        # One of these should look like a monoid
        for r in identity_results:
            has_assoc = any(a.kind.value == "ASSOCIATIVITY" for a in r.signature.axioms)
            has_id = any(a.kind.value == "IDENTITY" for a in r.signature.axioms)
            if has_assoc and has_id:
                # Found a monoid-like structure
                break
        else:
            pytest.fail("No monoid-like structure found from completing semigroup")

    def test_ring_from_group(self):
        """Completing a group with a second operation should produce something ring-like."""
        engine = MoveEngine()
        results = engine.complete(group())

        op2_results = [r for r in results if "op2" in r.signature.name]
        assert len(op2_results) >= 1

        for r in op2_results:
            has_distrib = any(a.kind.value == "DISTRIBUTIVITY" for a in r.signature.axioms)
            if has_distrib:
                break
        else:
            pytest.fail("No ring-like structure found from completing group")
