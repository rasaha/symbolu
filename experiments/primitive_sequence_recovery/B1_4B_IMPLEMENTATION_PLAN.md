# B1.4b — Implementation Plan (true L1→L2→L3 operator-interaction validation)

**Status:** Implementation planning only (docs-only). Nothing is built, downloaded, run, or scored.
**Governed by:** `PREREG_B1_4B_L1_L2_L3_OPERATOR_INTERACTION.md`, `B1_4B_TARGET_Y_ADMISSIBILITY_AUDIT.md`,
`MILESTONE_A_CANDIDATE_F_SPEC.md`, `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`.
**No meaning validated. No dataset built. Nothing run or scored. Track B remains blocked.**
**Structure, not validated meaning.**

Grounding (read-only): `symbolu_neural/structural_v1/operators.py`, `.../features.py` — **not modified**.

---

## 1. Purpose

This is an **implementation plan only** for B1.4b — the sequence of build/verify steps that *would* be taken to
run the pre-registered true L1→L2→L3 operator-interaction study. It writes no code, downloads no data, and runs
nothing. It exists so that, if approved, the build follows a frozen, leakage-controlled recipe rather than
being improvised. Every terminal outcome remains gated on the pre-registration; the expected honest result is
`F_COLLAPSES_TO_PHONOLOGY → ⊥`.

---

## 2. End-to-end architecture

```
concept word ─▶ [L1] frozen operators M_σ = expm(Σ_j f_{σ,j} G_j)  (phonology-parameterized, orthogonal)
            ─▶ [L2] F-3: operator-interaction / commutator features  z = F₃(M_σ…, s₀) ∈ S   (no norm/magnitude)
            ─▶ [L3] decoder/probe D over z  ── separate from F ──▶ prediction of Y (or word-blind generation)
                                                     │
   independent target Y (human feature-production norms) ◀── frozen before any F-3 fit
                                                     │
   baseline suite B (phonology primary, bag/shuffle/random, length/freq, sentiment, chance) ── all must be beaten
                                                     │
                                              ⊥ if any baseline ties/wins or any leakage/validity gate trips
```

- **L1** — frozen Stage A operators, read-only.
- **L2** — F-3 operator-interaction latent (§5), norm/magnitude features excluded (degenerate under
  orthogonality).
- **L3** — a decoder/probe mapping `z → Y` (or `z → passage`), capacity-matched to baselines, separate from
  `F`.
- **Independent Y** — human-produced semantic feature norms (audit §5 preferred).
- **Baselines B** — §6; phonology co-primary.
- **⊥** — the correct output whenever a baseline is not beaten or a validity gate trips.

---

## 3. Inputs

Required inputs (all frozen before fitting):

- **Frozen L1 operator definitions** — `operators.py` generators `G_A..G_D` and `features.py` phonological chart
  `f_{σ,j}` (consumed read-only).
- **Word/concept list** — the intersection of (a) concepts with entries in the chosen Y norm set and (b) words
  with a clean cmudict→varṇa decomposition.
- **Varṇa decomposition** — the existing frozen G2P→varṇa pipeline (read-only), producing the operator sequence
  per word.
- **Independent feature-norm `Y`** — the selected human feature-production norms (§4), as a frozen
  concept × attribute matrix.
- **Phonological feature baselines** — `f_{σ,j}` used directly (mean/pooled per word) and a phonological
  similarity space.
- **Covariates** — length, frequency, and sentiment/valence, held as **nuisance covariates** to be partialled
  out (not targets).

---

## 4. `Y` source selection

Concrete-dataset selection criteria (choose and freeze exactly one primary set; a secondary set for
triangulation):

