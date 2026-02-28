# Architecture

A comprehensive specification of the system design, data flow, and component responsibilities for the Agentic AI for Mathematical Structure Discovery project.

---

## Table of Contents

- [System Overview](#system-overview)
- [Component Diagram](#component-diagram)
- [Data Flow](#data-flow)
- [Core Abstractions](#core-abstractions)
- [The Discovery Pipeline](#the-discovery-pipeline)
- [The 7 Structural Moves](#the-7-structural-moves)
- [Verification Strategy](#verification-strategy)
- [Scoring and Ranking](#scoring-and-ranking)
- [Agent Architecture](#agent-architecture)
- [Search Space Analysis](#search-space-analysis)
- [Storage and Persistence](#storage-and-persistence)
- [Extension Points](#extension-points)

---

## System Overview

The system discovers structurally novel algebraic structures by composing seven predefined transformations over a library of known mathematical objects, then verifying the results with SAT/SMT solvers.

Three properties distinguish it from conventional AI-for-math approaches:

1. **Creativity lives in the combinatorics.** The search space is an explicit graph of structural transformations. No neural network generates candidate axioms. The LLM steers which paths to explore -- it does not invent the paths.

2. **Verification is complete.** Every claim about finite models passes through Z3 or Mace4. The agent can reason loosely in its planning phase because the tools catch every error before anything enters the library.

3. **The search space is tractable.** Depth-2 composition of 7 moves on 14 seed structures produces roughly 95,000 candidates. A laptop can enumerate and score them all in under 10 seconds without model checking, or check the top few hundred with Z3 in minutes.

The architecture separates three concerns:

```
WHAT to explore       -->  Agent Controller (LLM-driven)
HOW to explore        -->  MoveEngine + ScoringEngine (deterministic)
WHETHER it's valid    -->  Z3 / Mace4 / Prover9 (formal verification)
```

---

## Component Diagram

```
                    +--------------------------------------------------+
                    |              AGENT CONTROLLER                     |
                    |        (Claude Code CLI subprocess)               |
                    |                                                   |
                    |          plan -> execute -> interpret -> act      |
                    |                                                   |
                    |   +------------------------------------------+   |
                    |   |           TOOL INTERFACE                  |   |
                    |   |                                           |   |
                    |   |   explore()      check_models()           |   |
                    |   |   prove()        score()                  |   |
                    |   |   search_library()  add_to_library()      |   |
                    |   +------------------+-----------------------+   |
                    +---------------------|----------------------------+
                                          |
              +---------------------------+---------------------------+
              |                           |                           |
              v                           v                           v
    +-------------------+     +---------------------+     +------------------+
    |    MOVE ENGINE     |     |   SOLVER LAYER      |     |  SCORING ENGINE  |
    |                    |     |                      |     |                  |
    | 7 structural moves |     | Z3ModelFinder        |     | 10 dimensions    |
    | Single: DUALIZE    |     | Mace4Solver          |     |                  |
    |   COMPLETE         |     | Mace4Fallback        |     | Structural:      |
    |   QUOTIENT         |     | Prover9Solver        |     |   connectivity   |
    |   INTERNALIZE      |     | ConjectureGenerator  |     |   richness       |
    |   DEFORM           |     | FOLTranslator        |     |   tension        |
    | Pairwise: ABSTRACT |     |                      |     |   economy        |
    |   TRANSFER         |     | CayleyTable          |     |   fertility      |
    +--------+-----------+     +----------+-----------+     |                  |
             |                            |                 | Model-theoretic: |
             |                            |                 |   has_models     |
             |                            |                 |   model_diversity|
             v                            v                 |   spectrum       |
    +-------------------+     +---------------------+      |                  |
    |  CORE TYPES        |     |   FINITE MODELS     |      | Novelty:         |
    |                    |     |                      |      |   is_novel       |
    | Signature          |     | CayleyTable          |      |   distance       |
    |   Sort             |     |   n x n tables       |      +--------+---------+
    |   Operation        |     |   Latin square?      |               |
    |   Axiom            |     |   commutative?       |               |
    | Expr (AST)         |     |   identity?          |               |
    |   Var, Const, App  |     |   associative?       |               |
    |   Equation         |     |   entropy, symmetry  |               |
    | AxiomKind (enum)   |     |   automorphisms      |               |
    |                    |     |   isomorphism check   |               |
    +--------+-----------+     +----------+-----------+               |
             |                            |                           |
             +----------------------------+---------------------------+
                                          |
                                          v
                              +---------------------+
                              |  LIBRARY MANAGER     |
                              |                      |
                              | known/    (14 seeds)  |
                              | discovered/ (JSON)    |
                              | conjectures/ (JSON)   |
                              | reports/  (Markdown)  |
                              +----------------------+
```

Dependencies flow downward. The Agent Controller depends on everything below it through the Tool Interface. The Move Engine and Solver Layer depend only on Core Types. The Scoring Engine depends on Core Types and Finite Models. The Library Manager is a leaf node used for persistence.

---

## Data Flow

A single discovery follows this path through the system:

```
  KNOWN STRUCTURES (14 seeds)
         |
         |  load_all_known()
         v
  list[Signature]
         |
         |  MoveEngine.apply_all_moves()
         v
  list[MoveResult]              Each MoveResult wraps:
         |                        - signature: Signature (the candidate)
         |                        - move: MoveKind
         |                        - parents: list[str]
         |                        - description: str
         |
         |  ScoringEngine.score()
         v
  list[(MoveResult, ScoreBreakdown)]
         |
         |  filter by score threshold
         |  sort descending
         v
  TOP CANDIDATES
         |
         |  Z3ModelFinder.compute_spectrum()
         |     or Mace4Solver.compute_spectrum()
         v
  ModelSpectrum                 Maps domain size -> count of models
         |                      Stores CayleyTable instances per size
         |
         |  ScoringEngine.score(sig, spectrum, known_fps)
         v
  FINAL SCORED CANDIDATES       Re-scored with model-theoretic dimensions
         |
         |  ConjectureGenerator.generate_conjectures()
         |  Prover9Solver.prove()
         v
  VERIFIED CONJECTURES          PROVED / DISPROVED / TIMEOUT
         |
         |  LibraryManager.add_discovery()
         v
  PERSISTENT LIBRARY            JSON files in library/discovered/
```

The flow has two scoring passes. The first pass uses only structural dimensions (cheap, runs on all candidates). The second pass adds model-theoretic scores (expensive, runs on the top N candidates after Z3/Mace4 model checking). This two-phase approach keeps total compute manageable even at depth 2 with all 14 seed structures.

### Iterative Deepening

For depth > 1, the output signatures of one pass become the input signatures of the next:

```
  Depth 0:  14 known structures
              |
              |  apply_all_moves()
              v
  Depth 1:  ~319 candidates          <0.1 seconds
              |
              |  apply_all_moves()   (on depth-1 results)
              v
  Depth 2:  ~95,000 candidates       ~10 seconds
```

Each depth level applies all 7 moves (5 single-input, 2 pairwise) to every signature in the current frontier. The branching factor varies per move and per structure -- COMPLETE produces the most children (up to 4 per binary operation), while ABSTRACT only fires when two signatures share axiom kinds.

---

## Core Abstractions

### Expression AST (`src/core/ast_nodes.py`)

Four frozen dataclasses represent algebraic expressions:

```
Expr (abstract base)
  |
  +-- Var(name: str)               Variable: x, y, z
  |
  +-- Const(name: str)             Named constant: e, zero, one
  |
  +-- App(op_name: str,            Operation application: mul(x, y)
  |       args: tuple[Expr, ...])  Rendered as (x mul y) for binary ops
  |
  +-- Equation(lhs: Expr,          Equational law: lhs = rhs
               rhs: Expr)
```

Every expression node supports three operations:

| Method | Purpose |
|--------|---------|
| `size()` | Count of AST nodes. Used by the economy scoring dimension. |
| `variables()` | Set of free variable names. Used by the Z3 encoder to determine quantifier scope. |
| `substitute(mapping)` | Capture-avoiding substitution. Used during axiom instantiation. |

All four types are frozen (immutable after construction). `App` stores `args` as a tuple, not a list, to preserve immutability. The `__init__` override in `App` uses `object.__setattr__` to convert a list argument to a tuple on frozen dataclasses.

### Algebraic Signature (`src/core/signature.py`)

The `Signature` class is the central data structure. Every component either produces, consumes, or transforms signatures.

```python
@dataclass
class Signature:
    name: str
    sorts: list[Sort]               # Types in the algebra
    operations: list[Operation]     # Typed function symbols
    axioms: list[Axiom]             # Equational laws
    description: str
    derivation_chain: list[str]     # How this was derived (for provenance)
    metadata: dict[str, Any]        # Extensible key-value store
```

Unlike the expression types, `Signature` is mutable. The move engine builds candidate signatures incrementally -- appending sorts, operations, and axioms during move application. Making it immutable would require a builder pattern with significantly more boilerplate for no practical benefit, since signatures are never shared across threads.

**Sort, Operation, and Axiom** are all frozen dataclasses:

| Type | Fields | Notes |
|------|--------|-------|
| `Sort` | `name`, `description` | A named type. Single-sorted structures use one sort. |
| `Operation` | `name`, `domain: tuple[str, ...]`, `codomain: str`, `description` | `domain` lists input sort names; `arity` is derived as `len(domain)`. Constants have arity 0. |
| `Axiom` | `kind: AxiomKind`, `equation: Equation`, `operations: tuple[str, ...]`, `description` | `operations` lists which operations the axiom constrains (used for fingerprinting and move logic). |

**AxiomKind** is a string enum with 16 variants:

```
ASSOCIATIVITY    COMMUTATIVITY    IDENTITY       INVERSE
DISTRIBUTIVITY   ANTICOMMUTATIVITY IDEMPOTENCE   NILPOTENCE
JACOBI           POSITIVITY       BILINEARITY    HOMOMORPHISM
FUNCTORIALITY    ABSORPTION       MODULARITY     CUSTOM
```

The `CUSTOM` kind is the catch-all for axioms that do not fit a standard pattern, including deformed axioms (q-associativity, q-commutativity) and the curry-eval adjunction from INTERNALIZE.

### Fingerprinting

`Signature.fingerprint()` computes a 16-character hex digest (SHA-256 truncation) from a canonical representation of the signature's shape:

```json
{"sorts": 1, "op_arities": [0, 1, 2], "axiom_kinds": ["ASSOCIATIVITY", "IDENTITY", "INVERSE"]}
```

Two signatures with the same fingerprint have the same number of sorts, the same operation arities (as a sorted list), and the same axiom kinds (as a sorted list). This is structural isomorphism up to renaming -- it does not check equation structure. It is used for:

- **Novelty checking:** The `is_novel` scoring dimension compares a candidate's fingerprint against all known fingerprints.
- **Deduplication:** The library manager stores fingerprints with each discovery.

### Equation Builders

The module provides seven factory functions for common axiom equations:

| Builder | Equation | Example |
|---------|----------|---------|
| `make_assoc_equation("mul")` | `(x mul y) mul z = x mul (y mul z)` | Semigroup axiom |
| `make_comm_equation("mul")` | `x mul y = y mul x` | Abelian group axiom |
| `make_identity_equation("mul", "e")` | `x mul e = x` | Monoid axiom (right identity) |
| `make_inverse_equation("mul", "inv", "e")` | `x mul inv(x) = e` | Group axiom |
| `make_idempotent_equation("mul")` | `x mul x = x` | Band/semilattice axiom |
| `make_anticomm_equation("bracket")` | `bracket(x, y) = neg(bracket(y, x))` | Lie algebra axiom |
| `make_distrib_equation("mul", "add")` | `mul(a, add(b, c)) = add(mul(a, b), mul(a, c))` | Ring axiom (left) |
| `make_jacobi_equation("bracket")` | `add(bracket(x, bracket(y, z)), bracket(y, bracket(z, x))) = neg(bracket(z, bracket(x, y)))` | Lie algebra axiom |

These builders are used by both the known structures library (to define seed signatures) and the move engine (to construct axioms in new candidates).

---

## The Discovery Pipeline

### Phase 1: Enumeration

The `MoveEngine` takes a list of signatures and returns a list of `MoveResult` objects. Each result contains the new candidate signature, which move produced it, the parent signature name(s), and a human-readable description.

```python
engine = MoveEngine()
candidates = engine.apply_all_moves(bases)   # Single pass
```

For depth > 1, the CLI and agent iterate:

```python
current = bases
for d in range(depth):
    results = engine.apply_all_moves(current)
    all_results.extend(results)
    current = [r.signature for r in results]
```

### Phase 2: Scoring (Structural)

All candidates are scored on structural dimensions only (no model checking yet). This is fast -- it examines the signature's shape without calling any external solver.

```python
scorer = ScoringEngine()
score = scorer.score(sig, known_fingerprints=known_fps)
```

Candidates below a configurable threshold are discarded.

### Phase 3: Model Checking (Top N)

The top candidates are checked for finite models. The system tries Mace4 first; if unavailable, it falls back to Z3.

```python
spectrum = solver.compute_spectrum(sig, min_size=2, max_size=6)
```

This produces a `ModelSpectrum` mapping each domain size to the number of non-isomorphic models found, along with the actual `CayleyTable` instances.

### Phase 4: Re-scoring (Full)

Candidates are re-scored with all 10 dimensions, including the three model-theoretic ones now available.

```python
score = scorer.score(sig, spectrum, known_fps)
```

### Phase 5: Conjecture and Verification

For the most interesting candidates, the system generates conjectures (does associativity hold? commutativity? idempotence?) and attempts to prove or disprove them via Prover9.

### Phase 6: Persistence

Verified discoveries are saved to the library as JSON files. Cycle reports are saved as Markdown.

---

## The 7 Structural Moves

Each move is a method on `MoveEngine`. Five operate on a single signature; two require a pair.

### Single-Input Moves

**DUALIZE** -- For each non-commutative binary operation, produce a variant where `op(x,y) = op(y,x)`. Adds a commutativity axiom. Skips operations that are already commutative (dualizing a commutative operation is the identity transformation).

**COMPLETE** -- Add missing structure. Four sub-moves:
1. Add an identity element for a binary operation that lacks one.
2. Add an inverse for a binary operation that has an identity but no inverse.
3. Add a second binary operation with distributivity over the first (only when exactly one binary op exists).
4. Add a norm function (unary, mapping to a scalar sort).

**QUOTIENT** -- Force additional equations on binary operations. Two sub-moves per operation: add commutativity, add idempotence. Skips axioms that are already present.

**INTERNALIZE** -- For each binary operation `op: S x S -> S`, create a new sort `Hom_op` representing partial applications. Adds `curry_op: S -> Hom_op` and `eval_op: Hom_op x S -> S` with the adjunction axiom `eval(curry(a), b) = op(a, b)`. This is a syntactic version of internal Hom objects from category theory.

**DEFORM** -- For each non-CUSTOM, non-POSITIVITY axiom, remove it and replace it with a q-deformed variant. For associativity: `(x*y)*z = q * (x*(y*z))`. For commutativity: `x*y = q * (y*x)`. Other axiom kinds receive a generic deformation (the original equation is kept but tagged as CUSTOM). Adds a `Param` sort and a deformation scaling operation.

### Pairwise Moves

**ABSTRACT** -- Given two signatures, find the set of axiom kinds present in both. Build a minimal single-sorted, single-operation signature with only those shared axiom kinds. Returns nothing if the intersection is empty. This extracts the common categorical essence of two structures.

**TRANSFER** -- Combine two signatures into one two-sorted structure connected by a homomorphism. The first binary operation of each is linked by a functoriality axiom: `transfer(a_op(x, y)) = b_op(transfer(x), transfer(y))`. All operations are prefixed (`a_` and `b_`) to avoid name collisions.

### Move Taxonomy

```
                     +---------- Single ----------+     +--- Pairwise ---+
                     |                             |     |                |
         Constrain   |  DUALIZE   QUOTIENT         |     |  ABSTRACT      |
         (add axioms)|  (comm)    (comm/idem)      |     |  (shared kinds)|
                     |                             |     |                |
         Enrich      |  COMPLETE  INTERNALIZE      |     |  TRANSFER      |
         (add ops)   |  (id/inv/  (Hom-objects)    |     |  (morphism)    |
                     |   op2/norm)                 |     |                |
                     |                             |     |                |
         Relax       |  DEFORM                     |     |                |
         (weaken)    |  (q-parameter)              |     |                |
                     +-----------------------------+     +----------------+
```

---

## Verification Strategy

The system uses three external solvers, each for a different purpose.

### Z3 (`src/solvers/z3_solver.py`)

**Role:** Primary finite model finder. Always available (installed via `pip install z3-solver`).

**Encoding:** Multi-sorted signatures are collapsed to a single integer domain `[0, n)`. Operations become lookup tables of Z3 integer variables:

| Arity | Representation |
|-------|----------------|
| 0 (constant) | A single `z3.Int` variable with `0 <= v < n` |
| 1 (unary) | An array of `n` `z3.Int` variables |
| 2 (binary) | An `n x n` grid of `z3.Int` variables |

Axioms with universally quantified variables are encoded by **complete instantiation**: for each axiom with `k` free variables, the encoder generates `n^k` ground constraints. For a binary associativity axiom over domain size 6, this produces `6^3 = 216` constraints.

**Expression evaluation** uses direct table indexing when both arguments are concrete integers. When an argument is a Z3 expression (e.g., the result of evaluating a subexpression), If-Then-Else chains are constructed for the lookup. For 2D tables, this produces a nested ITE structure: first over rows, then over columns within each row.

**Multiple model finding:** After finding a satisfying assignment, the solver blocks it by adding a disjunction asserting that at least one table entry differs from the found model. This is repeated up to `max_models` times.

**Timeout:** Configurable, default 30 seconds per solver call.

### Mace4 (`src/solvers/mace4.py`)

**Role:** Alternative finite model finder. Used when installed (`apt-get install prover9` or manual build).

**Encoding:** The `FOLTranslator` produces LADR-format input files. Equations are translated to Mace4's term syntax: `f(x, g(y, z))` with the standard `=` operator.

**Output parsing:** Mace4's output contains interpretation blocks delimited by `==========` lines. Within each block, function tables are extracted with regex patterns:
- Binary: `function(f(_,_), [0,1,2,1,2,0,2,0,1]).`
- Unary: `function(g(_), [1,2,0]).`
- Constants: `function(e, [0]).`

The parsed values are assembled into `CayleyTable` objects.

**Fallback:** The `Mace4Fallback` class provides the same interface but delegates to `Z3ModelFinder`. The `ToolExecutor` selects the appropriate solver at initialization time.

### Prover9 (`src/solvers/prover9.py`)

**Role:** Theorem prover for equational theories. Used to verify conjectures of the form "do these axioms imply this equation?"

**Encoding:** The `FOLTranslator` produces LADR-format input with `formulas(assumptions)` for the signature axioms and `formulas(goals)` for the conjecture.

**Results:** Three outcomes:
- `PROVED` -- Prover9 found a proof. The proof text is extracted and returned.
- `DISPROVED` -- Prover9 exhausted the search space without finding a proof (search failed).
- `TIMEOUT` -- The time limit expired.

**ConjectureGenerator** produces testable conjectures from a signature by checking which standard properties are not already axioms. For each binary operation, it generates conjectures for commutativity, idempotence, and associativity (if not already present).

### Solver Selection Logic

```
ToolExecutor.__init__():

    mace4 = Mace4Solver()
    if mace4.is_available():
        model_finder = mace4           # Prefer Mace4 when installed
    else:
        model_finder = Mace4Fallback() # Delegates to Z3ModelFinder
```

The FOLTranslator is shared between Mace4 and Prover9 for LADR format generation. Z3 has its own encoder built into `Z3ModelFinder._encode_axiom()`.

### Cayley Tables (`src/models/cayley.py`)

Finite models are represented as `CayleyTable` objects: an `n x n` numpy array per binary operation, plus a dictionary of constant assignments.

Available analyses on a Cayley table:

| Method | What it checks | Complexity |
|--------|---------------|------------|
| `is_latin_square(op)` | Every row and column is a permutation | O(n^2) |
| `is_commutative(op)` | Table equals its transpose | O(n^2) |
| `has_identity(op)` | Exists element `e` with `e*x = x*e = x` for all `x` | O(n^2) |
| `is_associative(op)` | `(a*b)*c = a*(b*c)` for all `a,b,c` | O(n^3) |
| `row_entropy(op)` | Average Shannon entropy across rows | O(n^2) |
| `column_entropy(op)` | Average Shannon entropy across columns | O(n^2) |
| `symmetry_score(op)` | Normalized unique-elements-per-row/column count | O(n^2) |
| `automorphism_count_estimate(op)` | Brute-force count of automorphisms | O(n! * n^2), capped at n <= 8 |

Isomorphism checking between two models is also brute-force over all permutations, capped at size 10.

---

## Scoring and Ranking

The `ScoringEngine` evaluates candidates across 10 dimensions, each normalized to [0, 1]. The final score is a weighted sum.

### Dimensions

**Structural (5 dimensions):**

| Dimension | What it measures | How it's computed |
|-----------|-----------------|-------------------|
| `connectivity` | How well operations connect the sorts | For multi-sorted: (sort coverage + cross-sort op ratio) / 2. Single-sorted: 0.5. |
| `richness` | Balance between axioms and operations | `exp(-(ratio - 1)^2)` where ratio = axioms / operations. Peak at 1:1. |
| `tension` | Diversity of axiom kinds | (distinct kinds) / min(total kinds, 6). More diverse = more interesting. |
| `economy` | Occam's razor -- penalizes bloat | Based on total component count (sorts + ops + axioms). Ideal range: 3-12. |
| `fertility` | Capacity for further exploration | (min(sorts/3, 1) + min(binary_ops/3, 1)) / 2. More sorts and ops = more fertile. |

**Model-theoretic (3 dimensions):**

| Dimension | What it measures | How it's computed |
|-----------|-----------------|-------------------|
| `has_models` | Binary: does it have any non-trivial finite models? | 1.0 if spectrum is non-empty, else 0.0. |
| `model_diversity` | How many models at how many sizes? | (size coverage + count_score) / 2, where count_score = 1 - exp(-avg/3). |
| `spectrum_pattern` | Does the model spectrum show a pattern? | Checks for primes-only (0.9), powers-of-2 (0.8), arithmetic progression (0.7), monotone counts (0.5). |

**Novelty (2 dimensions):**

| Dimension | What it measures | How it's computed |
|-----------|-----------------|-------------------|
| `is_novel` | Not fingerprint-equivalent to anything known? | 0.0 if fingerprint matches a known structure, else 1.0. |
| `distance` | How far from nearest known structure? | (chain_length/5 + move_diversity/7) / 2. Longer chains and more diverse moves score higher. |

### Default Weights

```
connectivity:     0.08    |  has_models:       0.15
richness:         0.08    |  model_diversity:  0.10
tension:          0.08    |  spectrum_pattern:  0.10
economy:          0.10    |
fertility:        0.06    |  is_novel:          0.15
                          |  distance:          0.10
```

The largest weights (0.15 each) go to `has_models` and `is_novel` -- a structure that has no models is vacuously true (uninteresting), and a structure identical to something known is not a discovery.

---

## Agent Architecture

### Controller (`src/agent/controller.py`)

The `AgentController` drives a research loop using the Claude Code CLI (`claude --print`) as a subprocess. Each research cycle follows 4 phases:

```
1. PLAN      -->  Claude designs the exploration strategy (via CLI call)
2. EXECUTE   -->  Tools run locally: explore candidates, check models via Z3
3. INTERPRET -->  Claude analyzes results and proposes conjectures (via CLI call)
4. ACT       -->  Add discoveries to library, log conjectures, save report
```

Each cycle makes exactly 2 Claude CLI calls: one for planning, one for interpretation. Claude outputs structured JSON between XML tags (`<plan>`, `<decisions>`), which the controller parses and executes. Live progress is printed at every step — timestamped log lines, animated spinners during Claude calls, and per-candidate model checking status.

The controller builds a context message for each Claude call containing:
- The list of known structures (14 seeds)
- Any previously discovered structures with their scores
- Summary of the previous cycle (candidates generated, models found, discoveries)
- The current research goal
- Suggested base structures, depth, and model size limits

### Tool Interface (`src/agent/tools.py`)

Six tools are exposed to the LLM as JSON schemas:

| Tool | Input | Output |
|------|-------|--------|
| `explore` | base_structures, moves, depth, score_threshold | total_candidates, above_threshold, top 50 candidates |
| `check_models` | signature_id, min_size, max_size, max_models_per_size | spectrum, sizes_with_models, example models |
| `prove` | signature_id, conjecture, timeout_sec | list of proof results (proved/disproved/timeout) |
| `score` | signature_id | full 10-dimension score breakdown |
| `search_library` | query, min_score, has_models | matching structures from known and discovered |
| `add_to_library` | signature_id, name, notes | confirmation with final score |

The `ToolExecutor` maintains two in-memory caches for the current session:
- `_candidates: dict[str, Signature]` -- all signatures generated by `explore` calls
- `_spectra: dict[str, ModelSpectrum]` -- all spectra computed by `check_models` calls

These caches allow the `score` and `add_to_library` tools to reference candidates by name without re-generating them.

### System Prompt

The agent receives a system prompt (via `--system-prompt` flag) that:
1. Establishes its role as a mathematical research agent in universal algebra
2. Describes the 7 available structural moves
3. Defines what makes a structure mathematically interesting
4. Injects the current research goal

Claude's built-in tools are disabled (`--tools ""`) — it acts purely as a planner and analyst, outputting structured JSON decisions that the controller executes locally.

---

## Search Space Analysis

### Branching Factor by Move

The number of children produced per signature depends on the structure's shape:

| Move | Children per signature | Depends on |
|------|----------------------|------------|
| DUALIZE | 0 to B | B = number of non-commutative binary ops |
| COMPLETE | 0 to 4B + 1 | B = binary ops. Identity, inverse, second op, norm. |
| QUOTIENT | 0 to 2B | B = binary ops. Commutativity, idempotence per op. |
| INTERNALIZE | B | One Hom-object per binary op |
| DEFORM | A | A = number of non-CUSTOM, non-POSITIVITY axioms |
| ABSTRACT | 0 or 1 per pair | 1 if shared axiom kinds exist, 0 otherwise |
| TRANSFER | 1 per pair | Always produces exactly one result |

### Size at Each Depth

With 14 seed structures and all 7 moves:

| Depth | Candidates | Time (enumeration only) | Time (with Z3, top 20, size <= 6) |
|-------|-----------|------------------------|-----------------------------------|
| 1 | ~319 | < 0.1 s | ~30 s |
| 2 | ~95,000 | ~10 s | hours (impractical for all) |
| 3 | ~25,000,000 (estimated) | minutes | infeasible |

The practical strategy is depth-2 enumeration with structural scoring, followed by Z3 checking on only the top-scoring candidates. The agent further reduces this by choosing subsets of base structures and moves per cycle.

### Deduplication

Fingerprint-based deduplication is applied during scoring (the `is_novel` dimension penalizes duplicates) but candidates are not pruned from the enumeration itself. This means depth-2 may contain many near-duplicates. A more aggressive deduplication during enumeration would reduce the candidate count at depth 2 by an estimated 40-60%, but at the cost of potentially missing structures that are fingerprint-equivalent but semantically distinct (different equation shapes with the same axiom kinds).

---

## Storage and Persistence

### Directory Layout

```
library/
  known/              Reserved for future use (seeds are currently in-code)
  discovered/
    disc_0001_*.json   One file per discovery
    disc_0002_*.json
  conjectures/
    open.json          List of unresolved conjectures
    proved.json        Proved conjectures
    disproved.json     Disproved conjectures
  reports/
    cycle_001_report.md
    cycle_002_report.md
```

### Discovery JSON Schema

Each discovery file (`disc_NNNN_name.json`) contains:

```json
{
  "id": "disc_0001",
  "name": "Commutative Deformed Semigroup",
  "signature": {
    "name": "...",
    "sorts": [{"name": "S", "description": "..."}],
    "operations": [{"name": "mul", "domain": ["S", "S"], "codomain": "S", "description": "..."}],
    "axioms": [{"kind": "ASSOCIATIVITY", "equation": "...", "operations": ["mul"], "description": "..."}],
    "description": "...",
    "derivation_chain": ["Dualize(mul)", "Complete(identity for mul)"],
    "fingerprint": "a3b2c1d4e5f6a7b8"
  },
  "derivation_chain": ["Dualize(mul)", "Complete(identity for mul)"],
  "score": 0.6234,
  "score_breakdown": {
    "connectivity": 0.5,
    "richness": 0.8,
    "tension": 0.33,
    "economy": 0.76,
    "fertility": 0.17,
    "has_models": 1.0,
    "model_diversity": 0.45,
    "spectrum_pattern": 0.7,
    "is_novel": 1.0,
    "distance": 0.3,
    "total": 0.6234
  },
  "notes": "Agent notes about why this is interesting",
  "fingerprint": "a3b2c1d4e5f6a7b8"
}
```

### Conjecture JSON Schema

Each conjecture file (e.g., `proved.json`) is a JSON array:

```json
[
  {
    "signature": "Group_dual(mul)",
    "statement": "(x mul y) = (y mul x)",
    "status": "proved",
    "details": "Proof text from Prover9..."
  }
]
```

### Known Structures (In-Code)

The 14 seed structures are defined as factory functions in `src/library/known_structures.py` and registered in the `KNOWN_STRUCTURES` dictionary. They are not stored as JSON -- they are constructed fresh on each load via `load_all_known()` or `load_by_name(name)`.

The hierarchy of the 14 seeds:

```
Magma
  |
  +-- Semigroup (+ASSOC)
        |
        +-- Monoid (+ID)
        |     |
        |     +-- Group (+INV)
        |           |
        |           +-- AbelianGroup (+COMM)
        |
        +-- Quasigroup (different axiomatization: cancellation laws)
              |
              +-- Loop (+ID)

Ring (abelian group + mult + distrib)
  |
  +-- Field (+COMM mult + mult ID + recip)

Lattice (meet + join + absorption)

LieAlgebra (vector space + antisymmetric bracket + Jacobi)

VectorSpace (abelian group + scalar mult)
  |
  +-- InnerProductSpace (+inner product + positivity)

Category (objects + morphisms + composition + identities)
```

---

## Extension Points

The architecture is designed for extension at four points. Each follows a documented pattern.

### Adding a New Known Structure

1. Write a factory function in `src/library/known_structures.py` that returns a `Signature`.
2. Register it in the `KNOWN_STRUCTURES` dictionary.
3. The structure immediately becomes available to `load_all_known()`, `load_by_name()`, the CLI, and the agent.

### Adding a New Structural Move

1. Add a variant to the `MoveKind` enum in `src/moves/engine.py`.
2. Write a method on `MoveEngine` that takes one or two `Signature` arguments and returns `list[MoveResult]`.
3. Wire it into `apply_all_moves()` (in the single or pairwise loop) and `apply_move()` (in the dispatch dict).
4. Single-input moves should handle edge cases (e.g., "no binary operations") by returning an empty list.

### Adding a New Scoring Dimension

1. Add a `float` field to `ScoreBreakdown` in `src/scoring/engine.py`.
2. Add a weight entry to `DEFAULT_WEIGHTS`.
3. Write a `_method_name(self, sig, ...)` method on `ScoringEngine`.
4. Call it from `score()` and assign the result to the breakdown field.
5. Add the field name to `to_dict()`.

### Adding a New Axiom Kind

1. Add an entry to the `AxiomKind` enum in `src/core/signature.py`.
2. Optionally write a `make_*_equation()` builder function.
3. If moves should generate this axiom kind, update the relevant move methods.
4. If scoring should recognize it, update `_tension()` or add a new dimension.

### Adding a New Solver

The solver interface is implicit (Mace4Solver, Z3ModelFinder, and Mace4Fallback all expose `find_models()` and `compute_spectrum()` with the same argument types). To add a new solver:

1. Write a class with `find_models(sig, domain_size, max_models) -> Mace4Result` and `compute_spectrum(sig, min_size, max_size, max_models_per_size) -> ModelSpectrum`.
2. Add an `is_available()` method.
3. Update the solver selection logic in `ToolExecutor.__init__()`.

---

## Appendix: Key File Index

| File | LOC (approx) | Responsibility |
|------|-------------|----------------|
| `src/core/ast_nodes.py` | 107 | Expression AST: Var, Const, App, Equation |
| `src/core/signature.py` | 231 | Sort, Operation, Axiom, Signature, AxiomKind, equation builders |
| `src/moves/engine.py` | 540 | MoveEngine with 7 structural moves, MoveKind enum, MoveResult |
| `src/models/cayley.py` | 187 | CayleyTable representation and analysis, isomorphism checking |
| `src/solvers/fol_translator.py` | 164 | Signature-to-LADR and signature-to-Z3 translation |
| `src/solvers/z3_solver.py` | 283 | Z3-based finite model finder with ITE-chain encoding |
| `src/solvers/mace4.py` | 253 | Mace4 subprocess wrapper, output parser, Mace4Fallback |
| `src/solvers/prover9.py` | 167 | Prover9 subprocess wrapper, ConjectureGenerator |
| `src/scoring/engine.py` | 286 | ScoringEngine, ScoreBreakdown, 10 scoring dimensions |
| `src/agent/tools.py` | 324 | 6 tool schemas, ToolExecutor with caching |
| `src/agent/controller.py` | 318 | AgentController, CycleReport, 8-phase research loop |
| `src/library/known_structures.py` | 346 | 14 seed structures as factory functions |
| `src/library/manager.py` | 149 | LibraryManager: JSON persistence, search, fingerprint index |
| `src/cli.py` | 322 | Click CLI: explore, agent, list-structures, inspect, report |
| `src/utils/display.py` | 118 | Rich console rendering for signatures, scores, spectra |
| `run.py` | 7 | Entry point |
