# B1.4b′ — Evidence-Run Pre-Freeze Review (v2, post-harness)

**Status:** Pre-freeze review (docs-only). **No evidence freeze created. No decoder trained on real McRae Y.
Nothing run or scored.**
**Supersedes:** the v1 review (`869e9ae`, `BLOCKED_BASELINES`) now that the scorer/arm registry exists
(`92fbae9`).
**Governed by:** `b1_4b_prime_scorer.py` + tests (`92fbae9`), `b1_4b_prime_prepare_mcrae_y.py` + manifest
(`23968c4`), `stage_a_prime_coverage.py` (`8d4b097`), `B1_4B_PRIME_MCRAE_FREEZE_PACKAGE_PLAN.md` (`5605b82`).
**No meaning validated. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated
meaning.**

---

## 1. Purpose

This re-runs the pre-freeze review now that the run harness (F-3 extractor + 9-arm registry + matched-capacity
decoder + CV + metric/label logic) is implemented and synthetic-tested. It checks whether B1.4b′ is ready for an
**evidence freeze + real decoder/baseline run** — **without** creating the freeze and **without** running the
real scorer. Output: one readiness decision.

---

## 2. Current package status

- **Stage A′ coverage:** passed; module hash `217c9ec9…` matches the Y-prep manifest (verified this review).
- **McRae Y prep:** `B1_4B_PRIME_Y_PREP_READY`.
- **Retained concepts:** 521; **features:** 242; **private Y shape:** 521 × 242 (git-ignored, not committed).
- **Scorer / arm registry:** complete — 9 predictor-feature arms + decoder + CV + metric/label logic.
- **No real run:** synthetic tests only.

---

## 3. Terms-of-Use compliance ✅ READY

- **Raw McRae data not tracked** — verified (`git ls-files`: no `CONCS`/`FEATS`/`cos_matrix`).
- **Private Y not tracked** — `frozen/private_mcrae/` git-ignored (`mcrae_y_matrix.npz` not tracked).
- **Only hashes/config/counts/exclusions committed** — manifest + exclusions carry no feature values.
- **Citation / provenance recorded** — McRae et al. (2005) + Psychonomic archive + Terms note in the manifest;
  private-file SHA-256 recorded.

---

## 4. Concept / Y readiness ✅ READY

- **Homographs excluded** — 18 members of the 9 collapsed sense-pairs. ✓
- **`cloak`/`clock` excluded** — G2P false collision. ✓
- **Retained concepts fully decompose** — 521/521 under Stage A′ (Y-prep check true). ✓
- **Retained phoneme sequences unique** — 521 distinct sequences. ✓
- **Private Y available by hash** — `y_matrix_sha256` + shape `[521, 242]` in the manifest. ✓
- **Y preprocessing deterministic** — pre-declared rules; re-run reproduces identical hashes (Y-prep test). ✓

---

## 5. Stage A′ readiness ✅ READY

- **Module version/hash:** `stage_a_prime_coverage.py` `217c9ec9…a9e2cd` — **matches the manifest**. ✓
- **Coverage tests pass:** 11/11. ✓
- **Operator sanity pass:** operators finite/orthogonal/deterministic (coverage tests). ✓
- **No Stage A′ changes since Y-prep:** `git status` clean for the module + frozen Stage A. ✓

---

## 6. F-3 readiness ✅ READY

- **Extractor implemented** — `extract_f3` over Stage A′ operator sequences (adjacent-commutator mean/max +
  ordered-vs-reversed non-commutativity). ✓
- **Deterministic feature shape** — `[n, 3]`; verified deterministic + order-sensitive (test). ✓
- **Finite-output checks** — `_finite()` raises on non-finite. ✓
- **Reversal-symmetry limitation documented** — `‖[a,b]‖=‖[b,a]‖`, `‖prod−rprod‖` symmetric (module docstring). ✓
- **No post-hoc oriented extension** — barred unless separately pre-registered. ✓

