"""Tests for the equation parser, Signature.from_dict(), backtest loading, and failed archiving."""

import json
import shutil
from pathlib import Path

import pytest

from src.core.ast_nodes import App, Const, Equation, Var, parse_equation, parse_expr
from src.core.signature import Signature
from src.library.known_structures import KNOWN_STRUCTURES, load_all_known
from src.library.manager import LibraryManager


# --- Parser tests ---


def test_parse_expr_var():
    result = parse_expr("x")
    assert result == Var("x")


def test_parse_expr_const():
    result = parse_expr("e", constants={"e"})
    assert result == Const("e")


def test_parse_expr_binary():
    result = parse_expr("(x mul y)")
    assert result == App("mul", [Var("x"), Var("y")])


def test_parse_expr_unary():
    result = parse_expr("inv(x)")
    assert result == App("inv", [Var("x")])


def test_parse_expr_nested():
    result = parse_expr("((x mul y) mul z)")
    expected = App("mul", [App("mul", [Var("x"), Var("y")]), Var("z")])
    assert result == expected


def test_parse_expr_deeply_nested():
    result = parse_expr("(x mul (y mul z))")
    expected = App("mul", [Var("x"), App("mul", [Var("y"), Var("z")])])
    assert result == expected


def test_parse_expr_const_in_binary():
    result = parse_expr("(x mul e)", constants={"e"})
    assert result == App("mul", [Var("x"), Const("e")])


def test_parse_expr_unary_in_binary():
    result = parse_expr("(x mul inv(x))")
    expected = App("mul", [Var("x"), App("inv", [Var("x")])])
    assert result == expected


def test_parse_expr_curry_eval():
    """Parse the curry-eval adjunction pattern from discoveries."""
    result = parse_expr("(curry_mul(a) eval_mul b)")
    expected = App("eval_mul", [App("curry_mul", [Var("a")]), Var("b")])
    assert result == expected


def test_parse_expr_multiarg():
    result = parse_expr("op(a, b, c)")
    expected = App("op", [Var("a"), Var("b"), Var("c")])
    assert result == expected


def test_parse_equation():
    result = parse_equation("(x mul y) = x")
    assert result == Equation(App("mul", [Var("x"), Var("y")]), Var("x"))


def test_parse_equation_with_const():
    result = parse_equation("(x mul e) = x", constants={"e"})
    expected = Equation(App("mul", [Var("x"), Const("e")]), Var("x"))
    assert result == expected


def test_parse_equation_identity():
    result = parse_equation("(x mul inv(x)) = e", constants={"e"})
    expected = Equation(
        App("mul", [Var("x"), App("inv", [Var("x")])]),
        Const("e"),
    )
    assert result == expected


def test_parse_equation_norm():
    """Parse the norm(x) = norm(x) tautology pattern."""
    result = parse_equation("norm(x) = norm(x)")
    expected = Equation(App("norm", [Var("x")]), App("norm", [Var("x")]))
    assert result == expected


# --- Signature.from_dict() roundtrip tests ---


@pytest.mark.parametrize("name", list(KNOWN_STRUCTURES.keys()))
def test_signature_from_dict_roundtrip(name):
    """from_dict(sig.to_dict()) produces an equivalent signature for all known structures."""
    original = KNOWN_STRUCTURES[name]()
    d = original.to_dict()
    reconstructed = Signature.from_dict(d)

    # Same fingerprint
    assert reconstructed.fingerprint() == original.fingerprint(), (
        f"{name}: fingerprint mismatch"
    )

    # Same structure
    assert len(reconstructed.sorts) == len(original.sorts)
    assert len(reconstructed.operations) == len(original.operations)
    assert len(reconstructed.axioms) == len(original.axioms)

    # Same sort names
    assert [s.name for s in reconstructed.sorts] == [s.name for s in original.sorts]

    # Same operation signatures
    for orig_op, new_op in zip(original.operations, reconstructed.operations):
        assert new_op.name == orig_op.name
        assert new_op.domain == orig_op.domain
        assert new_op.codomain == orig_op.codomain
        assert new_op.arity == orig_op.arity

    # Same axiom kinds
    for orig_ax, new_ax in zip(original.axioms, reconstructed.axioms):
        assert new_ax.kind == orig_ax.kind

    # Equation repr roundtrips (the key test)
    for orig_ax, new_ax in zip(original.axioms, reconstructed.axioms):
        assert repr(new_ax.equation) == repr(orig_ax.equation), (
            f"{name}: equation mismatch for {orig_ax.kind}: "
            f"{repr(orig_ax.equation)} != {repr(new_ax.equation)}"
        )


