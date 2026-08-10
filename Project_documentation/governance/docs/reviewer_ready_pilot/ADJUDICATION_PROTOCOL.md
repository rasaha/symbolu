# Adjudication Protocol (Phase 16)

*How reviewer disagreements are resolved — and when they are honestly left unresolved. Implemented in
`reviewer_ready_pilot/adjudication.py` and `metrics.py`. No real disagreement exists in this track;
these are the rules and the apparatus the pilot administrator applies once real reviewers run.*

## When adjudication triggers

After Stage-A labels are collected, `metrics.find_disputes` flags each artifact where **real** reviewers
disagree on the obligation level. Mock records are excluded, so a simulated disagreement never enters
adjudication.

## Who adjudicates

A reviewer holding the **Adjudicator** role (Phase 2), who did **not** review the artifact themselves. The
code enforces this separation: `adjudicate` raises if the adjudicator's ID is among the artifact's
reviewers.

## What the adjudicator may record

The adjudicator sees the disagreeing blinded labels and the reasons, then records exactly one of:

1. **RESOLVED** — a single obligation level plus a reason. Both are required; a resolution with no reason
   or no level is rejected.
2. **UNRESOLVED** — with a reason. This is the honest terminus for an *irreducible* domain judgment call.
   Forcing false consensus is prohibited; `UNRESOLVED` is a valid, first-class outcome, not a failure.

The adjudicator's decision is **supplied by the human**; the module records and validates it but never
decides for them (`resolution=None` raises).

## What adjudication is not

- It does **not** enforce or execute anything (`enforced` is never set).
- It does **not** tune, relabel, or modify the frozen policy — a resolution is a record of human judgment
  on one artifact, not a change to the policy's rules.
- A RESOLVED obligation is **not** a claim that the policy is correct. It is a reviewer-side resolution of
  a reviewer-side disagreement. Human validation of policy correctness remains **NOT EVALUATED**.

## Metrics interaction (Phase 15)

`metrics.compute` reports, from real records only: reviewer–reviewer agreement, reviewer–system agreement,
trap-catch rate, override rate, and a disagreement taxonomy (`OBLIGATION_LEVEL`, `SAFETY_DIRECTION`,
`TRAP_MISS`, `ACTIONGATE_INTERPRETATION`, `GENUINE_AMBIGUITY`). With no real records, every human-dependent
metric is `NOT_EVALUATED` and the status is `NOT_ENOUGH_HUMAN_EVIDENCE`. Agreement is always described as
reviewer behaviour, never as system correctness.
