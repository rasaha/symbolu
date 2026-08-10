# Readiness Assessment (Phase 22)

*Aggregates every dimension of the apparatus into one verdict. Produced by
`reviewer_ready_pilot/readiness.py` (run it to regenerate). Current decision:
**REVIEWER-READY — WAITING FOR REAL REVIEWERS**.*

## Method

Each dimension is checked programmatically. Dimensions are evaluated in a fixed order; the **first**
failing dimension selects the decision, so the assessment always names a concrete thing to fix. If every
dimension passes, the decision is REVIEWER-READY. The assessment can only ever return one of the eight
allowed decisions, and never one implying real human validation.

## Dimensions (in evaluation order)

| Dimension | Checks | If it fails |
|---|---|---|
| honesty | prior artifacts intact (45 guarded) + honesty invariants (human-validation NOT_EVALUATED, production NOT_READY, external pilot BLOCKED, policy unmodified, enforcement DISABLED) | **DO NOT PROCEED** |
| eligible_artifacts | ≥ 75 natural eligible artifacts | **NOT ENOUGH ELIGIBLE ARTIFACTS** |
| source_metadata | provenance + surface metadata on every natural item | **SOURCE METADATA NEEDS IMPROVEMENT** |
| reviewer_guide | guide + quick-ref + errors + decision tree + qualification protocol present | **REVIEWER GUIDE NEEDS IMPROVEMENT** |
| review_set | final review set audit passes (blinding, disjointness, coverage) | **REVIEW SET NEEDS IMPROVEMENT** |
| review_workflow | blinded workflow runs end-to-end and stays honest (audit ok, no stop, mock excluded, metrics NOT_ENOUGH_HUMAN_EVIDENCE) | **REVIEW WORKFLOW NEEDS FIXES** |
| internal_pilot | governance + role model + recruitment + onboarding + adjudication + audit spec + future-eval freeze in place | **INTERNAL PILOT NOT READY** |

## Current result — all dimensions PASS

- honesty: prior artifacts intact; all invariants hold.
- eligible_artifacts: 78 natural (min 75).
- source_metadata: 0 items missing metadata.
- reviewer_guide: all materials present.
- review_set: REVIEW_SET_OK.
- review_workflow: end-to-end simulated run is well-formed; metrics on real records
  NOT_ENOUGH_HUMAN_EVIDENCE; no stop fired; all records mock.
- internal_pilot: all governance/plan docs present; future-evaluation freeze verifies.

→ **DECISION: REVIEWER-READY — WAITING FOR REAL REVIEWERS.**

## What this decision means (and does not)

It means the packaging is complete: a real reviewer could be added and begin blinded review immediately,
without rebuilding the workflow or changing the frozen policy. It does **not** mean the policy has been
validated by humans. Human validation stays **NOT EVALUATED**; the external customer pilot stays
**BLOCKED**; production readiness stays **NOT READY**. Those change only after a separately-scoped human
study runs under the frozen future-evaluation protocol (Phase 20).
