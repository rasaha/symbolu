# Conscious Generation Training — T1-v2: Powered C×R×S-LoRA Internalization on Mistral — PRE-REGISTRATION

## 1. Title
Powered follow-up to T1: does a C×R×S-LoRA reliably internalize semantic-frame behavior into Mistral's
weights (plain-prompt arm C vs base arm A), under adequate statistical power?

## 2. Status
**DESIGN ONLY, doc-only, locked before training.** No training started; no DPO; no Guna/Vritti/Kosha/Bhava
losses; no 32-D symbolic head; no runtime change; no C×R×S wrapper change; no post-hoc label retuning. This
document fixes the question, dataset, splits, metrics, gates, power, and decision labels **before** any run.

## 3. Prior result being followed up
T1 (`docs/RESULTS_CG_TRAINING_CRS_T1.md`, commit `c5ac659`; four-arm, `n_test=20`):
- **T1 decision: `CG_TRAINING_WRAPPER_STILL_BEST`.** The inference wrapper (arm B) remains the best current
  deployment path.
- **LoRA-only arm C showed an underpowered internalization hint:** C matched B on `primary_frame_correct`
  (0.90 = 0.90) and on `generalization_to_unseen_terms` (0.90), and beat base A (0.80) — but ΔC−A's
  bootstrap CI included 0 and C did not improve `rejected_domain_avoidance` over A (tie 0.95), so the strict
  gate was not met.
- **LoRA+wrapper arm D regressed badly** (primary 0.60, rejected-domain 0.65, factuality 0.80), warning
  against naive stacking.
- **T1 is NOT a failure of Conscious Generation.** The validated product remains the inference-time C×R×S
  wrapper; training-side internalization remains experimental.

## 4. Motivation
T1's only encouraging signal (plain-prompt LoRA ≈ wrapper on frame correctness) was **statistically
underpowered** (`n_test=20`, wide CIs, single seed) and carried a **completeness regression**
(`must_include_recall` 0.40→0.20 for C). T1-v2 exists to test whether that internalization hint is **real**
under adequate power, with explicit guardrails for the recall/terseness regression and stricter held-out
splits — **before** any decision to pursue DPO (T2) or symbolic-state heads.

## 5. Hypotheses
- **H1 (primary):** C×R×S-LoRA improves plain-prompt generation over base Mistral (arm C > arm A) on
  `primary_frame_correct` and generalization, **without** reducing `factuality_preserved`,
  `rejected_domain_avoidance`, or `must_include_recall`.
- **H2 (secondary):** C×R×S-LoRA **approaches** the inference wrapper (arm C → arm B) on
  `primary_frame_correct` — but the wrapper may remain best, and that is an acceptable outcome.
- **H0 (null):** C×R×S-LoRA does not add reliable incremental value over base Mistral, or it degrades
  factuality/recall.

## 6. Non-goals
No T2/DPO; no Guna/Vritti/Kosha/Bhava losses; no direct Bhava training; no 32-D symbolic head; no runtime
wiring; no C×R×S wrapper change; no post-hoc relabeling; no consciousness/cognitive-state claim. **The
failed Agentic C×R×S governance result is NOT evidence against Conscious Generation** — different task,
different question; it is out of scope here. **Beating the wrapper is NOT the sole success condition** (H2
allows the wrapper to remain best).

## 7. Dataset plan
Scale up substantially from T1's 78 examples.
- **Targets:** training **≥ 300 (prefer 500+)**, validation **≥ 50**, held-out test **≥ 100 (prefer
  150–200)**.
- **Composition (must span):** high-confidence primary matches · ambiguous terms · near-miss secondary
  domains · rejected-domain traps · unknown/unseen terms · domain-conflict prompts · negative controls ·
  multi-domain terms · examples carrying explicit `must_include` factual constraints.
- **Source:** if self-distillation is used, training targets are the wrapper's **audit-passing** answers
  (expanded over more eval items / arms / seeds to reach the size). The document states plainly:
  > **Self-distillation cannot prove superiority over the wrapper.** It tests *internalization and
  > compression of wrapper behavior into weights*, plus generalization to unseen terms/domains — not
  > whether the model can exceed its teacher.
- Domains stay within the C×R×S engine's registry where MATCH traces are needed (the engine scores only its
  23 registry domains); out-of-registry items may appear as plain-prompt generalization cases but carry no
  MATCH trace.

