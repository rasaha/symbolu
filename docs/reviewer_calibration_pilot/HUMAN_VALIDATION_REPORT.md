# Human-Validation Report (Phase 17)

*`reviewer_calibration_pilot/eval_results/outcome_review.json`. The honest result of the outcome-bearing
review: **NOT ENOUGH HUMAN EVIDENCE** — no real reviewers were available, so no human validation was
produced. Every human-dependent metric is **NOT EVALUATED**.*

## Result

| | |
|---|---|
| **Human validation** | **NOT EVALUATED** |
| Real reviewers | **0** (minimum required: 2) |
| Reviewer roles | — |
| Training completed | No |
| Final review artifacts | 100 (frozen, unreviewed) |
| Completed reviews | 0 |
| Excluded reviews | 0 |

## Agreement and safety metrics

| Metric | Value |
|---|---|
| Acceptable-obligation agreement | NOT EVALUATED |
| Exact obligation agreement | NOT EVALUATED |
| Risk agreement | NOT EVALUATED |
| Source-authority agreement | NOT EVALUATED |
| Clean-allow agreement | NOT EVALUATED |
| Evidence-satisfaction agreement | NOT EVALUATED |
| Unsafe-allow disagreement | NOT EVALUATED |
| High-risk unsafe-allow disagreement | NOT EVALUATED |
| Qualification agreement | NOT EVALUATED |
| Native ActionGate agreement | NOT EVALUATED |
| Blinded / post-reveal agreement | NOT EVALUATED |
| Override rate / direction | NOT EVALUATED |
| Adjudication / unresolved rate | NOT EVALUATED |
| Median / p90 review time | NOT EVALUATED |
| Reviewer confidence | NOT EVALUATED |
| Explanation usefulness | NOT EVALUATED |
| Trace comprehensibility | NOT EVALUATED |
| Workload (artifacts/reviewer hour) | NOT EVALUATED |

## What *was* established (infrastructure, not validation)

- A complete, audited, replayable **blinded-review apparatus** exists and works end-to-end (dry run:
  20 non-final artifacts, all plumbing OK, non-enforcing).
- The **frozen minimal policy runs read-only** through it, preserving the native ActionGate vocabulary
  (6 outcomes) and producing deterministic, replayable traces.
- The **final review set (100 artifacts, blind)**, **training/qualification set (20)**, **ground-truth
  protocol**, **metrics**, **disagreement taxonomy**, **stop conditions**, and **evaluation freeze** are
  all in place and ready for real reviewers.

## What was NOT established

Any statement about **human agreement, human-validated safety or utility, review burden, explanation
quality, or external-pilot readiness.** None of these can be produced without real reviewers, and none is
inferred from the mock reviewer (whose records `metrics.compute` excludes and reports as
`NOT_ENOUGH_HUMAN_EVIDENCE`).

## Scope of the claim

This report claims **no** human validation — not even a narrow one. The infrastructure is validated; the
policy's human acceptability is **not**. The result is `NOT ENOUGH HUMAN EVIDENCE`, and it must not be
read as any degree of human endorsement of the policy.
