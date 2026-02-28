# Known Algebraic Structures

The system ships with 14 seed algebraic structures. These are the starting points from which all candidates are derived via structural moves.

Each structure is defined as a **signature**: a collection of sorts (types), operations (typed functions), and axioms (equational laws).

---

## Structure Hierarchy

```
Magma (no axioms)
 └─ Semigroup (+associativity)
     └─ Monoid (+identity)
         └─ Group (+inverse)
             └─ AbelianGroup (+commutativity)

Ring = AbelianGroup(add) + Semigroup(mul) + distributivity
 └─ Field (+commutative mul + multiplicative inverse)

Lattice = two commutative, associative, idempotent ops + absorption

Quasigroup (Latin square: left/right division)
 └─ Loop (+identity)

LieAlgebra = VectorSpace + antisymmetric bracket + Jacobi identity

VectorSpace = AbelianGroup(add) + scalar multiplication
 └─ InnerProductSpace (+symmetric bilinear form + positivity)

Category = objects + morphisms + associative composition + identities
```

---

## Detailed Definitions

### 1. Magma

The simplest algebraic structure: a set with a binary operation and no axioms at all.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `S` — carrier set |
| **Operations** | `mul: S × S → S` |
| **Axioms** | *(none)* |

Every finite set with every possible binary operation is a magma. There are n^(n²) magmas of order n.

---

### 2. Semigroup

A magma where the operation is associative.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `S` — carrier set |
| **Operations** | `mul: S × S → S` |
| **Axioms** | `(x mul y) mul z = x mul (y mul z)` — ASSOCIATIVITY |

Examples: (ℕ, +), (ℕ, ×), string concatenation.

---

### 3. Monoid

A semigroup with an identity element.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `S` — carrier set |
| **Operations** | `mul: S × S → S`, `e: () → S` |
| **Axioms** | ASSOCIATIVITY, `x mul e = x` — IDENTITY |

Examples: (ℕ, ×, 1), (strings, concat, "").

---

### 4. Group

A monoid where every element has an inverse.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `G` — group elements |
| **Operations** | `mul: G × G → G`, `e: () → G`, `inv: G → G` |
| **Axioms** | ASSOCIATIVITY, IDENTITY, `x mul inv(x) = e` — INVERSE |

The most studied algebraic structure. Every finite group has a Cayley table that is a Latin square.

Model spectrum: groups exist at every size ≥ 1. Number of groups of order n (up to isomorphism):
- n=1: 1, n=2: 1, n=3: 1, n=4: 2, n=5: 1, n=6: 2, n=7: 1, n=8: 5

---

### 5. AbelianGroup

A group where the operation is commutative.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `G` — group elements |
| **Operations** | `mul: G × G → G`, `e: () → G`, `inv: G → G` |
| **Axioms** | ASSOCIATIVITY, IDENTITY, INVERSE, `x mul y = y mul x` — COMMUTATIVITY |

By the fundamental theorem, every finite abelian group is a direct product of cyclic groups.

---

### 6. Ring

An abelian group (under addition) with a second associative operation (multiplication) that distributes over addition.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `R` — ring elements |
| **Operations** | `add: R × R → R`, `mul: R × R → R`, `zero: () → R`, `neg: R → R` |
| **Axioms** | ASSOCIATIVITY(add), COMMUTATIVITY(add), IDENTITY(add, zero), INVERSE(add, neg), ASSOCIATIVITY(mul), `mul(a, add(b,c)) = add(mul(a,b), mul(a,c))` — DISTRIBUTIVITY |

Examples: ℤ, ℤ/nℤ, polynomial rings, matrix rings.

---

### 7. Field

A commutative ring where every nonzero element has a multiplicative inverse.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `R` — field elements |
| **Operations** | `add`, `mul`, `zero`, `neg`, `one: () → R`, `recip: R → R` |
| **Axioms** | All ring axioms + COMMUTATIVITY(mul) + IDENTITY(mul, one) |

Finite fields exist at sizes p^k for prime p. The Galois field GF(p^k) is unique up to isomorphism.

---

### 8. Lattice

A set with two binary operations (meet and join) satisfying absorption laws.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `L` — lattice elements |
| **Operations** | `meet: L × L → L`, `join: L × L → L` |
| **Axioms** | ASSOCIATIVITY(meet), ASSOCIATIVITY(join), COMMUTATIVITY(meet), COMMUTATIVITY(join), IDEMPOTENCE(meet), IDEMPOTENCE(join), `meet(x, join(x, y)) = x` — ABSORPTION, `join(x, meet(x, y)) = x` — ABSORPTION |

