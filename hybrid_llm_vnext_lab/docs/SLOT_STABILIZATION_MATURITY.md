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

**Result: `PROVISIONALLY_STABILIZED`.** The selected candidate **CR1** (curriculum + temporary
write-read alignment) passed every pre-registered Stage B gate on fresh seeds 8–12: formation
**4/5** (beating the frozen baseline B0's 3/5), causal collapse on every forming seed, quality
preserved, distance-robust, bounded state, no Phase/KDA/MLA. This moves the slot subsystem from
`WORKING_BUT_UNSTABLE` toward — but **not yet to** — `MULTI_SEED_VALIDATED`: 4/5 is above the
baseline but not the perfect reliability that a full validation would require, and the candidate was
selected over multiple arms on a development set.

The distinction is deliberate: **development-seed rescue (3/6/7) is not generalization.** The 4/5
figure is the *fresh-holdout* result, and even it is labelled *provisional*.

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
