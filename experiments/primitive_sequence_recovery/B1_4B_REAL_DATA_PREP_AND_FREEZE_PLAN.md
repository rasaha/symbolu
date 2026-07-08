# B1.4b — Real-Data Preparation & Freeze Plan

**Status:** Preparation / freeze plan (docs-only). **No data acquired, none downloaded, nothing run or
scored.** Specifies how the independent `Y`, concept set, feature matrix, F-3 features, baselines, probes,
metrics, and freeze package **will be** selected and locked — before any real-data step.
**Governed by:** `PREREG_B1_4B_L1_L2_L3_OPERATOR_INTERACTION.md`, `B1_4B_TARGET_Y_ADMISSIBILITY_AUDIT.md`,
`B1_4B_IMPLEMENTATION_PLAN.md`, `MILESTONE_A_CANDIDATE_F_SPEC.md`, `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`.
**No meaning validated. Track B remains blocked. Structure, not validated meaning.**

Synthetic harness reference (complete, committed): `458fb1e0c87054f7b5ccaf5372cbd342c359f95a`.

---

## 1. Purpose

This is a **preparation and freeze plan only**. It is **not** data acquisition, **not** a download, and
**not** a run. Its object is to fix, in advance, the exact recipe by which the independent target `Y`, the
concept set, the F-3 feature list, the baselines, the probe, the metrics, and the freeze artifacts will be
chosen and hash-locked — so that the eventual (separately authorized) real-data step cannot be improvised or
tuned to an outcome. Nothing here touches real data; the expected honest outcome remains
`F_COLLAPSES_TO_PHONOLOGY → ⊥`.

---

## 2. Current state

- **B1.4b pre-registration complete** — F-3 admitted; phonology co-primary; terminal labels fixed.
- **Target-Y audit passed for preparation** — `Y_ADMISSIBLE_FOR_B1_4B_PREP` (primary = human feature-production
  norms; affective/sentiment demoted to controls).
- **Implementation plan complete** — end-to-end architecture, leakage controls, pilot staging.
- **Synthetic harness complete** — `458fb1e`: all 10 labels reachable, 12/12 fixtures match, 10/10 tests pass,
  synthetic-only, no Stage A import.
- **No real data used yet** — no dataset acquired, downloaded, or scored.

---

## 3. `Y` source selection

Criteria for choosing the single primary independent `Y` (all mandatory):

- **Human-produced semantic feature norms preferred** — attribute features produced by human raters, not read
  off definitions.
- **No varṇa/gloss derivation** — `Y` is not generated from, or aligned to, the varṇa attribute table, vṛtti,
  sphere, or polarity meanings.
- **No dictionary-definition matching** — `Y` is not the word's definition nor a match-to-definition score.
- **Licensing / accessibility** — academically redistributable or citable; provenance documented. *(No file is
  fetched by this plan.)*
- **Reliability** — published or derivable inter-rater / split-half reliability meeting a pre-registered floor.
- **Sufficient concepts and attributes** — meets the minimum concept count and attribute dimensionality (§5).
- **Usable before F-3 fitting** — fully specifiable and freezable prior to computing any F-3 feature.

A secondary set may be named for triangulation only; affective/sentiment norms are **controls/covariates**,
never the primary `Y`.

---

## 4. Candidate `Y` datasets (to evaluate — none acquired here)

| Candidate | Type | Role | Note |
|---|---|---|---|
| **McRae et al. (2005) feature-production norms** | human-produced concept features | **primary candidate** | concrete nouns; attribute-structured; widely used |
| **CSLB concept property norms** | human-produced property norms | **primary candidate** | larger concept set; property lists |
| **Binder et al. (2016) feature ratings** | human attribute ratings (experiential) | **primary candidate** | brain-based experiential dimensions |
| **SWOW / free-association norms** | behavioral association | **secondary / triangulation** | associations, not attributes; large coverage |
| **Warriner et al. VAD + sentiment/lexicon norms** | affective / polarity | **control / covariate ONLY** | ≈ sentiment baseline; never primary `Y` |
| **Other established feature-production norms** | human-produced | candidate if audited | must meet §3 criteria |

Selection is deferred to the coverage audit (§5); this table only scopes what *would* be evaluated.

---

