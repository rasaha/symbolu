# C×R×S MATCH-Filter — Phase 2B-v2 Robustness Validation — RESULTS

> Pre-registered locked rubric `framed_answer_rubric_v2` (authored/committed at `93e0286` BEFORE the
> rerun) over the corrected held-out dataset (110 cases), frozen Phase 1 frame + Phase 2 framed prompt,
> Mistral-7B-Instruct-v0.3, real frame (`all-MiniLM-L6-v2`), deterministic judge. rubric_v1, the frozen
> scorer, and the framed prompt are UNCHANGED.

## 🧊 PHASE 2B-v2 CLOSEOUT (FROZEN)

- ✅ **Deterministic gates all pass** (primary, rejected-avoidance, overreach, factuality, trace) —
  robustly, lift distributed across 10/10 categories with no single-category domination.
- ✅ **Primary-frame lift survives** — +0.154 (base 0.609 → framed 0.764) on the held-out set under a
  rubric locked before the run.
- ✅ **Factuality regression disappears** — framed = base = 0.945 (Δ 0.000); the Phase 2B-v1 −0.073 was
  a rubric_v1 artifact (factuality↔must_not coupling), removed by decoupling factuality to `false_claims`.
- ⚖️ **Final label remains `PHASE2B_V2_NEEDS_HUMAN_REVIEW`** — *because the judge is deterministic*. The
  harness will not certify a full `ROBUSTNESS_PASS` on a deterministic proxy.

**Next recommended work: Phase 2C — independent (LLM/human) judge validation. NOT architecture changes.**
rubric_v2 is locked and will not be modified; no rescoring with changed scoring. **Phase 2B-v2 stops here.**

---

## Verdict: `PHASE2B_V2_NEEDS_HUMAN_REVIEW` — the Phase 2 lift SURVIVED; full pass needs an independent judge

Under the decoupled rubric_v2, **every deterministic gate passes robustly and the v1 factuality
regression is gone.** The label is `NEEDS_HUMAN_REVIEW` (not `ROBUSTNESS_PASS`) only because the
harness will not certify a full robustness pass on a *deterministic* judge.

### Mistral metrics (n=110, base → framed)

| metric | base | framed | Δ | gate |
|---|---:|---:|---:|---|
| primary_frame_correct | 0.609 | **0.764** | **+0.154** | PASS |
| rejected_domain_avoidance | 0.855 | **0.918** | +0.064 | PASS (≥0.90 abs) |
| factuality_preserved | 0.945 | **0.945** | **+0.000** | PASS (no regression) |
| phoneme_overreach_rate | 0.000 | 0.000 | 0 | PASS |
| must_include_recall | 0.382 | 0.464 | +0.082 | — |
| clarity_proxy | 0.936 | 0.982 | +0.045 | PASS |
| alternate_true_sense_mention | 0.118 | 0.109 | — | (informational) |
| rejected_domain_promotion | 0.127 | 0.082 | −0.045 | framing reduces promotion |
| trace_completeness | — | 1.000 | — | PASS |

`lift_distribution`: overall +0.155, dominated_by_single_category = None, 10/10 categories framed ≥ base
→ `robust=True`, `polysemy_ok=True`.

## Answers to the Phase 2B questions
- **Does the primary-frame lift survive?** **Yes** — +0.154, distributed across all 10 categories, no
  single-category domination, on a larger held-out set under a pre-registered rubric.
- **Does rejected-domain avoidance survive under the corrected definition?** **Yes** — 0.918 framed
  (≥ 0.90), up +0.064; alternate true-sense mentions no longer mislabeled as leaks.
- **Does the factuality regression disappear?** **Yes** — framed = base = 0.945 (Δ 0.000). The v1
  −0.073 was a rubric artifact (factuality↔must_not coupling), now decoupled (factuality = false_claims
  only).
- **Any real factuality regressions remain?** Marginal: 6/110 per-example cases (`ord_005/020`,
  `ctxsec_*`, `close_*`), balanced by similar base failures, so the aggregate is flat.

## Factuality separated from frame adherence (the v2 fix, working)
factuality_preserved is now computed from `false_claims` only and is independent of must_not /
rejected mentions. Polysemy answers that correctly note an alternate true sense ("python is also a
snake in biology") are no longer penalized.

## Honest residuals (genuine, ~8% each)
- `rejected_leaks` 9/110 — Mistral sometimes frames around a rejected domain.
- `secondary_promoted` 9/110 (mostly polysemy) — leads with the alternate sense instead of the context
  primary; a frame/model issue on ambiguous terms.
- `factuality_regressions` 6/110 — a few genuine per-example issues (non-polysemy).

## Decision: lift validated; certification pending an independent judge
- **Do NOT** modify the locked rubric_v2 / frozen prompt / scorer based on these numbers.
- **Run the LLM-as-judge** to corroborate the deterministic pass:
  `--judge-backend llm --judge-llm-backend mistral`. If it agrees → `PHASE2B_V2_ROBUSTNESS_PASS`.
- **Spot-check** the ~9 leaks/promotions and 6 factuality cases with human review.
- **Then** Phase 3 *design* may proceed; **product use still requires human review** — a deterministic
  (and even single-LLM) judge is necessary but not sufficient.

## Status of the effort
| phase | result | commit |
|---|---|---|
| Phase 1 — frame selection | PASS / frozen | `5cb4f76` |
| Phase 2 — framed vs base | PASS / caveated | `c22a323` / `d41a5ac` |
| Phase 2B-v1 — robustness | primary lift robust; factuality inconclusive (rubric_v1 flaw) | `e28f7c9` |
| **Phase 2B-v2 — robustness (pre-registered)** | **lift survived; no factuality regression; gates pass; needs independent judge** | this doc |

## Reproduce
```
python scripts/cg_wrapper_ablation/csr_match_filter/eval_framed_answers_robustness.py \
  --data scripts/cg_wrapper_ablation/csr_match_filter/eval_data/framed_answer_eval_v2_rubricv2.jsonl \
  --rubric scripts/cg_wrapper_ablation/csr_match_filter/eval_data/framed_answer_rubric_v2.yaml \
  --answer-backends mistral --judge-backend deterministic --semantic-backend real \
  --arms base,framed --explain-failures --write-traces --out runs/csr_phase2b/robustness_eval_v2.json
```
