# B1.4b′ — McRae Freeze-Package Plan

**Status:** Freeze-package **plan** (docs-only). Specifies exactly what would be frozen before any B1.4b′
semantic/attribute run. **No raw McRae data committed. No Y matrix built. No decoder trained. Nothing run or
scored.**
**Governed by:** `B1_4B_PRIME_MCRAE_AUTHORITATIVE_Y_OVERLAP_AUDIT.md` (`301329a`),
`B1_4B_PRIME_LAYER3_DECODER_Y_DESIGN.md`, `PREREG_B1_4B_L1_L2_L3_OPERATOR_INTERACTION.md`,
`stage_a_prime_coverage.py` (`8d4b097`, read-only).
**No meaning validated. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated
meaning.**

---

## 1. Purpose

This is a **freeze-package plan only** — it fixes, in advance, exactly which artifacts, rules, and
configurations a future B1.4b′ run would hash-freeze, so the eventual run cannot be tuned to an outcome. It
**builds no `Y` matrix, commits no raw data, trains no decoder, and runs nothing.** It is design/specification,
gated to a separate Y-construction approval.

---

## 2. Current state

- **Stage A′ coverage passed** on repo-local pools (`8d4b097`): Sanskrit 107/107, English 92/92.
- **Stage A′ sample L1→L2 trace passed** (`af9935b`): 20/20 words, F-3 computable.
- **McRae concept-overlap audit passed** (`301329a`): `Y_SOURCE_OVERLAP_AUDIT_PASS` — 541 concepts, 517 as-is /
  541 tag-stripped decomposable, ≥100 satisfied.
- **Layer 3 now has a candidate independent `Y` source** — the authoritative McRae norms (operator-provided,
  Terms-of-Use-bound).
- **No `Y` matrix has been built.** **No semantic validation has been performed.**

---

## 3. Terms of Use / data handling

- **Permitted use:** McRae norms may be used for **non-commercial research/education** with **required
  citation** of both the article and the retrieved Psychonomic Web Archive norms.
- **All rights remain with the authors; redistribution is not granted.** Therefore **raw McRae data must NOT be
  committed** to the repo (public).
- **What may appear in the repo:** **derived counts/statistics**, a few **already-public example concepts**,
  and **provenance hashes** of the local private files (hashes do not redistribute data).
- **Required citation (any downstream use):** McRae, K., Cree, G. S., Seidenberg, M. S., & McNorgan, C. (2005),
  *Behavior Research Methods*, 37(4), 547–559, + the retrieved Psychonomic Web Archive norms.

**Provenance hashes of the operator-provided private files (recorded, data not redistributed):**

| Logical file | SHA-256 |
|---|---|
| `CONCS_brm.txt` (541 concepts + stats) | `a2cf1005d9e01d9818c7260d4aad912f0070563d9d9ca022c3ba1a5f7da7a4c0` |
| `CONCS_FEATS_concstats_brm.txt` (concept×feature) | `fe796831232b164635c258095749320665c18c40186778e8d8baf4b0c4cdba23` |
| `FEATS_brm.txt` (2,526 features) | `c73f3284bef2afd449046047d2f38c10ca3b1e823d9093b6c4ceb0fe1b3b64ed` |
| `READ_ME.txt` | `8384ec7e9068ab07587feca2b52873db5a67e4515c6c000bef1e19efb4137551` |
| `ReadMe_Terms_of_Use.txt` | `2f52993903af2ba93ecb2729fcc09d9b7f3b02534a7ef18142ad61917ba660b0` |

---

## 4. McRae source files

| File | Role | Needed for B1.4b′? |
|---|---|---|
| `CONCS_brm.txt` | concept list + per-concept stats | **required** (concept universe; covariates) |
| `CONCS_FEATS_concstats_brm.txt` | concept×feature listings + stats | **required** (the `Y` attribute source) |
| `FEATS_brm.txt` | feature-level stats (2,526 features) | **required** (feature inclusion/pruning) |
| `READ_ME.txt`, `ReadMe_Terms_of_Use.txt` | provenance + license | **required** (compliance record) |
| `cos_matrix_brm_IFR_*` (541×541 cosine) | between-concept similarity | **optional** (not used for the primary `Y`; possible auxiliary control) |

All are held as **local private files**; only hashes + derived artifacts enter the repo.

---

## 5. Concept preprocessing freeze

Fixed **before** any `Y` build or fit:

- **Case normalization:** lowercase; strip surrounding whitespace.
- **`_(sense)` tag stripping:** pre-declared rule removing a trailing `_(...)` sense tag (e.g.
  `bat_(animal)` → `bat`). Declared here, before results.
