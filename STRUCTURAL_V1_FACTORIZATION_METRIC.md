# STRUCTURAL_V1 — Factorization Metric

> **Type:** pre-implementation design doc. No code. Defines how Stage A tests whether the
> order-effects decompose into `k ≪ n` primitive factors. **Honest scope:** at Stage A this
> is a **self-consistency / expressiveness check on provisional operators**, *not* a
> discovery of real factors. The non-circular factorization test requires **human**
> order-effect data and is deferred.

## 1. Input matrix analyzed

For the frozen unit set (size `n`) and operators `{M_σ}`:
- compute the **order-effect magnitude matrix** `B ∈ ℝ^{n×n}`, `B_{ij} = ‖[M_i,M_j] s₀‖`
  (symmetric, zero diagonal) — "how much does order matter for the pair `(i,j)`."
- alongside, retain the **directed** order-effect `e_{ij}` (antisymmetric) for the
  sign-level predictions.

`B` is the object whose structure is tested.

## 2. What counts as factor structure

Each unit `i` has a **feature vector** `f_i` from the existing chart (place, manner,
voicing; vowel height/backness), partitioned into `k` **factors**. Under the factorization
hypothesis (operators built from `k` feature-generators with a `2⊗2` layout), `B_{ij}` is
**predicted by which factors differ between `i` and `j` and whether those factors'
generators commute.** Concretely, factor structure is present iff a **parameter-light,
feature-based model**

`B_{ij} ≈ g(f_i, f_j)` — a function of *which factors differ × generator-commutativity*

explains `B` **out-of-sample**, with **low effective dimension** (the operators lie in a
`k`-factor generated algebra; `B` is approximately low-rank).

## 3. Disjoint-factor → COMMUTE prediction

If `i,j` differ **only** on factors whose generators **commute** (e.g., independent
articulators / independent `2⊗2` slots), then `[M_i,M_j] ≈ 0` ⇒ **`B_{ij} ≈ 0`**.
**Falsifiable:** such pairs must have **significantly lower** order-effects than shared-factor
pairs.

## 4. Shared-factor → INTERACTION prediction

If `i,j` differ on a factor whose generator **does not commute** with the others, `B_{ij}` is
**large**. **Falsifiable:** these pairs must have **significantly higher** order-effects.

The **disjoint < shared** gap is the sharp, directional factorization prediction.

## 5. Random-factorization null

Build the null by **randomly reassigning** units to feature configurations (or randomly
permuting the factor groupings), `K ≥ 200` times, and recomputing the feature-model fit each
time. This yields a null distribution for the explained-variance score under *arbitrary*
factor structure of the same complexity. (Complementary nulls: random-orthogonal operators
and the relabel control from the gate doc.)

## 6. Pass / fail criteria

- **PASS** requires **all**:
  - the feature-based model explains `B` out-of-sample with score **> 95th percentile** of
    the random-factorization null;
  - the **disjoint < shared** order-effect gap is reliable (separation beyond resampling
    noise);
  - the **effective dimension is low** (`k ≪ n`; e.g., `B`'s effective rank or the operators'
    generated-algebra dimension is small and stable across resampling);
  - the structure **survives relabel** (real binding beats the relabel null — shared with
    gate **G3**).
- **FAIL** if random factorization explains `B` as well (no genuine factor structure), or the
  disjoint pairs do **not** commute, or the effective dimension is not low.

## 7. Limitations (binding, stated up front)

- **Partial circularity.** The provisional operators are *built* from feature-generators, so
  *some* factor structure is **baked in by construction**. A bare "factorization detected"
  is therefore partly tautological. The only informative results are the **relative** ones:
  does the real feature→unit binding beat **relabel** and **random-factorization** nulls, and
  does the recovered structure match the **independently-known feature chart** better than
  random groupings? Absolute factorization scores are not evidence.
- **No meaning, no reality.** Stage A factorization tests the *operators we initialized*, on
  no human data. It cannot show the factors are **perceptually or semantically real**. That
  requires factorizing **human** order-effect data (the deferred study), which is
  non-circular precisely because the operators are then *estimated*, not assumed.
- **Sanskrit-neutral.** Whether the varṇa chart's factors beat IPA / data-derived factors is
  a **separate secondary analysis**, not part of this metric's pass/fail.
- Consequently, a factorization **PASS at Stage A** means: *the framework + a feature-derived
  init produce order-effects whose factor structure (i) matches the known chart, (ii) beats
  relabel and random-factorization nulls, and (iii) is low-dimensional.* It is an
  **expressiveness/consistency** result, not a discovery.
