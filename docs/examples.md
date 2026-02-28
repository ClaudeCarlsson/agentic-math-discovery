# Worked Examples

This document walks through concrete examples of using the mathematical discovery system, from basic exploration to interpreting results.

---

## Example 1: Rediscovering Abelian Groups

**Goal**: Starting from Group, use the QUOTIENT move to recover AbelianGroup.

```bash
python3 run.py explore --base Group --moves QUOTIENT --depth 1
```

**What happens:**
1. The MoveEngine examines Group's binary operation `mul`
2. `mul` is not commutative → QUOTIENT adds COMMUTATIVITY
3. `mul` is not idempotent → QUOTIENT adds IDEMPOTENCE

**Result:** Two candidates:
- `Group_q(COMM,mul)` — a group with commutative multiplication = AbelianGroup
- `Group_q(IDEM,mul)` — a group where x*x = x for all x (only the trivial group satisfies this with inverses)

**Verification:**
```bash
python3 run.py explore --base Group --moves QUOTIENT --depth 1 --check-models --max-size 5
```

The commutative variant has many models (abelian groups exist at every order). The idempotent variant has only the trivial model at size 1 — it's a contradiction for groups of size > 1 (since x*x = x and x*inv(x) = e implies x = e for all x).

---

## Example 2: From Semigroup to Ring (via COMPLETE)

**Goal**: Show that applying COMPLETE twice to a Semigroup recovers a ring-like structure.

```bash
python3 run.py explore --base Semigroup --moves COMPLETE --depth 2 --top 20
```

**Depth 1 produces:**
- `Semigroup+id(mul)` — adds identity element → this is a Monoid
- `Semigroup+op2` — adds second binary op with distributivity
- `Semigroup+norm` — adds norm function with positivity

**Depth 2 applies COMPLETE again to each depth-1 result:**
- `Semigroup+id(mul)+inv(mul)` — Monoid + inverse → this is a Group!
- `Semigroup+id(mul)+op2` — Monoid + second op with distributivity → Ring-like!
- `Semigroup+op2+id(op2)` — second op gets its own identity

The system rediscovers the Semigroup → Monoid → Group → Ring hierarchy through pure structural exploration.

---

## Example 3: Inspecting Group Models

```bash
python3 run.py inspect Group --max-size 6
```

**Output interpretation:**

The model spectrum shows:
```
Size | Models
  2  |   2
  3  |   3
  4  |  10
  5  |  10
  6  |  10
```

