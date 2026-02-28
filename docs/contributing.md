# Contributing

This guide covers how to extend the mathematical discovery system: adding new structures, moves, scoring dimensions, solvers, and axiom kinds.

---

## Development Setup

```bash
git clone https://github.com/ClaudeCarlsson/agentic-math-discovery.git
cd agentic-math-discovery
pip install click rich pydantic networkx numpy z3-solver pytest ruff
python3 -m pytest tests/ -v   # verify all tests pass
```

---

## Adding a New Known Structure

**File:** `src/library/known_structures.py`

1. Create a factory function that returns a `Signature`:

```python
def boolean_algebra() -> Signature:
    """Boolean algebra: a complemented distributive lattice."""
    from src.core.ast_nodes import Var, App, Equation

    sig = lattice()  # Start from Lattice
    sig.name = "BooleanAlgebra"
    sig.description = "A complemented distributive lattice."

    x, y, z = Var("x"), Var("y"), Var("z")

    # Add complement operation
    sig.operations.append(Operation("compl", ["L"], "L", "complement"))

    # Add distributivity of meet over join
    sig.axioms.append(Axiom(
        AxiomKind.DISTRIBUTIVITY,
        Equation(
            App("meet", [x, App("join", [y, z])]),
            App("join", [App("meet", [x, y]), App("meet", [x, z])]),
        ),
        ["meet", "join"],
        "meet distributes over join",
    ))

    # Add complement axioms
    sig.axioms.append(Axiom(
        AxiomKind.CUSTOM,
        Equation(App("join", [x, App("compl", [x])]), Const("top")),
        ["join", "compl"],
        "x ∨ ¬x = ⊤",
    ))

    return sig
```

2. Register it:

```python
KNOWN_STRUCTURES["BooleanAlgebra"] = boolean_algebra
```

3. Add tests in `tests/test_library.py`:

```python
def test_boolean_algebra_has_complement(self):
    ba = boolean_algebra()
    op_names = [op.name for op in ba.operations]
    assert "compl" in op_names
```

4. Run tests: `python3 -m pytest tests/test_library.py -v`

---

## Adding a New Structural Move

**File:** `src/moves/engine.py`

1. Add the move to `MoveKind` enum:

```python
class MoveKind(str, Enum):
    # ... existing moves ...
    RESTRICT = "RESTRICT"  # Drop an axiom
```

2. Implement the move as a method on `MoveEngine`:

```python
def restrict(self, sig: Signature) -> list[MoveResult]:
    """Drop one axiom at a time to weaken the structure."""
    results = []
    for i, axiom in enumerate(sig.axioms):
        new_sig = _deep_copy_sig(sig, f"{sig.name}_restrict({axiom.kind.value})")
        new_sig.derivation_chain.append(f"Restrict({axiom.kind.value})")
        new_sig.axioms = [a for j, a in enumerate(new_sig.axioms) if j != i]
        results.append(MoveResult(
            signature=new_sig,
            move=MoveKind.RESTRICT,
            parents=[sig.name],
            description=f"Drop {axiom.kind.value} from {sig.name}",
        ))
    return results
```

3. Register it in `apply_all_moves()` and `apply_move()`:

```python
def apply_all_moves(self, sigs):
    # ... existing single moves ...
    results.extend(self.restrict(sig))

def apply_move(self, kind, sigs):
    dispatch = {
        # ... existing entries ...
        MoveKind.RESTRICT: lambda: self._single(sigs, self.restrict),
    }
```

4. Add tests in `tests/test_moves.py`:

```python
class TestRestrict:
    def test_restrict_drops_axiom(self, engine):
        g = group()
        results = engine.restrict(g)
        assert len(results) == 3  # 3 axioms in group
        for r in results:
            assert len(r.signature.axioms) == 2
```

---

## Adding a New Scoring Dimension

**File:** `src/scoring/engine.py`

1. Add a field to `ScoreBreakdown`:

```python
@dataclass
class ScoreBreakdown:
    # ... existing fields ...
    symmetry_depth: float = 0.0  # Automorphism group complexity
```

2. Add it to `to_dict()`:

