# C×R×S Phase 4 — Capstone Results (one page)

> Top-level summary of the Phase 4 hidden-state effort. Records the full arc and fixes the claims so
> they cannot be overstated later. Documentation only — no code, runtime, or Phase 1–3 changes.

## 1. Executive verdict

- **Phase 4 found a real hidden-only (h0) signal:** `PHASE4_H1_STATIC_H0_STABLE_PREDICTIVE`.
- **Phase 4 did NOT validate the learned Bhava readout:**
  `PHASE4_BHAVA_COLLAPSE / PHASE4_HIDDEN_ONLY_SUFFICIENT`.
- The **hidden-state Bhava track is CLOSED** under the pre-registered kill criterion
  (`CSR_MATCH_FILTER_PHASE4_STAGEB2_BHAVA.md §7–8`).
- **Bhava remains interpretive / research-only and is NOT wired into CSR runtime.**
- **C×R×S Phase 1–3 remains the validated product path.**

## 2. What was positive (banked)

The pre-answer **final-prompt-token hidden state** linearly predicts, within-arm:
- `frame_violation` — framed AUROC ≈ **0.76**;
- `rejected_domain_leak` — framed AUROC ≈ **0.83**.

These hold **within-arm** (the base-vs-framed confound, `hidden→arm≈1.00`, is controlled),
**within-row-type** (not merely detecting "this is an adversarial prompt"), and **above a surface
prompt-token n-gram baseline** (by ≈ **+0.09 to +0.21 AUROC** — the signal is more than lexical). The
signal is **strongest under adversarial semantic stress** and present-but-weaker on ordinary prompts.
It is a **correlational linear probe only** — not causal, not mechanistic.

## 3. What was negative (banked)

The Stage-B2 **target-orthogonal learned Bhava read** (primary 7-class object-mode taxonomy):
- **orthogonality control PASSED** (mode→target 0.45 / 0.54 ≤ 0.60) — so the negative is **not** a
  leakage artifact;
- the Bhava read **collapsed**: effective rank ≈ **2.58 < 3** (person_role-dominated taxonomy);
- `hidden_plus_bhava` added **≈ 0 or negative** AUROC over `hidden_only` across all configs;
- `bhava_only` was **at or below chance** (0.43–0.49);
- it did **not** beat the **dimension-matched random control**;
- **`gate_pass_frac = 0`** — it failed the strict incremental-value gate on every seed × n_pca config.

## 4. What this means

- Hidden-state risk detection is **useful as a research finding**.
- Bhava is **not technically justified** as a diagnostic layer on this operationalization.
- **No Phase 5 Bhava/CSR integration should proceed.**
- Any future Bhava attempt requires a **new pre-registration** (not a re-roll of this taxonomy).

## 5. Product implication

- The product is **C×R×S MATCH-filter + framed prompting + answer audit** (Phase 1 frozen, Phase 2/2B
  validated, Phase 3 audit).
- The product **does not depend on Bhava**.
- **Bhava is not runtime-active.**
- **No model weights, hidden states, or logits are modified.**

## 6. Boundaries (do NOT claim)

- ❌ consciousness;
- ❌ Bhava is proven;
- ❌ hidden-state CSR is active;
- ❌ causal mechanism;
- ❌ cross-model generalization;
- ❌ generation steering.

The only valid Phase 4 claims: *(a)* a pre-answer hidden-state linear probe detects `frame_violation`
and `rejected_domain_leak` above surface and confound baselines on this dataset/model; *(b)* a
target-orthogonal Bhava-style readout adds no diagnostic signal beyond that hidden state.

## 7. Final recommendation

- **Close Phase 4.**
- **Bank** hidden-only h0 risk detection as a **positive** research result.
- **Bank** the Bhava readout as a **clean negative**.
- **Return focus to the C×R×S wrapper / audit product.**

---

### Arc & references
Stage-A collection → Stage-B1 (n=110 underpowered, fragile) → pre-registered §2.2 power-vs-level gate →
expanded re-test (n=1032, static h0 stable-predictive) → field-stress + row-type confound checks →
Stage-B2 pre-registration → Stage-B2 learned-Bhava test (negative).

A **separate, later pre-registration — Phase 4D (Guna/Vritti-controlled residual Bhava)** — also landed
negative (`PHASE4D_LEAKAGE_SUSPECTED`): the "Vritti" drift proxy is definitionally nested in the audit
targets, and the residual added no signal over hidden-only. Same bottom line: hidden-only is
sufficient; no Bhava-structured read adds value; Bhava stays out of runtime. See `RESULTS_PHASE4D.md`.
Detail: `RESULTS_PHASE4_STAGEB.md` (§7 robustness, §8 expanded re-test, §9 subset/field-stress),
`RESULTS_PHASE4_STAGEB2.md` (Bhava verdict),
`CSR_MATCH_FILTER_PHASE4_HIDDEN_STATE_PROBE.md` (§2.1 wiring status, §2.2 kill criterion),
`CSR_MATCH_FILTER_PHASE4_STAGEB2_BHAVA.md` (pre-registration).
