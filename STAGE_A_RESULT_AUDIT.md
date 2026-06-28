# STAGE_A_RESULT_AUDIT

> **Post-result scientific audit.** No code, no threshold changes, no operator
> re-initialization, no attempt to make G4 pass. This document interprets the
> Stage A result as recorded and defines the next scientifically valid step.
> **structure, not validated meaning.**

## Recorded result (frozen)

| gate | result | key numbers |
|---|---|---|
| G1 order-sensitivity | **PASS** | mean standardized order-effect 1.124 ≥ 0.10; bag = 0 |
| G2 beats random-orthogonal | **PASS** | real structure_score 0.599 > null p95 0.010 (null mean −0.099) |
| G3 beats relabel | **PASS** | real 0.599 > null p95 0.097 (null mean −0.075) |
| G4 factorization | **FAIL** | low_dim ✓ (eff_rank 3.68 ≤ 6); beats random-factor ✓ (0.599 > 0.034); **gap_reliable ✗** (disjoint<shared gap CI low = −0.018) |
| **Overall** | **FAIL** | commuting coef 0.438 vs coupling coef 0.682; n=14 units, 91 pairs; score std 0.023 |

Commit: `2d42bf6`. Result is deterministic (fixed seeds).

---

## 1. Per-gate interpretation

### G1 — order-sensitivity exists (PASS)
- **Passed:** the operator product `M_{i}M_{j}s₀ ≠ M_{j}M_{i}s₀` for the inventory; mean
  standardized order-effect 1.124, far above the 0.10 floor, against a bag baseline that is
  identically 0.
- **Means:** the engine works and non-commutativity is real, not a numerical artifact; the
  bag is the correct degenerate null (additive aggregation cannot encode order).
- **Does NOT mean:** anything inventory-specific. *Any* set of non-commuting operators passes
  G1. This is a sanity/harness check, deliberately a low bar. A pass here is necessary, not
  informative on its own.

### G2 — beats random-orthogonal on structure (PASS)
- **Passed:** the feature-derived initialization's *structure score* (out-of-sample R² of a
  wedge-feature model predicting the order-effect matrix `B`) is 0.599, vs a random-orthogonal
  null whose 95th percentile is 0.010 and whose mean is ≈0.
- **Means:** the order-effects of feature-built operators are **predictable from the feature
  coordinates** in a way generic non-commuting operators are not. The features carry
  *structural* signal beyond "any rotation cluster." Note the discriminator is **structure,
  not magnitude** — random operators can have larger raw order-effects; what they lack is the
  feature-predictable pattern.
- **Does NOT mean:** the features are *correct*, *real*, or *meaningful*. It means the
  order-effects are a function of the features **by construction** (operators were built from
  features) and that this function is non-degenerate. G2 confirms the construction is
  non-trivial; it cannot confirm the construction is true.

### G3 — beats relabel (PASS)
- **Passed:** structure score 0.599 vs a relabel null (permute which feature vector is bound to
  which unit, recompute against the real `B`) with p95 = 0.097.
- **Means:** the **specific** feature→unit binding matters — predictions degrade when the
  binding is scrambled. The chart is not interchangeable with a random reassignment of the
  same feature vectors.
- **Does NOT mean:** the binding is the *right* one, only that it is *a* binding the
  order-structure depends on. G3 rules out "the binding is arbitrary"; it does not establish
  "the binding is veridical."

### G4 — factorization (FAIL)
G4 had three sub-conditions; two passed, one failed.
- **low_dim — PASS:** effective rank of `B` is 3.68 ≤ 6 (the C(4,2) generator-pair bound). The
  order-effect matrix is low-dimensional. *(Note: low rank is partly forced by d=4 and the
  6-predictor wedge model; it is the weakest of the three sub-conditions.)*
- **beats_randfactor — PASS:** real structure score 0.599 exceeds the random-factorization
  null p95 = 0.034 (predict real `B` from column-shuffled features). The *joint* feature
  configuration of each unit matters, not just the marginal feature distributions.
