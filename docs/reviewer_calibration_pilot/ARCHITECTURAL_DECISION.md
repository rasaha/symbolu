# Architectural / Pilot Decision (Phase 21)

*`reviewer_calibration_pilot/decision.py` → `eval_results/decision.json`. One of ten pilot options, gated
on real reviewer evidence.*

## Separated dimensions (each on its own evidence)

| Dimension | Finding |
|---|---|
| **Reviewer evidence** | **NONE** (0 real reviewers; minimum 2) |
| Policy safety | technically 0 unsafe (prior track), **NOT human-validated** |
| Policy utility | 48% clean allow (system output), **NOT human-validated** |
| Review burden | **NOT EVALUATED** |
| Explanation quality | **NOT EVALUATED** |
| High-risk readiness | **NOT EVALUATED** |
| External-pilot readiness | **BLOCKED** (human validation missing) |
| Production readiness | **NOT established** |

## The ten options

| # | Option | Chosen |
|---|---|---|
| A | PROCEED TO SINGLE-CUSTOMER EXTERNAL SHADOW PILOT | No — human validation missing |
| B | PROCEED TO LOW-RISK EXTERNAL SHADOW PILOT ONLY | No — human validation missing |
| C | PROCEED TO INTERNAL SINGLE-TENANT PILOT | No — the internal calibration review could not run |
| D | PROCEED ONLY WITH MANDATORY HUMAN REVIEW | No — no reviewers to staff it |
| E | FIX REVIEWER GUIDANCE FIRST | No — no evidence of a guide defect |
| F | FIX POLICY RULES FIRST | No — no evidence of a rule defect |
| G | FIX SOURCE AUTHORITY OR EVIDENCE BINDING FIRST | No — no evidence |
| H | RUN ANOTHER HUMAN CALIBRATION ROUND | No — the first round could not run |
| **I** | **NOT ENOUGH HUMAN EVIDENCE** | **CHOSEN** |
| J | DO NOT PROCEED | No — no evidence of a defect that would justify rejection |

## Decision: Option I — NOT ENOUGH HUMAN EVIDENCE

Every "proceed" option requires human-validated safety/utility; every "fix-X-first" option requires human
evidence of that specific defect; "do not proceed" requires evidence of harm. **With 0 real reviewers,
none of that evidence exists.** The honest decision is Option I: the human-validation evidence needed to
choose any other option is absent, and it must not be fabricated.

This is consistent with, and does not weaken, the prior track's decision: the minimal policy remains
technically validated and internal-pilot-*ready in apparatus*, but the **real human validation that gates
progression has not been produced**, so no forward pilot step — internal or external — is recommended on
this track's evidence.

## Constructive next step

Engage ≥ 2 qualified real reviewers, run the frozen outcome-bearing review already built here, and re-make
both the calibration decision (Phase 20) and this pilot decision on real human evidence.

## One-line statement

> Every prerequisite apparatus for real-reviewer calibration is built, frozen, and tested — but with **0
> real reviewers**, no human agreement, safety, or utility evidence exists, so the calibration decision is
> **NOT ENOUGH HUMAN EVIDENCE** and the pilot decision is **NOT ENOUGH HUMAN EVIDENCE**; no external (or
> further internal) pilot is recommended, and no simulated result is offered in place of human validation.
