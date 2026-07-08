# B1.4b′ — Evidence-Run Pre-Freeze Review

**Status:** Pre-freeze review (docs-only). **No evidence freeze created. No decoder trained. Nothing run or
scored.**
**Governed by:** `B1_4B_PRIME_MCRAE_FREEZE_PACKAGE_PLAN.md` (`5605b82`),
`b1_4b_prime_prepare_mcrae_y.py` + manifest (`23968c4`), `stage_a_prime_coverage.py` (`8d4b097`),
`B1_4B_PRIME_LAYER3_DECODER_Y_DESIGN.md`.
**No meaning validated. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated
meaning.**

---

## 1. Purpose

This is a **pre-freeze review** of the B1.4b′ evidence-run package: it checks whether everything needed for a
reproducible, pre-registered evidence run is in place — **without creating the freeze and without running the
decoder**. It trains nothing, scores nothing, and claims no result. Its output is a single readiness decision.

---

## 2. Current package status

From the Y-prep (`23968c4`, verified this review):

- **521 retained concepts** (541 − 20 excluded).
- **242 attribute features**.
- **Private Y matrix 521 × 242** (binary), written to the git-ignored `frozen/private_mcrae/` — **not
  committed**.
- **Exclusions:** 18 homograph sense-pair members + `cloak`/`clock` (false collision); 0 non-decomposable.
- **Hashes / provenance:** manifest records SHA-256 of the 5 private source files + derived concept-list,
  attribute-list, Y-matrix, preprocessing-config, exclusion-list, Stage A′ module, and F-3 / baseline /
  decoder spec hashes + self-hash.
- **No raw data committed** (re-verified: `git ls-files` shows no `CONCS`/`FEATS`/`cos_matrix`/`private_mcrae`/
  `y_matrix`/`_full.txt`).

---

## 3. Terms-of-Use compliance ✅ READY

- **Raw McRae data not tracked** — verified (0 matches).
- **Private Y artifacts not tracked** — `frozen/private_mcrae/` is git-ignored (`git check-ignore` passes).
- **Only hashes/counts/config/exclusions committed** — manifest + exclusions carry no feature values
  (`Prod_Freq` absent; verified by test).
- **Citation / provenance recorded** — McRae et al. (2005) + Psychonomic archive + Terms note in the manifest.

**Verdict:** compliant; no Terms blocker.

---

## 4. Concept / exclusion review ✅ READY

- **Homograph exclusions** — the 9 collapsed sense-pairs (`bat`, `board`, `bow`, `cap`, `hose`, `mink`,
  `mouse`, `pipe`, `tank`) excluded (18 members). ✓
- **`cloak`/`clock` exclusion** — the G2P false collision excluded. ✓
- **No post-hoc filtering** — exclusion rules were **pre-declared** in the freeze plan (`5605b82`) *before* this
  data step; concept set frozen before any F-3/scoring. ✓
- **Retained concepts fully decompose** — all 521 decompose fully under Stage A′ (`all_retained_fully_decompose`
  check true). ✓
- **Retained phoneme sequences unique** — 521 distinct Stage A′ sequences (`retained_sequences_unique` true). ✓

**Verdict:** ready.

---

## 5. Y matrix readiness ✅ READY (data side)

- **Representation:** binary concept×feature; absence = 0 (pre-declared).
- **Feature threshold:** McRae `Prod_Freq ≥ 5` (the ≥5/30 inclusion rule); **non-taxonomic** features only.
- **Feature pruning:** feature retained iff present in **≥ 5 retained concepts**.
- **Missing/absence rule:** unlisted feature = 0; no imputation.
- **Retained feature count:** **242** (> 0; check true).
- **Private hash/reference:** `y_matrix_sha256` + shape `[521, 242]` recorded; matrix itself private/untracked.

**Verdict:** the Y artifact is frozen-ready and Terms-compliant.

---

## 6. Stage A′ readiness ✅ READY

- **Module hash/version:** `stage_a_prime_coverage.py` SHA-256 `217c9ec9…a9e2cd` — **matches the manifest
  exactly** (verified this review).
- **Coverage tests pass:** `test_stage_a_prime_coverage.py` **11/11**.
- **Operator sanity pass:** all operators orthogonal / finite / deterministic (per coverage tests).
- **No code changes since Y-prep:** `git status` clean for the module and frozen Stage A. ✓

**Verdict:** ready and version-pinned.

---

## 7. F-3 feature readiness ⚠️ SPEC READY / EXTRACTOR NOT IMPLEMENTED

- **Features specified:** adjacent-commutator mean/max + ordered-vs-reversed non-commutativity; state
  norm/magnitude features excluded. (Spec + hash in the manifest.) ✓
- **Reversal-symmetry limitation recorded** — `‖[a,b]‖=‖[b,a]‖`, `‖prod−rprod‖` symmetric. ✓
- **No post-hoc oriented extensions** — barred unless separately pre-registered. ✓
- **Feature extractor version/hash:** **PENDING** — there is a *spec hash* but **no implemented F-3 extractor
  that computes `z` over the 521 retained concepts' Stage A′ operator sequences.** The B1.4b synthetic harness
  (`458fb1e`) demonstrated the F-3 computation on synthetic operators, but a McRae-concept F-3 extractor is not
  built.

