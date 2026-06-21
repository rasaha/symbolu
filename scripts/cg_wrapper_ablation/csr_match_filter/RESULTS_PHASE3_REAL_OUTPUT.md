# C×R×S MATCH-Filter — Phase 3 Real-Output Audit Validation — RESULTS

> Goal: run the FROZEN Phase 3 auditor over **saved real Mistral** Phase 2 / 2B answers and check
> whether it catches the rubric_v2 residual failures without hurting good framed answers. The Phase 1
> scorer, Phase 2 prompt, rubric_v2, generation behaviour, and the Phase 3 audit rules are all
> UNCHANGED (read-only).

## 🚧 Status: `PHASE3_REAL_OUTPUT_AUDIT_BLOCKED_NO_REAL_TRACES`

**No real Mistral answer text is available in this environment, and none can be produced here.**
- The real Phase 2B-v2 Mistral run wrote to `runs/csr_phase2b/robustness_eval_v2.json`, which is
  **gitignored** and absent from this freshly-cloned container.
- No real-LLM framed-answer traces were ever committed to git (only the aggregate RESULTS docs were).
- This container has **no `torch`/`transformers`** (LocalHF/Mistral cannot load) and **no
  `ANTHROPIC_/OPENAI_` keys** (RealLLMAdapter unavailable), so the answers cannot be regenerated.

The only saved traces present are **stub** (`production_valid=False`) answers, additionally scored with
**rubric_v1**, not rubric_v2 — unsuitable for a real-output verdict. The harness therefore refuses to
certify and returns `BLOCKED_NO_REAL_TRACES` (see "stub smoke" below for why its provisional numbers
are uninformative). **This is an environmental blocker, not an audit failure.**

To get a real verdict, run (where the real traces or a GPU/Mistral exist):
```
# 1) produce real traces (GPU env):
python .../eval_framed_answers_robustness.py \
  --data .../framed_answer_eval_v2_rubricv2.jsonl --rubric .../framed_answer_rubric_v2.yaml \
  --answer-backends mistral --judge-backend deterministic --semantic-backend real \
  --arms base,framed --write-traces --out runs/csr_phase2b/robustness_eval_v2.json
# 2) audit them vs the saved rubric_v2 labels:
python .../eval_real_output_audit.py --traces runs/csr_phase2b/robustness_eval_v2.json \
  --data .../framed_answer_eval_v2_rubricv2.jsonl --out runs/csr_phase3/real_output_audit.json
```

## The harness (`eval_real_output_audit.py`, committed and ready)