---

## 7. Arm registry readiness ✅ READY

All nine arms exist (verified): `A_F3_REAL`, `B_PHONOLOGY_PLAIN`, `C_PHONOLOGY_SIMILARITY`, `D_BAG_OF_PHONEMES`,
`E_SHUFFLED_ORDER_F3`, `F_RANDOM_RELABEL_F3`, `G_LENGTH_FREQUENCY`, `H_SENTIMENT_LEXICON`, `I_NULL_CHANCE`.

- **Predictor-feature arms, not B1.3 prompt/rendering arms** — each produces a feature matrix for the same
  concepts; the same decoder predicts the same Y; no text generated, no judge preference
  (`arms_are: predictor_feature_arms_not_llm_prompt_arms`). ✓
- **Rows align to retained concepts** — arm extractors index the same concept list (test `arms_rows_aligned`). ✓
- **Matched decoder capacity** — same ridge `LAM`, same probe family for all arms. ✓
- **Same CV folds** — deterministic concept-level folds shared across arms. ✓

---

## 8. Pending-source arms ⚠️ DECISION: one genuine blocker

- **`G_LENGTH_FREQUENCY` (frequency component):** flagged `FREQ_BASELINE_PENDING_SOURCE` when no covariate is
  passed — **but the source is IN HAND.** McRae `CONCS_brm.txt` contains `KF` and `BNC` frequency columns
  (verified). Frequency is therefore a **wiring step** (pass McRae KF/BNC as covariates at run time), **not** a
  missing source. **Not a blocker.**
- **`H_SENTIMENT_LEXICON`:** flagged `BASELINE_PENDING_SOURCE`. McRae provides **no** sentiment; an approved
  external sentiment/affect lexicon (e.g. Warriner VAD / NRC) is **not in the repo and egress-blocked**. This is
  a **genuine missing baseline.**