- **gap_reliable — FAIL:** the sharp, directional factorization prediction — **pairs differing
  on disjoint (commuting) factors have lower order-effects than pairs differing on shared
  (coupling) factors** — is **not reliably recovered**. Point estimate is in the right
  direction (coupling coef 0.682 > commuting coef 0.438), but the bootstrap CI for the gap
  has lower bound −0.018, i.e. it crosses zero. The disjoint-commute / shared-interact
  structure is not statistically separable from noise under this estimator.
- **Means:** the **factorization refinement** — that the inventory decomposes into `k`
  independent factors whose commuting/non-commuting algebra predicts the order-effect pattern
  — **is not supported** by the feature-derived operators. The cleanest theoretical signature
  of factorization (commuting factors ⇒ near-zero order-effect) is washed out, mechanically
  because the wedge predictors are collinear, so OLS inflates the commuting-pair coefficient
  away from its true ≈0 value.
- **Does NOT mean:** that factorization is *false for the theory*. It means **these
  provisional operators do not exhibit it cleanly**. The construction baked factorization in
  (commuting `G_A,G_B`); the test still could not certify it. That is a strong negative *about
  the benchmark*, not yet about nature.

---

## 2. The exact claim that failed

Five separable claims, in increasing ambition:

| # | claim | Stage A verdict |
|---|---|---|
| 1 | **Operator framework** — ordered, non-commuting operator product produces order-dependent structure | **SUPPORTED** (G1) |
| 2 | **Feature-derived initialization** — features carry structure beyond generic non-commutativity, and the specific binding matters | **SUPPORTED** (G2, G3) |
| 3 | **Factorization refinement** — the inventory factors into independent primitives whose commuting algebra predicts the order-effect pattern | **FAILED** (G4 gap_reliable) |
| 4 | **Meaning claim** — the order-structure carries semantic content | **UNTESTED** (out of Stage A scope; needs human + semantic data) |
| 5 | **Sanskrit / varṇa privilege** — the varṇa chart beats IPA / data-derived partitions | **UNTESTED** (no comparative arm in Stage A) |

**Failed: claim 3 (factorization refinement) — specifically the disjoint<shared directional
prediction.** Claims 1–2 stand (at benchmark level). Claims 4–5 were never in scope and remain
entirely open.

The headline "Overall FAIL" is therefore **narrow**: it is a failure of the *factorization
refinement on feature-derived operators*, not a failure of the operator framework and not a
verdict on meaning or Sanskrit privilege.

---

## 3. Causal-direction audit

**What Stage A tested:**
```
phonological features  →  operators (M_σ = exp(Σ f_{σj} G_j))  →  order-structure (B)
```
Features are the **independent input**; operators are a deterministic function of them;
structure is read out. The factorization test then asks whether structure is predictable from
the *same features* that generated the operators.

**What the theory may actually require:**
```
latent operator structure  →  phonological features as one projection/observable
```
i.e. the operators (or an underlying latent algebra) are primary, and phonological features
are a **downstream, partial, possibly noisy projection** of that latent structure — not its
generator.

**Verdict: Stage A tested a proxy of the wrong direction.** Concretely:

- Stage A makes phonological features **causally upstream** of the operators. If the true
  generative order is operators → features, then features are a *lossy readout*, and forcing
  `M_σ = exp(Σ f_{σj} G_j)` imposes a parameterization the real operators need not obey.
- Under the operators-primary view, G4's failure is **expected and uninformative**: if real
  operators do not factor along *these* phonological axes, a model that *assumes* they do
  (and then tests that assumption with the same axes) can fail for reasons that have nothing
  to do with whether a latent factorization exists. The features may simply be the wrong
  basis in which to see it.
- G2/G3 passing is consistent with **either** direction: features predict structure because
  structure was built from features (forward proxy), which tells us nothing about whether
  features are projections of a deeper operator algebra.

**Consequence:** Stage A is an **expressiveness test of one forward parameterization**, not a
test of the theory's preferred causal claim. The non-circular test must let the operators be
**estimated** (from independent data), and only then ask whether the *recovered* operators
project onto phonological features and factorize. Stage A could not do this because it had no
operator-bearing data — it had to assume the operators. This is the core limitation, and it is
exactly what the freeze documents flagged ("data-estimated operators are deferred").