Format-agnostic over either runner's `--write-traces` JSON. Per arm it runs the frozen
`audit_answer` on each saved answer (frame = the row's `expected_primary/secondary_true_senses/
rejected`) and compares findings to the **saved rubric labels** (no rescoring), across the five
requested categories:

| # | category | audit finding | saved rubric label |
|---|---|---|---|
| 1 | rejected-domain leak | `rejected_domain_promoted` | `rejected_domain_avoidance == False` |
| 2 | secondary promoted to primary | `secondary_promoted_to_primary` | `secondary_promoted == True` |
| 3 | phoneme-overreach | `phoneme_overreach_claim` | `phoneme_overreach == True` |
| 4 | factuality-suspected | `factuality_suspected` | `factuality_preserved == False` |
| 5 | generic / off-frame | audit `passed == False` | `primary_frame_correct == False` |

Reports per arm: `audit_pass_rate`, `critical_findings_rate`, `rewrite_recommended_rate`; per category:
catch-recall, FN, FP with examples; and a "help-without-hurt" block (residual recall vs. rewrites
recommended on rubric-clean answers). A real `PASS` is gated on `production_valid` traces.

## Stub smoke (provenance-gated; numbers NOT meaningful)

`--traces runs/csr_phase2b/robustness_stub.json` → `BLOCKED_NO_REAL_TRACES`. The provisional framed
numbers (audit_pass_rate 0.891, rewrite_recommended_rate 0.109, false_rewrite_on_clean 0.000) and the
near-zero category recalls are artefacts of two mismatches, not the auditor:
1. **stub answers** are fixed templates ("Primarily, this concerns medicine — medicine (medical
   healing physician care)…"), not model prose;
2. the stub run was scored with **rubric_v1** (factuality coupled to `must_not`), so its saved
   `factuality_preserved` labels are not the rubric_v2 / audit `false_claims` definition — hence 72
   spurious "FN" on factuality. Apples-to-oranges by construction.

The one genuinely reassuring signal even here: **false_rewrite_on_clean = 0.000** — the auditor did not
recommend rewriting any rubric-clean framed answer.

## Analytical cross-check (DERIVED from the published rubric_v2 residuals, not an empirical run)

Because the auditor **re-uses the exact rubric_v2 detectors** (`asserted_domains`,
`mentioned_domains`, `has_phoneme_overreach`, `forbidden_rate`), its findings on the real answers are a
deterministic relabelling of the published Phase 2B-v2 rubric_v2 results (`RESULTS_PHASE2B_V2.md`,
framed arm, n=110):

| residual (rubric_v2, real Mistral) | count | audit finding | expected catch |
|---|---:|---|---|
| rejected_leaks (`rejected_domain_avoidance==0`) | 9/110 | `rejected_domain_promoted` (same `asserted_domains`) | **9/9** |
| secondary_promoted | 9/110 | `secondary_promoted_to_primary` (same promotion logic) | **9/9** |
| factuality_regressions (`false_claims` asserted) | 6/110 | `factuality_suspected` (same `forbidden_rate`) | **6/6** |
| phoneme_overreach | 0/110 | `phoneme_overreach_claim` | 0/0 (nothing to catch) |

So, **derived** answers to the five questions:
1. **rejected-domain leaks** — caught (shares the leak detector). ✅
2. **secondary promoted to primary** — caught (shares the promotion detector). ✅
3. **phoneme-overreach** — none occurred; detector validated on the constructed set at recall 1.0. ✅
4. **factuality-suspected** — caught (identical `false_claims` detector). ✅
5. **generic / off-frame** — caught; here the auditor is **stricter** than rubric_v2 because of its
   Phase-3 term-awareness (a bare polysemous subject term does not assert its sense), so on polysemy
   rows it may flag a few *extra* `primary_frame_missing`/promotion cases that rubric_v2 passed. ⚠️

**False positives (derived):** the only divergence is category 5 — term-awareness can flag extra
polysemy off-frame cases vs rubric_v2. `should_rewrite` gates most of these out (rewrite only on
critical leak/overreach or high-confidence pfm/promotion), so they surface as *warnings*, not rewrites.
**False negatives (derived):** none expected on categories 1–4 (shared detectors); the lone edge case
is a rejected-domain whose only leak keyword is literally the subject term (term-excluded) — not
observed in the published residual IDs.

**Would the audit have helped Phase 2B-v2 without hurting good framed answers?** **Derived: yes.** It
flags all 24 rubric_v2 residuals (9 leaks + 9 promotions + 6 factuality) using the same detectors, and
because clean framed answers assert the primary with real domain vocabulary (not the bare term), they
audit as `frame_compliant` — so `false_rewrite_on_clean ≈ 0` (consistent with the stub run's 0.000).
The conservative `should_rewrite` policy means only the critical/high-confidence subset is pushed to
rewrite.

## Decision

- **Empirical real-output label: `PHASE3_REAL_OUTPUT_AUDIT_BLOCKED_NO_REAL_TRACES`** — cannot be run
  here (no real answers, no generator).
- **Provisional-if-run-on-real-traces (derived, unverified): `PHASE3_REAL_OUTPUT_AUDIT_PASS`** — high
  residual recall via shared detectors, ~0 hurt to good framed answers; the only thing to watch is the
  term-awareness divergence on polysemy off-frame (could nudge toward `NEEDS_TUNING` if those extra
  flags are judged undesirable).

**Recommended next step:** execute the two commands above in the GPU/real-LLM environment (or supply
`runs/csr_phase2b/robustness_eval_v2.json` with saved answers) to convert the derived expectation into
an empirical verdict. No audit-rule, scorer, prompt, rubric_v2, or generation changes are needed.