**Verdict:** spec ready; **extractor implementation pending** (blocks a run).

---

## 8. Baseline readiness ⛔ NOT IMPLEMENTED (blocks the run)

Specified in the manifest, but **none is implemented** as runnable code over the McRae/Stage A′ data:

| Baseline | Spec | Implemented? |
|---|---|---|
| plain phonological features | ✓ | ✗ |
| phonological similarity | ✓ | ✗ |
| bag-of-phonemes | ✓ | ✗ |
| shuffled-order | ✓ | ✗ |
| random / relabel operators | ✓ | ✗ |
| length / frequency | ✓ | ✗ |
| sentiment / lexicon | ✓ | ✗ |
| chance / null | ✓ | ✗ |

The **plain-phonological** and **phonological-similarity** baselines are the **primary-endpoint comparators**;
without them a run cannot evaluate `Δ vs phonology` and would be `INVALID` (missing phonology baseline).

**Verdict:** **blocked** — all 8 baselines require implementation.

---

## 9. Decoder / probe readiness ⛔ NOT IMPLEMENTED (blocks the run)

- **First-pass regularized linear** — specified (ridge / L2-logistic). ✗ implemented.
- **Capacity parity** — specified (same family/grid/CV for F-3 and every baseline). ✗ implemented.
- **Concept-level CV** — specified (fold seed fixed). ✗ implemented.
- **Hyperparameter grid** — specified; ✗ implemented.
- **No test tuning** — specified; ✗ implemented.

**Verdict:** **blocked** — the decoder/probe + CV harness is unimplemented.

---

## 10. Metric / endpoint readiness ⚠️ SPEC READY / SCORER NOT IMPLEMENTED

- **Primary Δ vs phonology; co-primary Δ vs bag/shuffle/random** — specified. ✓
- **R²/correlation/accuracy** — specified. ✓
- **CIs / permutation** — specified. ✓
- **Holm correction** — specified. ✓
- **Terminal-label rules** — the 9 evidence-run labels defined. ✓
- **Scorer implementation:** **PENDING** — no code computes the endpoints, CIs, permutation nulls, or emits a
  terminal label.

**Verdict:** spec ready; **scorer implementation pending**.

---

## 11. Invalid-run checklist (voiders — for the eventual run)

- raw McRae data committed → **not present** (compliant now); must stay so.
- Terms of Use breach → none now.
- **missing phonology baseline → CURRENTLY TRUE** (not implemented) — would void a run today.
- decoder capacity mismatch → n/a (decoder unimplemented).
- post-hoc exclusions → none (pre-declared).
- Stage A′ changed without prereg → none (hash matches).
- semantic claim without endpoint success → none (no claim made).

---

## 12. Readiness decision

**`B1_4B_PRIME_PREFREEZE_BLOCKED_BASELINES`.**

The **data/spec half is frozen-ready** — Y (521×242, private), exclusions, Stage A′ (hash-pinned, tests green),
Terms compliance, and the F-3 / baseline / decoder / metric **specifications** (all hashed). But the **run
harness is unimplemented**: the **8 baselines** (§8, primary blocker — including the decisive phonology
baselines), the **decoder/CV** (§9, co-blocker), the **F-3 extractor** over McRae concepts (§7), and the
**metric/endpoint scorer** (§10) do not exist as code. A package cannot be frozen for an evidence *run* when the
run machinery — especially the phonology comparator that the primary endpoint depends on — is absent.

(Not `READY_FOR_EVIDENCE_FREEZE`: half the run harness is unbuilt. Not `BLOCKED_TERMS`: compliant. Not
`BLOCKED_DECODER` alone: the baselines are the broader gap and the phonology comparator is primary. Not
`INCONCLUSIVE`: the gap is specific and enumerated.)

---

## 13. Expected result

The expected honest result of the eventual run remains **`F_COLLAPSES_TO_PHONOLOGY → ⊥`.** Stage A′ is
explicitly phonology-derived, so the phonological baseline is decisive and likely strong; the homograph
structure reinforces the ceiling (identical sound → identical F-3 → forced identical prediction for
different-attribute words). This review exists to make the eventual verdict trustworthy, not to advance a
positive.

---

## 14. Next gate

Because the decision is **blocked on the run harness**, the next step is **implementation of the B1.4b′ run
harness** (F-3 extractor over Stage A′ operator sequences + the 8 baselines at matched capacity + the
concept-level-CV decoder + the metric/endpoint scorer), **synthetic-tested first** (as the B1.4b synthetic
harness was), under a **separate approval**. Only after that harness exists and passes its synthetic
positive/null controls would a **second** pre-freeze review return `B1_4B_PRIME_READY_FOR_EVIDENCE_FREEZE`, and
only then — under a **further explicit operator approval** — would an evidence freeze + run be created. **No
automatic run.**

---

## 15. Boundary statement

> B1.4b′ evidence-run pre-freeze review completed. No decoder trained. No semantic validation performed. No
> evidence freeze declared. No raw McRae data committed. Original B1.4b remains blocked. Track B remains
> blocked. Structure, not validated meaning.