## 8. Train / validation / test split plan
Strict, leakage-controlled, grouped:
- **Held-out terms** (no term in both train and test) — the core generalization axis.
- **Held-out domains** where data permits (a disjoint set of primary domains forced to test only).
- **Held-out domain-pair combinations** (primary×rejected pairs unseen in train).
- **Held-out rejected-domain traps** (specific trap configurations only in test).
- A term may appear in both splits **only** if explicitly marked as a *non-generalization* (seen-term)
  slice, reported separately — never silently.
- No single **prompt template** may dominate train or test (template diversity tracked).
- **Target-answer text must never appear in any evaluation prompt.**

## 9. Training plan
`Mistral-7B` or `Mistral-7B-Instruct-v0.3`; **LoRA or QLoRA**; small controlled run; **no full-weight
training; no architecture change; no 32-D symbolic head.** The 32-D symbolic-state head and Guna/Vritti/
Kosha/Bhava remain **future tracks only** (separate pre-registrations). Output: a `crs-lora-v2` checkpoint
per seed.

## 10. Evaluation arms (four; same as T1)
| arm | model | prompt |
|---|---|---|
| **A** | base Mistral | plain (no frame text) |
| **B** | base Mistral + C×R×S wrapper | framed (validated baseline) |
| **C** | **crs-lora-v2** Mistral | plain (no frame text) — the internalization test |
| **D** | crs-lora-v2 + C×R×S wrapper | framed |
> **Arm D is EXPLORATORY/DIAGNOSTIC ONLY.** Because T1 showed wrapper+LoRA interference, **D is NOT required
> for T1-v2 success.** D measures only whether stacking remains harmful; a D regression does **not** fail C.

## 11. Metrics
`primary_frame_correct · rejected_domain_avoidance · rejected_domain_leak_rate ·
secondary_overpromotion_rate · factuality_preserved · clarity_usefulness · must_include_recall ·
generalization_to_unseen_terms · generalization_to_unseen_domains · answer_length · terse_answer_rate ·
over_framing_mechanical_rate`.
**Per-slice** (each metric, all arms): `ambiguous_terms · rejected_domain_traps · unseen_terms ·
unseen_domains · must_include_constraints · negative_controls`. All primary deltas reported with bootstrap
CIs, per seed and pooled.
- `terse_answer_rate` = fraction of answers below a pre-set word floor (guards the T1 completeness
  regression). `over_framing_mechanical_rate` = fraction that talk about frames/domains instead of
  answering naturally (guards mechanical SFT artifacts).

## 12. Success / failure decision labels (use exactly these)
`CG_TRAINING_T1V2_INTERNALIZATION_CONFIRMED · CG_TRAINING_T1V2_WRAPPER_STILL_BEST ·
CG_TRAINING_T1V2_NO_INCREMENTAL_VALUE · CG_TRAINING_T1V2_DEGRADES_FACTUALITY ·
CG_TRAINING_T1V2_DEGRADES_RECALL · CG_TRAINING_T1V2_OVERFITS_FRAMES · CG_TRAINING_T1V2_STACKING_HARMFUL ·
CG_TRAINING_T1V2_INSUFFICIENT_POWER · CG_TRAINING_T1V2_ENV_UNAVAILABLE`

## 13. Pass/fail gates
**Primary success is C-vs-A, NOT D.** `CG_TRAINING_T1V2_INTERNALIZATION_CONFIRMED` requires ALL:
1. C beats A on `primary_frame_correct` with **bootstrap CI lower bound > 0** (pooled across seeds);
2. C **improves or maintains** `rejected_domain_avoidance` vs A (≥ A);
3. C does **not** reduce `factuality_preserved` by more than **0.02** absolute vs A;
4. C does **not** reduce `must_include_recall` by more than **0.03** absolute vs A;
5. C improves `generalization_to_unseen_terms` **or** `generalization_to_unseen_domains` vs A;
6. C does **not** raise `terse_answer_rate` or `over_framing_mechanical_rate` beyond pre-set thresholds
   (`terse ≤ A + 0.05`; `mechanical ≤ A + 0.05`).

**Secondary interpretation:**
- B remains best **and** C reliably beats A without regressions → `INTERNALIZATION_CONFIRMED` (and note the
  wrapper remains the deployment path).
- B remains best **and** C does not reliably beat A → `WRAPPER_STILL_BEST` (if C ≈ A with no signal) or
  `NO_INCREMENTAL_VALUE`.