At size 2, there are 2 groups (both isomorphic to Z/2Z — Z3 doesn't deduplicate by isomorphism, so it may find equivalent tables). At size 4, the 10 models include Z/4Z, Z/2Z × Z/2Z, and relabelings. The count of 10 is capped by `max_models_per_size`.

**Scoring breakdown:**
- `has_models: 1.0` — models exist
- `model_diversity: 0.94` — models at all tested sizes with multiple per size
- `spectrum_pattern: 0.7` — arithmetic progression (sizes 2,3,4,5,6)
- `is_novel: 0.0` — Group is a known structure
- `total: ~0.59` — moderate (known structure, so novelty scores are 0)

---

## Example 4: Exploring Quasigroup Variants

Quasigroups (Latin squares) are a rich source of novel structures.

```bash
python3 run.py explore --base Quasigroup --depth 1 --check-models --max-size 5 --top 10
```

**Interesting candidates:**
- `Quasigroup_dual(mul)` — commutative quasigroup (commutative Latin square)
- `Quasigroup_q(IDEM,mul)` — idempotent quasigroup (diagonal is a permutation)
- `Quasigroup+norm` — quasigroup with a norm function
- `Quasigroup_int(mul)` — Hom-object quasigroup (internalizes the operation)

Idempotent quasigroups are particularly interesting: they correspond to Steiner systems in combinatorics. Their model spectrum is sparser than general quasigroups.

---

## Example 5: Transfer Between Domains

Transfer connects two algebraic structures with a homomorphism:

```bash
python3 run.py explore --base Group --base Lattice --moves TRANSFER --depth 1 --check-models --max-size 4
```

**Result:** `Transfer(Group, Lattice)` creates a structure with:
- Sort G (from Group), Sort L (from Lattice)
- All group operations (prefixed `a_mul`, `a_e`, `a_inv`)
- All lattice operations (prefixed `b_meet`, `b_join`)
- A transfer morphism: `transfer: G → L`
- Functoriality: `transfer(a_mul(x,y)) = b_meet(transfer(x), transfer(y))`

This is a group-to-lattice homomorphism — the transfer maps group multiplication to lattice meet. Models of this structure are groups equipped with a lattice structure on the same underlying set, connected by a structure-preserving map.

---

## Example 6: Deforming Associativity

```bash
python3 run.py explore --base AbelianGroup --moves DEFORM --depth 1 --check-models --max-size 4
```

**The DEFORM move on AbelianGroup produces candidates for each axiom:**
- `AbelianGroup_deform(ASSOCIATIVITY)` — q-associativity: (x*y)*z = q*(x*(y*z))
- `AbelianGroup_deform(IDENTITY)` — deformed identity
- `AbelianGroup_deform(INVERSE)` — deformed inverse
- `AbelianGroup_deform(COMMUTATIVITY)` — q-commutativity: x*y = q*(y*x)

The q-deformed structures are related to quantum groups in mathematical physics. At q=1, you recover the original structure. At other values of q, you get a genuinely different algebraic object.

---

## Example 7: Programmatic Pipeline

```python
from src.library.known_structures import group, semigroup
from src.moves.engine import MoveEngine, MoveKind
from src.scoring.engine import ScoringEngine
from src.solvers.z3_solver import Z3ModelFinder

# Set up components
engine = MoveEngine()
scorer = ScoringEngine()
z3 = Z3ModelFinder(timeout_ms=10000)

# Generate candidates from Group
results = engine.apply_all_moves([group()])
print(f"Generated {len(results)} candidates")

# Score them (structural only, no models yet)
scored = []
for r in results:
    score = scorer.score(r.signature)
    scored.append((r, score))

scored.sort(key=lambda x: x[1].total, reverse=True)

# Check models for the top 5
for r, score in scored[:5]:
    sig = r.signature
    spectrum = z3.compute_spectrum(sig, min_size=2, max_size=5)

    # Re-score with model information
    full_score = scorer.score(sig, spectrum)

    print(f"\n{sig.name}")
    print(f"  Move: {r.move.value}")
    print(f"  Structural score: {score.total:.3f}")
    print(f"  Full score: {full_score.total:.3f}")
    print(f"  Spectrum: {spectrum.spectrum}")
    print(f"  Has models: {not spectrum.is_empty()}")
```

---

## Example 8: Custom Scoring Weights

Focus the search on model-theoretic properties:

```python
from src.scoring.engine import ScoringEngine

# Weight model properties heavily
model_weights = {
    "connectivity": 0.02,
    "richness": 0.02,
    "tension": 0.02,
    "economy": 0.04,
    "fertility": 0.02,
    "has_models": 0.25,       # doubled
    "model_diversity": 0.20,  # doubled
    "spectrum_pattern": 0.20, # doubled
    "is_novel": 0.15,
    "distance": 0.08,
}

scorer = ScoringEngine(weights=model_weights)
```

---

## Example 9: Finding Structures with Prime-Only Spectra

A dream scenario: a structure whose models exist only at prime sizes.

```python
from src.library.known_structures import load_all_known
from src.moves.engine import MoveEngine
from src.solvers.z3_solver import Z3ModelFinder

engine = MoveEngine()
z3 = Z3ModelFinder(timeout_ms=15000)
primes = {2, 3, 5, 7}

# Generate depth-1 candidates
bases = load_all_known()
results = engine.apply_all_moves(bases)

# Check each for prime-only spectrum
for r in results:
    spectrum = z3.compute_spectrum(r.signature, min_size=2, max_size=8, max_models_per_size=1)
    sizes = spectrum.sizes_with_models()

    if len(sizes) >= 2 and all(s in primes for s in sizes):
        composites_checked = [s for s in range(4, 9) if s not in primes]
        no_composite_models = all(spectrum.spectrum.get(s, 0) == 0 for s in composites_checked)

        if no_composite_models:
            print(f"PRIME-ONLY: {r.signature.name}")
            print(f"  Spectrum: {spectrum.spectrum}")
            print(f"  Move: {r.move.value}")
            print(f"  Parents: {r.parents}")
```

---

## Example 10: Building a Discovery Report

After running the agent, review and analyze results:

```bash
# Run the agent (uses Claude Code CLI with Opus + high-effort thinking)
python3 run.py agent --cycles 10 --goal "find novel loop variants" \
  --base Loop --base Quasigroup --base Group

# You'll see live progress throughout:
#   [   0s] PLAN
#   [  43s] Claude planning done (43s, 55 lines)
#   [  43s] Strategy: Loops occupy a rich intermediate space...
#   [  44s] Checking models for top 10 candidates...
#   [  44s]   [ 1/10] Loop_q(COMM,mul)_int(mul) sizes={2,3,4,5,6} models=44 (0.8s)
#   ...

# View the latest report
python3 run.py report --cycle latest

# View all discoveries sorted by score
python3 run.py report --top 50 --sort-by score

# Programmatic access
python3 -c "
from src.library.manager import LibraryManager
lib = LibraryManager('library')
for d in lib.list_discovered():
    print(f\"{d['id']}: {d['name']} (score: {d['score']:.3f})\")
    print(f\"  Chain: {d['derivation_chain']}\")
    print()
"
```