Examples: power set lattice, divisibility lattice on ℕ.

---

### 9. Quasigroup

A set with a binary operation that forms a Latin square: for any a, b, the equations a*x = b and y*a = b have unique solutions.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `Q` — quasigroup elements |
| **Operations** | `mul: Q × Q → Q`, `ldiv: Q × Q → Q` (left division), `rdiv: Q × Q → Q` (right division) |
| **Axioms** | `mul(x, ldiv(x, y)) = y`, `mul(rdiv(x, y), y) = x`, `ldiv(x, mul(x, y)) = y`, `rdiv(mul(x, y), y) = x` |

A finite quasigroup of order n is equivalent to a Latin square of order n. There is no associativity requirement.

---

### 10. Loop

A quasigroup with a two-sided identity element.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `Q` — loop elements |
| **Operations** | `mul`, `ldiv`, `rdiv`, `e: () → Q` |
| **Axioms** | All quasigroup axioms + `mul(x, e) = x` — IDENTITY |

Loops are a rich source of interesting finite structures. Moufang loops, Bol loops, and other varieties have deep connections to geometry and combinatorics.

---

### 11. Lie Algebra

A vector space with an antisymmetric bracket satisfying the Jacobi identity.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `L` — Lie algebra elements, `K` — scalar field |
| **Operations** | `add: L × L → L`, `scale: K × L → L`, `bracket: L × L → L`, `neg: L → L`, `zero: () → L` |
| **Axioms** | ASSOCIATIVITY(add), COMMUTATIVITY(add), IDENTITY(add, zero), INVERSE(add, neg), `bracket(x,y) = neg(bracket(y,x))` — ANTICOMMUTATIVITY, `add(bracket(x,bracket(y,z)), bracket(y,bracket(z,x))) = neg(bracket(z,bracket(x,y)))` — JACOBI, BILINEARITY(bracket, add) |

Lie algebras are the infinitesimal version of Lie groups. They arise in physics (symmetries), differential geometry, and representation theory.

---

### 12. VectorSpace

A module over a field with vector addition and scalar multiplication.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `V` — vectors, `K` — scalars |
| **Operations** | `add: V × V → V`, `scale: K × V → V`, `neg: V → V`, `zero: () → V` |
| **Axioms** | ASSOCIATIVITY(add), COMMUTATIVITY(add), IDENTITY(add, zero), INVERSE(add, neg) |

The simplest multi-sorted structure in the library. Important as a base for inner product spaces and Lie algebras.

---

### 13. InnerProductSpace

A vector space equipped with a symmetric, positive-definite bilinear form.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `V` — vectors, `K` — scalars |
| **Operations** | `add`, `scale`, `neg`, `zero`, `inner: V × V → K` |
| **Axioms** | All VectorSpace axioms + `inner(x,y) = inner(y,x)` — COMMUTATIVITY(inner), `inner(x,x) ≥ 0` — POSITIVITY |

The positivity axiom is encoded symbolically (as a self-equality) since first-order logic cannot directly express inequalities. The scoring system treats POSITIVITY as a special marker.

Important as a starting point for RH-relevant searches: positivity + bilinear form + functorial maps.

---

### 14. Category

The signature of a category: objects, morphisms, and associative composition.

| Component | Definition |
|-----------|-----------|
| **Sorts** | `Ob` — objects, `Mor` — morphisms |
| **Operations** | `comp: Mor × Mor → Mor`, `id: Ob → Mor`, `dom: Mor → Ob`, `cod: Mor → Ob` |
| **Axioms** | ASSOCIATIVITY(comp), `comp(f, id(dom(f))) = f` — right identity, `comp(id(cod(f)), f) = f` — left identity |

Categories are the most abstract structure in the library. They bridge all other structures: groups form a category, rings form a category, etc.

---

## Adding New Structures

To add a new seed structure:

1. Create a factory function in `src/library/known_structures.py`:

```python
def boolean_algebra() -> Signature:
    sig = lattice()
    sig.name = "BooleanAlgebra"
    sig.operations.append(Operation("compl", ["L"], "L", "complement"))
    # Add complement axioms...
    return sig
```

2. Register it in the `KNOWN_STRUCTURES` dict:

```python
KNOWN_STRUCTURES["BooleanAlgebra"] = boolean_algebra
```

3. Add tests in `tests/test_library.py`.

---

## Fingerprint Uniqueness

Each structure has a fingerprint based on its shape (sort count, operation arities, axiom kinds). Most of the 14 structures have unique fingerprints, but some may collide if they share the same abstract shape. The fingerprint is used for novelty checking — candidates with fingerprints matching known structures are scored as non-novel.
