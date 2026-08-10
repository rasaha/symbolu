# Human-Validation Status (Phase 1)

*The single, unambiguous status of human validation for this track, and what "reviewer-ready" does and
does not mean.*

## Status

**Human validation: NOT EVALUATED.** No real reviewers participate in this track. Nothing here measures,
infers, or claims human agreement, usability, review time, or confidence.

## What "reviewer-ready" means (and does not)

This track's success target is **REVIEWER-READY — WAITING FOR REAL REVIEWERS**. That is a statement about
the **apparatus**, not the policy's human acceptability:

- **It means:** the review workflow (roles, governance, guide, training/qualification, final set, blinded
  interface, assignment/access, frozen policy runner, audit, adjudication, metrics, stop conditions,
  recruitment/onboarding, future-evaluation protocol) is complete, tested, and executable the moment
  real reviewers are engaged — with no rebuild and no policy change.
- **It does not mean:** any human has judged the policy; that reviewers agree with it; that it is usable;
  or that it is ready for an external customer pilot. Those remain **NOT EVALUATED** / **BLOCKED**.

## The simulated workflow test

Phase 18 runs a workflow simulation with **deterministic test actors** to verify the plumbing
(assignment, blinded display, post-reveal, timing fields, override recording, adjudication, audit,
replay, stop conditions, deletion, policy immutability). All of its output is labelled
`SIMULATED_WORKFLOW_ONLY`. It **never** claims reviewer agreement, human usability, human review time,
human confidence, or human validation. The metrics module returns `NOT_EVALUATED` until **real** reviewer
records exist and never synthesizes metric values.

## Downstream status

- **External customer pilot:** BLOCKED (requires human validation, which is absent).
- **Production readiness:** NOT READY.

## Consequence

The honest terminus of this track is a **readiness** statement — the workflow is prepared and waiting —
paired with an unchanged **NOT EVALUATED** on human validation. Readiness of the apparatus and validation
by humans are kept strictly separate; this track can achieve the first and must not imply the second.
