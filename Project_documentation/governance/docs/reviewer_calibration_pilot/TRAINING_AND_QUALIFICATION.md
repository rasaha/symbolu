# Training and Qualification Set (Phase 4)

*`reviewer_calibration_pilot/data/training_v1/`. 20 non-final artifacts (12 natural + 8 constructed
traps) **with** revealed gold labels, explanations, and triggered invariants. Training data never appears
in the final review set (verified disjoint).*

## Purpose

Real reviewers learn the framework on these labelled examples before qualifying. Because training reveals
answers, its gold labels come from the frozen minimal policy (read-only) plus the reviewer guide's
rubric. Reviewers may receive examples, correct labels, explanations, and feedback here — and **only**
here (the final set is never used to train or coach).

## Composition

- **12 natural artifacts** spanning obligation levels, each with the policy's obligation + one-trace
  rationale.
- **8 constructed traps** (labelled), one per key safety pattern: self-verification, circular evidence,
  stale authority, fixture-as-telemetry, implementation-as-operational, action-without-approval,
  attribution-as-truth, high-risk-opinion.

## Qualification criteria (a reviewer must meet all to label the final set)

1. **Risk agreement** — assigns the same risk tier as the reference on ≥ 80% of training items.
2. **No unsafe downgrade on high-risk** — never assigns an obligation below the risk floor on any
   high-risk training example.
3. **Self-verification recognition** — correctly raises every self-verification / circular trap to ≥ E3
   (never accepts self-support at E1/E2).
4. **Source authority vs claim truth** — correctly distinguishes "the source is authoritative for this
   claim" from "the claim is true" on the authority traps (implementation ≠ operational, stale authority,
   attribution ≠ truth).
5. **ActionGate interpretation** — correctly reads the native ActionGate outcome on the action trap
   (action needs approval → not a clean allow).

A reviewer failing qualification **may not** label the final set until retrained or replaced. Training
performance is recorded per pseudonymous reviewer.

## Separation guarantee

`training_v1` and `final_review_v1` share no artifact IDs (verified by test). Training-set artifacts never
enter final evaluation, so qualification cannot leak final answers.

## Status in this environment

The training set exists and is ready. **No real reviewers are available to train or qualify**, so no
qualification results are produced — consistent with the NOT ENOUGH HUMAN EVIDENCE terminus.
