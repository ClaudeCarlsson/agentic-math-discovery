# Agentic AI for Mathematical Structure Discovery

A neuro-symbolic system for automated theory formation in universal algebra. It discovers structurally novel algebraic structures by combining LLM-driven search with formal verification.

## Architecture

```
Agent Controller (LLM) ← plans, interprets, conjectures
        ↓
   Tool Interface
        ↓
┌───────────┬───────────┬──────────┐
│ Structure │   Model   │  Proof   │
│  Engine   │  Checker  │  Engine  │
│ 7 moves   │ Mace4/Z3  │ Prover9  │
└───────────┴───────────┴──────────┘
        ↓
┌───────────┬───────────┐
│  Scorer   │  Library  │
│ Interest  │  Manager  │
└───────────┴───────────┘
```

## The 7 Structural Moves

| # | Move | What it does |
|---|------|-------------|
| 1 | ABSTRACT | Extract shared structure from two signatures |
| 2 | DUALIZE | Reverse arrows / add commutativity |
| 3 | COMPLETE | Add missing structure (identity, inverse, second op, norm) |
| 4 | QUOTIENT | Force additional equations (commutativity, idempotence) |
| 5 | INTERNALIZE | Turn an operation into a first-class sort (Hom-objects) |
| 6 | TRANSFER | Map structure between domains via a homomorphism |
| 7 | DEFORM | Introduce a parameter that relaxes an axiom |

## Quick Start

```bash
# Install dependencies
pip install click rich pydantic networkx numpy z3-solver anthropic

# List known algebraic structures
python3 run.py list-structures

# Explore: generate candidates from known structures
python3 run.py explore --depth 1 --top 20

# Explore with model checking (requires z3-solver)
python3 run.py explore --depth 2 --check-models --max-size 6

# Focus on specific structures and moves
python3 run.py explore --base Group --base Ring --depth 2

# Inspect a specific structure
python3 run.py inspect Group --max-size 4

# Run the LLM agent (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=your-key
python3 run.py agent --cycles 5 --goal "find structures with positivity"

# View reports
python3 run.py report --cycle latest
```

## 14 Known Seed Structures

Magma, Semigroup, Monoid, Group, AbelianGroup, Ring, Field, Lattice, Quasigroup, Loop, LieAlgebra, VectorSpace, InnerProductSpace, Category

## Interestingness Scoring

Candidates are scored across 10 dimensions:

- **Structural**: connectivity, richness, tension, economy, fertility
- **Model-theoretic**: has_models, model_diversity, spectrum_pattern
- **Novelty**: is_novel, distance from known structures

## Testing

```bash
python3 -m pytest tests/ -v
```

## External Tools (Optional)

- **Mace4/Prover9**: Finite model finding and theorem proving. Install from https://www.cs.unm.edu/~mccune/prover9/
- **Z3**: SMT solver (used as fallback). `pip install z3-solver`
- **Lean 4**: Formal proof assistant. https://leanprover.github.io/
