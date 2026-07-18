# STRUCTURAL_V1 — Operator Initialization (provisional)

> **Type:** pre-implementation design doc. No code. Defines how the **provisional** per-unit
> operators `M_σ` are initialized for Stage A. **These operators are not claimed to be
> real** — Stage A tests whether the *framework* (operator product) can express
> inventory-specific, factorizable **order-structure**, not whether the operators are
> correct. Data-estimated operators are deferred to human order-effect data.

## Fixed choices

- **Dimension `d = 4`**, with an intended **`2 ⊗ 2` tensor structure** (two binary factor
  slots) so the factorization metric has a target to test. `d=2` is too restrictive
  (limited algebra); `d=4` is the smallest that is both non-trivially non-commutative and
  factorizable. **Frozen.**
- **One operator per unit**, **shared across all sequences** — no per-word, per-context, or
  per-sequence operators. **No fitting. No tuning. No hidden normalization.**
- Operators are **orthogonal** (norm-preserving) so readings cannot blow up over long
  sequences.

## Options compared

| option | non-commutative? | numerically safe | risk | verdict |
|---|---|---|---|---|
| **(a) identity + small feature perturbation** `M=I+εF` | only `O(ε²)` | yes | **suppresses order-effects** — `[I+εA,I+εB]=ε²[A,B]`; would fail order-sensitivity for a *trivial* reason | **reject as primary**; keep as a weak-coupling control |
| **(b) feature-derived generator exponential** `M_σ = exp(Σ_j f_{σ,j} G_j)` | **yes** (if `G_j` don't commute) | yes (orthogonal if `G_j` skew-symmetric) | generator choice is a design DOF — must be **pre-registered, not tuned** | **recommended primary** |
| **(c) random orthogonal** | yes (generic) | yes | none — but feature-blind | **control, not primary** |
| **(d) data-estimated operators** | — | — | requires human order-effect data we don't have | **deferred** |

## Recommended v1 initializer — option (b), with mandatory controls

**Primary:** `M_σ = exp(Σ_{j=1}^{k} f_{σ,j} · G_j)`, where
- `{G_j}` are **fixed, pre-registered, skew-symmetric `4×4` generators** (one per feature
  factor), chosen so they are **generically non-commuting** and respect the `2⊗2` factor
  layout (some `G_j` act on factor-1, some on factor-2, some couple them);
- `f_{σ,j}` are the unit's **feature values** read from the existing varṇa/phonological chart
  (place, manner, voicing; vowel height/backness), **normalized** to a fixed range;
- `exp(skew-symmetric) ⇒ orthogonal`, so `M_σ` is bounded and norm-preserving.

This is feature-grounded, **deterministic**, genuinely non-commutative, and **bakes in the
factorization hypothesis** precisely so it can be *tested* against nulls (it is not evidence
by itself — see below).

**Mandatory controls run alongside (same harness):**
1. **Bag baseline** — additive aggregation (order-blind ⇒ zero order-effect by construction).
2. **Random-orthogonal operators** — does *any* non-commuting set produce order-effects
   (generic non-commutativity level)?
3. **Relabel** — permute which unit gets which operator (fixed permutation); does the
   *specific* feature→unit binding matter?
4. **Weak-coupling (option a)** — optional, to confirm order-effect scales with coupling.

## What a feature-init result does and does not mean

- Producing order-effects from `(b)` is **expected** (non-commuting operators do) and is
  **not** evidence the operators are real. The only informative comparisons are: does the
  feature-init produce **structured/factorizable** order-effects that **random-orthogonal
  does not**, and that **survive relabel**? If feature-init ≈ random-orthogonal on
  *structure*, the features add nothing beyond generic non-commutativity.

## What would make the initialization INVALID

- **Any** per-word/per-sequence **fitting or tuning** to produce order-effects (circular).
- Choosing the generators `{G_j}` (or normalization/scaling) **after** seeing which produce
  effects (post-hoc / garden of forking paths).
- **All `G_j` commuting** — then no order-effects are possible and the init cannot exercise
  the test.
- **Unbounded-norm** operators (readings diverge over sequences).
- Hand-setting operators so a target pair satisfies `AB > BA` on a chosen axis
  (encoding the answer).
- Any **hidden normalization** tuned to pass the gate.

All of the above must be excluded by construction and asserted in the Stage-A tests.
