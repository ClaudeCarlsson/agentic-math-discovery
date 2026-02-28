# Getting Started

This guide walks you through installing the system, running your first exploration, and understanding what the output means. By the end, you will have generated candidate algebraic structures, checked them for finite models, and (optionally) launched the LLM-driven research agent.

No background in abstract algebra is required. If you know what a function is and can read Python, you have enough.

---

## 1. Prerequisites

You need:

- **Python 3.11 or newer**. Check with `python3 --version`.
- **pip**. Comes with Python on most systems. Check with `pip --version`.

That is all. No virtual environment is required for a quick start, though you are welcome to use one.

---

## 2. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/ClaudeCarlsson/agentic-math-discovery.git
cd agentic-math-discovery
```

Install the core dependencies:

```bash
pip install click rich pydantic networkx numpy z3-solver
```

These provide:

| Package | Purpose |
|---------|---------|
| `click` | CLI framework |
| `rich` | Colored terminal output, tables, trees |
| `pydantic` | Data validation |
| `networkx` | Graph analysis for connectivity scoring |
| `numpy` | Cayley table representation |
| `z3-solver` | SAT/SMT solver for finding finite models of algebraic structures |

### Optional dependencies

```bash
# For the LLM-driven research agent — requires the Claude Code CLI
npm install -g @anthropic-ai/claude-code
claude auth    # authenticate once

# For running the test suite
pip install pytest pytest-cov ruff
```

### External tools (optional)

The system can also use **Mace4** (model finder) and **Prover9** (theorem prover) from the LADR suite. These are not required. When they are not installed, the system falls back to Z3 for model finding. Z3 handles the vast majority of use cases on its own.

If you want to install them anyway, see https://www.cs.unm.edu/~mccune/prover9/.

---

## 3. Verify Installation

Run these three commands to confirm everything is working:

```bash
python3 run.py --help
```

You should see the top-level help listing all available commands:

```
Usage: run.py [OPTIONS] COMMAND [ARGS]...

  Agentic AI for Mathematical Structure Discovery.

Options:
  --library-path TEXT  Path to the library directory
  --help               Show this message and exit.

Commands:
  agent            Run the LLM-driven research agent.
  explore          Explore the space of algebraic structures using...
  inspect          Inspect a specific structure in detail.
  list-structures  List all known algebraic structures in the library.
  report           View discovery reports.
```

Next, list the built-in structures:

```bash
python3 run.py list-structures
```

This should print 15 known algebraic structures with their sorts, operations, and axioms. If it runs without errors, your core dependencies are installed correctly.

Finally, run the test suite:

```bash
python3 -m pytest tests/ -v
```

You should see 169 tests passing. If any fail, check that you have `z3-solver` installed (`pip install z3-solver`).

---

## 4. Understanding the Output

When you run `list-structures`, the system prints every known algebraic structure in a tree format. Here is what the output for **Group** looks like:

```
╭──────────────────── Signature: Group ────────────────────╮
│ Group                                                     │
│ ├── Sorts                                                 │
│ │   └── G: group elements                                 │
│ ├── Operations                                            │
│ │   ├── mul: G x G -> G                                   │
│ │   ├── e: () -> G                                        │
│ │   └── inv: G -> G                                       │
│ └── Axioms                                                │
│     ├── [ASSOCIATIVITY] ASSOCIATIVITY                     │
│     ├── [IDENTITY] IDENTITY                               │
│     └── [INVERSE] INVERSE                                 │
╰───────────────────────────────────────────────────────────╯
```

Three concepts define every algebraic structure:

### Sorts (types)

A sort is a named set of elements. Group has one sort called `G`, described as "group elements." Think of it as a type declaration: every element in the structure belongs to `G`.

Some structures have multiple sorts. For example, **VectorSpace** has two: `V` (vectors) and `K` (scalars). **Category** has `Ob` (objects) and `Mor` (morphisms).

### Operations (typed functions)

An operation is a function with typed inputs and a typed output.

- `mul: G x G -> G` -- takes two group elements, returns a group element (binary operation)
- `e: () -> G` -- takes no inputs, returns a group element (constant / identity element)
- `inv: G -> G` -- takes one group element, returns a group element (unary operation)

The number of inputs is the operation's **arity**: `mul` has arity 2 (binary), `inv` has arity 1 (unary), `e` has arity 0 (constant).

### Axioms (equational laws)

An axiom is an equation that the operations must satisfy. Group has three:

- **ASSOCIATIVITY**: `mul(mul(x, y), z) = mul(x, mul(y, z))` -- grouping does not matter
- **IDENTITY**: `mul(x, e) = x` -- multiplying by `e` changes nothing
- **INVERSE**: `mul(x, inv(x)) = e` -- every element has an inverse

These are the rules of the game. When the system generates a new candidate structure, it defines it by choosing sorts, operations, and axioms. When the solver checks for models, it searches for concrete Cayley tables (multiplication tables) that satisfy all the axioms simultaneously.

---

## 5. Your First Exploration

Run this command:

```bash
python3 run.py explore --base Semigroup --base Group --depth 1 --top 10
```

This tells the system:

- Start from **Semigroup** and **Group** as base structures
- Apply all 8 structural moves once (`--depth 1`)
- Show the top 10 candidates by interestingness score

### What "depth 1" means

At depth 1, each of the 8 structural moves is applied once to each base structure:

| Move | What it does |
|------|-------------|
| **ABSTRACT** | Extract shared axioms from two structures (pairwise) |
| **DUALIZE** | Add commutativity to a non-commutative operation |
| **COMPLETE** | Add missing structure: identity elements, inverses, second operations, norms |
| **QUOTIENT** | Force additional equations (commutativity, idempotence) |
| **INTERNALIZE** | Turn an operation into a first-class sort (Hom-objects) |
| **TRANSFER** | Combine two structures with a homomorphism between them |
| **DEFORM** | Weaken an axiom with a deformation parameter (q-analogs) |
| **SELF_DISTRIB** | Add left and/or full (left+right) self-distributivity |

Six moves (DUALIZE, COMPLETE, QUOTIENT, INTERNALIZE, DEFORM, SELF_DISTRIB) apply to each structure individually. Two moves (ABSTRACT, TRANSFER) apply to pairs of structures. With 2 base structures, depth 1 typically produces a few dozen candidates.

### How to read the results table

The output looks like this:

```
                    Exploration Results
┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┳━━━━━━━┓
┃ # ┃ Name                           ┃ Move     ┃ Score ┃ S/O/A ┃
┡━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━╇━━━━━━━┩
│ 1 │ Group+op2                      │ COMPLETE │ 0.542 │ 1/4/4 │
│ 2 │ Semigroup+op2                  │ COMPLETE │ 0.521 │ 1/2/2 │
│ 3 │ Transfer(Semigroup,Group)      │ TRANSFER │ 0.498 │ 2/5/4 │
│ 4 │ Group_deform(ASSOCIATIVITY)    │ DEFORM   │ 0.465 │ 2/4/3 │
│ ...                                                           │
└───┴────────────────────────────────┴──────────┴───────┴───────┘
```

Each column:

- **#** -- rank by score
- **Name** -- the name of the candidate structure, derived from its parent and the move applied
- **Move** -- which structural move produced this candidate
- **Score** -- overall interestingness score (0 to 1). This is a weighted sum of 10 dimensions (see Section 10 for links)
- **S/O/A** -- counts of Sorts, Operations, and Axioms. A structure with `2/5/4` has 2 sorts, 5 operations, and 4 axioms

### What the score means (briefly)

The score combines 12 dimensions, each normalized to [0, 1]:

| Dimension | Measures |
|-----------|----------|
| connectivity | How well operations connect the sorts |
| richness | Axiom-to-operation ratio (best near 1:1) |
| tension | Diversity of axiom kinds |
| economy | Simplicity (smaller is better, up to a point) |
| fertility | Potential for further constructions |
| axiom_synergy | Known-good axiom combinations on binary ops |
| has_models | Whether finite models exist (0 or 1) |
| model_diversity | How many non-isomorphic models across sizes |
| spectrum_pattern | Whether the model spectrum has mathematical structure |
| solver_difficulty | Penalizes solver timeouts and trivially flat spectra |
| is_novel | Not isomorphic to any known structure (0 or 1) |
| distance | How far from the nearest known structure |

At depth 1 without `--check-models`, the model-theoretic dimensions (has_models, model_diversity, spectrum_pattern) are all 0 because no solver has run yet. The score reflects only structural properties. To get the full picture, add `--check-models`.

---

## 6. Checking Models

Run this command:

```bash
python3 run.py explore --base Group --depth 1 --check-models --max-size 4
```

This does everything from the previous section, and then for each top candidate, it asks Z3: "Does this set of axioms have a concrete finite model of size 2? Size 3? Size 4?"

### What model checking does

A **finite model** is a concrete Cayley table (a multiplication table like you might have seen in grade school) that satisfies all the axioms of a structure. Z3 encodes each operation as an integer lookup table over the domain `{0, 1, ..., n-1}` and each axiom as a set of constraints. If it finds a satisfying assignment, that assignment *is* the model.

For example, a Group of size 2 has a multiplication table like:

```
mul | 0  1
----+------
 0  | 0  1
 1  | 1  0