```python
def to_dict(self):
    return {
        # ... existing entries ...
        "symmetry_depth": self.symmetry_depth,
    }
```

3. Add a weight to `DEFAULT_WEIGHTS`:

```python
DEFAULT_WEIGHTS = {
    # ... existing weights (adjust to sum ≤ 1.0) ...
    "symmetry_depth": 0.05,
}
```

4. Implement the scoring method:

```python
def _symmetry_depth(self, sig: Signature, spectrum: ModelSpectrum | None) -> float:
    """Score based on automorphism group complexity of found models."""
    if not spectrum:
        return 0.0
    # ... implementation ...
```

5. Call it in `score()`:

```python
def score(self, sig, spectrum=None, known_fingerprints=None):
    # ...
    if spectrum:
        breakdown.symmetry_depth = self._symmetry_depth(sig, spectrum)
```

6. Add tests in `tests/test_scoring.py`.

---

## Adding a New Axiom Kind

**File:** `src/core/signature.py`

1. Add to the `AxiomKind` enum:

```python
class AxiomKind(str, Enum):
    # ... existing kinds ...
    CANCELLATION = "CANCELLATION"
```

2. Optionally add an equation builder:

```python
def make_left_cancel_equation(op_name: str) -> Equation:
    """Left cancellation: a*b = a*c implies b = c."""
    # Note: this is a conditional equation, which requires special handling
    # For equational encoding: we'd need to express this differently
    a, b, c = Var("a"), Var("b"), Var("c")
    # Simplified version: not directly expressible as a single equation
    # Would need to be handled as a CUSTOM axiom with description
    pass
```

3. Optionally update `_axiom_for_kind()` in `src/moves/engine.py` if the ABSTRACT move should recognize this axiom kind:

```python
def _axiom_for_kind(kind, op_name):
    dispatch = {
        # ... existing entries ...
        AxiomKind.CANCELLATION: make_left_cancel_equation,
    }
```

---

## Adding a New Solver

To add a new solver backend (e.g., CVC5):

1. Create `src/solvers/cvc5_solver.py` implementing the same interface as `Z3ModelFinder`:

```python
class CVC5ModelFinder:
    def __init__(self, timeout_ms: int = 30000): ...
    def is_available(self) -> bool: ...
    def find_models(self, sig, domain_size, max_models=10) -> Mace4Result: ...
    def compute_spectrum(self, sig, min_size, max_size, max_models_per_size) -> ModelSpectrum: ...
```

2. Add to the solver selection chain in `src/agent/tools.py`:

```python
class ToolExecutor:
    def __init__(self, library):
        self.mace4 = Mace4Solver()
        if not self.mace4.is_available():
            self.model_finder = CVC5ModelFinder()
            if not self.model_finder.is_available():
                self.model_finder = Mace4Fallback()  # Z3
        else:
            self.model_finder = self.mace4
```

---

## Code Style

- **Formatting:** Ruff with line length 100. Run `ruff check src/ tests/`
- **Types:** Use type annotations on all public functions
- **Docstrings:** Required for all public classes and functions. Use triple-quoted strings with brief description.
- **Naming:** Algebraic structures are PascalCase (Group, LieAlgebra). Operations and variables are lowercase (mul, x, y).
- **Immutability:** Core types (Sort, Operation, Axiom, Expr subclasses) are frozen dataclasses. Signature is mutable (used as a builder during move application).

---

## Testing Guidelines

- Every new feature needs tests
- Test files mirror source structure: `src/moves/engine.py` → `tests/test_moves.py`
- Use `pytest` fixtures for shared setup (engine instances, temporary library paths)
- Integration tests go in `tests/test_integration.py`
- Performance tests should assert time bounds (e.g., `assert elapsed < 5.0`)

Run the full suite before submitting:

```bash
python3 -m pytest tests/ -v
```

---

## Pull Request Checklist

- [ ] New feature has tests
- [ ] All tests pass
- [ ] `ruff check src/ tests/` has no errors
- [ ] Documentation updated (relevant docs/ file)
- [ ] CLAUDE.md updated if conventions changed
- [ ] Commit message describes the change clearly
