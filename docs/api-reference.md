# API Reference

This document covers the Python API for programmatic use of the mathematical discovery system. All public classes and functions are listed with their signatures, parameters, and return types.

---

## Core Data Structures

### `src.core.ast_nodes`

#### `Expr` (base class)

Abstract base for all expression nodes.

```python
class Expr:
    def size(self) -> int: ...
    def variables(self) -> set[str]: ...
    def substitute(self, mapping: dict[str, Expr]) -> Expr: ...
```

#### `Var(name: str)`

A variable in an algebraic expression.

```python
x = Var("x")
x.size()       # 1
x.variables()  # {"x"}
repr(x)        # "x"
```

#### `Const(name: str)`

A constant symbol (identity element, zero, etc.).

```python
e = Const("e")
e.size()       # 1
e.variables()  # set()
```

#### `App(op_name: str, args: Sequence[Expr])`

Application of an operation to arguments.

```python
x, y = Var("x"), Var("y")
expr = App("mul", [x, y])
expr.size()       # 3
expr.variables()  # {"x", "y"}
repr(expr)        # "(x mul y)"

# Nesting
inner = App("mul", [x, y])
outer = App("mul", [inner, Var("z")])
outer.size()      # 5
```

Binary operations print as `(a op b)`, unary as `op(a)`, n-ary as `op(a, b, c)`.

#### `Equation(lhs: Expr, rhs: Expr)`

An equation between two expressions.

```python
eq = Equation(App("mul", [x, y]), App("mul", [y, x]))
eq.variables()  # {"x", "y"}
eq.size()       # 6
repr(eq)        # "(x mul y) = (y mul x)"
```

```python
# Parsing (from string representation back to AST)
parse_equation(s: str, constants: set[str], op_names: set[str]) -> Equation
parse_expr(s: str, constants: set[str], op_names: set[str]) -> Expr
```

---

### `src.core.signature`

#### `AxiomKind` (enum)

```python
class AxiomKind(str, Enum):
    ASSOCIATIVITY       COMMUTATIVITY       IDENTITY
    INVERSE             DISTRIBUTIVITY      ANTICOMMUTATIVITY
    IDEMPOTENCE         NILPOTENCE          JACOBI
    POSITIVITY          BILINEARITY         HOMOMORPHISM
    FUNCTORIALITY       ABSORPTION          MODULARITY
    SELF_DISTRIBUTIVITY RIGHT_SELF_DISTRIBUTIVITY CUSTOM
```

#### `Sort(name: str, description: str = "")`

A type/sort in the algebraic signature. Frozen dataclass.

#### `Operation(name: str, domain: list[str] | tuple[str, ...], codomain: str, description: str = "")`

A typed function in the signature. Frozen dataclass.

```python
op = Operation("mul", ["G", "G"], "G", "group multiplication")
op.arity  # 2 (property, computed from domain length)
```

#### `Axiom(kind: AxiomKind, equation: Equation, operations: list[str] | tuple[str, ...], description: str = "")`

An equational law. Frozen dataclass.

```python
axiom = Axiom(
    AxiomKind.ASSOCIATIVITY,
    make_assoc_equation("mul"),
    ["mul"],
    "associativity of multiplication"
)
```

#### `Signature`

The central data structure: a complete algebraic signature.

```python
@dataclass
class Signature:
    name: str
    sorts: list[Sort]
    operations: list[Operation]
    axioms: list[Axiom]
    description: str = ""
    derivation_chain: list[str] = []
    metadata: dict[str, Any] = {}
```

**Methods:**

| Method | Returns | Description |
|--------|---------|-------------|
| `sort_names()` | `list[str]` | Names of all sorts |
| `op_names()` | `list[str]` | Names of all operations |
| `get_op(name)` | `Operation \| None` | Find operation by name |
| `get_ops_by_arity(n)` | `list[Operation]` | All operations of arity n |
| `fingerprint()` | `str` | 16-char hex hash for novelty checking |
| `to_dict()` | `dict` | JSON-serializable representation |
| `from_dict(data)` | `Signature` | Reconstruct from to_dict() representation |

#### Equation Builder Functions

