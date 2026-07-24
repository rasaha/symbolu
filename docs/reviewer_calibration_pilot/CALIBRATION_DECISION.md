# Calibration Decision (Phase 20)

*`reviewer_calibration_pilot/decision.py` → `eval_results/decision.json`. One of nine options, gated on
real reviewer evidence.*

## The nine options

| # | Option | Chosen |
|---|---|---|
| 1 | FREEZE POLICY AS VALIDATED | No — requires human validation |
| 2 | REVISE REVIEWER GUIDE ONLY | No — no reviewer data shows a guide defect |
| 3 | REVISE ONE OR TWO POLICY RULES | No — no reviewer data justifies a rule change |
| 4 | REVISE SOURCE-AUTHORITY METADATA | No — no reviewer data |
| 5 | REVISE EVIDENCE BINDING | No — no reviewer data |
| 6 | REQUIRE HUMAN REVIEW FOR ALL NON-LOW-RISK | No — premature |
| 7 | RUN ANOTHER INTERNAL CALIBRATION ROUND | No — the first round could not run |
| **8** | **NOT ENOUGH HUMAN EVIDENCE** | **CHOSEN** |
| 9 | REJECT POLICY FOR OPERATIONAL USE | No — no evidence of a defect |

## Decision: Option 8 — NOT ENOUGH HUMAN EVIDENCE

Every option except 8 requires real reviewer evidence to justify it: freezing-as-validated needs
agreement; revising the guide needs a demonstrated guide defect; revising rules/metadata/binding needs
demonstrated policy errors; rejecting needs demonstrated harm. **There are 0 real reviewers (minimum 2),
so none of that evidence exists**, and none may be synthesized from mock or rubric output.

The decision does **not** revise anything "because some disagreement exists" — there is no disagreement to
observe. It records the honest state: the calibration apparatus is complete and ready, and the human
evidence needed to calibrate is absent.

## What is *not* concluded

Not that the policy is good, bad, too complex, too conservative, or in need of a specific fix — those are
exactly the questions real reviewers would answer. The calibration is **suspended for lack of human
evidence**, not resolved.

## Constructive next step

When ≥ 2 qualified real reviewers are available, run the already-built, frozen outcome-bearing review
(`outcome_review.py`) on the frozen final set; it will populate the metrics and this decision can be
re-made on real evidence.
