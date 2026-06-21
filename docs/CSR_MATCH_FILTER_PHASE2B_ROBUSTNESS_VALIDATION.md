# C×R×S MATCH-Filter — Phase 2B: Robustness Validation

> **Principle:** *Phase 2B does not improve the wrapper. Phase 2B validates whether the Phase 2 lift
> is real.* It re-runs the frozen Phase 1 frame + frozen Phase 2 framed prompt against a **larger,
> held-out dataset** scored by a **pre-registered rubric** and a **pluggable judge**, across
> **multiple answer models**.

## 1. What Phase 1 proved
The C×R×S MATCH-filter **frame selector** (word→domain primary/secondary/rejected with the S-gated C
veto and group-aware R) is correct, vetoed, and generalizes — PASS / frozen at `5cb4f76`
(tag `csr-match-filter-phase1-pass`). Thresholds `primary_match=0.20, secondary_match=0.05`.

## 2. What Phase 2 proved
Putting that frame in front of a real generator (Mistral-7B-Instruct-v0.3) made answers more on-frame
— primary +0.227, rejected-domain avoidance +0.136, factuality preserved/improved, overreach 0 —
`PHASE2_FRAMED_ANSWER_PASS` at `c22a323`.

## 3. Why Phase 2 remains caveated
The deterministic rubric was **corrected twice after seeing model outputs** (overreach = assertion not
mention; refutation ≠ rejected-leak). The fixes are principled, symmetric (base improved too), and
tested — but the rubric was **not pre-registered**, and the eval was a single model on 44 templated
cases. That is a strong signal, not a robust claim.

## 4. What Phase 2B validates
Does the framed-answer advantage survive when:
- the rubric is **pre-registered and locked** (written before the v2 run),
- the judge can be **deterministic or an independent LLM judge**,
- the dataset is **≥100 held-out cases** with broader coverage,
- **multiple answer models** are used (stub + Mistral + future).

## 5. What is FROZEN (must not change)
- Phase 1 scorer: grouped-R logic, S-gated C/R penalty, thresholds (0.20/0.05).
- Phase 2 framed prompt (`prompts.build_framed_prompt`).
- The Phase 1/2 result commits and tags.

## 6. What is ALLOWED to vary
- Answer model (stub / Mistral / others) and judge backend (deterministic / LLM).
- The **dataset** (new v2, held-out).
- The **registry** may gain *additive* lanes (education, religion, construction) — new ontology data
  only; no change to existing templates, thresholds, or logic, and Phase 1 metrics are over a disjoint
  dataset so they are unaffected.
- Any new prompt/rubric is **versioned separately** (`framed_answer_rubric_v1`).

## 7. Rubric pre-registration
`eval_data/framed_answer_rubric_v1.yaml` is written **before** the v2 eval and the runner records
`rubric_version=framed_answer_rubric_v1`, `rubric_locked=true`. It encodes the two Phase 2 corrections
as explicit pre-registered rules, plus secondary-promotion and factuality-independence rules (§ rubric
doc). The deterministic scorer in `rubric.py` implements exactly these rules.

## 8. Judge strategy
`judge_adapter.py` exposes a `Judge` interface returning structured JSON
(`primary_frame_correct`, `secondary_handling_correct`, `rejected_domain_avoidance`,
`phoneme_overreach`, `factuality_preserved`, `clarity_score`, `reasons`).
- `DeterministicRubricJudge` — applies the locked rubric deterministically →
  `judge_backend=deterministic_rubric`, `production_valid=partial`.
- `StubJudge` — fixed outputs for tests.
- `LLMJudgeAdapter` — optional independent LLM judge (env-configured; no keys required for tests) →
  `judge_backend=real_llm_judge`, `production_valid=stronger`.

## 9. Multi-model strategy
`eval_framed_answers_robustness.py` runs `--answer-backends stub,mistral,...`, builds the frozen frame
once per example, generates base/framed (optionally framed_postcheck) per model, and scores every
answer with the chosen judge. Per-model and pooled metrics + deltas + **stratified** breakdowns are
reported. Post-check is secondary (Phase 2 showed framed-only ≥ framed+rewrite).

## 10. Pass/fail criteria
On the best available real answer backend:
- `primary_frame_correct`: framed ≥ base + 0.10 **or** ≥ 0.80
- `rejected_domain_avoidance`: framed ≥ base + 0.10 **or** ≥ 0.90
- `phoneme_overreach_rate`: framed ≤ base **and** ≤ 0.05
- `factuality_preserved`: framed ≥ base − 0.05
- `trace_completeness` ≥ 0.95
- **Robustness:** no single category accounts for all the lift; framed does not regress badly on
  polysemy/context cases; results labeled clearly if only the deterministic judge is used.

Labels: `PHASE2B_ROBUSTNESS_PASS`, `PHASE2B_WEAK_PASS_DETERMINISTIC_ONLY`, `PHASE2B_NO_ROBUST_LIFT`,
`PHASE2B_FACTUALITY_REGRESSION`, `PHASE2B_NEEDS_HUMAN_REVIEW`.

## 11. Known limitations
- The deterministic judge is still a proxy; only a real LLM judge (or human review) makes the claim
  production-grade. Deterministic-only runs are labeled `WEAK_PASS_DETERMINISTIC_ONLY` at best.
- Dataset is synthetic (templated queries, rule-labeled), not human-curated.
- Frame quality is inherited from Phase 1; polysemy residuals persist.
- Additive registry lanes are seed templates, not calibrated.