- C improves frame correctness but harms recall/factuality → `DEGRADES_RECALL` / `DEGRADES_FACTUALITY`.
- C beats A on seen terms but not unseen (CI through 0 on generalization) → `OVERFITS_FRAMES`.
- D regresses again → record `STACKING_HARMFUL` **diagnostically**, but **do not fail C** if C otherwise
  passes.
- CIs too wide to decide (e.g. n or seeds short of plan) → `INSUFFICIENT_POWER`. No GPU/deps →
  `ENV_UNAVAILABLE`.

## 14. Power / sample-size rationale
T1 had `n_test=20` — too small; every primary CI included 0. T1-v2 targets:
- **n_test ≥ 100 minimum, prefer 150–200**; training ≥ 300 (prefer 500+).
- **3 seeds** if feasible (different LoRA init + data shuffle); **bootstrap CIs for all primary deltas**.
- Rationale: to detect a ~+0.10 primary-frame delta (the T1 point estimate) at usable CI width, low-hundreds
  of test items are needed; 20 cannot separate +0.10 from 0. If the realized run falls short of these
  targets, the result is reported as `INSUFFICIENT_POWER`, not forced into a pass/fail.

## 15. Seed plan
Run **3 seeds** (or state why fewer). Report:
- a **seed-level table** (per-seed C-vs-A deltas + CIs),
- **mean across seeds**, **pooled CI**, and a **worst-seed check** (the conclusion must not hinge on a
  single lucky seed; if the worst seed flips the sign on the primary delta, downgrade toward
  `INSUFFICIENT_POWER` / `NO_INCREMENTAL_VALUE`).

## 16. Leakage controls (explicit)
- **No evaluation prompt may contain the target answer.**
- **Plain-prompt arms A and C receive NO primary/secondary/rejected frame text** (and no C/R/S/MATCH
  trace); only wrapper arms B and D receive frame text via the wrapper.
- The **same deterministic rubric** scores all four arms identically (no new judge, no model-as-judge).
- **No training example appears in the held-out test.** Term-grouped splits enforced and asserted.

## 17. Wrapper-stacking diagnostic (arm D)
D is measured purely to track whether LoRA+wrapper interference persists. Hypothesis: the LoRA, tuned on a
particular prompt distribution, degrades when handed the wrapper's longer framed prompt. D's result is
reported as a **diagnostic** (`STACKING_HARMFUL` if it regresses), and is **excluded from the C-pass gate**.
Mitigating stacking (e.g. training the LoRA *on* framed prompts) is **out of scope** for T1-v2 and would be
its own pre-registration.

## 18. Risks
- **Self-distillation ceiling:** C cannot exceed its teacher; T1-v2 tests internalization + generalization,
  not superiority over the wrapper.
- **Data scale-up dilutes quality:** more examples sourced from the wrapper may include weaker targets;
  keep the audit-pass filter and report target-quality stats.
- **Terseness/mechanical artifacts:** SFT on framed answers can shorten/robotize outputs — guarded by
  clauses 6 + the `terse`/`mechanical` metrics.
- **Domain registry bound:** MATCH traces only exist for the 23 registry domains; generalization-to-unseen-
  *domains* is limited by available in-registry domains (state the realized coverage).
- **Underpower risk persists** if data/seed targets aren't met → `INSUFFICIENT_POWER`.

## 19. Interpretation rules
- **If the wrapper remains best, that is NOT a product failure** — the validated inference wrapper stays the
  deployment path.
- **If internalization is confirmed,** it means training can compress *some* wrapper behavior into weights
  (a research result, not a runtime change — wiring requires a separate pre-registration).
- **If LoRA fails,** the inference wrapper remains the validated deployment path.
- **If LoRA+wrapper stacking harms again,** do not combine them without a separate wrapper-stacking
  pre-registration.

## 20. Future work (only AFTER T1-v2)
- If T1-v2 **confirms** internalization → consider **T2: C×R×S-DPO** (separate pre-registration).
- If T1-v2 **fails** → stop the training track or redesign the dataset (separate pre-registration).
- If **D remains harmful** → open a separate wrapper-stacking mitigation study only if needed.
- **Guna/Vritti/Kosha** diagnostic heads remain future tracks, only after C×R×S training is stable.
- **Bhava** remains interpretive/emergent — **not** a direct training target.

## 21. Current valid claim
*Conscious Generation training remains experimental. T1 showed an underpowered C×R×S-LoRA internalization
hint, but the inference wrapper remains the validated deployment path. T1-v2 is pre-registered to test the
internalization signal with adequate data, held-out splits, and multiple seeds before considering DPO or
Guna/Vritti/Kosha heads.*