**Decision:** the rulebook requires any semantic claim to beat the **sentiment/lexicon** baseline. Certifying
`L1_L2_L3_ATTRIBUTE_SIGNAL` without `H` would be invalid ("beats all baselines" uncertified). Therefore the
**pending sentiment source blocks a full evidence freeze** that could certify SIGNAL. Two acceptable resolutions
(operator's choice): **(a)** supply an approved sentiment lexicon (and wire McRae KF/BNC for `G`), then
re-review → ready; or **(b)** the operator **pre-registers a phonology-primary *screening* run** that, by
construction, cannot emit `SIGNAL` (only `F_COLLAPSES_TO_PHONOLOGY` / `BAG_OR_SHUFFLE_EXPLAINS` /
`RANDOM_RELABEL_EXPLAINS` / `NULL_RETURN_BOTTOM` / `INCONCLUSIVE`) — in which case the pending sentiment baseline
is acceptable because no positive certification is possible.

---

## 9. Decoder / probe readiness ✅ READY

- **Regularized linear first pass** — ridge / L2-logistic. ✓
- **Fixed hyperparameter grid** — single frozen `LAM` (a fixed grid). ✓
- **Concept-level CV** — rows = concepts; deterministic folds. ✓
- **Capacity parity** — same family/grid/folds for F-3 and every arm. ✓
- **No test tuning** — folds fixed; no selection on test rows. ✓

---

## 10. Metrics / endpoints readiness ✅ READY

- **Primary comparison:** `A_F3_REAL` vs `B_PHONOLOGY_PLAIN`. ✓
- **Co-primary:** `A_F3_REAL` vs `D_BAG_OF_PHONEMES`, `E_SHUFFLED_ORDER_F3`, `F_RANDOM_RELABEL_F3`. ✓
- **Terminal-label mapping** — implemented in `decide_label_arms` (all 9 labels; synthetic-verified). ✓
- **CIs / permutation / Holm:** `holm_correct()` implemented; `permutation_pvalue_hook()` present and returns
  `None` without a real permute function (a **justified placeholder** — not fabricated). Bootstrap CI is a
  documented hook to enable at run time. ⚠️ *Adequate for the primary/co-primary win-rate endpoints; the
  permutation/bootstrap enrichment should be enabled in the run config.*

---

## 11. Synthetic-test readiness ✅ READY

- **All 9 terminal labels reachable via synthetic tests** — 5 via arm pipeline regimes + 4 via injected arm
  scores. ✓
- **No real McRae Y used in synthetic tests** — guard test passes; scorer reads no private Y. ✓
- **Scorer tests: 17/17.** **Stage A′ tests: 11/11.** **Y-prep tests: 7/7.** ✓

---

## 12. Invalid-run checklist (voiders for the eventual run)

- raw data committed → **none now**;
- private Y committed → **none now**;
- Terms breach → **none**;
- **missing phonology baseline → NO** (B/C implemented) — *the phonology comparators are ready*;
- arm rows misaligned → **no** (verified);
- decoder capacity mismatch → **no** (matched);
- post-hoc exclusions → **none** (pre-declared);
- Stage A′ changed after freeze → **n/a** (hash pinned);
- scorer changed after freeze → **n/a** (would require re-review);
- **semantic claim without endpoint success → the standing risk** — `SIGNAL` must not be emitted while `H`
  (sentiment) is pending (see §8).

---

## 13. Readiness decision

**`B1_4B_PRIME_PREFREEZE_BLOCKED_PENDING_COVARIATES`.**

Everything else is ready — Terms compliance, Y (521×242), Stage A′ (hash-pinned, tests green), the F-3 extractor,
the 9-arm predictor-feature registry (rows-aligned, matched capacity, same folds), the decoder/CV, the
metric/endpoint logic, and 35/35 synthetic tests. The **single genuine blocker** is the **`H_SENTIMENT_LEXICON`
baseline**, which lacks an approved source; without it the required baseline suite is incomplete and a `SIGNAL`
certification would be invalid. (Frequency for `G` is resolvable from McRae KF/BNC already in hand — a wiring
step, not a blocker.)

(Not `READY_FOR_EVIDENCE_FREEZE`: the sentiment baseline is unsourced. Not `BLOCKED_BASELINES`: the primary/
co-primary baselines are now implemented — this is specifically the pending covariate/sentiment source. Not
`BLOCKED_DECODER` / `BLOCKED_TERMS` / `INCONCLUSIVE`: those are clear.)

---

## 14. Expected result

The expected honest result of the eventual run remains **`F_COLLAPSES_TO_PHONOLOGY → ⊥`.** `A_F3_REAL` is built
from phonology-derived operators, so `B_PHONOLOGY_PLAIN` is the decisive comparator and is expected to
match/beat it; the homograph structure reinforces the ceiling. Sourcing the sentiment baseline makes the
eventual verdict *more* trustworthy, not more favorable.

---

## 15. Next gate

To reach `READY_FOR_EVIDENCE_FREEZE`, one of (operator's choice, separate approval each):

1. **Complete the baseline suite** — supply an approved sentiment/affect lexicon for `H`, and wire McRae
   `KF`/`BNC` as the `G` frequency covariates; then a v3 pre-freeze review. **Or**
2. **Pre-register a phonology-primary screening run** that cannot emit `SIGNAL` (only F_COLLAPSES / BAG /
   RANDOM / NULL / INCONCLUSIVE), in which case the pending sentiment baseline is acceptable.

Only after that — and under **further explicit operator approval** — would an **evidence freeze + real
decoder/baseline run** be created. **No automatic run.** No `L1_L2_L3_ATTRIBUTE_SIGNAL` / `ONTOLOGICAL_SIGNAL`
is claimed.

---

## 16. Boundary statement

> B1.4b′ evidence-run pre-freeze review completed. No real decoder/baseline run performed. No evidence freeze
> declared. No raw McRae data committed. Original B1.4b remains blocked. Track B remains blocked. Structure, not
> validated meaning.
