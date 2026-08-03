# Slot Stabilization — Maturity

**Status:** EXPERIMENTAL · NOT_AN_INSTALLABLE_PACKAGE · NOT_A_PRODUCTION_MODEL ·
NOT_READY_FOR_PACKAGING

## Where this sits
Slot maturity vocabulary (from the lab `STATUS.md`):
`HISTORICAL_RESULT_ONLY → REPRODUCED → WORKING_BUT_UNSTABLE → MULTI_SEED_VALIDATED → …`

PR #1300 established `PARTIALLY_STABLE` (formation 3/5) → the slots are `WORKING_BUT_UNSTABLE`. This
phase asks whether a **training** intervention moves formation reliability toward
`MULTI_SEED_VALIDATED` **without** any architecture change.

## Phase classification (populated on completion)
One of: `NO_STABILIZATION_CANDIDATE` · `INTERVENTION_RESCUES_KNOWN_FAILURES_ONLY` ·
`FRESH_HOLDOUT_UNSTABLE` · `PROVISIONALLY_STABILIZED` · `INVALID_EXPERIMENT` · `RESOURCE_BLOCKED`.

<!-- RESULTS:MATURITY -->

## Readiness (invariant this phase)
**NOT_READY_FOR_KDA_VALIDATION.** Even a `PROVISIONALLY_STABILIZED` result does **not** grant KDA
readiness, because the intervention was chosen over multiple candidates on a development set. The
**only** next gate is:

> one independent confirmatory **five-seed** replication of the frozen winning intervention, with
> **no further tuning** and no configuration change.

KDA / MLA / composition / packaging remain out of scope and are not unblocked by this phase.

## Gate to leave the lab (unchanged from `STATUS.md`)
None of the packaging gates are cleared here. This phase does not create anything under `packages/`,
builds no wheel, and is not a distribution.

## Explicit non-generalization note
Any improvement observed on development seeds 3/6/7 is a **development observation** used only to
select a candidate. Generalization is claimed **only** from the fresh seeds 8–12 under the
pre-registered ≥4/5 gate, and even then is labelled *provisional* pending the confirmatory
replication above.