```

with `e = 0` and `inv(0) = 0, inv(1) = 1`. Z3 discovers tables like this automatically.

### How to read the spectrum

When model checking runs, you see output like:

```
  Checking Group+op2...
    Models found! Spectrum: {2: 2, 3: 5, 4: 16}

        Model Spectrum: Group+op2
    ┏━━━━━━┳━━━━━━━━┳━━━━━━━━━━┓
    ┃ Size ┃ Models ┃ Visual   ┃
    ┡━━━━━━╇━━━━━━━━╇━━━━━━━━━━┩
    │    2 │      2 │ ██       │
    │    3 │      5 │ █████    │
    │    4 │     16 │ ████████ │
    └──────┴────────┴──────────┘

    Sizes with models: [2, 3, 4]
    Total models: 23
```

The **spectrum** maps each domain size to the number of non-isomorphic models found at that size. Here:

- Size 2: 2 distinct models
- Size 3: 5 distinct models
- Size 4: 16 distinct models

### What it means when a structure has or does not have models

- **Models found**: The axioms are *consistent* -- there exist concrete mathematical objects satisfying them. This is the first test of whether a candidate is "real mathematics" rather than a vacuous set of contradictions.
- **No models found up to size N**: Either the axioms are inconsistent (contradictory, so no model of any size exists) or the smallest model is larger than N. Increasing `--max-size` can reveal models at larger sizes, but takes more time.

Structures with models at multiple sizes, and especially those whose spectra show a pattern (only primes, only powers of 2, regular gaps), score highest on model-theoretic dimensions.

---

## 7. Inspecting Structures

To examine a single structure in depth, use `inspect`:

```bash
python3 run.py inspect Group --max-size 5
```

This command does three things:

**1. Shows the full signature definition** -- the same tree you saw in `list-structures`, with all sorts, operations, and axioms.

**2. Computes the interestingness score** -- first a *pre-model* score (structural dimensions only), then a *post-model* score (after checking for finite models). You see both as tables:

```
     Interestingness Score: Group
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Dimension        ┃ Score                         ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ connectivity     │ 0.500 ██████████░░░░░░░░░░    │
│ richness         │ 1.000 ████████████████████    │
│ tension          │ 0.500 ██████████░░░░░░░░░░    │
│ economy          │ 0.920 ██████████████████░░    │
│ fertility        │ 0.333 ██████░░░░░░░░░░░░░░    │
│ has_models       │ 0.000 ░░░░░░░░░░░░░░░░░░░░    │
│ model_diversity  │ 0.000 ░░░░░░░░░░░░░░░░░░░░    │
│ spectrum_pattern │ 0.000 ░░░░░░░░░░░░░░░░░░░░    │
│ is_novel         │ 0.000 ░░░░░░░░░░░░░░░░░░░░    │
│ distance         │ 0.000 ░░░░░░░░░░░░░░░░░░░░    │
│ total            │ 0.272 █████░░░░░░░░░░░░░░░    │
└──────────────────┴───────────────────────────────┘
```

**3. Checks for finite models** up to the specified size and displays the model spectrum. After model checking, the score is recomputed with the model-theoretic dimensions filled in, so you can compare the pre-model and post-model scores.

`inspect` is the tool to use when a candidate from `explore` catches your eye and you want the full picture.

---

## 8. Depth-2 Exploration

Now try a deeper search:

```bash
python3 run.py explore --depth 2 --base Semigroup
```

### What depth 2 means

At depth 1, the 8 structural moves are applied directly to the base structures. At depth 2, the results from depth 1 become the *new* base structures, and all 8 moves are applied again.

This is where it gets interesting. A single Semigroup at depth 1 might produce 10 candidates. At depth 2, each of those 10 becomes a base for another round, potentially producing 100+ candidates. With all 15 known structures as bases, depth 2 generates roughly 95,000 candidates.

```
Depth 1: Semigroup  -->  [A, B, C, D, ...]     (a few dozen)
Depth 2: [A, B, C, D, ...]  -->  [AA, AB, AC, BA, BB, ...]  (hundreds to thousands)
```

Each depth-2 candidate is a *composition* of two moves. For example, you might get a structure that was first COMPLETED (add an identity element) and then DEFORMED (weaken associativity). These compound transformations explore corners of the algebraic landscape that no single move can reach.

### Combinatorial explosion is the point

The system is designed to explore what humans cannot. A mathematician might manually construct a few variations of a semigroup. The system generates thousands, scores them all, and surfaces the most interesting ones. The scoring engine acts as a filter, separating genuine novelty from noise.

If you want to focus the search, use `--moves` to restrict which moves are applied and `--threshold` to filter out low-scoring candidates:

```bash
python3 run.py explore --depth 2 --base Semigroup --base Lattice \
  --moves COMPLETE --moves DEFORM --threshold 0.3 --top 20
