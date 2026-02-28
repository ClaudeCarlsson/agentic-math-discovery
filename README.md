# Agentic AI for Mathematical Structure Discovery

A neuro-symbolic system for **automated theory formation** in universal algebra. It discovers structurally novel algebraic structures by combining LLM-driven strategic search with formal verification via SAT/SMT solvers.

The system navigates the combinatorial space of algebraic identities using 7 predefined structural moves, grounds every candidate in finite model theory, scores results for mathematical interestingness, and uses an LLM agent to steer the search toward genuinely novel mathematics.

> *"The computer is incredibly fast, accurate, and stupid. Man is incredibly slow, inaccurate, and brilliant. The marriage of the two is a force beyond calculation."*
> — attributed to Leo Cherne

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [The Discovery Loop](#the-discovery-loop)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Testing](#testing)
- [Hardware Requirements](#hardware-requirements)
- [License](#license)

---

## Why This Exists

Conventional AI struggles with creative mathematics because LLMs can hallucinate invalid proofs. This system sidesteps that problem entirely:

1. **The creativity is in the combinatorics, not the model.** We exhaustively enumerate a well-defined space of structural transformations. No approximation. No heuristics beyond scoring.
2. **Verification is complete.** If Z3/Mace4 says a structure has a model of size 7, it does. The agent can hallucinate all it wants in the planning phase — the tools catch everything.
3. **The search space is tractable.** Depth-2 compositions of 7 moves on 14 structures = ~95,000 candidates. Exhaustively checkable on a laptop in seconds.
4. **Discovery ≠ proof.** We find interesting objects; proving *why* their properties hold is a separate problem for human mathematicians.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   AGENT CONTROLLER                       │
│               (Claude / local LLM)                       │
│                                                          │
│  Planner → Interpreter → Conjecturer                     │
│       ↓                                                  │
│  ┌────────────────────────────────────────────────┐      │
│  │              TOOL INTERFACE                     │      │
│  │  explore()  check_models()  prove()  score()   │      │
│  │  search_library()  add_to_library()            │      │
│  └──────────────────┬─────────────────────────────┘      │
└─────────────────────┼────────────────────────────────────┘
                      │
     ┌────────────────┼────────────────────────┐
     │                ▼       TOOL LAYER        │
     │                                          │
     │  ┌────────────┐  ┌──────────┐  ┌──────┐ │
     │  │ Structure  │  │  Model   │  │Proof │ │
     │  │  Engine    │  │ Checker  │  │Engine│ │
     │  │ (7 moves)  │  │(Z3/Mace4)│  │(P9)  │ │
     │  └────────────┘  └──────────┘  └──────┘ │
     │                                          │
     │  ┌────────────┐  ┌──────────────────┐    │
     │  │  Scorer    │  │ Library Manager   │    │
     │  │(10 dims)   │  │(JSON persistence) │    │
     │  └────────────┘  └──────────────────┘    │
     │                                          │
     └──────────────────────────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for the full architectural specification.

---

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
git clone https://github.com/your-org/agentic-math-discovery.git
cd agentic-math-discovery

# Install core dependencies
pip install click rich pydantic networkx numpy z3-solver

# (Optional) For the LLM agent
pip install anthropic

# (Optional) For development
pip install pytest pytest-cov ruff
```

### Your First Exploration

```bash
# See all 14 known algebraic structures
python3 run.py list-structures

# Generate candidates from Group and Ring at depth 1
python3 run.py explore --base Group --base Ring --depth 1 --top 10

# Run depth-2 exploration with Z3 model checking
python3 run.py explore --base Semigroup --depth 2 --check-models --max-size 6

# Inspect a specific structure in detail
python3 run.py inspect Group --max-size 5
```

### Running the LLM Agent

```bash
export ANTHROPIC_API_KEY=your-key-here

# Broad exploration: 5 cycles
python3 run.py agent --cycles 5 --goal "explore broadly"

# Targeted search
python3 run.py agent --cycles 10 \
  --goal "find structures with positivity that constrain spectra" \
  --base InnerProductSpace --base LieAlgebra

# View the results
python3 run.py report --cycle latest
```

See [docs/getting-started.md](docs/getting-started.md) for a full walkthrough.

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `list-structures` | Display all 14 known algebraic structures with their sorts, operations, and axioms |
| `explore` | Generate candidate structures using structural moves, optionally check for models |
| `inspect <name>` | Deep-dive into a specific structure: show definition, score, and finite models |
| `agent` | Run the LLM-driven autonomous research loop |
| `report` | View cycle reports and discovered structures |

### `explore` Options

```
--depth N          Search depth: 1 = direct moves, 2 = compositions (default: 1)
--base NAME        Base structures to start from (repeatable; default: all 14)
--moves NAME       Specific moves to apply (repeatable; default: all 7)
--check-models     Run Z3/Mace4 on top candidates to find finite models
--max-size N       Maximum model size for model checking (default: 6)
--threshold F      Minimum interestingness score to display (default: 0.0)
--top N            Number of top candidates to show (default: 20)
```

### `agent` Options

```
--model NAME       LLM model to use (default: claude-sonnet-4-6)
--cycles N         Number of research cycles (default: 5)
--goal TEXT        Research goal in natural language
--depth N          Exploration depth per cycle (default: 2)
--max-size N       Maximum model size (default: 6)
--base NAME        Base structures (repeatable)
```

---

## The Discovery Loop

Each cycle of the agent follows this pattern:

```
1. ASSESS   → Review library and recent discoveries
2. PLAN     → Choose structures, moves, and depth
3. EXECUTE  → Run explore(), check_models(), score()
4. INTERPRET → LLM analyzes top candidates
5. CONJECTURE → Propose testable mathematical statements
6. VERIFY   → Test conjectures via model checking / Prover9
7. UPDATE   → Add discoveries to persistent library
8. REPORT   → Generate human-readable Markdown summary
```

See [docs/agent.md](docs/agent.md) for the full agent specification.

---

## Project Structure

```
agentic-math-discovery/
├── run.py                         # CLI entry point
├── pyproject.toml                 # Project metadata and dependencies
├── src/
│   ├── cli.py                     # Click CLI commands
│   ├── core/                      # Core data structures
│   │   ├── ast_nodes.py           #   Expression AST (Var, Const, App, Equation)
│   │   └── signature.py           #   Algebraic signatures (Sort, Operation, Axiom)
│   ├── moves/
│   │   └── engine.py              # The 7 structural moves
│   ├── models/
│   │   └── cayley.py              # Cayley table representation and analysis
│   ├── solvers/
│   │   ├── fol_translator.py      # Signature → first-order logic translation
│   │   ├── z3_solver.py           # Z3-based finite model finder
│   │   ├── mace4.py               # Mace4 integration + fallback
│   │   └── prover9.py             # Prover9 theorem prover integration
│   ├── scoring/
│   │   └── engine.py              # 10-dimensional interestingness scorer
│   ├── agent/
│   │   ├── controller.py          # LLM agent loop
│   │   └── tools.py               # Tool definitions and executor
│   ├── library/
│   │   ├── known_structures.py    # 14 seed algebraic structures
│   │   └── manager.py             # Persistent storage for discoveries
│   └── utils/
│       └── display.py             # Rich console output
├── tests/                         # 95 tests across 6 test files
│   ├── test_core.py               # AST and signature tests
│   ├── test_moves.py              # Structural move tests
│   ├── test_scoring.py            # Scoring engine tests
│   ├── test_solvers.py            # Solver and Cayley table tests
│   ├── test_library.py            # Library and known structure tests
│   └── test_integration.py        # End-to-end pipeline tests
├── library/                       # Persistent data (gitignored except known/)
│   ├── known/
│   ├── discovered/
│   ├── conjectures/
│   └── reports/
└── docs/                          # Detailed documentation
    ├── architecture.md
    ├── getting-started.md
    ├── structural-moves.md
    ├── scoring.md
    ├── solvers.md
    ├── agent.md
    ├── known-structures.md
    ├── api-reference.md
    ├── examples.md
    └── contributing.md
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System design, data flow, component responsibilities |
| [Getting Started](docs/getting-started.md) | Installation, first run, interpreting results |
| [Structural Moves](docs/structural-moves.md) | Detailed specification of all 7 moves with examples |
| [Scoring](docs/scoring.md) | How interestingness is measured across 10 dimensions |
| [Solvers](docs/solvers.md) | Z3, Mace4, and Prover9 integration details |
| [Agent](docs/agent.md) | LLM agent loop, tool interface, prompt engineering |
| [Known Structures](docs/known-structures.md) | Reference for all 14 seed algebraic structures |
| [API Reference](docs/api-reference.md) | Python API for programmatic use |
| [Examples](docs/examples.md) | Worked examples and tutorials |
| [Contributing](docs/contributing.md) | How to add moves, structures, and scoring dimensions |

---

## Testing

```bash
# Run all 95 tests
python3 -m pytest tests/ -v

# Run a specific test file
python3 -m pytest tests/test_moves.py -v

# Run with coverage
python3 -m pytest tests/ --cov=src --cov-report=term-missing
```

Test categories:
- **test_core.py** — AST nodes, signatures, fingerprinting, equation builders
- **test_moves.py** — All 7 structural moves, performance benchmarks
- **test_scoring.py** — Scoring dimensions, weights, model-theoretic scores
- **test_solvers.py** — FOL translation, Cayley tables, Z3 model finding
- **test_library.py** — Known structures, library manager, persistence
- **test_integration.py** — Full pipeline, tool executor, rediscovery tests

---

## Hardware Requirements

| Setup | Components | Notes |
|-------|-----------|-------|
| **Minimum** (CPU only) | Structure engine + Z3 | No LLM needed. You read results yourself. |
| **Recommended** | + Claude API or local 7B model | Full agent loop with strategic search. |
| **Optimal** | + Mace4/Prover9 + 24GB GPU | Parallel model checking, larger local models. |

The core engine (structure generation, scoring, Z3 model finding) runs on any machine with Python 3.11+ and 4GB RAM. Depth-2 exploration of all 14 structures generates ~95,000 candidates in under 10 seconds.

---

## License

MIT License. See [LICENSE](LICENSE).