- **Feature-production norms preferred** — human-produced attribute features per concept (audit §5 #2), because
  they are gloss-independent and attribute-structured.
- **Minimum coverage** — the norm set must cover ≥ the pre-registered concept count (audit §8: ≥ ~100) after
  intersecting with decomposable words.
- **Attribute dimensionality** — ≥ ~10–20 usable attribute dimensions (or a pre-declared fixed reduction).
- **Reliability** — published/derivable inter-rater or split-half reliability meeting the pre-registered floor;
  low-reliability attributes dropped **before** fitting.
- **Licensing / accessibility** — redistributable/academically accessible; provenance documented. *(No dataset
  is downloaded by this plan.)*
- **No dictionary/gloss leakage** — the norm set must be human-produced, **not** read off definitions/WordNet
  glosses (audit §6 rejects gloss-derived labels).

Output of this step: a frozen `Y` spec (dataset id, concept list, attribute set, reliability floor,
covariates) — an amendment to the pre-registration.

---

## 5. F-3 feature-extraction plan

For each word, from its ordered operator sequence `M_{σ_1}, …, M_{σ_n}` (and fixed `s_0`):

- **Operator sequence** — build `M_{σ_i}` per varṇa from the frozen features/generators (read-only); no fitting.
- **Pairwise commutators** — `[M_i, M_j] = M_i M_j − M_j M_i` for adjacent pairs (primary) and, optionally, all
  pairs; summarize each by rotation-invariant scalars (e.g. Frobenius norm of the commutator, principal angle
  of its rotation part). *These norms are of the commutator operator, which is not norm-degenerate — distinct
  from the excluded state-norm features.*
- **Non-commutativity measures** — distance between the realized ordered product `M_{σ_n}…M_{σ_1}` and an
  order-blind reference (symmetrized/averaged product), quantifying how much order changed the result.
- **Ordered-product features** — associator-style triple summaries and a fixed set of higher-order interaction
  scalars that a bag/single-pass baseline cannot reproduce.
- **Trajectory curvature (optional secondary)** — directional/angular change along `t_0…t_n` (geometry only).
- **Explicitly excluded** — **state norm / magnitude / energy** features (degenerate: `‖t_i‖ = ‖s_0‖` under
  orthogonal operators). Admitted only if a specific feature is proven non-degenerate and justified in writing
  **before** use.

The full F-3 feature list and its fixed-length vectorization are frozen before any fit.

---

## 6. Baselines

Computed with the **same** probe capacity as F-3 (§7):

- **Plain phonological feature baseline** — per-word pooled `f_{σ,j}` (place/manner/voicing/sonority).
- **Phonological similarity baseline** — predict `Y` from sound-neighborhood structure (meaning-unrelated).
- **Bag-of-varṇas baseline** — order-destroyed multiset features.
- **Shuffled-order baseline** — same varṇas, permuted order (recomputed F-3 on shuffles).
- **Random / relabel operator baseline** — operators reassigned to varṇas at random.
- **Length / frequency baseline** — word length + corpus frequency only.
- **Sentiment / lexicon baseline** — affect/lexicon predictor.
- **Chance / null** — label-permutation / marginal predictor.

---

## 7. Probe / model family

- **First pass = low-capacity, regularized linear:** ridge regression (continuous attribute values) or
  L2-regularized logistic (binary attributes); the same family for F-3 and **every** baseline.
- **Small bounded learned probe** — only if pre-registered, with capacity caps and a phonology-only learned
  control of identical architecture.
- **No high-capacity / overfit model in the first pass** — no deep nets, no unbounded boosting; capacity is a
  frozen pre-registration parameter.
- **Capacity parity is mandatory** — F-3 and baselines must use the *same* probe class, regularization search
  grid, and CV protocol, so any F-3 advantage is not a capacity artifact.

---

## 8. Metrics

- **Cross-validated prediction performance** — concept-level CV (§10 split rule).
- **Task-appropriate score** — Pearson/Spearman correlation or R² (continuous `Y`); balanced accuracy / AUC
  (binary attributes); averaged over attributes with the distribution reported, not just the mean.
- **Δ vs phonology** — F-3 minus plain-phonological and minus phonological-similarity (the decisive contrasts).
- **Δ vs bag / shuffle / random-relabel** — F-3 minus each order/structure control.
- **Confidence intervals** — bootstrap CIs on every score and every Δ.
- **Permutation test** — label-permutation null for the primary Δ, if computationally feasible.
- **Multiple-comparison correction** — Holm (or equivalent) across the baseline-contrast family, with the
  primary endpoint (§9) named in advance.

---

## 9. Primary endpoint

F-3 must **beat all** of, by the pre-registered margin with correction:

- the **plain phonological** baseline,
- the **phonological similarity** baseline,
- the **bag-of-varṇas** and **shuffled-order** baselines,
- the **random / relabel operator** baseline.

**Phonology is primary** (operators are phonology-parameterized) and **order baselines are co-primary** (F-3's
whole claim is order-dependent composition). **Failure to beat phonology → `F_COLLAPSES_TO_PHONOLOGY`.** Failure
to beat order baselines → `BAG_OR_SHUFFLE_EXPLAINS` / `RANDOM_RELABEL_EXPLAINS`. All must pass for
`L1_L2_L3_ATTRIBUTE_SIGNAL`.

---

## 10. Leakage controls

- **No dictionary/gloss features** anywhere in F-3 or baselines.
- **No varṇa glosses** — F-3 consumes operators only.
- **No target leakage from `Y` into feature construction** — F-3 and baselines are computed with no access to
  `Y`; `Y` is used only as the prediction target at scoring time.
- **No post-hoc attribute selection** — the attribute set and reliability floor are frozen before fitting;
  attributes are not chosen after seeing results.
- **Train/test split by concept** — folds partition *concepts* (no concept in both train and test), preventing
  item-identity leakage.
- **Pre-frozen feature extraction** — the F-3 feature list, vectorization, `s_0`, and baseline definitions are
  hash-frozen before any fit.
- **Validity trips** — any gloss reaching the decoder → `DECODER_LEAKAGE_INVALID`; any target-revealing token
  reaching a generator (P-generate variant) → `WORD_LEAKAGE_INVALID`.

---

## 11. Synthetic harness (before any real data)

Build and pass a synthetic harness first (synthetic operators + synthetic `Y`; no real norms):

- **Synthetic operator sequences** — generated from the frozen generator algebra.
- **Synthetic `Y` where F-3 should win** — a target constructed to depend on commutator/order structure;
  confirms the pipeline can *detect* an interaction signal when one exists (positive control).
- **Synthetic `Y` where phonology should win** — a target that is a function of `f_{σ,j}` alone; confirms the
  phonology baseline correctly wins and F-3 does **not** false-positive (→ `F_COLLAPSES_TO_PHONOLOGY`).
- **Synthetic null** — `Y` independent of everything; confirms all methods land at chance (→
  `NULL_RETURN_BOTTOM`).
- **Verifies** — that the scorer emits the correct §13 terminal label and the correct `⊥` failure states on
  each synthetic regime, and that capacity parity + permutation tests behave. **No evidence value.**

---

## 12. Real-data pilot (only after the harness passes)

- **Coverage audit** — intersect the chosen Y norm set with decomposable words; confirm ≥ pre-registered count;
  if short → `Y_NOT_INDEPENDENT` / `Y_TOO_COSTLY` and stop.
- **Freeze concept set** — the final word list, hash-frozen.
- **Freeze `Y` matrix** — concept × attribute values + covariates, hash-frozen.
- **Freeze feature extraction** — F-3 list, baselines, probe capacity, CV protocol, hash-frozen.
- **Run small pilot** — powered per the pre-registration amendment; report all §8 metrics.
- **No evidence claim from pilot plumbing** — only the frozen, powered run emits a terminal label; a smoke/pilot
  is plumbing confirmation, not a result.

---

## 13. Terminal labels

- **`L1_L2_L3_ATTRIBUTE_SIGNAL`** — F-3 beat phonology **and** order baselines **and** all others.
- **`F_COLLAPSES_TO_PHONOLOGY`** — phonological baseline matches/exceeds F-3.
- **`BAG_OR_SHUFFLE_EXPLAINS`** — order-blind/shuffled baseline matches F-3.
- **`RANDOM_RELABEL_EXPLAINS`** — random operator relabeling matches F-3.
- **`SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS`** — semantic-only / sentiment baseline accounts for the result.
- **`Y_NOT_INDEPENDENT`** — no gloss-independent `Y` could be secured/covered.
- **`DECODER_LEAKAGE_INVALID`** — gloss/meaning leaked into `D`.
- **`WORD_LEAKAGE_INVALID`** — target-revealing token reached a generator.
- **`NULL_RETURN_BOTTOM`** — clean run, no signal.
- **`INCONCLUSIVE`** — the study could not resolve the question.

Only `L1_L2_L3_ATTRIBUTE_SIGNAL` is positive, and it requires beating **all** baselines. **No
ONTOLOGICAL_SIGNAL. No Sanskrit privilege.**

---

## 14. Expected outcome

The expected honest result remains **`F_COLLAPSES_TO_PHONOLOGY → ⊥`.** Because the L1 operators are
parameterized entirely by phonological features, F-3 is at most *structured phonology*, and the standing prior
(sound-over-meaning; B1.1 `RANDOM_OR_SCRAMBLED_MATCHES`; scrambled ≈ real ~0.967) points to F-3 **not** beating
the phonological baseline. This plan is built to make that verdict **trustworthy and falsifiable** — with a
synthetic positive control proving the pipeline *could* detect interaction signal if it existed — not to avoid
it. A clean `⊥` here is a successful, informative outcome and joins the prior negatives; it is not a rescue
target.

---

## 15. Next-step gate

After this plan, the next step is **synthetic-harness design/build only, and only if explicitly approved** by
the operator. No real data is touched, no norm set downloaded, and no pilot run until (a) the synthetic harness
passes all §11 regimes and (b) the `Y` spec and feature/probe freeze (pre-registration amendment) are approved.
This document authorizes none of it.

---

## 16. Boundary statement

> B1.4b implementation plan completed. No meaning validated. No dataset built. Nothing run or scored. Track B
> remains blocked. Structure, not validated meaning.