---

## 4. Why not tune Stage A

The thresholds, generators `{G_j}`, the d=4 / 2⊗2 layout, the feature chart, the unit set, and
the gate definitions were **pre-registered and committed (213a0cc) before any run**. Changing
any of them *after seeing G4 fail* would be a textbook specification-search:

- **Changing generators** (e.g. picking a coupling structure that makes the gap significant)
  is choosing the hypothesis to fit the observed result — the garden of forking paths. The
  operator-initialization spec explicitly lists this as INVALID ("choosing the generators
  after seeing which produce effects").
- **Changing the factor chart / unit set** re-draws the very partition whose validity G4 is
  testing; a chart selected to pass G4 proves only that *some* chart can be found, not that the
  pre-committed one holds.
- **Lowering the gap-reliability threshold** (or swapping the bootstrap CI for a one-sided test
  tuned to clear −0.018) converts a null into a pass by definitional fiat. The gate doc binds
  this: "Any post-hoc change to thresholds, unit set, or generators after seeing results →
  logged amendment, re-run; results before the amendment are void."
- More deeply: **tuning cannot fix the causal-direction problem (§3).** Even a perfectly tuned
  forward parameterization is still the wrong test. Tuning would buy a cosmetic PASS while
  leaving the actual scientific question (do *recovered* operators factorize?) untouched — the
  worst outcome, because it would *look* like support.

The honest, pre-registered move is to **record the FAIL and change the experiment class**, not
the experiment's knobs.

---

## 5. Preserve Stage A as Stage A.1 (benchmark)

**Recommendation: record the current implementation as `Stage A.1 — feature-derived operator
benchmark`, frozen, never modified.**

Why it is useful despite failing:

- It is the **forward-parameterization control**: the definitive answer to "what happens if you
  *assume* operators are `exp(Σ f_{σj} G_j)`?" Any future operator source (data-estimated, IPA,
  latent) must be run through the **same frozen G1–G4 suite** and compared **against A.1**. A.1
  is the baseline the others have to beat.
- It establishes, cleanly and reproducibly, that **claims 1–2 hold at benchmark level** — that
  result is worth keeping regardless of G4.
- It documents the **negative result on factorization-by-assumption**, which prevents the team
  (and future readers) from re-running the same forward test expecting a different answer.
- Freezing it protects the pre-registration: A.1's numbers are citable precisely because they
  were never tuned.

Renaming is cosmetic and optional; the *freeze* is the substantive recommendation. If renamed,
keep the commit `2d42bf6` and report as the immutable record.

---

## 6. Stage A.2 — data-estimated operator benchmark (conceptual only)

**Definition (not to be implemented now):** `Stage A.2` estimates or constrains the per-unit
operators from **independent human order-effect data**, then runs the **same frozen G1–G4
suite** — flipping the causal direction from §3 (data → operators, then test factorization)
instead of (features → operators by assumption).

Key inversion vs A.1:
- A.1: operators **assumed** from features; factorization tested with the same features → circular.
- A.2: operators **estimated** from behaviour; factorization tested against features that
  **did not enter the estimation** → non-circular. Whether estimated operators project onto
  phonological features, and factorize, becomes a genuine empirical question.

**Data needed (minimum viable):**
- **Human order-effect measurements** on minimal unit sequences: for unit pairs (and short
  strings), a behavioural readout that differs when order is swapped — e.g. forced-choice or
  rating tasks on pseudoword pairs `σ_iσ_j` vs `σ_jσ_i` (the "Human Order-Effect Study"
  already drafted as a pre-registration is the intended source).
- **Coverage:** enough units (≈ the A.1 inventory) and enough ordered pairs per unit to
  estimate a `d×d` operator per unit with stable error bars (power analysis required; A.1's 91
  pairs is the structural floor, human data will need replication per pair).
- **A held-out feature chart** (phonological features) that is **not** used in estimation, so
  the projection/factorization questions are out-of-sample.
