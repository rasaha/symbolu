# C×R×S Phase 4 — Stage-B2 (learned Bhava read) PRE-REGISTRATION

> **Status: DESIGN ONLY, locked before implementation.** No probe is fit here. Same discipline as the
> Phase 2B rubric lock and the §2.2 kill criterion: fix the hypothesis, the Bhava definition, the
> controls, the gate, and the kill criterion BEFORE seeing any Stage-B2 number. Honesty note: the
> hidden-only baseline is now **strong** (framed frame_violation ≈0.76, rejected_leak ≈0.83), so
> "Bhava adds ≥0.05 over it" is a **hard** bar and a clean negative is the most likely, fully accepted
> outcome.

## 1. Stage-B2 question
**Does a TARGET-ORTHOGONAL learned "Bhava read" of the pre-answer hidden state add incremental value
over the validated static-h0 hidden-only baseline** for the confound-cleared failure targets? If yes →
a Bhava-style readout carries diagnostic signal the raw probe misses. If no → hidden-only is
sufficient, Bhava is not promoted, and stays out of CSR runtime.

## 2. Baseline & targets
Baseline = the validated **Stage-B1 h0 hidden-only** within-arm result (`RESULTS_PHASE4_STAGEB.md §8`).
- **Primary targets:** `frame_violation`, `rejected_domain_leak` (confound-cleared in §9).
- **Secondary / noisy:** `audit_fail` (within-subset fragile → diagnostic-only).
- **Exploratory:** `secondary_promoted`.
- Excluded: `factuality_suspected` (power), `meta_parroting` (detector over-fires).
Scope: **within-arm (framed primary)**, group-by-term CV, multi-seed × n_pca robustness, on
`runs/csr_phase4_v3` (final-prompt-token, no answer-token leakage).

## 3. Bhava supervision — target-orthogonal only
The Bhava read = a low-dim (≤12) set of **learned linear directions in hidden space**, fit by
supervision from the object's *disposition/mode* — a coarse **object-mode taxonomy** derived from the
object's frame-family (e.g. person-role / substance-element / artifact / abstract-role), ≤6 classes.
The Bhava read of an example = its projection onto those directions.

**Directions MUST NOT be trained directly on any failure/audit label:** not `audit_fail`, not
`frame_violation`, not `rejected_domain_leak`, not `secondary_promoted`, not `factuality_suspected`,
not `meta_parroting`. The supervision only orients axes in hidden space.

## 4. Orthogonality checks (disqualifier)
Report the association between the **Bhava-supervision labels** and each **target failure label**
(AUROC and/or mutual information). The supervision is admissible only if it does **not** predict the
target above chance (AUROC ≤ **0.60**). If the supervision is strongly correlated with failure →
**`PHASE4_BHAVA_LEAKAGE_SUSPECTED`** (it would smuggle the label in). If no orthogonal supervision
survives, Stage-B2 cannot make a clean supervised claim and says so.

## 5. Required controls
- **hidden-only h0 baseline** (the number to beat).
- **dimension-matched random control** (hidden ⊕ random features of width = Bhava): rejects "more dims
  for free."
- **optional unsupervised control** (top structured components / clustering of hidden states), reported
  separately.
- **decoded-token baseline** — required *if generated tokens are ever used as features*. Stage-B2 uses
  h0 only (no generated tokens), so a **prompt-token n-gram** baseline is used to check the hidden
  signal is not merely surface prompt lexicon; the generated-token decoded baseline is reserved for
  Phase 4C.
- **within-arm reporting** (arm is a confound, `hidden→arm≈1.00`).
- **within-row-type / stress-field reporting** (ordinary vs adversarial; the §9 control).
- **group-by-term CV** (no term in train and test).
- **Forbidden features:** no C/R/S score features, no phonemic 12D features, no CSR trace-vector
  features, no answer-text features. (Manifest already asserts `contains_*=false`.)

## 6. Incremental-value gate (strict, pre-committed)
`PHASE4_BHAVA_ADDS_SIGNAL` requires ALL of:
1. `hidden_plus_bhava` − `hidden_only` ≥ **0.05** AUROC with a **bootstrap delta CI clearly above 0**;
2. ≥ **0.05** over the **dimension-matched random control** with non-overlapping CIs;
3. ≥ **0.05** over the **prompt-token n-gram** baseline with non-overlapping CIs (not just surface words);
4. the Bhava read does **not collapse** (effective rank ≥ 3 of ≤12);
5. the orthogonality control (§4) passes;
6. holds **within-arm** (not pooled-only) and is **stable** across ≥80% of seed × n_pca configs.

## 7. Kill criterion (locked)
If target-orthogonal Bhava does **not** beat hidden-only under the strict gate, record
**`PHASE4_BHAVA_NO_INCREMENTAL_SIGNAL`** (or **`PHASE4_HIDDEN_ONLY_SUFFICIENT`** when h0 is itself
strong and Bhava adds nothing) and **STOP**: do not proceed to any Phase 5 Bhava/CSR integration, do
not search post hoc for a "better Bhava definition" (a new definition is a new pre-registration, not a
re-roll). C×R×S remains the validated Phase 1–3 product.

## 8. Decision labels
- `PHASE4_BHAVA_ADDS_SIGNAL` — all of §6 hold.
- `PHASE4_BHAVA_NO_INCREMENTAL_SIGNAL` — Bhava fails the incremental gate.
- `PHASE4_HIDDEN_ONLY_SUFFICIENT` — h0 strong, Bhava adds nothing (the expected case).
- `PHASE4_BHAVA_LEAKAGE_SUSPECTED` — orthogonality fails, or bhava_only ≈ perfect.
- `PHASE4_BHAVA_COLLAPSE` — Bhava read degenerates (eff. rank < 3).
- `PHASE4_INSUFFICIENT_LABEL_POWER` — too few within-arm positives to decide.

## 9. Interpretation boundaries
Even if Stage-B2 passes, do **not** claim: Bhava is conscious; Bhava is generation-active; Bhava is
wired into CSR runtime; or that model weights / hidden states / logits are modified. **The only valid
claim is:** *a target-orthogonal Bhava-style readout adds diagnostic signal beyond hidden-only on this
dataset and this model.* Bhava stays out of runtime regardless of outcome unless a future
pre-registered effort earns it.

## 10. Out of scope
No generation control, no logit/representation steering, no Guna/Vritti/JEPA, no Phase 5 integration,
no claim Bhava is "proven," no modification to Phase 1–3 logic.
