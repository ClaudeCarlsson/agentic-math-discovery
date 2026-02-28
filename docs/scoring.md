# Interestingness Scoring Reference

The scoring engine evaluates candidate algebraic signatures across 10 dimensions. Each dimension produces a value in [0, 1]. The final score is a weighted sum of all dimensions.

Source: `src/scoring/engine.py`

---

## Table of Contents

- [Overview](#overview)
- [Default Weights](#default-weights)
- [Structural Quality (40%)](#structural-quality)
  - [Connectivity](#1-connectivity)
  - [Richness](#2-richness)
  - [Tension](#3-tension)
  - [Economy](#4-economy)
  - [Fertility](#5-fertility)
- [Model-Theoretic Quality (35%)](#model-theoretic-quality)
  - [Has Models](#6-has-models)
  - [Model Diversity](#7-model-diversity)
  - [Spectrum Pattern](#8-spectrum-pattern)
- [Novelty (25%)](#novelty)
  - [Is Novel](#9-is-novel)
  - [Distance](#10-distance)
- [Interpreting Scores](#interpreting-scores)
- [Customizing Weights](#customizing-weights)
- [Design Philosophy](#design-philosophy)

---

## Overview

Every candidate signature produced by the move engine passes through the `ScoringEngine`. The engine computes a `ScoreBreakdown` with one float per dimension and a weighted total. The total determines whether the candidate enters the library, gets explored further, or gets discarded.

The 10 dimensions fall into three groups:

| Group               | Weight | Purpose                                     |
|---------------------|--------|---------------------------------------------|
| Structural Quality  | 40%    | Is the signature well-formed and balanced?   |
| Model-Theoretic     | 35%    | Does it have interesting finite models?      |
| Novelty             | 25%    | Is it genuinely new?                         |

---

## Default Weights

```python
DEFAULT_WEIGHTS = {
    "connectivity": 0.08,
    "richness": 0.08,
    "tension": 0.08,
    "economy": 0.10,
    "fertility": 0.06,
    "has_models": 0.15,
    "model_diversity": 0.10,
    "spectrum_pattern": 0.10,
    "is_novel": 0.15,
    "distance": 0.10,
}
```

Weights sum to 1.0. The total score is:

```
total = sum(weight[d] * score[d] for d in dimensions)
```

---

## Structural Quality

These five dimensions measure the intrinsic shape of the signature -- whether its sorts, operations, and axioms form a balanced, well-connected whole. They require no model checking and are computed directly from the signature definition.

Total structural weight: 0.08 + 0.08 + 0.08 + 0.10 + 0.06 = **0.40**


### 1. Connectivity

**Weight: 0.08**

Measures how well the operations connect the sorts in a multi-sorted signature.

**Formula:**

For single-sorted signatures (one sort): always returns **0.5** (neutral).

For multi-sorted signatures:

```
sort_coverage  = |sorts touched by operations| / |all sorts|
cross_sort_ratio = |cross-sort operations| / |all operations|
connectivity   = (sort_coverage + cross_sort_ratio) / 2
```

A *cross-sort operation* is one whose domain and codomain span more than one sort. For example, scalar multiplication `scale: K x V -> V` is cross-sort because it involves both sorts K and V.

**Intuition:** A multi-sorted signature where operations never mix sorts is really just several disconnected single-sorted signatures glued together. Connectivity rewards operations that bridge different sorts, creating genuine multi-sorted structure.

**Examples using known structures:**

| Signature         | Sorts | Cross-sort ops                  | Connectivity |
|-------------------|-------|---------------------------------|--------------|
| Group             | 1     | (single-sorted)                 | 0.50         |
| Ring              | 1     | (single-sorted)                 | 0.50         |
| VectorSpace       | V, K  | scale: K x V -> V               | ~0.75        |
| InnerProductSpace | V, K  | scale: K x V -> V, inner: V x V -> K | ~0.80  |
| LieAlgebra        | L, K  | scale: K x L -> L               | ~0.58        |

**When it matters:** This dimension primarily differentiates multi-sorted candidates. For single-sorted structures (the majority of classical algebra), it contributes a flat 0.04 to the total (0.08 * 0.5).


### 2. Richness

**Weight: 0.08**

Measures the axiom-to-operation ratio, rewarding signatures where each operation is constrained by roughly one axiom.

**Formula:**

```
ratio    = |axioms| / max(|operations|, 1)
richness = exp(-(ratio - 1.0)^2)
```

This is a Gaussian centered at ratio = 1.0. The score decays symmetrically as the ratio moves away from 1.0 in either direction.

**Intuition:** An algebraic structure is most interesting when its axioms and operations are in balance:

- **Underconstrained** (ratio << 1): Many operations with few axioms. The structure is too free -- almost anything satisfies it. Example: a magma (1 operation, 0 axioms, ratio = 0) scores `exp(-1) = 0.37`.
- **Balanced** (ratio near 1): Each operation is meaningfully constrained. Example: a semigroup (1 operation, 1 axiom, ratio = 1.0) scores `exp(0) = 1.0`.
- **Overconstrained** (ratio >> 1): Many axioms on few operations. The structure is likely trivial or contradictory. Example: 5 axioms on 1 operation (ratio = 5) scores `exp(-16) ~ 0.0`.

**Worked examples:**

| Signature   | Ops | Axioms | Ratio | Richness |
|-------------|-----|--------|-------|----------|
| Magma       | 1   | 0      | 0.0   | 0.37     |
| Semigroup   | 1   | 1      | 1.0   | 1.00     |
| Monoid      | 2   | 2      | 1.0   | 1.00     |
| Group       | 3   | 3      | 1.0   | 1.00     |
| Ring        | 4   | 6      | 1.5   | 0.80     |
| Lattice     | 2   | 8      | 4.0   | 0.00     |

Note: Lattice scores very low on richness because it has 8 axioms for just 2 operations. This is compensated by high tension (many axiom kinds) and other dimensions.


### 3. Tension

**Weight: 0.08**

Measures the diversity of axiom kinds present in the signature.

**Formula:**

```
tension = min(|unique axiom kinds| / 6, 1.0)
```

The denominator is capped at 6 regardless of how many `AxiomKind` values exist in the enum (currently 16). This means a signature needs 6 distinct axiom kinds to reach the maximum score.

**Intuition:** A structure that combines associativity, commutativity, distributivity, and positivity is more interesting than one with four copies of the same axiom kind. Diverse axiom kinds create *tension* -- the operations must satisfy qualitatively different constraints simultaneously, which is the hallmark of rich mathematical structure.

**The available axiom kinds:**

```
ASSOCIATIVITY, COMMUTATIVITY, IDENTITY, INVERSE, DISTRIBUTIVITY,
ANTICOMMUTATIVITY, IDEMPOTENCE, NILPOTENCE, JACOBI, POSITIVITY,
BILINEARITY, HOMOMORPHISM, FUNCTORIALITY, ABSORPTION, MODULARITY,
CUSTOM
```

**Worked examples:**

| Signature   | Axiom kinds                                | Unique | Tension |
|-------------|---------------------------------------------|--------|---------|
| Semigroup   | {ASSOC}                                     | 1      | 0.17    |
| Group       | {ASSOC, IDENTITY, INVERSE}                  | 3      | 0.50    |
| Ring        | {ASSOC, COMM, IDENTITY, INVERSE, DISTRIB}   | 5      | 0.83    |
| LieAlgebra  | {ASSOC, COMM, IDENTITY, INVERSE, ANTICOMM, JACOBI, BILINEAR} | 7 | 1.00 |
| Lattice     | {ASSOC, COMM, IDEMPOTENCE, ABSORPTION}      | 4      | 0.67    |

**Edge case:** A signature with no axioms returns 0.0.


### 4. Economy

**Weight: 0.10**

Occam's razor applied to signatures. Simpler signatures that still constrain heavily are preferred.

**Formula:**

```
total_size = |sorts| + |operations| + |axioms|

if total_size <= 2:  return 0.4
if total_size <= 12: return 1.0 - max(0, total_size - 5) * 0.04
if total_size > 12:  return max(0.1, 1.0 - total_size * 0.04)
```

This is a piecewise linear function:

```
Size:  1   2   3   4   5   6   7   8   9  10  11  12  15  20  25
Score: 0.4 0.4 1.0 1.0 1.0 0.96 0.92 0.88 0.84 0.80 0.76 0.72 0.40 0.20 0.10
```

Peak score (1.0) is at sizes 3-5. Signatures smaller than 3 are too trivial (0.4). Signatures larger than 12 are penalized steeply. The floor is 0.1.

**Intuition:** The best mathematical structures tend to be compact. A group (1 sort + 3 ops + 3 axioms = 7) packs a lot of structure into few components. A bloated signature with 20 components is likely an artifact of mechanical generation rather than a genuine mathematical object.

**Worked examples:**

| Signature         | Sorts | Ops | Axioms | Size | Economy |
|-------------------|-------|-----|--------|------|---------|
| Magma             | 1     | 1   | 0      | 2    | 0.40    |
| Semigroup         | 1     | 1   | 1      | 3    | 1.00    |
| Monoid            | 1     | 2   | 2      | 5    | 1.00    |
| Group             | 1     | 3   | 3      | 7    | 0.92    |
| AbelianGroup      | 1     | 3   | 4      | 8    | 0.88    |
| Ring              | 1     | 4   | 6      | 11   | 0.76    |
| Lattice           | 1     | 2   | 8      | 11   | 0.76    |
| LieAlgebra        | 2     | 5   | 7      | 14   | 0.44    |

Economy is the highest-weighted structural dimension (0.10). It acts as a soft penalty on move sequences that pile up sorts, operations, and axioms.


### 5. Fertility

**Weight: 0.06**

Can further constructions be built on this signature? Estimates the potential for the move engine to produce interesting children.

**Formula:**

```
sort_score = min(|sorts| / 3, 1.0)
op_score   = min(|binary operations| / 3, 1.0)
fertility  = (sort_score + op_score) / 2
```

**Intuition:** A signature with multiple sorts and binary operations gives the move engine more raw material. Binary operations are the fundamental building blocks -- they can be dualized, composed, distributed over each other, and used to define new operations. More sorts mean more potential for cross-sort moves like Transfer and Internalize.

**Worked examples:**

| Signature     | Sorts | Binary ops | Fertility |
|---------------|-------|------------|-----------|
| Magma         | 1     | 1          | 0.33      |
| Semigroup     | 1     | 1          | 0.33      |
| Group         | 1     | 1          | 0.33      |
| Ring          | 1     | 2          | 0.50      |
| Lattice       | 1     | 2          | 0.50      |
| Quasigroup    | 1     | 3          | 0.67      |
| VectorSpace   | 2     | 1          | 0.50      |
| LieAlgebra    | 2     | 2          | 0.67      |

**Why the lowest weight?** Fertility is forward-looking -- it predicts potential rather than measuring actual quality. It gets the smallest weight (0.06) because the system should not favor structures just because they are rich in components. Economy (0.10) counterbalances fertility by penalizing bloated signatures.

---

## Model-Theoretic Quality

These three dimensions require running a model checker (Z3 or Mace4) to find finite models of the signature. They provide the strongest signal of mathematical substance. A signature that passes structural checks but has no models is vacuous.

Total model-theoretic weight: 0.15 + 0.10 + 0.10 = **0.35**

If no spectrum is provided to `ScoringEngine.score()`, all three dimensions default to 0.0.


### 6. Has Models

**Weight: 0.15**

Binary check: does the signature have at least one non-trivial finite model?

**Formula:**

```
has_models = 1.0  if spectrum is not empty
has_models = 0.0  otherwise
```

A spectrum is "not empty" when `ModelSpectrum.total_models() > 0`, meaning at least one domain size has at least one model.

**Intuition:** This is the single most important dimension. A signature with no finite models is either:

1. **Contradictory** -- the axioms are mutually inconsistent. No structure can satisfy them all.
2. **Only infinite** -- models exist but are all infinite (like the theory of dense linear orders). These are mathematically real but not discoverable by finite model checking.

Either way, the system cannot verify the structure, so it scores zero on all model-theoretic dimensions. This makes it nearly impossible for a modelless signature to reach the "interesting" threshold.

**Impact on total score:** Since has_models is binary and weighted at 0.15, a signature without models loses 0.15 from the maximum total. Combined with model_diversity (0.10) and spectrum_pattern (0.10) also being zero, that is 0.35 total -- over a third of the possible score.


### 7. Model Diversity

**Weight: 0.10**

How many non-isomorphic models exist across how many domain sizes?

**Formula:**

```
sizes_with   = |{n : spectrum[n] > 0}|        # sizes that have at least one model
size_range   = max(spectrum keys) - min(spectrum keys) + 1
coverage     = sizes_with / size_range

avg_per_size = total_models / sizes_with
count_score  = 1 - exp(-avg_per_size / 3)

model_diversity = (coverage + count_score) / 2
```

**Two sub-scores:**

- **Coverage** (0-1): What fraction of the tested size range has models? A signature with models at sizes 2, 3, 4, 5, 6, 7, 8 (coverage = 7/7 = 1.0) scores higher than one with models only at sizes 2 and 7 (coverage = 2/6 = 0.33).
- **Count score** (0-1): Are there multiple non-isomorphic models per size? The exponential decay `1 - exp(-x/3)` saturates around 3+ models per size. Having 1 model per size gives count_score ~ 0.28. Having 3 gives ~ 0.63. Having 10 gives ~ 0.96.

**Intuition:** A structure with many non-isomorphic models at diverse sizes is rich. Groups are a prime example: there are 1 group of order 1, 1 of order 2, 1 of order 3, 2 of order 4, ..., 5 of order 8. This diversity signals genuine mathematical depth. A structure with exactly one model at one size is likely an artifact.

**Worked example:**

Consider a spectrum `{2: 1, 3: 2, 4: 3, 5: 0, 6: 1}`:

```
sizes_with   = {2, 3, 4, 6} => 4
size_range   = 6 - 2 + 1 = 5
coverage     = 4/5 = 0.80

total_models = 1 + 2 + 3 + 1 = 7
avg_per_size = 7/4 = 1.75
count_score  = 1 - exp(-1.75/3) = 1 - exp(-0.583) = 0.44

model_diversity = (0.80 + 0.44) / 2 = 0.62
```


### 8. Spectrum Pattern

**Weight: 0.10**

Does the model spectrum (which sizes have models) show a non-random pattern?

The engine checks for five specific patterns, in order of how remarkable they are:

| Pattern               | Score | Detection rule                                    |
|-----------------------|-------|---------------------------------------------------|
| Prime-only sizes      | 0.9   | All model sizes are in {2, 3, 5, 7, 11, 13, 17, 19, 23} |
| Power-of-2 sizes      | 0.8   | All model sizes are in {1, 2, 4, 8, 16, 32}      |
| Arithmetic progression| 0.7   | Consecutive size differences are all equal         |
| Geometric progression | 0.7   | Consecutive size ratios differ by less than 0.1    |
| Monotone increasing counts | 0.5 | Model counts increase with size               |

The highest matching score wins. If no pattern is detected, the score is 0.0.
Requires at least 2 sizes with models; returns 0.0 for fewer.

**Intuition:** If a structure has models only at prime sizes, that is a strong signal of a deep number-theoretic connection (like how fields of order n exist if and only if n is a prime power). Such patterns do not arise by accident.

**Worked examples:**

| Spectrum                  | Sizes with models | Pattern        | Score |
|---------------------------|-------------------|----------------|-------|
| {2:1, 3:1, 5:1, 7:1}     | 2, 3, 5, 7        | Prime-only     | 0.9   |
| {2:1, 4:1, 8:1}          | 2, 4, 8            | Power-of-2     | 0.8   |
| {2:1, 4:1, 6:1, 8:1}     | 2, 4, 6, 8         | Arithmetic (d=2)| 0.7   |
| {2:1, 3:2, 4:3, 5:5}     | 2, 3, 4, 5         | Monotone counts| 0.5   |
| {2:1, 5:1, 6:0, 9:1}     | 2, 5, 9            | None           | 0.0   |

**Implementation note:** The prime set is hardcoded to `{2, 3, 5, 7, 11, 13, 17, 19, 23}` and the power-of-2 set to `{1, 2, 4, 8, 16, 32}`, matching the practical range of sizes tested by the model checker (typically 2-8, sometimes up to 32).

---

## Novelty

These two dimensions measure whether the candidate is genuinely new or just a relabeled copy of something already known.

Total novelty weight: 0.15 + 0.10 = **0.25**


### 9. Is Novel

**Weight: 0.15**

Binary check: is the signature's fingerprint absent from the known set?

**Formula:**

```
fingerprint = SHA-256(sort_count, sorted_op_arities, sorted_axiom_kinds)[:16]

is_novel = 0.0  if fingerprint in known_fingerprints
is_novel = 1.0  otherwise
```

The fingerprint is a 16-character hex string computed by `Signature.fingerprint()`. It captures the structural shape of a signature -- sort count, sorted list of operation arities, sorted list of axiom kinds -- but not the names. Two signatures that differ only in naming (e.g., "mul" vs "op1", sort "G" vs sort "S") produce the same fingerprint.

**What the fingerprint captures:**

```python
# These two have the SAME fingerprint:
Sig(name="Group", sorts=["G"], ops=[mul/2, e/0, inv/1],
    axioms=[ASSOC, IDENTITY, INVERSE])

Sig(name="MyGroup", sorts=["X"], ops=[star/2, unit/0, flip/1],
    axioms=[ASSOC, IDENTITY, INVERSE])

# Canon: {"sorts": 1, "op_arities": [0, 1, 2], "axiom_kinds": ["ASSOC", "IDENTITY", "INVERSE"]}
```

**What it does not capture:** Operation domain/codomain sort assignments, axiom equations, or derivation history. Two signatures with the same fingerprint might have different axiom equations or sort assignments. The fingerprint is a fast filter, not a full isomorphism check.

**Interaction with the library:** When scoring, the caller passes `known_fingerprints`, the set of fingerprints to check against. The agent's `ToolExecutor` calls `LibraryManager.all_fingerprints()`, which includes both the 14 seed structures and all previously discovered structures. Any candidate matching an existing fingerprint scores 0.0. The impact is large: 0.15 weight means rediscovering a known or previously discovered structure loses 15% of the maximum score.


### 10. Distance

**Weight: 0.10**

How far is this candidate from known structures in the derivation space?

**Formula:**

```
length_score    = min(|derivation_chain| / 5, 1.0)
diversity_score = |unique move kinds used| / 7

distance = (length_score + diversity_score) / 2
```

The derivation chain is a list of strings stored on each `Signature` that records which moves were applied to produce it. Each entry is a human-readable description like `"Dualize(Group)"` or `"Complete(Semigroup_dual)"`.

The 7 possible move kinds, matched by substring:

```
Abstract, Dualize, Complete, Quotient, Internalize, Transfer, Deform
```

**Intuition:** A candidate produced by a long chain of diverse moves is further from known territory. A single dualization of a group is still "close" to groups. But if you dualize, then complete, then abstract, then transfer -- that is 4 moves with 4 kinds, giving:

```
length_score    = min(4/5, 1.0) = 0.80
diversity_score = 4/7 = 0.57
distance        = (0.80 + 0.57) / 2 = 0.69
```

**Edge case:** A base structure from the known library has an empty derivation chain, so distance = 0.0. This is correct -- known structures are at distance zero from themselves.

**Why two sub-scores?** Length alone would reward trivially repeated moves (e.g., applying Dualize five times just bounces back and forth). Diversity ensures the exploration genuinely covers different structural transformations.

---

## Interpreting Scores

| Score Range | Interpretation                               | Typical signature profile             |
|-------------|----------------------------------------------|---------------------------------------|
| 0.0 -- 0.2  | Trivial or contradictory                    | No models, no novelty, bloated        |
| 0.2 -- 0.4  | Known structure or simple variant            | Matches known fingerprint, few moves  |
| 0.4 -- 0.6  | Potentially interesting candidate            | Novel, balanced, pre-model-check      |
| 0.6 -- 0.8  | Interesting with verified models             | Novel + has models + good structure   |
| 0.8 -- 1.0  | Highly interesting                           | Novel + structured models + economical|

**Score ceilings without model checking:**

Without a model spectrum, has_models, model_diversity, and spectrum_pattern all default to 0.0. The maximum possible score from structural + novelty dimensions alone is:

```
max_no_models = 0.08 + 0.08 + 0.08 + 0.10 + 0.06 + 0.15 + 0.10 = 0.65
```

In practice, a candidate scoring above 0.50 without model data is a strong signal that model checking is worth the computational cost.

**A concrete walkthrough:**

Consider a novel candidate derived from Group by three diverse moves (Dualize, Complete, Abstract). It has 1 sort, 2 operations, 2 axioms (ASSOCIATIVITY, COMMUTATIVITY), and models at sizes 2, 3, 4 with 1, 1, 2 models respectively.

```
connectivity   = 0.50  (single-sorted)
richness       = 1.00  (2 axioms / 2 ops = ratio 1.0)
tension        = 0.33  (2 kinds / 6)
economy        = 1.00  (size = 1+2+2 = 5, in peak range)
fertility      = 0.33  (1 sort, 1 binary op)
has_models     = 1.00  (spectrum is non-empty)
model_diversity= 0.56  (coverage 3/3=1.0, avg 4/3=1.33, count_score=0.36 => (1+0.36)/2 ~ 0.56 - approx)
spectrum_pattern= 0.50 (counts 1,1,2 are monotone increasing)
is_novel       = 1.00  (fingerprint not in known set)
distance       = 0.64  (chain length 3, diversity 3/7)

total = 0.08*0.50 + 0.08*1.00 + 0.08*0.33 + 0.10*1.00 + 0.06*0.33
      + 0.15*1.00 + 0.10*0.56 + 0.10*0.50
      + 0.15*1.00 + 0.10*0.64
      = 0.04 + 0.08 + 0.026 + 0.10 + 0.020
      + 0.15 + 0.056 + 0.05
      + 0.15 + 0.064
      = 0.736
```

Score 0.74 -- solidly in the "interesting with verified models" range.

---

## Customizing Weights

Pass a custom weight dictionary to `ScoringEngine`:

```python
from src.scoring.engine import ScoringEngine

# Emphasize model-theoretic quality over structural heuristics
model_focused = {
    "connectivity": 0.03,
    "richness": 0.03,
    "tension": 0.03,
    "economy": 0.06,
    "fertility": 0.03,
    "has_models": 0.20,
    "model_diversity": 0.20,
    "spectrum_pattern": 0.20,
    "is_novel": 0.12,
    "distance": 0.10,
}

scorer = ScoringEngine(weights=model_focused)
result = scorer.score(candidate, spectrum=spectrum, known_fingerprints=known)
```

Weights do not need to sum to 1.0, but the total score will exceed 1.0 if they sum to more. It is recommended to keep the sum at 1.0 for consistent interpretation.

**Presets worth trying:**

```python
# Novelty-focused: find things that are genuinely different
novelty_weights = {
    "connectivity": 0.05, "richness": 0.05, "tension": 0.05,
    "economy": 0.05, "fertility": 0.05,
    "has_models": 0.10, "model_diversity": 0.05, "spectrum_pattern": 0.10,
    "is_novel": 0.25, "distance": 0.25,
}

# Economy-focused: find the simplest interesting structures
economy_weights = {
    "connectivity": 0.05, "richness": 0.10, "tension": 0.05,
    "economy": 0.25, "fertility": 0.05,
    "has_models": 0.15, "model_diversity": 0.10, "spectrum_pattern": 0.05,
    "is_novel": 0.10, "distance": 0.10,
}
```

---

## Design Philosophy

The scoring system is deliberately conservative. It is better to miss an interesting structure than to drown in false positives.

**Why model-theoretic dimensions dominate.** Structural heuristics (connectivity, richness, tension, economy, fertility) are educated guesses based on the shape of the signature. They can be computed instantly but they can be fooled. A signature might look well-balanced and novel but have no finite models -- meaning it is either contradictory or only realized in infinite structures neither of which the system can verify.

The model-theoretic dimensions (has_models, model_diversity, spectrum_pattern) provide ground truth. When a model checker finds a Cayley table satisfying all the axioms, that is a proof that the structure exists. The 35% weight on model-theoretic quality reflects this epistemic advantage.

**Why novelty is weighted heavily but not dominantly.** A novel structure with no models is worthless. A known structure with interesting models is already known. The 25% novelty weight ensures rediscoveries are penalized but does not let novelty override the requirement for verified models.

**Why economy gets the highest structural weight.** Among the structural dimensions, economy (0.10) is the most reliable. The move engine tends to grow signatures -- each move can add sorts, operations, and axioms. Without the economy penalty, the system would drift toward increasingly bloated candidates. Economy pulls back toward Occam's razor: the best structures are the ones that say a lot with a little.
