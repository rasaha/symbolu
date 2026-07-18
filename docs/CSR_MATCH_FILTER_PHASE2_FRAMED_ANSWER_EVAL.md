# C×R×S MATCH-Filter — Phase 2: Framed-Answer Evaluation vs Base LLM

> Builds on the **frozen Phase 1** scorer (`csr-match-filter-phase1-pass` / `5cb4f76`). Phase 1 logic
> is treated as immutable; Phase 2 only imports it read-only. **No** Bhava/Guna/Vritti/JEPA, no
> hidden-state control, no logit intervention, no threshold changes.

## Guiding principle

```
Softmax chooses likely next tokens.
C×R×S chooses/audits the semantic frame before and after generation.
```

C×R×S does **not** replace softmax, does **not** control hidden states, and phonemes do **not**
directly determine meaning. The LLM still generates the language; C×R×S **constrains and audits the
semantic answer-frame** around it.

## 1. Why Phase 2 exists

Phase 1 proved the *frame selection* is correct as a scoring layer (primary/secondary/rejected with
vetoes). It did **not** test whether putting that frame in front of a real generator changes the
*answer*. Phase 2 asks the behavioral question.

## 2. What Phase 1 proved (frozen)

Production `real_embed_fn` metrics: primary_frame_accuracy 0.814, expected_primary_misrejected 0.050,
C-veto 1.000, S-veto 0.947, phoneme-overreach prevention 1.000, rejected_recall 0.991, unknown-term
generalization 0.784, context_disambiguation 0.615. Thresholds `primary_match=0.20, secondary_match=0.05`.

## 3. What Phase 2 tests

> **Does C×R×S-framed answering outperform base LLM answering?**

Three arms, **same model**, different prompts:

- **A — Base:** the LLM answers the bare question.
- **B — Framed:** the LLM answers inside the frozen C×R×S frame (primary/secondary/rejected + rules).
- **C — Framed + post-check/rewrite:** B, then an automatic post-check; if the answer violates the
  frame, one rewrite pass.

## 4. Why this is not overbuilding softmax

The frame is a **prompt-level + audit-level** constraint, not a decoding modifier. We never touch
logits, hidden states, or the sampler. C×R×S is a *pre-generation frame selector* and a
*post-generation auditor*; the model's token distribution is its own. So this is orthogonal to
softmax, not a reimplementation of it.

## 5. Base vs Framed vs Framed+Post-check

| arm | input | what it controls |
|---|---|---|
| base | `Answer the question. {query}` | nothing (control) |
| framed | base + C×R×S primary/secondary/rejected + 5 rules | pre-generation semantic frame |
| framed+postcheck | framed → audit → (rewrite if it drifts) | pre- **and** post-generation audit |

## 6. Metrics (per arm; deterministic rubric — `judge_backend = deterministic_rubric`)

`primary_frame_correct`, `secondary_handling_correct`, `rejected_domain_avoidance`,
`phoneme_overreach_rate`, `factuality_preserved`, `must_include_recall`, `must_not_violation_rate`,
`answer_clarity_proxy`, `postcheck_rewrite_rate`, `trace_completeness`. Plus **deltas**:
`framed−base`, `framed_postcheck−base`, `framed_postcheck−framed`.

These are **rubric proxies, not human evaluation** (keyword/rule checks over the registry's domain
keywords + overreach patterns). An LLM-as-judge interface is left as an optional future hook.

## 7. Pass/fail criteria

**Phase 2 PASS** = framed improves over base on rejected-domain avoidance, phoneme-overreach, and
primary-frame correctness, **without** hurting factuality or clarity. Suggested thresholds:

```
rejected_domain_avoidance : framed ≥ base + 0.10  OR ≥ 0.90 absolute
phoneme_overreach_rate    : framed ≤ base  AND ≤ 0.05
primary_frame_correct     : framed ≥ base + 0.10  OR ≥ 0.75 absolute
factuality_preserved      : framed ≥ base − 0.05  (no real regression)
trace_completeness        : ≥ 0.95
```

**Result labels:**
- `PHASE2_STUB_SMOKE_ONLY` — stub LLM used (harness validation only, not behavioral evidence).
- `PHASE2_FRAMED_ANSWER_PASS` — real LLM, criteria met.
- `PHASE2_NO_BEHAVIORAL_LIFT` — real LLM, no improvement over base.
- `PHASE2_FACTUALITY_REGRESSION` — real LLM, framed hurts factuality.

## 8. Known limitations

- **Rubric is a proxy.** Keyword/rule scoring approximates a human judge; it can miss nuance and be
  gamed by keyword stuffing. LLM-as-judge is a later upgrade.
- **Stub mode is a simulation.** The stub is one deterministic "model" driven by prompt content; any
  stub-mode lift validates the *plumbing and scoring*, not real behavior.
- **Factuality is weakly measured** (must-not patterns + on-topic + term presence), not fact-checked.
- **Frame quality is inherited from Phase 1** (context cases that were rank-1-but-secondary may still
  under-frame).
- No external API/credentials required; a real backend is optional and explicitly labeled.

## 9. Module map

```
scripts/cg_wrapper_ablation/csr_match_filter/
  llm_adapter.py   — LLMAdapter, StubLLMAdapter, FixtureLLMAdapter, RealLLMAdapter, load_llm_adapter
  prompts.py       — build_base_prompt, build_framed_prompt, build_rewrite_prompt, postcheck_answer
  rubric.py        — deterministic scorers + score_answer
  eval_framed_answers.py — 3-arm runner, metrics, deltas, traces, labels
  eval_data/framed_answer_eval.jsonl
```
