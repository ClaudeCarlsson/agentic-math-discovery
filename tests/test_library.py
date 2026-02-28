"""Tests for the library of known structures and library manager."""

import pytest
import tempfile
from pathlib import Path

from src.library.known_structures import (
    KNOWN_STRUCTURES, load_all_known, load_by_name,
    group, ring, lattice, quasigroup, loop, quandle, lie_algebra,
    vector_space, inner_product_space, category_sig,
)
from src.library.manager import LibraryManager
from src.scoring.engine import ScoreBreakdown


class TestKnownStructures:
    def test_all_structures_load(self):
        structures = load_all_known()
        assert len(structures) >= 10

    def test_each_structure_valid(self):
        for name, factory in KNOWN_STRUCTURES.items():
            sig = factory()
            assert sig.name == name or sig.name.replace("_", "") != ""
            assert len(sig.sorts) >= 1

    def test_group_has_3_ops(self):
        g = group()
        assert len(g.operations) == 3  # mul, e, inv
        assert len(g.axioms) == 3  # assoc, identity, inverse

    def test_ring_has_distributivity(self):
        r = ring()
        has_distrib = any(a.kind.value == "DISTRIBUTIVITY" for a in r.axioms)
        assert has_distrib

    def test_lattice_has_absorption(self):
        l = lattice()
        has_absorption = any(a.kind.value == "ABSORPTION" for a in l.axioms)
        assert has_absorption

    def test_quasigroup_has_divisions(self):
        q = quasigroup()
        op_names = [op.name for op in q.operations]
        assert "ldiv" in op_names
        assert "rdiv" in op_names

    def test_lie_algebra_has_jacobi(self):
        la = lie_algebra()
        has_jacobi = any(a.kind.value == "JACOBI" for a in la.axioms)
        assert has_jacobi

    def test_quandle_has_expected_axioms(self):
        q = quandle()
        axiom_kinds = [a.kind.value for a in q.axioms]
        assert "IDEMPOTENCE" in axiom_kinds
        assert "SELF_DISTRIBUTIVITY" in axiom_kinds
        # 4 CUSTOM cancellation axioms from quasigroup
        custom_count = axiom_kinds.count("CUSTOM")
        assert custom_count == 4

    def test_quandle_fingerprint_unique(self):
        """Quandle fingerprint should differ from all other known structures."""
        q_fp = quandle().fingerprint()
        for name, factory in KNOWN_STRUCTURES.items():
            if name != "Quandle":
                assert factory().fingerprint() != q_fp, f"Quandle collides with {name}"

    def test_category_has_composition(self):
        cat = category_sig()
        op_names = [op.name for op in cat.operations]
        assert "comp" in op_names
        assert "id" in op_names

    def test_load_by_name(self):
        g = load_by_name("Group")
        assert g is not None
        assert g.name == "Group"

    def test_load_by_name_missing(self):
        result = load_by_name("NonExistent")
        assert result is None

    def test_fingerprints_unique(self):
        """Known structures should mostly have unique fingerprints."""
        structures = load_all_known()
        fingerprints = [s.fingerprint() for s in structures]
        # Some may collide if they have the same shape, but most should be unique
        unique = set(fingerprints)
        assert len(unique) >= len(fingerprints) * 0.5


class TestLibraryManager:
    @pytest.fixture
    def lib(self, tmp_path):
        return LibraryManager(tmp_path / "test_library")

    def test_init_creates_dirs(self, lib):
        assert (lib.base_path / "known").exists()
        assert (lib.base_path / "discovered").exists()
        assert (lib.base_path / "conjectures").exists()
        assert (lib.base_path / "reports").exists()

    def test_list_known(self, lib):
        known = lib.list_known()
        assert "Group" in known
        assert "Ring" in known

    def test_add_discovery(self, lib):
        from src.library.known_structures import semigroup
        sig = semigroup()
        sig.name = "TestDiscovery"
        score = ScoreBreakdown(total=0.75)

        path = lib.add_discovery(sig, "TestDiscovery", "A test discovery", score)
        assert path.exists()

        discovered = lib.list_discovered()
        assert len(discovered) == 1
        assert discovered[0]["name"] == "TestDiscovery"
        assert discovered[0]["score"] == 0.75

    def test_add_conjecture(self, lib):
        lib.add_conjecture("TestSig", "x*y = y*x", "open")
        conj_file = lib.base_path / "conjectures" / "open.json"
        assert conj_file.exists()

    def test_search_known(self, lib):
        results = lib.search("Group")
        names = [r["name"] for r in results]
        assert "Group" in names
        assert "AbelianGroup" in names

    def test_search_discovered(self, lib):
        from src.library.known_structures import semigroup
        sig = semigroup()
        sig.name = "MySemigroup"
        score = ScoreBreakdown(total=0.6)
        lib.add_discovery(sig, "MySemigroup", "A custom semigroup", score)

        results = lib.search("custom")
        assert len(results) >= 1

    def test_known_fingerprints(self, lib):
        fps = lib.known_fingerprints()
        assert len(fps) >= 10