- **Punctuation / multiword:** McRae concepts are single tokens; any residual punctuation is a decomposition
  failure to be **reported, not coerced** (no silent fallback).
- **Exclusion rules (pre-declared):** homographs (§6), false collisions (§7), and any concept that fails Stage
  A′ decomposition (0 in the tag-stripped set).
- **No post-hoc concept filtering** — the concept set is frozen before any F-3/`Y` fit; concepts are never
  dropped after seeing results.

---

## 6. Homograph handling

The 9 homograph sense-pairs — `bat`, `board`, `bow`, `cap`, `hose`, `mink`, `mouse`, `pipe`, `tank` — collapse
to identical Stage A′ phoneme/operator sequences → identical F-3. Options:

- **(A) Exclude all collapsed homograph sense-pairs** — drop both members of each pair from the concept set.
- **(B) Group each pair as one phonological item** — merge to a single row, but only if `Y` is collapsed
  consistently (e.g. averaged/union features) — which mixes two genuinely different meanings and is hard to
  justify.
- **(C) Retain only if `Y` is collapsed consistently** — same objection as (B).

**Recommended for the first evidence pass: (A) exclude.** Rationale: F-3 (sound-only, by design) cannot see the
sense difference, so homographs can neither fairly credit nor fairly blame F-3; and context is deliberately not
an input (bringing it in would reintroduce the leakage B1.4b′ exists to avoid). Excluding ~18 concepts leaves
the set well above the ≥100 floor.

---

## 7. False-collision handling

`cloak` / `clock` → `k-l-o-k` is a **Stage A′ G2P-faithfulness defect** (the coverage-oriented `A_PRIME_EN` maps
`c→k` and coarse vowels, wrongly merging two distinct words).

- **Treat as a Stage A′ defect**, not a McRae issue.
- **Recommended: exclude the false-collision cases** from the first evidence pass **unless Stage A′ is
  separately revised** with a phonetically accurate G2P (itself a new Stage A′ version requiring its own
  coverage pre-registration).
- **No post-hoc repair inside B1.4b′** — the fix belongs upstream in a versioned Stage A′, not as an ad-hoc
  patch during a run.

---

## 8. Y matrix freeze

How the McRae attribute data would become `Y` (construction is a **separate gated step**, not done here):

- **Representation:** a **binary concept×feature matrix** (feature present if listed by ≥ the McRae threshold),
  or a **production-frequency-normalized** feature vector — choose one, pre-declared.
- **Feature inclusion threshold:** use McRae's own **≥ 5-of-30** production-frequency cutoff (already the norm's
  inclusion rule); optionally restrict to **non-taxonomic** features (declared).
- **Sparse-feature pruning:** drop features occurring in **< k concepts** (k pre-declared, e.g. ≥ 5) to avoid
  degenerate one-hot columns.
- **Concept inclusion threshold:** concepts must survive §5–§7 exclusions and Stage A′ full decomposition.
- **Missing-value rules:** McRae listings are presence-based; unlisted = 0 (absence), pre-declared; no
  imputation of novel values.
- **No semantic/varṇa/KCPR-derived features added** — `Y` is McRae's human-produced features only; nothing from
  the varṇa system, gloss, four-sphere, polarity, or KCPR enters `Y`.

---

## 9. F-3 feature freeze

- **L1:** Stage A′ phoneme/operator sequence (`A_PRIME_EN`, `M_σ = expm(Σ_j f_{σ,j} G_j)`), version-pinned to
  `stage_a_prime_coverage.py` `8d4b097`.
- **L2 / F-3:** adjacent-commutator magnitudes (mean, max) + ordered-vs-reversed non-commutativity; **state
  norm/magnitude features excluded** (degenerate under orthogonality).
- **Ordered-product / associator features:** included only if pre-declared in the freeze; otherwise omitted.
- **Reversal-symmetry limitation:** F-3 is invariant to full sequence reversal (`‖[a,b]‖=‖[b,a]‖`,
  `‖prod−rprod‖` symmetric); recorded in the freeze.
- **No post-hoc oriented/signed extensions** unless separately pre-registered as a new feature set.

---

## 10. Baselines freeze

All at **matched decoder capacity** (§11):

- plain phonological features (pooled `f_σ`),
- phonological similarity,
- bag-of-phonemes,
- shuffled-order (F-3 on shuffled sequences),
- random / relabel operators,
- length / frequency (McRae `Length_Letters`, `KF`, `BNC` as covariates/baseline),
- sentiment / lexicon,
- chance / null (label permutation).

Baseline definitions + any RNG seeds are frozen with the package.

---

## 11. Decoder / probe freeze