## 5. Coverage audit plan

Before any dataset is committed, a **paper/spec-level** audit (still no download) must establish:

- **Word/concept overlap with `Y`** — how many concepts in the candidate norm set have a word usable by the
  frozen cmudict→varṇa pipeline.
- **Decomposability into varṇas** — each candidate word yields a clean varṇa sequence (no OOV/ambiguous G2P);
  record the decomposition rule and failures.
- **Minimum concept count** — the intersection must be ≥ the pre-registered floor (target ≥ ~100 concepts).
- **Minimum attribute dimensionality** — ≥ ~10–20 usable attribute dimensions (or a pre-declared fixed
  reduction).
- **Missingness** — per-concept and per-attribute missing-value rates; a pre-registered cap and imputation/drop
  rule.
- **Reliability** — attributes below the reliability floor are dropped **before** fitting.
- **Exclusions** — concepts lacking decomposition or coverage, raters/attributes failing checks; all rules
  fixed in advance.

Audit output = an **eligibility report** (counts only, no `Y` values fetched) that either clears the freeze or
returns `Y_NOT_INDEPENDENT` / `Y_TOO_COSTLY`.

---

## 6. `Y` freeze package

To be hash-frozen (a pre-registration amendment) before any F-3 fit:

- **Selected dataset** — name, **version**, and source/citation.
- **Concept list** — the final frozen list of concepts (post-exclusion).
- **`Y` matrix** — concept × attribute values (as they will be used), plus covariates.
- **Attribute list** — the exact attribute dimensions retained (post-reliability).
- **Preprocessing rules** — normalization, imputation/drop, any fixed reduction/projection.
- **Exclusion rules** — the frozen concept/attribute/rater exclusion criteria.
- **Train/test split policy** — concept-level folds (no concept in both train and test), with the fold seed
  fixed.
- **Hashes** — SHA-256 of every frozen artifact + a manifest self-hash.

---

## 7. F-3 feature freeze

The exact F-3 feature list to be frozen (from `MILESTONE_A_CANDIDATE_F_SPEC.md` / implementation plan §5):

- **Pairwise commutator measures** — `[M_i, M_j]` summaries (Frobenius norm, principal rotation angle) over
  adjacent (primary) and optionally all pairs.
- **Non-commutativity features** — distance between the ordered product `M_{σ_n}…M_{σ_1}` and an order-blind
  reference.
- **Ordered-product / associator terms** — *if included*, the exact associator summaries, fixed in advance.
- **Trajectory curvature** — *if included*, the exact directional/angular features, fixed in advance.
- **Excluded** — **state norm / magnitude / energy** features (degenerate under orthogonality; `‖t_i‖ =
  ‖s_0‖`). Admitted only if a specific feature is proven non-degenerate and justified **before** freeze.
- **Reversal-symmetry limitation recorded** — see §8; it is part of the frozen record.

Once frozen, the F-3 list, its vectorization, and `s_0` are immutable for the run.

---

## 8. Reversal-symmetry limitation (must be recorded before freeze)

The current F-3 magnitude summaries are **invariant to full sequence reversal**:

- `‖[a,b]‖ = ‖[b,a]‖` — adjacent-commutator magnitudes are unchanged when the order is reversed.
- `‖prod − rprod‖` is **symmetric** — the ordered-vs-reversed non-commutativity distance is identical for a
  word and its exact reversal.
- Consequence: the current F-3 scalars **distinguish non-reversal permutations but not exact reversal** — a
  word and its reverse map to identical F-3 features.

Rules:

- This limitation is **recorded in the freeze package** as a known blind spot (discovered in the synthetic
  harness, `458fb1e`).
- **Non-reversal order sensitivity remains** and is what the F-3 primary endpoint tests.
- Any **oriented / signed extension** (e.g. signed associators, orientation-aware summaries) that would break
  the reversal symmetry **must be separately pre-registered** as a new feature set; it **cannot be added
  post-hoc** to a run, and doing so voids the run (`post-hoc oriented features added`, §12).

---

## 9. Baselines to freeze

All computed at matched probe capacity (§10):

