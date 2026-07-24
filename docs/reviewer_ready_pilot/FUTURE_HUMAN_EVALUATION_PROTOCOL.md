# Future Human-Evaluation Protocol (Phase 20)

*The protocol a real human pilot MUST follow, frozen NOW — before any reviewer runs — so it cannot be
tuned after real results are seen. Pinned by `reviewer_ready_pilot/verify_evaluation_freeze.py` into
`eval_results/future_evaluation_freeze.json` (SHA-256 of the data sets + the config).*

## Why freeze it now

Freezing the metrics, thresholds, stop conditions, adjudication rules, and decision rule in advance is what
makes a later human study honest: no one can move the goalposts once real agreement numbers are in. The
freeze is a **readiness** artifact — it is explicitly **not** evidence that any human has evaluated the
policy.

## What is frozen

- **Data:** SHA-256 of `training.json`, `final_review.json`, `manifest.json`.
- **Frozen components / versions:** minimal policy `v1` (unmodified), label schema `v1`, interface `v1`,
  runner `v1`, audit `v1`; native ActionGate 6-outcome vocabulary.
- **Metrics:** reviewer–reviewer agreement, reviewer–system agreement, trap-catch rate, override rate,
  disagreement taxonomy.
- **Thresholds:** the frozen cumulative thresholds from Phase 17 (not tuned on the review set).
- **Stop conditions:** the full immediate-stop list from Phase 17.
- **Adjudication:** separated adjudicator; `UNRESOLVED` is a valid terminus; consensus is never forced.
- **Subgroup analyses:** risk tier, claim family, trap type, edge type, action-bearing, source kind.
- **Decision rule:** *metrics describe reviewer behaviour only; no metric outcome converts to a claim of
  policy correctness or human validation without a separately-scoped human study.*

## Frozen honesty invariants (the verifier enforces these)

`verify_evaluation_freeze.py verify` fails if any of these drift:

- `human_validation = NOT_EVALUATED`
- `production_readiness = NOT_READY`
- `policy_modified = false`
- `enforcement = DISABLED`
- `reviewer_roster = []`, `reviewer_count = 0`
- `external_customer_pilot = BLOCKED`

## What running this protocol later would and would not establish

Running it with real, qualified reviewers would produce reviewer-behaviour metrics (agreement,
disagreement structure, trap-catch). Even then, per the frozen decision rule, those numbers describe
reviewers — converting them into a claim about the policy's correctness would require a separate,
explicitly-scoped human-validation study. Until such a study runs, human validation stays **NOT
EVALUATED**, the external customer pilot stays **BLOCKED**, and production readiness stays **NOT READY**.
