# Solver Integrations Reference

The discovery system uses formal verification tools to ground every candidate
algebraic structure in mathematical truth. No structure is accepted on the
strength of heuristics alone -- if a claimed model exists, a solver confirms it;
if a conjecture is asserted, a prover checks it.

This document covers the five solver-layer modules and the Cayley table analysis
library they produce results into.

```
src/solvers/
  fol_translator.py   Signature -> FOL input strings
  z3_solver.py         Primary model finder (SMT)
  mace4.py             Mace4 subprocess wrapper + fallback
  prover9.py           Theorem prover + conjecture generator
  router.py            Smart solver routing based on signature

src/models/
  cayley.py            Cayley table storage and analysis
```

**Dependency graph:**

```
fol_translator  <--  mace4  (generates LADR input)
fol_translator  <--  prover9 (generates LADR input)
z3_solver       <--  mace4  (Mace4Fallback delegates to Z3ModelFinder)
z3_solver       <--  router (SmartSolverRouter uses Z3ModelFinder)
mace4           <--  router (SmartSolverRouter uses Mace4Solver)
cayley          <--  z3_solver, mace4 (both produce CayleyTable objects)
```

---

## Table of Contents

1. [FOL Translator](#fol-translator)
2. [Z3 Model Finder](#z3-model-finder)
3. [Mace4 Integration](#mace4-integration)
4. [Prover9 Integration](#prover9-integration)
5. [Cayley Table Analysis](#cayley-table-analysis)
6. [Solver Selection and Fallback](#solver-selection-and-fallback)
7. [Smart Solver Router](#smart-solver-router)

---

## FOL Translator

**File:** `src/solvers/fol_translator.py`

`FOLTranslator` converts an algebraic `Signature` (sorts, operations, axioms)
into first-order logic input strings consumed by Mace4, Prover9, and Z3.

### Class API

```python
class FOLTranslator:
    def to_mace4(self, sig: Signature, domain_size: int) -> str
    def to_prover9(self, sig: Signature, conjecture: Equation) -> str
    def to_z3_python(self, sig: Signature, domain_size: int) -> str
```

Two convenience functions are also exported at module level:

```python
def signature_to_mace4_input(sig: Signature, domain_size: int) -> str
def signature_to_prover9_input(sig: Signature, conjecture: Equation) -> str
```

### Mace4 Format (LADR)

`to_mace4` generates a complete Mace4 input file as a string. The structure:

```
assign(domain_size, N).

formulas(assumptions).

  % ASSOCIATIVITY
  mul(mul(x,y),z) = mul(x,mul(y,z)).

end_of_list.
```

Formatting rules:

| Element | Treatment |
|---------|-----------|
| Domain size | `assign(domain_size, N).` header |
| Axiom block | Wrapped in `formulas(assumptions). ... end_of_list.` |
| Equations | `lhs = rhs.` with trailing period |
| Variables | Kept as-is: `x`, `y`, `z` |
| Constants | Kept as-is: `e`, `zero` |
| Nullary operations | Bare name (no parentheses): `e` |
| Unary operations | `inv(x)` |
| Binary operations | `mul(x,y)` (no space after comma) |
| Comments | `% description` above each axiom |

### Prover9 Format

`to_prover9` generates input with two blocks:

1. `formulas(assumptions).` -- the axioms of the signature (same format as Mace4)
2. `formulas(goals).` -- the equation to prove or disprove

```
formulas(assumptions).
  mul(mul(x,y),z) = mul(x,mul(y,z)).
end_of_list.

formulas(goals).
  mul(x,y) = mul(y,x).
end_of_list.
```

The assumptions block uses the same `_equation_to_mace4` method internally;
both formats share the same term representation.

### Z3 Python Code Generation

`to_z3_python` generates executable Python source that imports `z3` and
declares an uninterpreted sort, distinct elements, and function symbols.

Operation arities map to Z3 declarations:

| Arity | Z3 declaration |
|-------|---------------|
| 0 | `Const('name', S)` |
| 1 | `Function('name', S, S)` |
| 2 | `Function('name', S, S, S)` |

Axiom constraints are included as comments (the `_axiom_to_z3_comment` method
produces a `ForAll([...], ...)` description string). The actual constraint
encoding for model finding is handled by `Z3ModelFinder`, not by this
generated code.

### Expression Translation Internals

The private `_expr_to_mace4` method recursively converts AST nodes:

- `Var("x")` -> `"x"`
- `Const("e")` -> `"e"`
- `App("mul", [x, y])` -> `"mul(x,y)"`
- `App("e", [])` (nullary) -> `"e"`
- Nested: `App("mul", [App("mul", [x, y]), z])` -> `"mul(mul(x,y),z)"`

Returns `None` for unrecognized expression types, which causes the axiom to be
silently skipped.

---

## Z3 Model Finder

**File:** `src/solvers/z3_solver.py`

The primary model-finding engine. Requires only `pip install z3-solver` -- no
external binaries. Encodes finite algebraic structures as integer constraint
satisfaction problems and uses Z3's SMT solver to find satisfying assignments.

### Class API

```python
class Z3ModelFinder:
    def __init__(self, timeout_ms: int = 30000)
    def is_available(self) -> bool
    def find_models(self, sig: Signature, domain_size: int, max_models: int = 10) -> Mace4Result
    def compute_spectrum(self, sig: Signature, min_size: int = 2, max_size: int = 8, max_models_per_size: int = 10) -> ModelSpectrum
```

The module-level flag `Z3_AVAILABLE` (bool) is set at import time based on
whether `import z3` succeeds.

### How Model Finding Works

**Step 1: Domain encoding.** For domain size N, the solver works over integers
in `[0, N)`. Each operation becomes a table of Z3 integer variables constrained
to this range.

| Operation arity | Encoding |
|-----------------|----------|
| 0 (constant) | Single `z3.Int` variable, constrained `0 <= v < N` |
| 1 (unary) | List of N `z3.Int` variables: `[op_0, op_1, ..., op_{N-1}]` |
| 2 (binary) | N x N matrix of `z3.Int` variables: `op_i_j` for `0 <= i,j < N` |

**Step 2: Axiom encoding.** For each axiom, the solver extracts all variable
names from the equation and performs complete instantiation: every combination
of domain values is substituted in. For domain size N with K variables in an
axiom, this produces N^K equality constraints.

```
Axiom: mul(mul(x,y),z) = mul(x,mul(y,z))
Variables: {x, y, z}  ->  K = 3
Domain size: 3         ->  N = 3
Constraints: 3^3 = 27 equalities added to the solver
```

Ground equations (no variables) produce a single equality constraint.

**Step 3: Expression evaluation.** The `_eval_expr` method walks the AST and
translates it into Z3 expressions:

- `Var("x")` with `env = {"x": 1}` resolves to the integer `1`
- `Const("e")` resolves to the Z3 variable for constant `e`
- `App("mul", [x, y])` with concrete arguments `(1, 2)` resolves to `table[1][2]`
  (a Z3 integer variable)
- Nested applications where an inner result is a Z3 expression (not a concrete
  int) trigger If-Then-Else chain lookups

**Step 4: Solving.** `solver.check()` is called. If `sat`, the model is
extracted. If `unsat`, no model is returned and the search ends. If
`unknown` (typically caused by a timeout), the search ends and the result
is returned with `timed_out=True`.

**Step 5: Model blocking.** To find multiple distinct models, each found model
is blocked by adding a disjunction requiring at least one table entry to differ:

```python
block = []
for each table entry:
    block.append(table[i][j] != found_value)
solver.add(z3.Or(block))
```

This repeats up to `max_models` times.

### Handling Nested Operations (If-Then-Else Chains)

When an axiom like associativity requires `table[table[a][b]][c]`, the inner
expression `table[a][b]` is a Z3 symbolic integer, not a concrete Python int.
You cannot index a Python list with a Z3 expression. The solver resolves this
with If-Then-Else (ITE) chains.

**1D lookup** (`_z3_lookup_1d`):

```
lookup(table, idx) = If(idx == 0, table[0],
                     If(idx == 1, table[1],
                     ...
                     table[N-1]))
```

Built bottom-up: starts with `table[N-1]` as the default, then wraps in
conditionals from `N-2` down to `0`.

**2D lookup** (`_z3_lookup_2d`):

For `table[row][col]` where either index is symbolic:

1. If `row` is concrete but `col` is symbolic: 1D lookup on `table[row]`
2. If `row` is symbolic: compute a 1D lookup result for each possible row,
   then wrap those in a row-level ITE chain

```
row_result[i] = _z3_lookup_1d(table[i], col, N)   for each i
result = If(row == 0, row_result[0],
         If(row == 1, row_result[1],
         ...
         row_result[N-1]))
```

The nesting depth grows linearly with domain size, which is why larger domains
are slower.

### Model Extraction

When Z3 returns `sat`, the solver extracts concrete values using
`model.evaluate(var, model_completion=True)`. The `model_completion=True` flag
ensures Z3 assigns a concrete value even to variables the solver left
unconstrained. Values are extracted via `.as_long()` and stored in numpy arrays.

Results are returned as `Mace4Result` objects (reusing the same dataclass from
the Mace4 module) containing `CayleyTable` instances.

### Model Spectrum Computation

```python
def compute_spectrum(self, sig, min_size=2, max_size=8, max_models_per_size=10) -> ModelSpectrum
```

Iterates from `min_size` to `max_size` inclusive, calling `find_models` at each
size. Returns a `ModelSpectrum` that maps each domain size to the count of
distinct models found (up to `max_models_per_size`).

This spectrum is the primary input to the scoring engine's `spectrum_pattern`
dimension.

### Performance Characteristics

| Domain size | Typical time | Notes |
|-------------|-------------|-------|
| 2-3 | < 0.1s | Instant for most structures |
| 4-5 | < 1s | Fast for typical equational theories |
| 6-8 | Seconds to minutes | Depends on axiom count and nesting depth |
| 9+ | May exceed timeout | Complex structures with many binary ops |

Performance is dominated by:

1. **Constraint count**: N^K per axiom, where K is the number of variables.
   Associativity (K=3) at size 8 generates 512 constraints.
2. **ITE chain depth**: Nested operations create deep symbolic expressions.
   Chains grow linearly with N but interact multiplicatively across nesting.
3. **Model blocking**: Each additional model adds a large disjunction.

The timeout is configurable:

```python
finder = Z3ModelFinder(timeout_ms=60000)  # 60 seconds
```

### Symmetry Breaking for Heavy Signatures

For signatures with O(n^3) equational axioms (self-distributivity, right self-distributivity, distributivity, Jacobi), the complete instantiation produces n^3 constraints per axiom. Combined with the n! isomorphic copies of each model (from element permutations), this causes Z3 to time out on moderate domain sizes.

The Z3ModelFinder applies **lex-leader symmetry breaking** when the signature is detected as "heavy":

**Detection criteria** (`_is_heavy_signature`):
1. Must be single-sorted (multi-sorted signatures risk cross-sort conflicts)
2. Must NOT have CUSTOM axioms (which often encode quasigroup-type cancellation laws)
3. Must have at least one axiom of kind: SELF_DISTRIBUTIVITY, RIGHT_SELF_DISTRIBUTIVITY, DISTRIBUTIVITY, or JACOBI

**The constraint**: For the first binary operation, the first row of the operation table must be non-decreasing:
```
op(0, 0) <= op(0, 1) <= ... <= op(0, n-1)
```

This safely prunes isomorphic models by fixing one canonical representative per isomorphism class. It is NOT applied to quasigroup-like structures (where rows must be permutations -- the only non-decreasing permutation is the identity, which would force a left identity that may not exist).

The heavy axiom kinds are exported as `HEAVY_AXIOM_KINDS`:
```python
HEAVY_AXIOM_KINDS = frozenset({
    AxiomKind.SELF_DISTRIBUTIVITY,
    AxiomKind.RIGHT_SELF_DISTRIBUTIVITY,
    AxiomKind.DISTRIBUTIVITY,
    AxiomKind.JACOBI,
})
```

---

## Mace4 Integration

**File:** `src/solvers/mace4.py`

Mace4 is William McCune's finite model finder from the LADR (Library for
Automated Deduction Research) package. It is often faster than Z3 for pure
equational theories because it uses specialized algorithms for finite model
search. However, it requires separate installation.

### Installation

```bash
# Debian/Ubuntu
apt-get install prover9

# From source
# https://www.cs.unm.edu/~mccune/prover9/
```

The `prover9` package includes both `mace4` and `prover9` binaries.

### Data Structures

#### Mace4Result

```python
@dataclass
class Mace4Result:
    domain_size: int              # The size that was searched
    models_found: list[CayleyTable]  # All models found
    exit_code: int                # Mace4 process exit code (0 = found models)
    raw_output: str               # Complete stdout from Mace4
    error: str = ""               # stderr or error message
    timed_out: bool = False       # True if subprocess exceeded timeout
```

Both `Mace4Solver` and `Z3ModelFinder` return this same type, making them
interchangeable.

#### ModelSpectrum

```python
@dataclass
class ModelSpectrum:
    signature_name: str
    spectrum: dict[int, int]               # size -> model count
    models_by_size: dict[int, list[CayleyTable]]  # size -> model list
    timed_out_sizes: list[int] = []    # sizes where solver timed out
```

| Method | Returns |
|--------|---------|
| `sizes_with_models()` | Sorted list of sizes that have at least one model |
| `total_models()` | Sum of all model counts across all sizes |
| `is_empty()` | `True` if no models were found at any size |
| `any_timed_out()` | `True` if any size timed out |
| `timed_out_sizes` | Field: list of sizes where the solver timed out before completing |

### Class API

```python
class Mace4Solver:
    def __init__(self, mace4_path: str = "mace4", timeout: int = 30)
    def is_available(self) -> bool
    def find_models(self, sig: Signature, domain_size: int, max_models: int = 10) -> Mace4Result
    def compute_spectrum(self, sig: Signature, min_size: int = 2, max_size: int = 8, max_models_per_size: int = 10) -> ModelSpectrum
```

### How It Works

1. **Generate input.** `FOLTranslator.to_mace4(sig, domain_size)` produces LADR
   text.

2. **Run subprocess.** The command is:
   ```
   mace4 -n <size> -N <size> [-m <max_models>]
   ```
   Input is piped via stdin. The `-n`/`-N` flags set the minimum and maximum
   domain size to the same value (search exactly one size). The `-m` flag
   requests multiple models when `max_models > 1`.

3. **Parse output.** Interpretation blocks in Mace4's output are separated by
   lines of `=` characters (10 or more). Each block is parsed for function
   tables.

4. **Return results.** Parsed tables are wrapped in `CayleyTable` objects and
   returned inside a `Mace4Result`.

### Output Parsing

Mace4 outputs interpretation blocks containing function definitions in three
patterns:

| Pattern | Regex | Meaning |
|---------|-------|---------|
| Binary op | `function(f(_,_), [values])` | N x N Cayley table, values in row-major order |
| Constant | `function(c, [value])` | Single element index |
| Unary op | `function(g(_), [values])` | N-element mapping |

Binary operation values are reshaped into an N x N numpy array. Unary
operations are stored under the key `_unary_{name}` in the tables dict.

The parser uses regex matching:

```python
# Binary: function(f(_,_), [0,1,2,1,2,0,2,0,1])
func_pattern = r"function\((\w+)\(_,_\),\s*\[\s*([\d,\s]+)\]\)"

# Constant: function(e, [0])
const_pattern = r"function\((\w+),\s*\[\s*(\d+)\s*\]\)"

# Unary: function(inv(_), [0,2,1])
unary_pattern = r"function\((\w+)\(_\),\s*\[\s*([\d,\s]+)\]\)"
```

### Timeout Handling

If the subprocess exceeds the configured timeout (default 30 seconds), a
`Mace4Result` is returned with `timed_out=True`, an empty model list, and
exit code `-1`.

`Z3ModelFinder` also sets `timed_out=True` on its returned `Mace4Result`
when `solver.check()` returns `z3.unknown`, which is the typical Z3
response when the configured timeout is exceeded. Any models found before
the timeout are still included in the result.

Both `Mace4Solver.compute_spectrum()` and `Mace4Fallback.compute_spectrum()`
propagate per-size timeout information into `ModelSpectrum.timed_out_sizes`,
ensuring the scoring engine can distinguish solver timeouts from proven
emptiness.

### Mace4Fallback

When Mace4 is not installed, `Mace4Fallback` provides the same interface but
delegates to `Z3ModelFinder` internally:

```python
class Mace4Fallback:
    def __init__(self, timeout: int = 30)
    def find_models(self, sig, domain_size, max_models=10) -> Mace4Result
    def compute_spectrum(self, sig, min_size=2, max_size=8, max_models_per_size=10) -> ModelSpectrum
```

The fallback converts the timeout from seconds to milliseconds when
constructing the Z3 solver: `Z3ModelFinder(timeout_ms=self.timeout * 1000)`.

If neither Mace4 nor Z3 is available, `find_models` returns a `Mace4Result`
with `error="Neither Mace4 nor Z3 available"`.

---

## Prover9 Integration

**File:** `src/solvers/prover9.py`

Prover9 is an automated theorem prover for first-order logic, also from
McCune's LADR package. The system uses it to verify conjectures about algebraic
structures -- for example, "does this axiom set imply commutativity?"

### Data Structures

#### ProofStatus

```python
class ProofStatus(str, Enum):
    PROVED = "proved"       # Theorem holds: axioms imply the conjecture
    DISPROVED = "disproved" # Search failed (SEARCH FAILED in output)
    TIMEOUT = "timeout"     # Exceeded time limit
    ERROR = "error"         # Prover9 not found or other error
```

Note: `DISPROVED` means Prover9's search space was exhausted without finding a
proof. This is evidence against the conjecture but not a formal refutation.
A formal counterexample requires a model finder (Mace4 or Z3).

#### ProofResult

```python
@dataclass
class ProofResult:
    status: ProofStatus
    conjecture: str          # String representation of the equation
    proof_text: str = ""     # Extracted proof (if PROVED)
    counterexample: str = "" # Counterexample info (if available)
    time_seconds: float = 0.0
    raw_output: str = ""     # Complete Prover9 stdout
```

### Class API

```python
class Prover9Solver:
    def __init__(self, prover9_path: str = "prover9", timeout: int = 30)
    def is_available(self) -> bool
    def prove(self, sig: Signature, conjecture: Equation) -> ProofResult
```

### How Proving Works

1. **Generate input.** `FOLTranslator.to_prover9(sig, conjecture)` produces
   LADR text with assumptions (axioms) and a goal (the conjecture).

2. **Run subprocess.** The command is:
   ```
   prover9 -t<timeout>
   ```
   Input is piped via stdin. The `-t` flag sets Prover9's internal time limit.
   The Python subprocess timeout is set to `timeout + 5` seconds to allow
   Prover9 to clean up.

3. **Interpret output.** The result is classified based on stdout content:

   | Stdout contains | Status |
   |-----------------|--------|
   | `"THEOREM PROVED"` and exit code 0 | `PROVED` |
   | `"SEARCH FAILED"` | `DISPROVED` |
   | Neither | `TIMEOUT` |

4. **Extract proof.** If proved, `_extract_proof` scans the output for lines
   between `"PROOF"` and `"end of proof"` (case-insensitive for the end
   marker).

### Conjecture Generator

```python
class ConjectureGenerator:
    def generate_conjectures(self, sig: Signature) -> list[Equation]
```

For each binary operation in the signature, the generator produces conjectures
for properties that are NOT already present in the axioms:

| Property | Equation template | Axiom kind checked |
|----------|------------------|--------------------|
| Commutativity | `op(x,y) = op(y,x)` | `COMMUTATIVITY` |
| Idempotence | `op(x,x) = x` | `IDEMPOTENCE` |
| Associativity | `op(op(x,y),z) = op(x,op(y,z))` | `ASSOCIATIVITY` |

The check for existing axioms matches on `axiom.kind.value` and whether the
operation name appears in `axiom.operations`. Only binary operations are
considered (operations with `arity != 2` are skipped).

### Error Handling

| Condition | Result |
|-----------|--------|
| Prover9 not installed | `ProofStatus.ERROR`, message in `raw_output` |
| Subprocess timeout | `ProofStatus.TIMEOUT`, empty output |
| Prover9 internal timeout | `ProofStatus.TIMEOUT` (no "THEOREM PROVED" or "SEARCH FAILED") |

---

## Cayley Table Analysis

**File:** `src/models/cayley.py`

`CayleyTable` is the standard representation for finite models discovered by
the solvers. It stores operation tables as numpy arrays and provides analysis
methods used by the scoring engine.

### Data Structure

```python
@dataclass
class CayleyTable:
    size: int                          # Domain size N
    tables: dict[str, np.ndarray]      # op_name -> array
    constants: dict[str, int] = {}     # const_name -> element index
```

Storage conventions:

- Binary operations: N x N numpy array where `table[i][j] = i op j`
- Unary operations: stored under the key `_unary_{name}` as a 1D array of
  length N
- Constants: stored in the `constants` dict mapping name to element index

### Analysis Methods

All analysis methods take an `op_name: str` parameter and operate on the
corresponding table. They return a sensible default (`False`, `None`, or `0.0`)
if the operation name is not found.

#### Structural Tests

**`is_latin_square(op_name) -> bool`**

Checks that every row and every column is a permutation of `{0, 1, ..., N-1}`.
This is the quasigroup property: left and right cancellation hold. The check
uses Python `set` uniqueness on each row and column.

**`is_commutative(op_name) -> bool`**

Checks whether the table equals its transpose: `table == table.T`. Uses
`np.array_equal` for the comparison.

**`has_identity(op_name) -> int | None`**

Searches for an element `e` such that `table[e][x] == x` and `table[x][e] == x`
for all `x`. Returns the element index, or `None` if no identity exists.
Performs a linear scan over candidate elements with early termination.

**`is_associative(op_name) -> bool`**

Brute-force check: `table[table[a][b]][c] == table[a][table[b][c]]` for all
triples `(a, b, c)`. This is O(N^3) and uses early termination on the first
failure.

#### Entropy Measures

**`row_entropy(op_name) -> float`**

Average Shannon entropy across rows. For each row, computes the frequency
distribution of elements, then:

```
H(row) = -sum(p * log2(p)) for p in probabilities where p > 0
```

Returns the mean of H across all rows. A Latin square achieves maximum row
entropy of `log2(N)`.

**`column_entropy(op_name) -> float`**

Same as `row_entropy` but operates on columns (`table[:, i]`).

**`max_entropy() -> float`**

The theoretical maximum entropy for the table's domain size: `log2(N)`.
Returns `0.0` for size 0 or 1.

#### Structure Scores

**`symmetry_score(op_name) -> float`**

Measures how "Latin-square-like" the table is. For each row and column, counts
the number of distinct elements and divides by N. The final score is the
average across all rows and columns, normalized to `[0, 1]`.

A perfect Latin square scores `1.0`. A constant table (all entries identical)
scores `1/N`.

**`automorphism_count_estimate(op_name) -> int`**

Counts automorphisms by brute force: for each permutation `perm` of
`{0, ..., N-1}`, checks whether `perm(table[a][b]) == table[perm(a)][perm(b)]`
for all `a, b`. Returns the count of permutations that satisfy this condition.

Only runs for `size <= 8` (returns `0` for larger tables, since N! grows too
fast). At size 8, this checks 40320 permutations.

### Serialization

```python
def to_dict(self) -> dict[str, Any]       # numpy arrays -> nested lists
@classmethod
def from_dict(cls, data) -> CayleyTable   # nested lists -> numpy arrays
```

The `to_dict`/`from_dict` roundtrip preserves all data. Tables are converted
via `.tolist()` and `np.array()`. Constants are plain dicts.

### Isomorphism Check

```python
def models_are_isomorphic(m1: CayleyTable, m2: CayleyTable, op_name: str) -> bool
```

Module-level function (not a method on `CayleyTable`). Checks whether two
models of the same size are isomorphic for a given operation by brute-force
search over all permutations.

A permutation `perm` witnesses isomorphism if:

```
perm(m1.table[a][b]) == m2.table[perm(a)][perm(b)]   for all a, b
```

Returns `False` immediately if sizes differ. Returns `False` without checking
if `size > 10` (the search would be too expensive).

---

## Solver Selection and Fallback

### SmartSolverRouter

**File:** `src/solvers/router.py`

The `SmartSolverRouter` inspects each signature and routes model-finding to the best available solver. This prevents the O(n^3) constraint explosion that causes Z3 to time out on structures with heavy equational axioms (self-distributivity, Jacobi, etc.).

```python
class SmartSolverRouter:
    def __init__(
        self,
        z3_timeout_ms: int = 30000,
        mace4_timeout: int = 30,
        heavy_timeout_multiplier: float = 2.0,
    )
    def is_available(self) -> bool
    def classify(self, sig: Signature) -> str
    def find_models(self, sig, domain_size, max_models=10) -> Mace4Result
    def compute_spectrum(self, sig, min_size=2, max_size=8, max_models_per_size=10) -> ModelSpectrum
```

### Routing Logic

The router classifies each signature into one of three routes:

| Route | Condition | Solver | Timeout |
|-------|-----------|--------|---------|
| `mace4_heavy` | Has heavy axioms AND Mace4 is available | Mace4 | `mace4_timeout` |
| `z3_heavy` | Has heavy axioms AND Mace4 unavailable | Z3 with symmetry breaking | `z3_timeout_ms * heavy_timeout_multiplier` |
| `z3_normal` | No heavy axioms | Z3 (standard) | `z3_timeout_ms` |

"Heavy axioms" are those with O(n^3) ground instances: `SELF_DISTRIBUTIVITY`, `RIGHT_SELF_DISTRIBUTIVITY`, `DISTRIBUTIVITY`, `JACOBI`.

Mace4 is preferred for heavy signatures because it has built-in symmetry breaking optimized for equational theories. When Mace4 is not installed, Z3 receives an extended timeout (default 2x) to compensate.

### Usage in the System

Both the CLI (`src/cli.py`) and the agent tool executor (`src/agent/tools.py`) use `SmartSolverRouter` as the primary model-finding interface:

```python
from src.solvers.router import SmartSolverRouter

solver = SmartSolverRouter()
if not solver.is_available():
    print("Neither Mace4 nor Z3 available")
    return

spectrum = solver.compute_spectrum(sig, min_size=2, max_size=6)
```

### Fallback Chain

```
1. SmartSolverRouter.classify(sig)
   |
   +-- heavy axioms + Mace4 available -> Mace4Solver
   +-- heavy axioms + Mace4 unavailable -> Z3ModelFinder (extended timeout + symmetry breaking)
   +-- normal axioms -> Z3ModelFinder (standard timeout)
```

If neither Mace4 nor Z3 is available, `SmartSolverRouter.is_available()` returns `False`.

For Prover9, there is no Z3-based fallback. If Prover9 is not installed, the `prove` tool returns an error directing the user to install it.
