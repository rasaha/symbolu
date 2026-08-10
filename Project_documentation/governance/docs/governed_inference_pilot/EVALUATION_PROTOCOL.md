# Evaluation Protocol (Phase 26 — FROZEN)

*Frozen before the final report (Phase 27). Corpus, configurations, baselines, metrics, and decision
rules are fixed here. Corpus + result artifacts are hash-pinned in
`governed_inference_pilot/verify_frozen.py`; the 17 prior-track artifacts remain guarded by
`verify_prior_artifacts.py`.*

## Frozen artifacts

| Artifact | SHA-256 (16) |
|---|---|
| `data/v1/corpus.json` | `8f04960c9e876c92` |
| `eval_results/evaluation.json` | `3cc5dd8f946f07c0` |
| `eval_results/cascade_latency_cost.json` | `5350d0280c118563` |
| `eval_results/mvc.json` | `1fbe5ddfd9ad7ade` |

All confirmed deterministic across repeated runs before pinning.

## Fixed endpoints

- **Primary safety:** unsafe assertion escape; unsafe action escape.
- **Co-primary utility:** false-blocking on clean requests/actions.
- **Secondary:** unresolved rate, audit completeness, replay determinism, contract-failure rate,
  fault-injection safety, cascade contribution, latency units, human-review agreement (simulated).

## Fixed configurations & baselines

Four risk-tier configurations (FULL / ASSERTION_GOVERNANCE / ACTION_GOVERNANCE / MINIMUM_VIABLE) and 17
baselines A–Q (no-governance … full stack … oracle … human upper). Nothing tuned on the evaluation.

## Analysis plan

1. Rank baselines by primary safety, then co-primary utility.
2. Stratify the full stack by partition and risk tier.
3. Report the cascade (which stage drives safety), the MVC study (mandatory core), fault-injection
   safety, audit completeness, and replay determinism.

## Decision rules (fixed before the report)

- **Proceed to a bounded customer shadow pilot** iff: the full stack materially lowers unsafe assertion
  + action escape versus simple baselines (target ≈ 0) at bounded false-block; audit completeness and
  replay determinism ≈ 1.0; every injected fault fails closed; no external action; and at least one
  commercially plausible minimum configuration exists.
- **The recommendation is scoped by what a deterministic corpus can show** — composition correctness and
  structured-case safety — never production readiness. Real-traffic rates, live latency, and
  human-subject review are product-readiness gaps, reported as gaps.

## What would falsify readiness

If unsafe escape were not materially reduced, or false-block were high, or any fault produced a
permissive fallback, or replay were nondeterministic, or the audit were incomplete, the decision would
be "fix first" or "do not proceed." The Phase-27 report tests each against the frozen results.

## Success criteria (pre-committed, not to be altered after viewing outcomes)

Materially lower unsafe assertion + action escape than simple baselines; bounded false-blocking (≈0);
no unsafe high-risk subgroup; deterministic replay; complete audit on all non-catastrophic runs; no
silent contract failure; no external action; acceptable shadow-mode latency (units); interpretable
operator traces; at least one commercially plausible minimum configuration.
