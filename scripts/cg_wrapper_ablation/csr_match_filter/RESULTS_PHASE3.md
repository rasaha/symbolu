# C×R×S MATCH-Filter — Phase 3: Answer Audit / Post-Check Layer — RESULTS

> **Phase 3 adds NO new ontology layers. It audits answer-frame compliance using the frozen C×R×S
> frame.** The Phase 1 scorer (thresholds 0.20/0.05, grouped-R, S-gated C/R) and the Phase 2 framed
> prompt are imported read-only and UNCHANGED. The auditor is deterministic and needs no LLM. No
> Bhava/Guna/vrittis/JEPA, no hidden states, no logits, no governance.

## The question

> **Can C×R×S detect when an answer violates its selected semantic frame?**

Answer: **Yes** — on a pre-registered 72-row fixture set the deterministic auditor classifies every
frame-compliance finding with finding-type **F1 = 1.000**, recommends rewrites with **precision = 1.000,
recall = 1.000**, a **false_rewrite_rate = 0.000**, and **missed_critical_failure_rate = 0.000**
(0 of 14 critical failures missed). Decision label: **`PHASE3_ANSWER_AUDIT_PASS`**.

## What the layer does (detect → classify → flag → explain → *optionally* rewrite)

`answer_audit.audit_answer(query, answer, csr_trace, …)` emits structured `AnswerAuditFinding`s
(finding_type, severity, domain, evidence, explanation) and an `AnswerAuditResult`
(`passed`, `needs_rewrite`, `confidence`, `summary`, `status`). It re-uses the same negation-aware
rubric detectors validated in Phase 2/2B, plus a Phase-3 **term-aware** refinement: a bare polysemous
*subject* term (e.g. "virus", "apple", "fire" — which are literally registry keywords of one sense)
does **not** by itself commit to that sense; corroborating domain vocabulary is required. Rewriting is
**off by default** and only ever *recommended* on a narrow set of high-confidence failures.

## Finding taxonomy (severity → confidence)

| finding_type | severity | passes? | rewrite? |
|---|---|---|---|
| `frame_compliant` | info (0.2) | ✅ | no |
| `alternate_true_sense_allowed` | info | ✅ | no |
| `rejected_domain_mentioned_as_refutation` | info | ✅ | no |
| `answer_too_generic` | warning (0.5) | ✅ | no |
| `primary_frame_missing` | error (0.8) | ❌ | **yes** (conf ≥ 0.75) |
| `secondary_promoted_to_primary` | error | ❌ | **yes** (conf ≥ 0.75) |
| `rejected_domain_promoted` (primary present) | error | ❌ | no (leak, not promotion) |
| `rejected_domain_promoted` (primary absent) | **critical** (0.9) | ❌ | **yes** |
| `phoneme_overreach_claim` | **critical** | ❌ | **yes** |
| `factuality_suspected` | error | ❌ | no (out of scope for a *frame* rewrite) |

`passed` = no finding ≥ error. `should_rewrite` is True ONLY for: critical `rejected_domain_promoted`,
critical `phoneme_overreach_claim`, `primary_frame_missing` (conf ≥ 0.75), or
`secondary_promoted_to_primary` (conf ≥ 0.75). The bias is deliberately toward **not** rewriting.

## Results (n = 72, deterministic audit, no LLM)

| metric | value | gate |
|---|---:|---|
| finding-type precision / recall / **F1** | 1.000 / 1.000 / **1.000** | PASS |
| rewrite-recommendation precision / recall | 1.000 / 1.000 | PASS |
| **false_rewrite_rate** | **0.000** | PASS (budget 0.10) |
| **missed_critical_failure_rate** | **0.000** (0/14) | PASS (must be 0) |
| allowed_alternate_sense_accuracy | 1.000 | PASS |
| refutation_not_leak_accuracy | 1.000 | PASS |
| phoneme_overreach_detection | 1.000 | PASS |
| trace_completeness | 1.000 | PASS |
| exact_match (findings + passed + needs_rewrite) | 1.000 | — |

