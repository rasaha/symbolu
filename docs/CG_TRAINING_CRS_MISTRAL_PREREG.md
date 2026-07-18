# Conscious Generation Training — T1: C×R×S-only LoRA Fine-Tuning on Mistral — PRE-REGISTRATION

> **Status: DESIGN ONLY, locked before training.** First stage (T1) of a staged roadmap. **No Bhava
> training; no Guna/Vritti/Kosha losses; no deep architecture change; no agentic runtime; no consciousness
> claim; no post-hoc threshold tuning.** The 32-D CG symbolic head is **scaffolded but DISABLED** and out
> of scope until a separate pre-registration.

## 0. One line
**Can a Mistral LoRA/QLoRA model trained on C×R×S-labeled examples internalize the semantic-frame behavior
that the current inference wrapper enforces — and does that add value *beyond the already-validated
wrapper*?**

## 1. Motivation & prior results (honest framing)
- **Validated today (inference):** C×R×S works as an *inference-time* semantic-framing mechanism. Framed
  generation improved primary-frame correctness (0.609→0.736), rejected-domain avoidance (0.855→0.909),
  factuality preserved (0.945→0.964) on the real-Mistral Phase-2B eval.
- **Closed negative (agentic governance):** C×R×S as an *agent/tool-domain governance* signal showed real
  ranking signal but **failed** the pre-registered gate (over-gated benign traffic;
  `AGENTIC_CRS_INCREASES_FALSE_BLOCKS`, `docs/RESULTS_AGENTIC_CRS_SIGNAL.md`). **Boundary: this track does
  NOT reopen agentic governance and makes no autonomous-agent claim.**
- **New question (this doc):** the wrapper enforces framing *at inference* via prompt construction + a
  frozen C×R×S filter. Can that behavior be **internalized into the weights** so the model frames
  correctly with a lighter (or no) wrapper? That is a deployment-cost and generalization question, not a
  consciousness question.

## 2. Architecture language (correct, pinned)
```
Mistral hidden state h ∈ R^4096
  → CG auxiliary symbolic projector            [SCAFFOLDED, DISABLED in T1]
  → s ∈ R^32                                   (NOT an attention head; Mistral head_dim = 128)
  → optional Guna/Vritti/Kosha/CRS heads       [T3–T6, separate pre-registrations]
```
T1 touches **none** of the 32-D path. T1 is **LoRA/QLoRA adapters on the frozen Mistral backbone**, trained
to produce frame-correct *text* — no auxiliary heads, no symbolic-state loss.

## 3. Hypothesis
A C×R×S-labelled SFT (and later DPO) LoRA makes Mistral **stay in the primary semantic frame, avoid
rejected-domain leakage, and not over-promote secondary domains, while preserving factuality/clarity** —
and does so well enough to **approach or beat the inference wrapper on ≥1 metric without regressions**.

## 4. Non-goals (T1)
No Bhava classifier; no Guna/Vritti/Kosha losses; no 32-D symbolic-state training; no full-weight
fine-tuning; no architecture surgery; no agentic governance; no threshold tuning to rescue a result.

## 5. Conceptual decision on Bhava
**Bhava is NOT a direct training target.** It is treated as an *emergent interpretive state* arising from
C×R×S semantic-frame alignment, later modulated by Guna/Vritti/Kosha diagnostics. T1 trains C×R×S **frame
behavior directly**; it trains **no** Bhava head.

## 6. Dataset plan
**Source = self-distillation of the validated wrapper** (the principled T1 target): join the C×R×S eval
metadata (`framed_answer_eval_v2_rubricv2.jsonl`: term, query, expected_primary/secondary/rejected,
must_include) with the real-Mistral robustness traces (`robustness_eval_v2.json`: framed-arm answers +
rubric scores). **Keep only framed answers that PASSED** (primary_frame_correct ∧ rejected-domain-avoided ∧
factuality preserved) as `target_answer`. Attach the C/R/S/MATCH trace from the real engine.
- **Example fields:** `id, term, query, primary_domain, secondary_domains, rejected_domains,
  match_trace{C,R,S,MATCH}, prompt (frame-constrained), target_answer, failure_modes{...}`.
- **Required slices:** high-confidence primary · ambiguous terms · near-miss secondary · rejected-domain
  traps · unknown/generalization terms · domain-conflict · negative controls.
- **Splits (leakage-controlled):** group by **term**; hold out a disjoint set of **unseen terms** AND a
  disjoint set of **unseen domains** for the generalization slices. No term or its target answer appears in
  both train and test. The eval (test) split's `target_answer` is **never** shown in training.
- **Honesty note:** self-distillation means the ceiling is the wrapper. T1 asks whether the *weights* can
  carry the behavior (and generalize), not whether the model can exceed its teacher.