# --- Discovery loading tests ---


def test_backtest_loads_discoveries():
    """Verify backtest can load and reconstruct all discoveries without error."""
    discovered_dir = Path("library/discovered")
    if not discovered_dir.exists():
        pytest.skip("No discoveries directory")

    files = sorted(discovered_dir.glob("disc_*.json"))
    if not files:
        pytest.skip("No discovery files")

    errors = []
    for f in files:
        data = json.loads(f.read_text())
        try:
            sig = Signature.from_dict(data["signature"])
            # Verify the reconstructed signature has the right shape
            assert len(sig.sorts) > 0, f"{f.name}: no sorts"
            assert len(sig.operations) > 0, f"{f.name}: no operations"
            # Verify equation repr roundtrips
            for ax in sig.axioms:
                repr_str = repr(ax.equation)
                assert len(repr_str) > 0, f"{f.name}: empty equation repr"
        except Exception as e:
            errors.append(f"{f.name}: {e}")

    assert not errors, f"Failed to load {len(errors)} discoveries:\n" + "\n".join(errors)


def test_backtest_discovery_fingerprints():
    """Verify reconstructed signatures produce consistent fingerprints."""
    discovered_dir = Path("library/discovered")
    if not discovered_dir.exists():
        pytest.skip("No discoveries directory")

    files = sorted(discovered_dir.glob("disc_*.json"))
    if not files:
        pytest.skip("No discovery files")

    for f in files:
        data = json.loads(f.read_text())
        sig = Signature.from_dict(data["signature"])
        stored_fp = data["signature"].get("fingerprint")
        if stored_fp:
            assert sig.fingerprint() == stored_fp, (
                f"{f.name}: fingerprint mismatch: {sig.fingerprint()} != {stored_fp}"
            )


# --- Failed archiving tests ---


@pytest.fixture
def tmp_library(tmp_path):
    """Create a temporary library with a fake discovery."""
    lib = LibraryManager(tmp_path / "library")
    disc_dir = tmp_path / "library" / "discovered"
    disc_data = {
        "id": "disc_9999",
        "name": "FakeStructure",
        "signature": {"name": "Fake", "sorts": [], "operations": [], "axioms": []},
        "score": 0.5,
        "score_breakdown": {"has_models": 1.0},
        "fingerprint": "abcd1234abcd1234",
    }
    (disc_dir / "disc_9999_FakeStructure.json").write_text(json.dumps(disc_data, indent=2))
    return lib


def test_archive_failed_moves_file(tmp_library):
    """archive_failed() moves file from discovered/ to failed/."""
    # Verify it exists in discovered
    assert len(tmp_library.list_discovered()) == 1

    dest = tmp_library.archive_failed("disc_9999", "no models found")
    assert dest is not None
    assert dest.exists()
    assert "failed" in str(dest)

    # No longer in discovered
    assert len(tmp_library.list_discovered()) == 0

    # Present in failed
    assert len(tmp_library.list_failed()) == 1


def test_archive_failed_annotates_reason(tmp_library):
    """Archived file contains backtest_status and backtest_reason."""
    tmp_library.archive_failed("disc_9999", "no models found")
    failed = tmp_library.list_failed()
    assert len(failed) == 1
    assert failed[0]["backtest_status"] == "FAIL"
    assert failed[0]["backtest_reason"] == "no models found"


def test_archive_failed_not_found(tmp_library):
    """archive_failed() returns None for nonexistent ID."""
    result = tmp_library.archive_failed("disc_0000", "test")
    assert result is None


def test_archive_failed_not_in_fingerprints(tmp_library):
    """Archived discoveries are excluded from all_fingerprints()."""
    fps_before = set(tmp_library.all_fingerprints())
    assert "abcd1234abcd1234" in fps_before

    tmp_library.archive_failed("disc_9999", "no models found")

    fps_after = set(tmp_library.all_fingerprints())
    assert "abcd1234abcd1234" not in fps_after