Per-finding-type support: frame_compliant 28, primary_frame_missing 28, rejected_domain_promoted 14,
secondary_promoted_to_primary 8, phoneme_overreach_claim 6, alternate_true_sense_allowed 6,
rejected_domain_mentioned_as_refutation 6, answer_too_generic 4, factuality_suspected 4 — all P=R=1.0.

## Honest caveat (why this is a unit-eval, not a field result)

The 72 fixture answers are **synthetic and keyword-aligned**: gold `expected_findings` were authored
independently from the Phase-3 spec, and the answers were then *constructed* (via
`eval_data/make_answer_audit_eval.py`) to exhibit exactly those behaviours under the frozen detectors.
This validates the audit **logic** (classification, severity, the conservative rewrite gate, the
term-aware sense rule, refutation-vs-leak, alternate-sense-vs-promotion) deterministically and
reproducibly — but a perfect score on a constructed set is **not** evidence about messy real-LLM
prose. Auditing real answers is exercised (off by default) through the Phase 2 runner integration
(`--audit-answers`), where on stub answers the framed arm already shows a higher `audit_pass_rate` and
lower `critical_findings_rate` than base. A real-LLM audit eval is the recommended next step.

## Decision labels (`eval_answer_audit.decide_phase3`)

`PHASE3_AUDIT_MISSES_CRITICAL_FAILURES` (any missed critical) **dominates**; then
`PHASE3_AUDIT_NO_VALUE` (F1 ≤ 0.5 or never recommends a needed rewrite); then
`PHASE3_AUDIT_WEAK_REWRITE_TOO_AGGRESSIVE` (false_rewrite_rate > 0.10); then
`PHASE3_ANSWER_AUDIT_PASS` (F1 ≥ 0.95, rewrite P/R ≥ 0.9, false_rewrite ≤ 0.05, 0 missed critical);
else `PHASE3_AUDIT_NEEDS_HUMAN_REVIEW`. **This run: `PHASE3_ANSWER_AUDIT_PASS`.**

## Phase 2 runner integration (opt-in, off by default)

`eval_framed_answers.py` gains `--audit-answers` and `--rewrite-mode {off,suggest,auto}` (default
`off`). When on, it reports `audit_pass_rate`, `rewrite_recommended_rate`, `critical_findings_rate` per
arm WITHOUT changing the frozen frame or the Phase 2 scores. `suggest` attaches a rewrite prompt;
`auto` performs one rewrite. Default is never `auto`.

## Status of the effort

| phase | result | commit |
|---|---|---|
| Phase 1 — frame selection | PASS / frozen | `5cb4f76` |
| Phase 2 — framed vs base | PASS / caveated | `c22a323` / `d41a5ac` |
| Phase 2B-v1 — robustness | primary lift robust; factuality inconclusive (rubric_v1 flaw) | `e28f7c9` |
| Phase 2B-v2 — robustness (pre-registered) | lift survived; no factuality regression; gates pass; needs independent judge | (RESULTS_PHASE2B_V2) |
| **Phase 3 — answer audit / post-check** | **`PHASE3_ANSWER_AUDIT_PASS`** on a constructed fixture set; real-LLM audit eval is next | this doc |

## Reproduce

```
python scripts/cg_wrapper_ablation/csr_match_filter/eval_data/make_answer_audit_eval.py   # rebuild fixtures
python scripts/cg_wrapper_ablation/csr_match_filter/eval_answer_audit.py --explain \
  --out runs/csr_phase3/answer_audit_eval.json
python -m pytest tests/test_csr_answer_audit.py -q
# opt-in audit over the Phase 2 arms (off by default):
python scripts/cg_wrapper_ablation/csr_match_filter/eval_framed_answers.py \
  --llm-backend stub --semantic-backend hashing --audit-answers --rewrite-mode suggest
```
