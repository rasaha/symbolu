# Next validation ladder

The exact next phase is determined **mechanically** by the confirmatory verdict. This document
records both branches; the `KDA_READINESS_DECISION.md` records which branch was taken.

## If REPLICATED_SLOT_FORMATION_STABILIZATION

`SLOT_FORMATION_REPLICATED`, `KDA_READINESS = ELIGIBLE_FOR_NEXT_VALIDATION_LADDER`.

**Next phase: BindingSlots Validation Ladder C1** — transfer studies under the *same* frozen causal
gate, still Phase-free and with no architecture change:

1. **task-family transfer** — beyond needle/ABC_MIX to additional synthetic retrieval families;
2. **sequence-length transfer** — beyond seq 160;
3. **slot-count transfer** — beyond 32 slots;
4. **retention transfer** — characterize post-scaffold retention across the ladder.

This designs (does **not** implement) the next ladder; it does not begin KDA integration.

## If CONFIRMATORY_REPLICATION_FAILED

`SLOT_FORMATION_NOT_REPLICATED`, `KDA_READINESS = KDA_VALIDATION_BLOCKED`.

**Next phase: BindingSlots Retention Development** — a *new* preregistered comparison (under the same
causal gate) of the indicated-but-unproven retention levers:

1. slower λ decay;
2. residual alignment;
3. consolidation through the curriculum→original handoff.

These are retention interventions, **not** a new architecture and **not** a KDA/Phase/MLA step; each
must be re-run under this same causal gate before any promotion.

## Not started here

This experiment does not implement KDA, does not tune CR1, does not test slower decay, does not add
residual alignment, and does not begin retention-consolidation experiments.
