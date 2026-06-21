# C×R×S MATCH-Filter — Phase 2 Framed-Answer Eval — RESULTS

> Harness: `eval_framed_answers.py` over `eval_data/framed_answer_eval.jsonl` (44 cases). Frame =
> frozen Phase 1 scorer (thresholds 0.20/0.05, unchanged). Judge = deterministic rubric proxy.

## 🧊 PHASE 2 CLOSEOUT (FROZEN) — read this first

1. **Phase 1 = PASS / FROZEN** at commit `5cb4f76` (tag `csr-match-filter-phase1-pass`): the C×R×S
   frame selector (primary/secondary/rejected with vetoes) is validated and immutable.
2. **Phase 2 = PASS / CAVEATED** at commit `c22a323`: C×R×S-framed answering beats base on a real
   generator, with the caveats below. This closeout commit freezes it.
3. **Exact Mistral-7B-Instruct-v0.3 metrics** (real frame `all-MiniLM-L6-v2`, n=44):
   primary_frame_correct base **0.682** → framed **0.909** (+0.227); rejected_domain_avoidance
   **0.773 → 0.909** (+0.136); factuality_preserved **0.909 → 0.955** (+0.045); phoneme_overreach
   **0.000 → 0.000**; must_include_recall **0.568 → 0.659**; must_not_violation **0.030 → 0.019**;
   clarity **0.932 → 0.955**; trace_completeness **1.000**. All four pass-gates clear.
4. **The deterministic rubric was corrected TWICE after model outputs were seen** (overreach =
   assertion not mention; refutation ≠ rejected-leak). Fixes are principled, tested, and applied
   symmetrically to base + framed (base scores rose too) — but the rubric was **not pre-registered**,
   so this is a strong signal, not a publication-grade claim.
5. **Post-check rewrite did NOT improve over framed-only** (framed 0.909 ≥ framed+postcheck 0.886;
   rewrite rate 0.432). On a strong instruct model the frame prompt suffices; the rewrite over-corrects.
6. **Residual failures (5/44) are polysemy / secondary-role edges**, not framing-mechanism failures:
   `ctx_apple_tech`, `ctx_virus_bio`, `ctx_virus_sec` (Phase-1 polysemy frame gaps) +
   `adv_surgeon_authority`, `sec_judge_authority` (authority secondary-role).
7. **Next validation = Phase 2B** (separate effort, NOT in this closeout): pre-registered rubric;
   LLM-as-judge; multiple models; larger human-reviewed dataset.

**Phase 2 work is stopped here.**

---

## ✅ VERDICT: `PHASE2_FRAMED_ANSWER_PASS`

Generator: **Mistral-7B-Instruct-v0.3** (`local_hf`, production_valid). Frame backend:
`sentence-transformers all-MiniLM-L6-v2`. Same model across all arms; only the prompt differs.

| metric | base | framed | framed+postcheck | Δ framed−base |
|---|---:|---:|---:|---:|
| primary_frame_correct | 0.682 | **0.909** | 0.886 | **+0.227** |
| rejected_domain_avoidance | 0.773 | **0.909** | 0.886 | **+0.136** |
| phoneme_overreach_rate | 0.000 | 0.000 | 0.000 | 0 |
| factuality_preserved | 0.909 | **0.955** | 0.955 | +0.045 |
| must_include_recall | 0.568 | 0.659 | 0.682 | +0.091 |
| must_not_violation_rate | 0.030 | 0.019 | 0.019 | −0.011 |
| answer_clarity_proxy | 0.932 | 0.955 | 0.977 | +0.023 |
| trace_completeness | — | — | 1.000 | — |

Pass gates (framed arm): rejected-avoidance 0.909 ≥ 0.90 ✓; primary 0.909 ≥ 0.75 & ≥ base+0.10 ✓;
overreach 0.0 ≤ 0.05 ✓; factuality 0.955 ≥ base−0.05 ✓.

**C×R×S framing makes Mistral's answers measurably more on-frame** (primary +0.227, rejected-domain
avoidance +0.136) **without hurting factuality or clarity** (both improved). Post-check rewrite
(rate 0.432) did **not** add over plain framed here (−0.023 primary/rejected) — on a strong instruct
model the frame prompt suffices and the rewrite occasionally over-corrects.

## Methodology caveats (read before quoting the PASS)

- **Rubric is a deterministic proxy, not human eval.** Keyword/rule scoring over registry domain
  keywords + negation handling. It can miss nuance.
- **The rubric was corrected twice after observing real-model outputs**, which flipped the label from
  `NO_BEHAVIORAL_LIFT` to PASS. Both fixes are principled, tested, and applied **symmetrically to base
  and framed** (base scores rose too), so they remove measurement bias rather than favour framing —
  but ideally a rubric is pre-registered before seeing outputs. The fixes:
  1. **Overreach = assertion, not mention.** The framed prompt says "do not claim phonemes prove
     meaning"; models echo it, and the naive detector flagged the *negation* as overreach.
  2. **Refutation ≠ leak.** Adversarial queries ("is a doctor a fruit?") force a correct answer to
     name the rejected domain to deny it ("a doctor is **not** a fruit"); the mention-based detector
     counted that as a rejected-domain leak / must-not violation. Now negation-aware (`asserted_domains`).
- **Single model, single frame backend, 44 templated cases.** Not a broad benchmark.
- **Frame quality is inherited from Phase 1** — the residual misses are Phase-1 limitations, not the
  framing mechanism.

## Remaining framed-arm failures (5/44) — genuine
- **Frame-quality polysemy (3):** `ctx_apple_tech` (rejected fruit), `ctx_virus_bio` (rejected
  security), `ctx_virus_sec` (rejected biology) — real S did not fully separate these senses, so the
  frame left an empty/weak primary and Mistral drifted. Inherited Phase-1 context residual (0.615).
- **Authority secondary-role (2):** `adv_surgeon_authority`, `sec_judge_authority` — Mistral discussed
  authority as a real secondary role; the must-not on authority is arguably too strict for these.

## What would strengthen the result (before product use)
- **Pre-register the rubric**, then run; or add an **LLM-as-judge** for factuality/nuance (interface
  is ready, `judge_backend=deterministic_rubric` today).
- **Bigger, human-reviewed dataset** with real queries, multiple models, multiple frame backends.
- **Cost/latency:** the framed (+post-check) path adds LLM calls; post-check gave no lift here, so it
  may be optional for strong instruct models.
- Improve Phase-1 frame on the polysemy residuals (the 3 frame-quality misses).

## Reproduce
```
# generate with Mistral (writes traces)
export CSR_LLM_MODEL=mistralai/Mistral-7B-Instruct-v0.3
python scripts/cg_wrapper_ablation/csr_match_filter/eval_framed_answers.py \
  --llm-backend mistral --semantic-backend real --write-traces \
  --out runs/csr_phase2/framed_answer_eval_mistral.json
# re-score saved answers with the current rubric (no model reload)
python scripts/cg_wrapper_ablation/csr_match_filter/eval_framed_answers.py \
  --rescore runs/csr_phase2/framed_answer_eval_mistral.json --explain-failures
```