- **plain phonological features** (pooled `f_{σ,j}`),
- **phonological similarity** (sound-neighborhood, meaning-unrelated),
- **bag-of-varṇas** (order-destroyed histogram),
- **shuffled-order** (F-3 recomputed on shuffled sequences),
- **random / relabel operators** (operators reassigned to varṇas at random),
- **length / frequency**,
- **sentiment / lexicon**,
- **chance / null** (label-permutation / marginal).

The baseline definitions and any RNG seeds (shuffle, relabel, permutation) are frozen with the package.

---

## 10. Probe and capacity freeze

- **First-pass probe** — regularized linear only: ridge (continuous `Y`) or L2-logistic (binary attributes).
- **Same capacity for F-3 and every baseline** — identical probe class, regularization grid, and CV protocol;
  no method gets extra capacity.
- **Cross-validation policy** — concept-level k-fold (fold seed fixed), matching the synthetic harness pattern.
- **No high-capacity / overfit model** — no deep nets, no unbounded boosting in the first pass.
- **Learned probe only by separate pre-registration** — with capacity caps and a phonology-only learned
  control; not part of this freeze.

---

## 11. Metrics and thresholds

Frozen before any fit:

- **Primary endpoint = Δ vs phonology** — F-3 minus plain-phonological and minus phonological-similarity.
- **Co-primary = Δ vs bag / shuffle / random-relabel** — F-3 minus each order/structure control.
- **Score** — R² / Pearson / Spearman (continuous `Y`) or balanced accuracy / AUC (binary), averaged over
  attributes with the distribution reported.
- **Bootstrap / permutation** — bootstrap CIs on every score and Δ; a label-permutation null for the primary Δ.
- **CI and margin thresholds** — the exact margin F-3 must beat each baseline by, and the CI rule, fixed in
  advance.
- **Multiple-comparison correction** — Holm (or equivalent) across the baseline-contrast family; primary
  endpoint named in advance (both `Δ vs phonology` and `Δ vs order` required to pass).

---

## 12. Invalid-run conditions

The run is **invalid** (report the matching label, never a signal) if any hold:

- **`Y` source not independent** — gloss/varṇa-derived or definition-matched (`Y_NOT_INDEPENDENT`).
- **Concept coverage too thin** — below the pre-registered floor after exclusions.
- **Feature extraction changed after freeze** — any edit to the F-3 list / vectorization / `s_0` post-freeze.
- **Baselines missing** — any required baseline in §9 not computed.
- **Probe capacity mismatch** — F-3 and baselines not at identical capacity/CV.
- **F-3 fails synthetic sanity** — the synthetic harness positive control no longer fires SIGNAL / controls no
  longer behave.
- **Post-hoc oriented features added** — any reversal-breaking feature added to a run without separate
  pre-registration.
- **Any dictionary/gloss leakage** — into `Y`, features, decoder, or (P-generate) generator
  (`DECODER_LEAKAGE_INVALID` / `WORD_LEAKAGE_INVALID`).

---

## 13. Expected result

The expected honest outcome remains **`F_COLLAPSES_TO_PHONOLOGY → ⊥`.** Because the L1 operators are
parameterized entirely by phonological features, F-3 is at most *structured phonology*, and the standing prior
(sound-over-meaning; B1.1 `RANDOM_OR_SCRAMBLED_MATCHES`; scrambled ≈ real ~0.967) points to F-3 **not** beating
the phonological baseline. This freeze plan exists to make that verdict **trustworthy and falsifiable** (the
synthetic positive control proves the pipeline could detect interaction signal if it existed), not to avoid it.
A clean `⊥` is a successful, informative outcome and joins the prior negatives; it is not a rescue target.

---

## 14. Next operator gate

After this plan, the next step is **operator approval for a coverage audit only** — the counts-only
eligibility report of §5, which fetches **no** `Y` values and scores nothing. **Dataset acquisition / download
still requires separate, explicit operator approval** and does not proceed on the strength of this document or
the coverage audit alone. In order: (1) approve coverage audit → (2) review eligibility report → (3) if it
clears, approve dataset acquisition + freeze package → (4) only then, under a further authorization, the pilot
run. No step is auto-triggered.

---

## 15. Boundary statement

> B1.4b real-data preparation and freeze plan completed. No real data acquired. No meaning validated. Nothing
> run or scored. Track B remains blocked. Structure, not validated meaning.