```python
make_assoc_equation(op_name: str) -> Equation
# (x op y) op z = x op (y op z)

make_comm_equation(op_name: str) -> Equation
# x op y = y op x

make_identity_equation(op_name: str, id_name: str) -> Equation
# x op id = x

make_inverse_equation(op_name: str, inv_name: str, id_name: str) -> Equation
# x op inv(x) = id

make_idempotent_equation(op_name: str) -> Equation
# x op x = x

make_anticomm_equation(op_name: str) -> Equation
# x op y = neg(y op x)

make_distrib_equation(mul_name: str, add_name: str) -> Equation
# a mul (b add c) = (a mul b) add (a mul c)

make_jacobi_equation(bracket_name: str) -> Equation
# [x,[y,z]] + [y,[z,x]] = -[z,[x,y]]

make_self_distrib_equation(op_name: str) -> Equation
# a op (b op c) = (a op b) op (a op c)

make_right_self_distrib_equation(op_name: str) -> Equation
# (a op b) op c = (a op c) op (b op c)
```

---

## Structural Moves

### `src.moves.engine`

#### `MoveKind` (enum)

```python
class MoveKind(str, Enum):
    ABSTRACT   DUALIZE   COMPLETE   QUOTIENT
    INTERNALIZE   TRANSFER   DEFORM   SELF_DISTRIB
```

#### `MoveResult`

```python
@dataclass
class MoveResult:
    signature: Signature
    move: MoveKind
    parents: list[str]
    description: str
```

#### `MoveEngine`

```python
engine = MoveEngine()

# Apply all moves to a list of signatures
results: list[MoveResult] = engine.apply_all_moves([sig1, sig2])

# Apply a specific move
results = engine.apply_move(MoveKind.COMPLETE, [sig1])

# Individual move methods
engine.abstract(sig_a, sig_b) -> list[MoveResult]   # pairwise
engine.dualize(sig) -> list[MoveResult]              # single
engine.complete(sig) -> list[MoveResult]             # single
engine.quotient(sig) -> list[MoveResult]             # single
engine.internalize(sig) -> list[MoveResult]          # single
engine.transfer(sig_a, sig_b) -> list[MoveResult]    # pairwise
engine.deform(sig) -> list[MoveResult]               # single
engine.self_distrib(sig) -> list[MoveResult]         # single
```

---

## Model Checking

### `src.models.cayley.CayleyTable`

```python
ct = CayleyTable(size=3, tables={"mul": np.array(...)}, constants={"e": 0})

ct.is_latin_square("mul") -> bool
ct.is_commutative("mul") -> bool
ct.has_identity("mul") -> int | None     # returns element index or None
ct.is_associative("mul") -> bool
ct.row_entropy("mul") -> float
ct.column_entropy("mul") -> float
ct.symmetry_score("mul") -> float        # 0-1, 1.0 = perfect Latin square
ct.automorphism_count_estimate("mul") -> int  # size ≤ 8 only
ct.to_dict() -> dict
CayleyTable.from_dict(data) -> CayleyTable
```

```python
models_are_isomorphic(m1, m2, op_name) -> bool  # size ≤ 10 only
```

### `src.solvers.z3_solver.Z3ModelFinder`

```python
finder = Z3ModelFinder(timeout_ms=30000)

finder.is_available() -> bool

result: Mace4Result = finder.find_models(
    sig: Signature,
    domain_size: int,
    max_models: int = 10,
)
# result.domain_size: int
# result.models_found: list[CayleyTable]
# result.exit_code: int
# result.raw_output: str
# result.error: str
# result.timed_out: bool

spectrum: ModelSpectrum = finder.compute_spectrum(
    sig: Signature,
    min_size: int = 2,
    max_size: int = 8,
    max_models_per_size: int = 10,
)
```

### `src.solvers.mace4.Mace4Solver`

Same interface as Z3ModelFinder. Requires `mace4` binary on PATH.

```python
solver = Mace4Solver(mace4_path="mace4", timeout=30)
solver.is_available() -> bool
solver.find_models(sig, domain_size, max_models) -> Mace4Result
solver.compute_spectrum(sig, min_size, max_size, max_models_per_size) -> ModelSpectrum
```

### `src.solvers.mace4.ModelSpectrum`

```python
@dataclass
class ModelSpectrum:
    signature_name: str
    spectrum: dict[int, int]                    # size -> model count
    models_by_size: dict[int, list[CayleyTable]]
    timed_out_sizes: list[int] = []             # sizes where solver timed out

    def sizes_with_models(self) -> list[int]
    def total_models(self) -> int
    def is_empty(self) -> bool
    def any_timed_out(self) -> bool   # True if any size timed out
```

### `src.solvers.router.SmartSolverRouter`