- **First-pass decoder:** regularized **linear** only — ridge (continuous `Y` / per-feature regression) or
  L2-logistic (binary features).
- **Capacity parity:** identical probe family, regularization grid, and CV protocol for F-3 **and** every
  baseline.
- **Concept-level cross-validation:** folds partition **concepts** (no concept in train and test); fold seed
  fixed.
- **Hyperparameter grid:** pre-declared; selected by **inner** CV on training folds only.
- **No high-capacity model** in the first evidence pass (no deep nets / unbounded boosting).
- **No tuning on test concepts** — test folds never touched during model selection.

---

## 12. Metrics and endpoints

- **Primary endpoint:** Δ vs **phonology** (F-3 minus plain-phonological and minus phonological-similarity).
- **Co-primary:** Δ vs **bag / shuffle / random-relabel**.
- **Score:** R² / correlation (continuous) or balanced accuracy / AUC (binary), averaged over features, with
  distribution reported.
- **CIs / permutation:** bootstrap CIs on every score and Δ; label-permutation null for the primary Δ.
- **Multiple-comparison correction:** Holm (or equivalent) across the baseline-contrast family; primary
  endpoint named in advance (both Δ-phonology **and** Δ-order must pass).
- **Terminal-label rules:** emit exactly one of `L1_L2_L3_ATTRIBUTE_SIGNAL` (only if F-3 beats **all**
  baselines on the pre-registered endpoint) / `F_COLLAPSES_TO_PHONOLOGY` / `BAG_OR_SHUFFLE_EXPLAINS` /
  `RANDOM_RELABEL_EXPLAINS` / `SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS` / `Y_NOT_INDEPENDENT` /
  `DECODER_LEAKAGE_INVALID` / `NULL_RETURN_BOTTOM` / `INCONCLUSIVE`. **This plan claims none of them.**

---

## 13. Invalid-run conditions

The run is **invalid** (report the matching label, never a signal) if any hold:

- **raw McRae data committed publicly** / Terms of Use not respected,
- **`Y` built after inspecting F-3 outcomes** (post-hoc target),
- **missing phonology baseline**,
- **decoder capacity mismatch** between F-3 and baselines,
- **post-hoc concept exclusions** (dropping concepts after seeing results),
- **Stage A′ code changed without separate pre-registration**,
- **a semantic claim made without a passed primary endpoint**.

---

## 14. Freeze manifest design

The eventual freeze manifest (a JSON, created only under separate approval) must include:

- **source / provenance** — McRae 2005 citation + Psychonomic archive + Terms-of-Use acknowledgment;
- **local private-file hashes** — SHA-256 of `CONCS_brm.txt`, `CONCS_FEATS_concstats_brm.txt`, `FEATS_brm.txt`,
  `ReadMe_Terms_of_Use.txt` (see §3);
- **concept list hash** — SHA-256 of the frozen, post-exclusion concept list (a derived artifact, not raw data);
- **attribute list hash** — SHA-256 of the frozen feature/attribute set;
- **Y preprocessing hash** — representation + thresholds + missing-value rules;
- **F-3 feature-extractor version/hash** — `stage_a_prime_coverage.py` commit + F-3 feature spec;
- **baselines version/hash** — definitions + seeds;
- **decoder / metric config hash** — probe family, grid, CV, endpoint, thresholds;
- **exclusion-list hash** — homographs + false collisions + any decomposition failures;
- **manifest self-hash**.

Only **hashes and derived artifacts** are committed; the **raw McRae data never is**.

---

## 15. Expected outcome

The expected honest result remains **`F_COLLAPSES_TO_PHONOLOGY → ⊥`.** Stage A′ is explicitly phonology-derived,
so the phonological baseline is **decisive and, with fuller faithful coverage, likely stronger**. Homographs
(§6) further make the point: identical sound → identical F-3 → the model is forced to predict identical
attributes for words with genuinely different attributes. This freeze exists to make the eventual verdict
**trustworthy and falsifiable**, not to manufacture a positive.

---

## 16. Next gate

After this plan, the next step is **explicit operator approval for `Y`-matrix construction and freeze-manifest
preparation** — building the derived (non-raw) `Y` artifacts + hashes from the private McRae files, still with
**no decoder training and no semantic run**. Only after that freeze, and under a **further** authorization,
would a B1.4b′ evidence run be considered. No `Y` build, no run, is authorized by this document.

---

## 17. Boundary statement

> B1.4b′ McRae freeze-package plan completed. No raw McRae data committed. No Y matrix created. No semantic
> validation performed. No evidence freeze declared. Original B1.4b remains blocked. Track B remains blocked.
> Structure, not validated meaning.