- **Controls collected in the same protocol:** position/order biases, response-time confounds,
  familiarity, so the estimated order-effect is not an artifact of task mechanics.

A.2 PASS/FAIL is read under the **identical frozen gates**, so A.2 and A.1 are directly
comparable.

---

## 7. Future operator-source comparison arms

All run through the **same frozen G1–G4 gate**, so differences are attributable to the operator
source, not the test.

| arm | operator source | what the comparison tests |
|---|---|---|
| **feature-derived** (A.1) | `exp(Σ f_{σj} G_j)` from the chart | forward-parameterization baseline; expressiveness ceiling of the assumed form |
| **human-data-estimated** (A.2) | fit to human order-effect data | do **behaviourally real** operators show order-structure / factorization? the decisive arm |
| **random** | random orthogonal | generic non-commutativity floor; every arm must beat this on **structure** |
| **relabeled** | estimated/feature operators with binding permuted | does the **specific unit→operator** assignment carry the signal, or is it interchangeable? |
| **IPA-derived** | operators from IPA features instead of varṇa | is **varṇa privileged**, or do standard phonological features do as well/better? (claim 5) |
| **data-derived latent factors** | factors learned directly from data (no chart) | is there a factorization at all, in **any** basis, and does it align with phonological features or with something else? separates "factorization exists" from "factorization is phonological" |

Crucial contrasts:
- **A.2 vs random/relabeled:** does estimated structure beat the nulls (the real A.1 analogue,
  now non-circular)?
- **A.2 vs A.1:** do *behavioural* operators agree with *feature-assumed* ones? Disagreement
  localizes the forward-parameterization error.
- **varṇa vs IPA vs data-derived latent:** the Sanskrit-privilege question (claim 5), only
  meaningful once operators are data-grounded.

---

## 8. Updated conservative roadmap

1. **Freeze Stage A.1.** Treat `symbolu_neural/structural_v1/` + commit `2d42bf6` as the
   immutable feature-derived benchmark. No edits.
2. **Commit this post-result audit** (`STAGE_A_RESULT_AUDIT.md`) — *only on explicit
   authorization*. Records the narrow FAIL and the causal-direction limitation.
3. **Do not modify Stage A.1.** No threshold/generator/chart changes; any future variant is a
   new, separately-named stage with its own pre-registration.
4. **Prepare human order-effect data collection.** Finalize the already-drafted Human
   Order-Effect Study pre-registration; run the power analysis; collect the data. *This is the
   binding constraint — data, not code.*
5. **Build Stage A.2 only after data exists.** Estimate operators from the human data; run the
   frozen G1–G4 suite; keep features out-of-sample.
6. **Compare operator sources under the same gate.** Feature-derived (A.1) vs data-estimated
   (A.2) vs random vs relabeled vs IPA vs data-derived latent. Only after this do claims 4–5
   (meaning, Sanskrit privilege) become testable, and only with their own additional data.

---

## Recommendation

**COLLECT HUMAN DATA → then build Stage A.2 later.** Do **not** tune, do **not** rerun A.1
(it is deterministic and already answered its question), and do **not** stop the program — but
recognize that the current testbed has reached the limit of what assumed operators can show.

- **Not stop:** claims 1–2 hold; the framework is not dead. The factorization failure is
  narrow and partly a consequence of testing the wrong causal direction (§3).
- **Not tune:** would void the pre-registration and produce a cosmetic PASS on the wrong test
  (§4).
- **Not rerun:** A.1 is deterministic; rerunning yields the identical FAIL.
- **Collect human data, then Stage A.2:** the only move that turns the open questions
  (factorization-in-real-operators, meaning, Sanskrit privilege) into falsifiable tests. The
  decisive investment is the **human order-effect study**, exactly as the freeze documents
  concluded. Until that data exists, engine elaboration cannot advance the science.

> **structure, not validated meaning.** Stage A.1 established a structural benchmark and a
> narrow factorization null on *assumed* operators. It did not test — and cannot test — meaning,
> Sanskrit privilege, or the theory's preferred operators-primary direction. Those require data
> no engine can produce.
