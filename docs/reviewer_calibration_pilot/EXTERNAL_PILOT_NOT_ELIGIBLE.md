# External Pilot Plan — Not Eligible (Phase 22)

*Phase 22 instructs: "**Only if** the decision permits external shadow use, create the single-customer
external shadow pilot plan." The decision does **not** permit it, so no such plan is created. This
document records why.*

## Gate not passed

| Gate | Status |
|---|---|
| Calibration decision (Phase 20) | **Option 8 — NOT ENOUGH HUMAN EVIDENCE** |
| Pilot decision (Phase 21) | **Option I — NOT ENOUGH HUMAN EVIDENCE** |
| Human validation | **NOT EVALUATED** (0 real reviewers) |
| External-pilot readiness | **BLOCKED** |

The governing spec is explicit: with fewer than 2 real reviewers, **do not recommend an external pilot**,
and the external pilot plan is created **only if** the decision permits external shadow use. Neither
condition is met.

## Why no plan is written

Writing a single-customer external shadow pilot plan would imply the policy is ready for external
exposure. It is not — its human acceptability is unmeasured. Producing the plan now would misrepresent
the state of evidence. Per the spec's own constraint ("do not identify or invent a real customer" and "do
not recommend an external pilot" without the gate), the plan is deliberately **withheld**.

## What exists instead

- The **internal** pilot apparatus is complete (this track) and the prior track's `INTERNAL_PILOT_PLAN.md`
  already defines the internal single-tenant pilot whose purpose is to produce the missing real human
  validation.
- The **frozen outcome-bearing review** is built and ready; running it with ≥ 2 qualified real reviewers
  is the sole precondition to re-gating any external-pilot discussion.

## Condition to revisit

An external single-customer shadow pilot plan becomes appropriate **only after**: (1) ≥ 2 qualified real
reviewers complete the frozen outcome-bearing review; (2) acceptable-obligation agreement, high-risk
agreement, and unsafe-allow disagreement clear the frozen thresholds; and (3) the calibration decision
(Phase 20) moves to a "proceed" option on that real evidence. Until then, the external pilot plan does not
exist by design.