## 7. Training plan
- **Base:** `mistralai/Mistral-7B-Instruct-v0.3` (or `-v0.3` base), frozen. **LoRA/QLoRA** (4-bit), small
  run, no full-weight FT, no architecture change. Output: **`crs-lora` checkpoint**.
- **Prompt format (instruction):** explicit frame constraints, e.g.:
  ```
  You are answering within a primary semantic frame.
  Primary frame: medicine/healing
  Secondary frames: authority/status
  Rejected frames: finance, astrology, weapons
  Answer the user's question while staying in the primary frame. Do not promote rejected frames.
  ```
  Target answers are **natural**, not mechanical.
- **Stage 2 (T2, separate run after T1 SFT):** C×R×S preference/DPO (chosen = frame-correct, rejected =
  frame-violating). Pre-registered separately if T1 shows signal.
- **Disabled scaffolding:** a 32-D symbolic-projector stub may exist in code but its loss weight is **0**
  and it is **not instantiated** in T1 (asserted by tests).

## 8. Evaluation arms (MANDATORY — all four)
| arm | model | wrapper |
|---|---|---|
| **A** | base Mistral | none |
| **B** | base Mistral | **+ C×R×S inference wrapper** (the validated baseline) |
| **C** | **crs-lora** Mistral | none |
| **D** | crs-lora Mistral | + C×R×S wrapper |

The key question is **not** only "does C beat A" — it is **"does C×R×S fine-tuning add value beyond the
already-validated wrapper (B)?"** and "is D not worse than B?".

## 9. Metrics (same deterministic rubric/audit as the validated eval — no new judge)
`primary_frame_correct · rejected_domain_avoidance · secondary_overpromotion_rate ·
rejected_domain_leak_rate · factuality_preserved · clarity/usefulness · must_include_recall ·
answer_length/control · generalization_to_unseen_terms · generalization_to_unseen_domains`.
Plus: **per-domain breakdown**, **ambiguous-term slice**, **rejected-domain-trap slice**, **unseen-term
slice**, and **bootstrap CIs**. Reported for all four arms.

## 10. Success / failure labels
`CG_TRAINING_CRS_ADDS_VALUE · CG_TRAINING_CRS_NO_INCREMENTAL_VALUE · CG_TRAINING_WRAPPER_STILL_BEST ·
CG_TRAINING_DEGRADES_FACTUALITY · CG_TRAINING_OVERFITS_FRAMES · CG_TRAINING_INSUFFICIENT_DATA ·
CG_TRAINING_ENV_UNAVAILABLE`

## 11. Pass/fail gate (`CG_TRAINING_CRS_ADDS_VALUE` requires ALL)
1. **C beats A** on primary-frame correctness **and** rejected-domain avoidance (bootstrap CI on the delta);
2. C does **not** degrade factuality or clarity (≥ A within tolerance) — else `CG_TRAINING_DEGRADES_FACTUALITY`;
3. C **generalizes** to unseen terms/domains (improvement holds on the unseen slices, not just seen) — else
   `CG_TRAINING_OVERFITS_FRAMES`;
4. C **approaches or improves over B** on ≥1 meaningful metric **without regressions**;
5. **D is not worse than B.**
- If B remains clearly best and C/D don't clear (4)/(5) → **`CG_TRAINING_WRAPPER_STILL_BEST`** (not a
  product failure — it means inference wrapping is the better deployment path *today*).
- Too few labelled examples → `CG_TRAINING_INSUFFICIENT_DATA`. No GPU/deps → `CG_TRAINING_ENV_UNAVAILABLE`.

## 12. Risk controls
- **No post-hoc tuning** to rescue a result; a new attempt is a new pre-registration.
- **Self-distillation ceiling** disclosed (C cannot exceed the wrapper it learned from; the test is
  weight-internalization + generalization).
- **Leakage controls:** term-grouped splits, unseen-term/domain holdouts, eval targets never trained on.
- **Same rubric/audit** as the validated eval (no new, weaker judge; no model-as-judge).
- **Four-arm** comparison mandatory (base-vs-finetuned-only is explicitly disallowed).
- **Disabled symbolic head** asserted by tests (no Bhava/Guna/Vritti/Kosha loss active in T1).

## 13. Roadmap (only T1 pre-registered/implemented now)
```
T1  C×R×S SFT on Mistral (LoRA/QLoRA)            ← THIS doc
T2  C×R×S DPO/preference tuning
T3  Guna diagnostic auxiliary head
T4  Vritti diagnostic auxiliary head
T5  Kosha depth/readiness diagnostic head
T6  Combined CG symbolic-state training — ONLY if T1–T5 independently show signal
```
Each later stage is a **separate pre-registration**; none is started here.

## 14. Standing claim (until T1 passes)
*Conscious Generation training is a new experimental track. C×R×S is validated today as an inference-time
semantic-framing mechanism; whether that behavior can be internalized into Mistral through LoRA
fine-tuning remains unvalidated.*