```python
router = SmartSolverRouter(z3_timeout_ms=30000, mace4_timeout=30, heavy_timeout_multiplier=2.0)

router.is_available() -> bool
router.classify(sig: Signature) -> str    # "mace4_heavy", "z3_heavy", or "z3_normal"

result: Mace4Result = router.find_models(sig, domain_size, max_models=10)
spectrum: ModelSpectrum = router.compute_spectrum(sig, min_size=2, max_size=8, max_models_per_size=10)
```

### `src.solvers.prover9.Prover9Solver`

```python
prover = Prover9Solver(prover9_path="prover9", timeout=30)
prover.is_available() -> bool
result: ProofResult = prover.prove(sig: Signature, conjecture: Equation)
# result.status: ProofStatus (PROVED | DISPROVED | TIMEOUT | ERROR)
# result.proof_text: str
```

### `src.solvers.fol_translator.FOLTranslator`

```python
translator = FOLTranslator()
mace4_input: str = translator.to_mace4(sig, domain_size=4)
prover9_input: str = translator.to_prover9(sig, conjecture)
z3_code: str = translator.to_z3_python(sig, domain_size=4)
```

---

## Scoring

### `src.scoring.engine.ScoringEngine`

```python
scorer = ScoringEngine(weights=None)  # uses DEFAULT_WEIGHTS

breakdown: ScoreBreakdown = scorer.score(
    sig: Signature,
    spectrum: ModelSpectrum | None = None,
    known_fingerprints: set[str] | None = None,
)
```

### `ScoreBreakdown`

```python
@dataclass
class ScoreBreakdown:
    connectivity: float    richness: float     tension: float
    economy: float         fertility: float     axiom_synergy: float
    has_models: float      model_diversity: float   spectrum_pattern: float
    solver_difficulty: float
    is_novel: float        distance: float
    total: float

    def to_dict(self) -> dict[str, float]
```

---

## Library

### `src.library.known_structures`

```python
load_all_known() -> list[Signature]          # all 15 structures
load_by_name(name: str) -> Signature | None  # by exact name
KNOWN_STRUCTURES: dict[str, callable]        # name -> factory function

# Individual factories
magma() semigroup() monoid() group() abelian_group()
ring() field() lattice() quasigroup() loop() quandle()
lie_algebra() vector_space() inner_product_space() category_sig()
```

### `src.library.manager.LibraryManager`

```python
lib = LibraryManager(base_path="library")

lib.known_fingerprints() -> list[str]
lib.all_fingerprints() -> list[str]       # known + discovered
lib.list_known() -> list[str]
lib.list_discovered() -> list[dict]
lib.add_discovery(sig, name, notes, score) -> Path
lib.add_conjecture(sig_name, statement, status, details) -> None
lib.search(query, min_score=None) -> list[dict]
lib.get_discovery(discovery_id) -> dict | None
lib.archive_failed(discovery_id, reason) -> dict   # archive a failed discovery
lib.list_failed() -> list[dict]                     # list archived failures
```

---

## Agent

### `src.agent.controller.AgentConfig`

```python
@dataclass
class AgentConfig:
    model: str = "claude-opus-4-6"    # Claude model
    effort: str = "high"              # Thinking effort: low, medium, high
    max_cycles: int = 10              # Maximum research cycles
    goal: str = "Explore broadly: find novel algebraic structures"
    explore_depth: int = 2            # Move depth per cycle
    max_model_size: int = 6           # Z3/Mace4 domain size limit
    score_threshold: float = 0.3      # Minimum score to consider
    base_structures: list[str] = ["Group", "Ring", "Lattice", "Quasigroup"]
```

### `src.agent.controller.AgentController`

Drives the Claude CLI-powered research loop. Requires the `claude` CLI on PATH.

```python
controller = AgentController(config: AgentConfig, library: LibraryManager)
reports: list[CycleReport] = controller.run(num_cycles=5)
```

Each cycle makes 2 Claude CLI calls (`claude --print --model <model> --effort <effort>`):
1. **Planning call** — Claude outputs a JSON plan between `<plan>` tags
2. **Interpretation call** — Claude outputs decisions between `<decisions>` tags

Live progress is printed to the console throughout.

### `src.agent.tools.ToolExecutor`

```python
executor = ToolExecutor(library: LibraryManager)
result: dict = executor.execute(tool_name: str, args: dict)
```

Available tools: `"explore"`, `"check_models"`, `"prove"`, `"score"`, `"search_library"`, `"add_to_library"`.
