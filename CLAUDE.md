# CLAUDE.md — Project Instructions for AI Assistants

## What This Project Is

Agentic AI for Mathematical Structure Discovery — a neuro-symbolic system that discovers new algebraic structures by combining LLM-driven search with formal verification (Z3/Mace4). Python 3.11+, ~4,930 LOC.

## Project Layout

```
src/core/           Core data structures (AST, Signature)
src/moves/          8 structural moves (Abstract, Dualize, Complete, Quotient, Internalize, Transfer, Deform, SelfDistrib)
src/models/         Cayley table representation and analysis
src/solvers/        Z3, Mace4, Prover9 integration + smart solver router + parallel model checking
src/scoring/        12-dimensional interestingness scorer
src/agent/          LLM agent controller + tool interface
src/library/        Known structures library + persistence manager
src/utils/          Rich console display
src/cli.py          Click CLI entry point
tests/              175 tests across 7 files
docs/               Detailed documentation
```

## Key Conventions

- **Immutable core types**: `Sort`, `Operation`, `Axiom`, `Expr` subclasses are all frozen dataclasses. `Signature` is mutable (used as a builder during move application).
- **Fingerprinting**: `Signature.fingerprint()` produces a 16-char hex string for novelty checking. Two signatures with identical fingerprints have the same structural shape (sort count, operation arities, axiom kinds).
- **Moves produce `MoveResult`**: Each structural move returns a list of `MoveResult` objects containing the new signature, the move kind, parent names, and a description.
- **Scoring is always 0–1 per dimension**: The `ScoreBreakdown` dataclass has 10 float fields, each normalized to [0, 1]. The `total` field is a weighted sum.
- **Z3 as primary solver**: Mace4/Prover9 are subprocess wrappers used when installed. Z3 is always available via `pip install z3-solver` and serves as the fallback.
- **Multi-sorted signatures collapse to single-sort for model finding**: The Z3 solver encodes everything over a single integer domain `[0, n)`.

## Running Tests

```bash
python3 -m pytest tests/ -v          # All 175 tests
python3 -m pytest tests/ -v -k z3    # Just Z3 tests
```

## Running the CLI

```bash
python3 run.py list-structures
python3 run.py explore --base Group --depth 1 --top 10
python3 run.py explore --depth 2 --check-models --max-size 6 --workers 8
python3 run.py inspect Semigroup --max-size 4
python3 run.py inspect disc_0035 --max-size 6  # Inspect discovered structures by name or ID
python3 run.py agent --cycles 5 --goal "explore broadly" --workers 8 --exclude-moves ABSTRACT,TRANSFER
```

## Common Development Tasks

### Adding a new known structure
Add a factory function to `src/library/known_structures.py` and register it in the `KNOWN_STRUCTURES` dict. Follow the pattern of existing structures (return a `Signature` with sorts, operations, axioms).

### Adding a new structural move
Add a method to `MoveEngine` in `src/moves/engine.py`. It should take a `Signature` (or two for pairwise moves), return `list[MoveResult]`, and be registered in `apply_all_moves()` and `apply_move()`.

### Adding a new scoring dimension
Add a field to `ScoreBreakdown`, a weight to `DEFAULT_WEIGHTS`, and a `_method()` to `ScoringEngine` in `src/scoring/engine.py`.

### Adding a new axiom kind
Add an entry to `AxiomKind` enum in `src/core/signature.py` and optionally a `make_*_equation()` builder function.

## Dependencies

Core: `click`, `rich`, `pydantic`, `networkx`, `numpy`, `z3-solver`
Agent: Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
Dev: `pytest`, `pytest-cov`, `ruff`