```

This applies only COMPLETE and DEFORM at each depth, starting from Semigroup and Lattice, showing only candidates scoring above 0.3.

---

## 9. Running the Agent

The LLM agent wraps the entire exploration pipeline in an autonomous research loop. Instead of you choosing which structures and moves to try, Claude (via the Claude Code CLI) makes those decisions, interprets the results, forms conjectures, and records discoveries.

### Setup

Install and authenticate the Claude Code CLI:

```bash
npm install -g @anthropic-ai/claude-code
claude auth    # authenticate once
```

### Running it

```bash
python3 run.py agent --cycles 3 --goal "find novel algebraic structures"
```

By default this uses Claude Opus 4.6 with high-effort thinking. You can customize:

```bash
python3 run.py agent --model sonnet --effort medium --cycles 5
```

### What happens in each cycle

The agent runs 4 phases per cycle, with live progress output at every step:

```
1. PLAN      Claude designs the exploration strategy (which bases, moves, depth)
2. EXECUTE   Tools run locally: generate candidates, check models via Z3
3. INTERPRET Claude analyzes results, proposes conjectures
4. ACT       Add discoveries to persistent library, log conjectures
```

You'll see timestamped log lines, spinners with elapsed timers during Claude calls, per-candidate model checking status, and Claude's reasoning summaries printed inline. You'll always know exactly what it's doing and how long it's been running.

The agent has access to 6 local tools: `explore`, `check_models`, `prove`, `score`, `search_library`, and `add_to_library`. Claude outputs structured JSON plans, and the controller executes these tools on its behalf.

### Where reports are saved

After each cycle, a Markdown report is written to the `library/reports/` directory:

```
library/
  reports/
    cycle_001_report.md
    cycle_002_report.md
    cycle_003_report.md
```

Each report contains:

- The research goal
- Statistics: how many candidates were generated, how many had models, how many were added as discoveries
- Top candidates with their names, moves, parents, and scores
- Discovered structures
- The agent's reasoning (its natural language interpretation of the results)

### Viewing results

To read the latest report in your terminal:

```bash
python3 run.py report --cycle latest
```

To view a specific cycle:

```bash
python3 run.py report --cycle 2
```

The report command renders the saved Markdown file with Rich formatting and also lists all discovered structures with their scores.

### Customizing the agent

You can steer the agent's focus with `--goal` and `--base`:

```bash
# Targeted search: structures combining order theory and group theory
python3 run.py agent --cycles 5 \
  --goal "find structures that combine lattice operations with group inverses" \
  --base Lattice --base Group

# Broad exploration with deeper search
python3 run.py agent --cycles 10 --depth 2 --goal "explore broadly"

# Use a faster model with less thinking effort
python3 run.py agent --model sonnet --effort medium --cycles 5
```

The default base structures are Group, Ring, Lattice, and Quasigroup. The default model is `claude-opus-4-6` with `--effort high`. Increasing `--cycles` lets the agent build on its own discoveries across cycles; each cycle sees the results of all previous ones.

---

## 10. What's Next

Now that you have the basics, explore the detailed documentation:

| Document | What you will learn |
|----------|-------------------|
| [Structural Moves](structural-moves.md) | How each of the 8 moves transforms a signature, with before/after examples |
| [Scoring](scoring.md) | The 10 interestingness dimensions, their weights, and why each matters |
| [Examples](examples.md) | Worked examples: discovering commutative semigroups, q-deformed groups, and more |
| [Contributing](contributing.md) | How to add new structures, moves, scoring dimensions, and solvers |

For deeper architectural understanding:

| Document | What you will learn |
|----------|-------------------|
| [Architecture](architecture.md) | System design, data flow between components, and design decisions |
| [Known Structures](known-structures.md) | Reference for all 15 seed algebraic structures in the library |
| [Solvers](solvers.md) | How Z3, Mace4, and Prover9 are integrated and when each is used |
| [Agent](agent.md) | The LLM agent's prompt, tool interface, and multi-turn cycle design |
| [API Reference](api-reference.md) | Python API for programmatic use outside the CLI |
