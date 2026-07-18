# STRUCTURAL_V1 — Stage A Gate Thresholds (pre-registered)

> **Type:** pre-implementation design doc. No code. Defines the **frozen** Stage A
> structural gates, set *before* any run. **Passing Stage A means only: a structural signal
> exists** (the feature-grounded operator product produces inventory-specific, factorizable
> order-structure beyond bag/random/relabel). **It does NOT mean meaning exists**, and it
> does NOT mean Sanskrit is privileged. Both are out of Stage A's scope.

## What Stage A computes

Over a **frozen** unit set and a **frozen** set of order-pairs `{(i,j)}` (each unit pair in
both orders), using the provisional operators (`STRUCTURAL_V1_OPERATOR_INITIALIZATION.md`):

- **per-pair order-effect** `e_{ij} = ‖M_i M_j s₀ − M_j M_i s₀‖` (and its readout form); the
  magnitude matrix `B_{ij}=|e_{ij}|`.
- the same under **bag**, **random-orthogonal**, **relabel**, and **weak-coupling**.
- the **factorization score** (`STRUCTURAL_V1_FACTORIZATION_METRIC.md`).

## Gates (frozen; exact percentile cutoffs fixed by a pre-run null calibration)

- **G1 — order-sensitivity exists.** Mean standardized order-effect of the feature-init is
  reliably **> 0** and **≫ bag** (bag = 0 by construction). *Planning threshold:* mean
  standardized `B ≥ 0.10`. *(Low bar — confirms the engine works and bag is the correct
  null; near-guaranteed for non-commuting operators.)*
- **G2 — beats random-operator on STRUCTURE (not magnitude).** The feature-init's
  **factorization/structure score** exceeds the random-orthogonal null (**> 95th percentile**
  of random-orthogonal draws). *Note:* feature-init need **not** have larger order-effect
  *magnitude* than random — random can be large; the discriminator is **structure**.
- **G3 — beats relabel.** The structure score for the **real** feature→unit binding exceeds
  the **relabel null** (`K ≥ 200` fixed permutations; **> 95th percentile**). Tests that the
  *specific* binding matters.
- **G4 — factorization precondition.** The factorization metric passes its own criteria
  (random-factorization null + disjoint-commute / shared-interact predictions) per
  `STRUCTURAL_V1_FACTORIZATION_METRIC.md`.

**Stage A PASS = G1 ∧ G2 ∧ G3 ∧ G4.**

## Warning / failure rules (surface, never swallow)

- Any **numerical blow-up** (operator/reading norms diverge), **NaN/Inf**, or **non-finite**
  metric → **hard FAIL**, reported.
- Any **silent default** in the unit-extraction path (e.g., empty sequence quietly treated
  as neutral) → **hard FAIL**; extraction must surface every failure as an explicit warning.
- **Underpowered** (fewer than the pre-registered minimum order-pairs, or unstable scores
  across resampling) → **INCONCLUSIVE**, not pass/fail.
- Any post-hoc change to thresholds, unit set, or generators after seeing results → logged
  amendment, re-run; results before the amendment are void.

## Reading the outcomes (honest interpretation)

- **G1 fails:** the engine/inputs are broken (non-commuting operators must produce *some*
  order-effect) — fix the harness, not the theory.
- **G2 or G3 fails:** the **features/inventory carry no structural signal beyond generic
  non-commutativity** — the operator framework adds nothing over "any non-commuting
  operators." Stage A **fails the inventory-specific-structure claim.**
- **G4 fails:** **no factorization** — the factorization refinement is dead at Stage A.
- **All pass:** a structural signal exists — *on provisional operators*. This means the
  framework **plus a feature-derived init can express inventory-specific factorizable
  order-structure**; it is a statement about **expressiveness and the feature chart's
  structure**, **not** about reality, meaning, or Sanskrit.

## Scope reminder (loud)

> A Stage A PASS establishes **structural signal only.** Meaning is untested (needs human
> order-effect + semantic data). Sanskrit privilege is untested (needs the IPA / random-
> partition comparison, a separate secondary analysis). A passing *structural* result must
> **never** be reported, labeled, or reused as a *meaning* result.
