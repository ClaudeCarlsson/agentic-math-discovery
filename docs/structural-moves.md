# The 8 Structural Moves

This is the complete reference for the move engine that drives all structure generation
in the system. Every candidate algebraic structure is produced by applying one of these
eight typed transformations to an existing signature.

No other mechanism creates new mathematics. If a structure exists in the system, it was
either a seed from the known-structures library or it was produced by a finite sequence
of these moves.

---

## Table of Contents

- [Background: What Is a Signature?](#background-what-is-a-signature)
- [Move Summary Table](#move-summary-table)
- [M1: ABSTRACT (Pairwise)](#m1-abstract-pairwise)
- [M2: DUALIZE (Single)](#m2-dualize-single)
- [M3: COMPLETE (Single)](#m3-complete-single)
- [M4: QUOTIENT (Single)](#m4-quotient-single)
- [M5: INTERNALIZE (Single)](#m5-internalize-single)
- [M6: TRANSFER (Pairwise)](#m6-transfer-pairwise)
- [M7: DEFORM (Single)](#m7-deform-single)
- [M8: SELF_DISTRIB (Single)](#m8-self_distrib-single)
- [Composing Moves](#composing-moves)
- [Performance Characteristics](#performance-characteristics)
- [Implementation Reference](#implementation-reference)

---

## Background: What Is a Signature?

A **signature** is the typed skeleton of an algebraic structure. It has three components:

| Component      | What it is                          | Example (Group)                                      |
|----------------|-------------------------------------|------------------------------------------------------|
| **Sorts**      | The types of elements               | `G` (group elements)                                 |
| **Operations** | Typed functions between sorts       | `mul: G x G -> G`, `e: -> G`, `inv: G -> G`         |
| **Axioms**     | Equational laws the operations obey | `mul(mul(x,y),z) = mul(x,mul(y,z))` (associativity) |

Operations are classified by **arity**: nullary (constants like `e`), unary (like `inv`),
binary (like `mul`). Axioms are tagged with a **kind** drawn from a fixed enum
(`ASSOCIATIVITY`, `COMMUTATIVITY`, `IDENTITY`, `INVERSE`, `DISTRIBUTIVITY`,
`ANTICOMMUTATIVITY`, `IDEMPOTENCE`, `NILPOTENCE`, `JACOBI`, `POSITIVITY`,
`BILINEARITY`, `HOMOMORPHISM`, `FUNCTORIALITY`, `ABSORPTION`, `MODULARITY`,
`SELF_DISTRIBUTIVITY`, `RIGHT_SELF_DISTRIBUTIVITY`, `CUSTOM`).

Two signatures are considered structurally isomorphic when they have the same
**fingerprint** -- a hash of sort count, operation arities, and axiom kinds, ignoring
names. The fingerprint is what the novelty checker uses to filter duplicates.

Every move takes one or two signatures and returns a list of `MoveResult` objects. A
`MoveResult` bundles the new signature with the move kind, parent names, and a
human-readable description.

---

## Move Summary Table

| Move          | Arity    | Input                 | Output                          | Mathematical Essence              |
|---------------|----------|-----------------------|---------------------------------|-----------------------------------|
| M1 ABSTRACT   | Pairwise | Two signatures        | Their shared axiom structure    | Greatest common sub-theory        |
| M2 DUALIZE    | Single   | One signature         | Same + commutativity per op     | "What if order didn't matter?"    |
| M3 COMPLETE   | Single   | One signature         | Same + missing structural parts | Fill structural gaps              |
| M4 QUOTIENT   | Single   | One signature         | Same + forced equations         | Impose additional constraints     |
| M5 INTERNALIZE| Single   | One signature         | Same + Hom-object sort          | Turn operations into data         |
| M6 TRANSFER   | Pairwise | Two signatures        | Combined + homomorphism         | Bridge two domains                |
| M7 DEFORM     | Single   | One signature         | Same with weakened axioms       | Parametric relaxation             |
| M8 SELF_DISTRIB | Single   | One signature         | Same + left SD, or same + both left and right SD | Left and/or full self-distributivity (racks/quandles) |

---

## M1: ABSTRACT (Pairwise)

### What It Does

ABSTRACT extracts the common algebraic core of two structures. Given two signatures, it
identifies which *kinds* of axioms appear in both and builds a minimal new signature that
contains exactly those shared axiom types applied to a single abstract binary operation.

This is the algebraic analogue of finding a greatest common divisor -- not of numbers,
but of theories.

### Input / Output

- **Input**: Two signatures, `sig_a` and `sig_b`.
- **Output**: Zero or one `MoveResult`. Returns nothing if the two signatures share no
  axiom kinds.

### Algorithm

```
1. Collect axiom_kinds_a = {a.kind for a in sig_a.axioms}
2. Collect axiom_kinds_b = {a.kind for a in sig_b.axioms}
3. Compute shared_kinds = axiom_kinds_a & axiom_kinds_b  (set intersection)
4. If shared_kinds is empty, return []
5. Create a new signature with:
   - One sort: S
   - One operation: op : S x S -> S
   - For each kind in shared_kinds, generate the standard equation for that
     kind applied to "op" (using _axiom_for_kind)
6. Filter: only axiom kinds that have a standard equation builder are included.
   Currently supported: ASSOCIATIVITY, COMMUTATIVITY, IDEMPOTENCE.
   Kinds like IDENTITY or INVERSE are skipped because they require additional
   nullary/unary operations that the minimal signature does not include.
7. If no axioms survive filtering, return []
8. Return the new signature as a single MoveResult
```

### Example: Abstract(Group, Ring)

**Group axiom kinds**: `{ASSOCIATIVITY, IDENTITY, INVERSE}`

**Ring axiom kinds**: `{ASSOCIATIVITY, COMMUTATIVITY, IDENTITY, INVERSE, DISTRIBUTIVITY}`

**Shared kinds**: `{ASSOCIATIVITY, IDENTITY, INVERSE}`

**After filtering** (only kinds with standard builders): `{ASSOCIATIVITY}`

**Result**: A signature named `Abstract(Group,Ring)` with one sort `S`, one binary
operation `op`, and one axiom: `op(op(x,y),z) = op(x,op(y,z))`. This is a **Semigroup**.

```
Before:  Group (3 ops, 3 axioms)  +  Ring (4 ops, 6 axioms)
After:   Abstract(Group,Ring)     =  Sig(S, {op/2}, {ASSOCIATIVITY})
                                     [structurally a Semigroup]
```

### When It Is Interesting

- Two structures from different branches of mathematics (say, a Lattice and a Group)
  share unexpected common axiom structure.
- The abstraction matches a known structure, revealing a hidden subsumption relationship.
- At depth 2, abstracting two *generated* candidates can surface patterns that were not
  obvious from the seeds alone.

### Limitation

The current implementation only generates standard equations for ASSOCIATIVITY,
COMMUTATIVITY, and IDEMPOTENCE. Axiom kinds that require additional operations (IDENTITY
needs a constant, INVERSE needs a unary op) are silently dropped. This means ABSTRACT
often produces a sparser result than the full intersection would warrant.

---

## M2: DUALIZE (Single)

### What It Does

DUALIZE asks: "What if this operation were symmetric?" For each binary operation in the
signature that is not already commutative, it produces a new signature where that
operation is forced to be commutative by adding the axiom `op(x,y) = op(y,x)`.

In categorical terms, dualization swaps the two arguments of a binary operation. When the
operation is already commutative, swapping is the identity -- so the move correctly
produces nothing.

### Input / Output

- **Input**: One signature.
- **Output**: Zero or more `MoveResult`s -- one per non-commutative binary operation.

### Algorithm

```
1. Find all binary operations: binary_ops = sig.get_ops_by_arity(2)
2. For each binary op:
   a. Deep-copy the signature
   b. Check if any existing axiom has kind=COMMUTATIVITY for this op
   c. If already commutative: skip (dualization is the identity)
   d. Otherwise: append Axiom(COMMUTATIVITY, op(x,y) = op(y,x), [op])
   e. Emit a MoveResult
```

### Example: Dualize(Semigroup)

**Semigroup**: sort `S`, operation `mul: S x S -> S`, axiom `ASSOCIATIVITY(mul)`.

`mul` is not commutative, so dualization adds: `mul(x,y) = mul(y,x)`.

**Result**: `Semigroup_dual(mul)` -- a **commutative semigroup**.

```
Before:  Semigroup  =  Sig(S, {mul/2}, {ASSOC})
After:   Semigroup_dual(mul)  =  Sig(S, {mul/2}, {ASSOC, COMM})
         [structurally a Commutative Semigroup]
```

### Example: Dualize(AbelianGroup)

`mul` is already commutative in AbelianGroup. The move returns an empty list. No new
candidate is generated.

### When It Is Interesting

- Adding commutativity to a group produces an abelian group, which has radically
  different representation theory and model spectrum.
- Adding commutativity to the `meet` or `join` of a non-commutative semilattice-like
  structure can collapse the model count, signaling strong structural constraint.
- Commutativity interacts non-trivially with DISTRIBUTIVITY: a commutative ring has
  properties (e.g., ideals commute) that a general ring does not.

---

## M3: COMPLETE (Single)

### What It Does

COMPLETE adds missing structural components to a signature. It looks for "gaps" -- a
binary operation without an identity element, a monoid without inverses, a structure with
only one binary operation that could support a second one -- and fills them.

This is the most prolific move. It typically produces 2--4 candidates per input
signature.

### Input / Output

- **Input**: One signature.
- **Output**: Zero or more `MoveResult`s (often 2--4).

### Algorithm

The move applies four independent completions, each producing a separate candidate:

```
For each binary operation op : S x S -> S:

  (a) IDENTITY completion
      If op has no IDENTITY axiom:
        - Add a nullary operation e_op : -> S
        - Add axiom: op(x, e_op) = x
        - Emit candidate "{name}+id({op})"

  (b) INVERSE completion
      If op HAS an identity but NO INVERSE axiom:
        - Find the identity constant name (e.g., "e")
        - Add a unary operation inv_op : S -> S
        - Add axiom: op(x, inv_op(x)) = e
        - Emit candidate "{name}+inv({op})"

  Note: inverse requires identity. A semigroup (no identity) gets an
  identity completion but NOT an inverse completion. A monoid (has identity)
  gets an inverse completion.

Then, independently:

  (c) SECOND OPERATION completion
      If the signature has exactly one binary operation op:
        - Add a second binary operation op2 : S x S -> S
        - Add axiom: op2(a, op(b,c)) = op(op2(a,b), op2(a,c))
          (left distributivity of op2 over op)
        - Emit candidate "{name}+op2"

  (d) NORM completion
      If the signature has at least one binary operation (or 2+ sorts)
      and no existing "norm" operation:
        - Add a unary operation norm : S -> S (or S -> S2 if multi-sorted)
        - Add a POSITIVITY axiom: norm(x) >= 0
          (encoded symbolically as norm(x) = norm(x), a placeholder)
        - Emit candidate "{name}+norm"
```

### Example: Complete(Semigroup)

**Semigroup**: `{mul/2}`, axioms: `{ASSOC(mul)}`. No identity, no inverse.

| Candidate              | What was added                          | Recognizable as       |
|------------------------|-----------------------------------------|-----------------------|
| `Semigroup+id(mul)`   | `e_mul: -> S`, `mul(x, e_mul) = x`     | Monoid                |
| `Semigroup+op2`       | `op2: S x S -> S`, distributivity axiom | Semigroup + semiring direction |
| `Semigroup+norm`      | `norm: S -> S`, positivity axiom        | Normed semigroup      |

Note: no inverse completion, because Semigroup has no identity.

### Example: Complete(Monoid)

**Monoid**: `{mul/2, e/0}`, axioms: `{ASSOC(mul), IDENTITY(mul,e)}`. Has identity, no
inverse.

| Candidate              | What was added                          | Recognizable as       |
|------------------------|-----------------------------------------|-----------------------|
| `Monoid+inv(mul)`     | `inv_mul: S -> S`, `mul(x,inv_mul(x)) = e` | Group             |
| `Monoid+op2`          | `op2: S x S -> S`, distributivity axiom | Monoid + ring direction |
| `Monoid+norm`         | `norm: S -> S`, positivity axiom        | Normed monoid         |

Here, completing a Monoid with an inverse **recovers a Group**.

### When It Is Interesting

- Completing a semigroup recovers a monoid. Completing that monoid recovers a group.
  This demonstrates the system can *rediscover the classical algebraic hierarchy* from
  below.
- Completing a group with a second operation plus distributivity recovers a ring-like
  structure. This is how the system bridges single-operation and multi-operation algebra.
- Norm completions are interesting when the resulting structure has finite models with
  non-trivial norm behavior.

---

## M4: QUOTIENT (Single)

### What It Does

QUOTIENT forces additional equational constraints on binary operations. Where DUALIZE
only adds commutativity, QUOTIENT can impose commutativity or idempotence on any binary
operation that does not already satisfy them.

The name comes from universal algebra: forcing an equation on a structure is equivalent
to taking a quotient by the congruence generated by that equation.

### Input / Output

- **Input**: One signature.
- **Output**: Zero or more `MoveResult`s -- up to two per binary operation (one for
  commutativity, one for idempotence), minus any already present.

### Algorithm

```
Supported quotient axioms:
  - COMMUTATIVITY:  op(x,y) = op(y,x)
  - IDEMPOTENCE:    op(x,x) = x

For each binary operation op:
  For each (kind, label, equation_builder) in quotient_axioms:
    If op does not already have an axiom of this kind:
      - Deep-copy the signature
      - Append the new axiom
      - Emit candidate "{name}_q({label},{op})"
```

### Example: Quotient(Group)

**Group**: `{mul/2, e/0, inv/1}`, axioms: `{ASSOC(mul), IDENTITY(mul,e), INVERSE(mul,inv,e)}`.

`mul` has no COMMUTATIVITY and no IDEMPOTENCE, so both quotients apply:

| Candidate                  | Forced equation          | Recognizable as             |
|----------------------------|--------------------------|-----------------------------|
| `Group_q(COMM,mul)`       | `mul(x,y) = mul(y,x)`   | Abelian group               |
| `Group_q(IDEM,mul)`       | `mul(x,x) = x`          | Idempotent group (= trivial group, since idempotence + inverse forces `x = e` for all `x`) |

The second result is structurally degenerate -- its only model is the trivial one-element
group. This is exactly the kind of insight the scoring engine flags: a dramatic collapse
in the model spectrum.

### Example: Quotient(Semigroup)

| Candidate                      | Forced equation          | Recognizable as             |
|--------------------------------|--------------------------|-----------------------------|
| `Semigroup_q(COMM,mul)`       | `mul(x,y) = mul(y,x)`   | Commutative semigroup       |
| `Semigroup_q(IDEM,mul)`       | `mul(x,x) = x`          | Band (idempotent semigroup) |

### When It Is Interesting

- When the forced equation **collapses the model spectrum**: if a structure had models of
  every finite size and the quotient reduces it to only sizes 1, 2, 3, that constraint
  is doing serious work.
- When idempotence combines with other axioms to produce unexpected consequences (as in
  the group example above, where idempotence forces triviality).
- Bands (idempotent semigroups) have a rich structure theory of their own -- Green's
  relations, semilattice decompositions -- so the Semigroup quotient is genuinely
  interesting.

---

## M5: INTERNALIZE (Single)

### What It Does

INTERNALIZE turns a binary operation into data. For a binary operation `f: S x S -> S`,
it creates a new sort `Hom_f` that represents "partially applied" versions of `f`. This
is the **curry-eval adjunction** from category theory, made concrete inside the
signature.

The intuition: instead of thinking of multiplication as a *process* that combines two
elements, think of each element as *defining a function* (left-multiply-by-x). That
function lives in a new sort. The result is a multi-sorted signature with a richer type
structure.

### Input / Output

- **Input**: One signature.
- **Output**: One `MoveResult` per binary operation.

### Algorithm

```
For each binary operation f : S x S -> S:
  1. Deep-copy the signature
  2. Add a new sort: Hom_f
  3. Add operation eval_f : Hom_f x S -> S  (apply a "stored function" to an element)
  4. Add operation curry_f : S -> Hom_f     (turn an element into its multiplication map)
  5. Add axiom: eval_f(curry_f(a), b) = f(a, b)
     This says: "currying then evaluating is the same as applying f directly"
  6. Emit candidate "{name}_int({f})"
```

The axiom is tagged as `AxiomKind.CUSTOM` with description "curry-eval adjunction".

### Example: Internalize(Semigroup, mul)

**Before**:
```
Sorts:      S
Operations: mul : S x S -> S
Axioms:     mul(mul(x,y),z) = mul(x,mul(y,z))   [ASSOCIATIVITY]
```

**After** (`Semigroup_int(mul)`):
```
Sorts:      S, Hom_mul
Operations: mul : S x S -> S
            eval_mul : Hom_mul x S -> S
            curry_mul : S -> Hom_mul
Axioms:     mul(mul(x,y),z) = mul(x,mul(y,z))              [ASSOCIATIVITY]
            eval_mul(curry_mul(a), b) = mul(a, b)           [CUSTOM: curry-eval]
```

### When It Is Interesting

- The Hom-object `Hom_f` may carry its own algebraic structure. If `f` is associative,
  then `Hom_f` forms a monoid under composition. The system can discover this by applying
  further moves to the internalized signature.
- This is how **categories arise from algebraic structures**: the morphisms of a category
  are precisely the Hom-objects of composition.
- At depth 2, applying COMPLETE to an internalized signature may add identity or inverse
  to the Hom sort, recovering function-space structure.
- Internalization increases the sort count, which affects the fingerprint and can push a
  candidate into a novel region of the search space.

---

## M6: TRANSFER (Pairwise)

### What It Does

TRANSFER builds a bridge between two algebraic domains. Given signatures A and B, it
constructs a combined signature containing all operations from both (prefixed to avoid
name collisions) plus a **transfer morphism** from A's carrier sort to B's carrier sort,
constrained by a **functoriality axiom** that forces the transfer to be a homomorphism.

This is the algebraic formalization of "structure-preserving map."

### Input / Output

- **Input**: Two signatures, `sig_a` and `sig_b`.
- **Output**: Exactly one `MoveResult`.

### Algorithm

```
1. Let sort_a = first sort of sig_a, sort_b = first sort of sig_b
2. If sort names collide, rename sort_b to "{sort_b}_2"
3. Create a new signature with both sorts
4. Copy all operations from sig_a, prefixed with "a_":
   - a_mul, a_e, a_inv, etc.
   - Remap domain/codomain sort names accordingly
5. Copy all operations from sig_b, prefixed with "b_":
   - b_add, b_mul, b_zero, etc.
6. Copy all axioms from both, updating operation name references to use prefixes
7. Add transfer : sort_a -> sort_b  (a unary operation)
8. Find the first binary op in each signature (op_a from sig_a, op_b from sig_b)
9. If both exist, add FUNCTORIALITY axiom:
   transfer(a_op(x, y)) = b_op(transfer(x), transfer(y))
10. Emit the combined signature
```

### Example: Transfer(Group, Ring)

**Group operations** (prefixed): `a_mul: G x G -> G`, `a_e: -> G`, `a_inv: G -> G`

**Ring operations** (prefixed): `b_add: R x R -> R`, `b_mul: R x R -> R`,
`b_zero: -> R`, `b_neg: R -> R`

**Transfer morphism**: `transfer: G -> R`

**Functoriality**: `transfer(a_mul(x, y)) = b_add(transfer(x), transfer(y))`

(The functoriality axiom pairs `a_mul` with `b_add` because those are the *first* binary
operations listed in each signature.)

**Result**: A multi-sorted signature with 2 sorts, 8 operations, and axioms from both
Group and Ring plus the homomorphism constraint. This describes **a group homomorphism
into the additive group of a ring**.

```
Before:  Group (1 sort, 3 ops, 3 axioms)
       + Ring  (1 sort, 4 ops, 6 axioms)

After:   Transfer(Group,Ring)
         2 sorts: G, R
         8 ops:   a_mul, a_e, a_inv, b_add, b_mul, b_zero, b_neg, transfer
         10 axioms: 3 from Group + 6 from Ring + 1 FUNCTORIALITY
```

### When It Is Interesting

- The homomorphism constraint can force unexpected relationships between the two
  structures. For example, if the source is a finite group and the target is a ring,
  the transfer must map into the additive torsion of the ring.
- Transfer between a lattice and a group is unusual in classical mathematics --
  discovering that such a transfer exists (or that it forces triviality) is a genuine
  mathematical observation.
- At depth 2, applying DEFORM to a transfer signature relaxes the functoriality axiom,
  producing "approximate homomorphisms" -- a concept with real applications in functional
  analysis (stability of homomorphisms, Ulam's problem).

---

## M7: DEFORM (Single)

### What It Does

DEFORM introduces a parameter `q` that continuously relaxes an axiom. Instead of
requiring an equation to hold exactly, the deformed version holds "up to a factor of q."
When `q = 1`, the original axiom is recovered. When `q` deviates from 1, the structure
is genuinely different.

This is the algebraic analogue of a perturbation. Quantum groups, q-commutative algebras,
and quasi-Hopf algebras all arise from deformations of classical axioms.

### Input / Output

- **Input**: One signature.
- **Output**: One `MoveResult` per deformable axiom. Axioms of kind `CUSTOM` and
  `POSITIVITY` are skipped.

### Algorithm

```
1. Add a new sort "Param" (if not already present)
2. For each axiom in the signature (index i):
   a. Skip if kind is CUSTOM or POSITIVITY
   b. Deep-copy the signature
   c. Remove the original axiom at index i
   d. Based on axiom kind, add a deformed replacement:

      ASSOCIATIVITY on op:
        - Add operation q_op : Param x S -> S  (deformation scaling)
        - Replace: op(op(x,y),z) = op(x,op(y,z))
          with:    op(op(x,y),z) = q_op(q, op(x,op(y,z)))
        - This is "q-associativity"

      COMMUTATIVITY on op:
        - Add operation q_op : Param x S -> S  (deformation scaling)
        - Replace: op(x,y) = op(y,x)
          with:    op(x,y) = q_op(q, op(y,x))
        - This is "q-commutativity"

      Any other kind:
        - Keep the original equation but re-tag it as CUSTOM
          with description "deformed-{kind}"
        - No structural change to the equation itself

   e. Tag the new axiom as AxiomKind.CUSTOM
   f. Emit candidate "{name}_deform({kind})"
```

### Example: Deform(Semigroup, ASSOCIATIVITY)

**Before**:
```
Sorts:      S
Operations: mul : S x S -> S
Axioms:     mul(mul(x,y),z) = mul(x,mul(y,z))   [ASSOCIATIVITY]
```

**After** (`Semigroup_deform(ASSOCIATIVITY)`):
```
Sorts:      S, Param
Operations: mul : S x S -> S
            q_mul : Param x S -> S
Axioms:     mul(mul(x,y),z) = q_mul(q, mul(x,mul(y,z)))   [CUSTOM: q-deformed ASSOCIATIVITY]
```

When `q = 1` and `q_mul` acts as the identity, this reduces to an ordinary semigroup.

### Example: Deform(AbelianGroup, COMMUTATIVITY)

The COMMUTATIVITY axiom `mul(x,y) = mul(y,x)` becomes:

```
mul(x,y) = q_mul(q, mul(y,x))
```

This is a **q-commutative group**. With the remaining axioms (associativity, identity,
inverse) still in place, this describes a structure where commutativity is "twisted" by a
parameter -- the algebraic setting in which quantum groups live.

### When It Is Interesting

- Deformed structures often have **sparser model spectra** than their classical
  counterparts. A structure that has models at every finite size may, after deformation,
  only admit models at specific sizes. This sparsity is a strong interestingness signal.
- **Quantum groups** historically arose as q-deformations of Lie group enveloping
  algebras. The DEFORM move can rediscover this pattern automatically.
- The `q = 0` specialization often yields interesting *degenerations* (e.g.,
  q-associativity at q=0 gives `(x*y)*z = 0`, which collapses the structure into a
  nilpotent regime).
- At depth 2, deforming a transferred signature relaxes the functoriality axiom,
  producing approximate homomorphisms.

---

## M8: SELF_DISTRIB (Single)

### What It Does

SELF_DISTRIB adds self-distributivity to binary operations. For each binary operation, it can produce up to two variants:

1. **Left-only** (`_sd`): `a*(b*c) = (a*b)*(a*c)` -- left self-distributivity
2. **Full** (`_fsd`): Both left AND right self-distributivity: `a*(b*c) = (a*b)*(a*c)` plus `(a*b)*c = (a*c)*(b*c)`

Right self-distributivity was added because research revealed that BOTH left and right self-distributivity are needed for prime-power spectra. The engine can now construct structures with full distributivity in a single move.

### Input / Output

- **Input**: One signature.
- **Output**: Zero to two `MoveResult`s per binary operation:
  - Left-only variant (if left SD not already present)
  - Full variant (both left + right SD, adding whichever is missing)
  - If both already present: no results for that operation

### Algorithm

```
For each binary operation op:
  has_left  = op already has SELF_DISTRIBUTIVITY axiom
  has_right = op already has RIGHT_SELF_DISTRIBUTIVITY axiom

  If has_left AND has_right: skip (nothing to add)

  If NOT has_left:
    - Deep-copy the signature
    - Append Axiom(SELF_DISTRIBUTIVITY, a*(b*c) = (a*b)*(a*c), [op])
    - Emit candidate "{name}_sd({op})"   (left-only)

  Always (unless both present):
    - Deep-copy the signature
    - Add SELF_DISTRIBUTIVITY if not already present
    - Add RIGHT_SELF_DISTRIBUTIVITY: (a*b)*c = (a*c)*(b*c) if not already present
    - Emit candidate "{name}_fsd({op})"  (full)
```

### Example: SelfDistrib(Semigroup)

**Semigroup**: sort `S`, operation `mul: S x S -> S`, axiom `ASSOCIATIVITY(mul)`.

`mul` has neither left nor right self-distributivity, so the move produces both variants.

**Result:** Two candidates:
- `Semigroup_sd(mul)` -- associative + left self-distributive magma
- `Semigroup_fsd(mul)` -- associative + fully self-distributive magma (both left and right)

```
Before:  Semigroup  =  Sig(S, {mul/2}, {ASSOC})
After:   Semigroup_sd(mul)   =  Sig(S, {mul/2}, {ASSOC, SELF_DISTRIB})
         Semigroup_fsd(mul)  =  Sig(S, {mul/2}, {ASSOC, SELF_DISTRIB, RIGHT_SELF_DISTRIB})
```

### Example: SelfDistrib(Ring)

Ring has two binary operations (`add` and `mul`), so the move produces four candidates:
- `Ring_sd(add)` -- left self-distributivity on addition
- `Ring_fsd(add)` -- full self-distributivity on addition
- `Ring_sd(mul)` -- left self-distributivity on multiplication
- `Ring_fsd(mul)` -- full self-distributivity on multiplication

### When It Is Interesting

- Self-distributivity combined with idempotence and invertibility produces **quandles**,
  which classify knots via the knot quandle invariant.
- Adding self-distributivity to an associative operation yields structures related to
  **racks**, which have applications in Yang-Baxter equations and braided monoidal categories.
- The model spectrum of self-distributive structures is often sparser than the base
  structure, signaling genuine constraint.
- Full self-distributivity (left + right together) produces structures with prime-power
  spectra, connecting to deep number-theoretic patterns. The `_fsd` variant provides this
  in a single move.
- At depth 2, combining SELF_DISTRIB with QUOTIENT(IDEM) on a quasigroup recovers the
  full quandle axiomatization.

---

## Composing Moves

The real power of the system comes from **depth-2 and beyond**, where moves compose.
The exploration engine applies all moves to the seed library (depth 1), then applies all
moves again to the depth-1 outputs (depth 2), and so on.

### Composition Examples

| Composition                            | What Happens                                             | Recognizable As                     |
|----------------------------------------|----------------------------------------------------------|-------------------------------------|
| `Complete(Dualize(Semigroup))`         | Commutative semigroup gets identity, inverse, op2, norm  | Commutative monoid / comm. ring direction |
| `Dualize(Complete(Semigroup))`         | Monoid/op2/norm variants get commutativity               | Commutative monoid, etc.            |
| `Transfer(Group, Complete(Semigroup))` | Group maps into a monoid (semigroup + identity)          | Group homomorphism into a monoid    |
| `Deform(Quotient(Group))`             | Abelian group with q-relaxed commutativity               | q-commutative group                 |
| `Internalize(Complete(Semigroup))`     | Monoid's Hom-object: functions S -> S                    | Endomorphism monoid direction       |
| `Abstract(Complete(A), Complete(B))`   | Shared structure of two independently completed objects   | Common algebraic core at next level |
| `Complete(Complete(Semigroup))`        | Monoid gets inverse (= Group); Group gets op2 (= Ring)   | Rediscovers the classical hierarchy |
| `SelfDistrib(Quotient(Quasigroup))`  | Quasigroup + idempotence + self-distributivity     | Quandle (left) or Full-Distrib Quandle |

The last example is particularly significant: by iterating COMPLETE twice starting from
Semigroup, the system walks up the standard algebraic ladder:

```
Semigroup --Complete--> Monoid --Complete--> Group --Complete(+op2)--> Ring-like
```

This demonstrates that the 8 moves are expressive enough to **rediscover known algebraic
relationships** as emergent consequences of structural search.

### Depth Budget

Each depth level multiplies the candidate count roughly 8-fold (6 single moves applied to
each candidate, plus pairwise moves across all pairs). In practice:

- **Depth 0**: 15 seed structures (from `known_structures.py`)
- **Depth 1**: ~319 candidates
- **Depth 2**: ~95,000 candidates

At depth 2, the scoring engine and fingerprint-based deduplication become essential to
keep results manageable.

---

## Performance Characteristics

### Measured Throughput

| Depth | Input Count | Output Count | Wall Time | Notes                      |
|-------|-------------|--------------|-----------|----------------------------|
| 1     | 15          | ~319         | < 0.1s    | All 15 seeds               |
| 2     | ~319        | ~95,000      | ~10s      | Pairwise moves dominate    |
| 3     | ~95,000     | ~50 million  | ~hours    | Rarely needed              |

### Complexity

The move engine's time complexity is:

```
O(6 * n  +  2 * C(n,2))  per depth level
  ^^^^^     ^^^^^^^^^^^
  single    pairwise
  moves     moves
```

Where `n` is the number of input signatures. The 6 single moves each iterate over
operations within a signature (typically 1--4), so the constant factor is small. The 2
pairwise moves (ABSTRACT and TRANSFER) iterate over all unordered pairs.

Across depth levels, the growth is approximately `O(8^d * n_0^2)` where `d` is depth and
`n_0` is the seed count. This is exponential in depth but polynomial within each level.

### Memory

Each `Signature` object is lightweight (a few hundred bytes). At depth 2, ~95,000
candidates require roughly 50--100 MB of memory. The system is entirely CPU-bound with no
GPU requirements.

---

## Implementation Reference

### Key Files

| File                                  | Role                                         |
|---------------------------------------|----------------------------------------------|
| `src/moves/engine.py`                | `MoveEngine` class with all 8 moves          |
| `src/core/signature.py`              | `Signature`, `Sort`, `Operation`, `Axiom`     |
| `src/core/ast_nodes.py`              | `Expr`, `Var`, `Const`, `App`, `Equation`     |
| `src/library/known_structures.py`    | 15 seed structures                            |
| `tests/test_moves.py`                | 28 tests covering all moves + performance     |

### MoveEngine API

```python
from src.moves.engine import MoveEngine, MoveKind

engine = MoveEngine()

# Apply all moves to a list of signatures
results = engine.apply_all_moves([sig_a, sig_b, sig_c])

# Apply a specific move
results = engine.apply_move(MoveKind.COMPLETE, [sig_a, sig_b])

# Individual move methods
engine.abstract(sig_a, sig_b)   # -> list[MoveResult]
engine.dualize(sig)             # -> list[MoveResult]
engine.complete(sig)            # -> list[MoveResult]
engine.quotient(sig)            # -> list[MoveResult]
engine.internalize(sig)         # -> list[MoveResult]
engine.transfer(sig_a, sig_b)   # -> list[MoveResult]
engine.deform(sig)              # -> list[MoveResult]
engine.self_distrib(sig)        # -> list[MoveResult]
```

### MoveResult Structure

```python
@dataclass
class MoveResult:
    signature: Signature    # The generated candidate
    move: MoveKind          # Which move produced it (ABSTRACT, DUALIZE, ...)
    parents: list[str]      # Names of input signature(s)
    description: str        # Human-readable explanation
```

### Naming Convention

Generated signatures follow a consistent naming pattern:

| Move         | Name Pattern                            | Example                        |
|--------------|-----------------------------------------|--------------------------------|
| ABSTRACT     | `Abstract({a},{b})`                     | `Abstract(Group,Ring)`         |
| DUALIZE      | `{name}_dual({op})`                     | `Semigroup_dual(mul)`          |
| COMPLETE     | `{name}+id({op})`, `+inv({op})`, `+op2`, `+norm` | `Monoid+inv(mul)`     |
| QUOTIENT     | `{name}_q({label},{op})`                | `Group_q(COMM,mul)`            |
| INTERNALIZE  | `{name}_int({op})`                      | `Semigroup_int(mul)`           |
| TRANSFER     | `Transfer({a},{b})`                     | `Transfer(Group,Ring)`         |
| DEFORM       | `{name}_deform({kind})`                 | `Semigroup_deform(ASSOCIATIVITY)` |
| SELF_DISTRIB | `{name}_sd({op})` or `{name}_fsd({op})` | `Semigroup_sd(mul)`, `Semigroup_fsd(mul)` |

### Derivation Chain

Every signature carries a `derivation_chain: list[str]` that records the sequence of
moves that produced it. This is the signature's provenance:

```python
sig = results[0].signature
print(sig.derivation_chain)
# ['Complete(identity for mul)', 'Dualize(mul)']
# = This signature was created by completing a semigroup with an identity,
#   then dualizing the result.
```
