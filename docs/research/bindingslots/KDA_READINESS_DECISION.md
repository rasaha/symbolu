# KDA readiness decision

## Mechanical inputs

- Primary verdict: **`CONFIRMATORY_REPLICATION_FAILED`**
- Slot-formation status: **`SLOT_FORMATION_NOT_REPLICATED`**

## Decision

**`KDA_READINESS = KDA_VALIDATION_BLOCKED`.**

The single independent confirmatory replication of frozen CR1 did **not** reproduce the merged 4/5
holdout result on fresh seeds 13–17. CR1 forms-and-retains only 3/5, one of those three is not
cleanly slot-causal, and the post-scaffold retention-collapse mode recurred on 2/5 seeds. Because a
valid scientific run completed and a scientific gate failed, the verdict is a genuine failure — not
`CONFIRMATORY_RESOURCE_BLOCKED`, `CONFIRMATORY_INTEGRITY_FAILED`, or `CONFIRMATORY_PROTOCOL_VIOLATED`.

This result is **not softened**. 3/5 is not "nearly replicated." Transient formation on seeds 13/14
does not count as success. KDA validation remains blocked.

## What this does and does not authorize

- **Does not** authorize any KDA, Phase, MLA, or architecture work.
- **Does not** authorize promoting or packaging the slot system.
- **Authorizes** the retention-development next phase (below) — a new preregistered study, not a
  change to CR1 in this phase.

## Exact next phase

**BindingSlots Retention Development** — a new preregistered comparison, under this same causal gate,
of the indicated-but-unproven retention levers:

1. slower λ decay;
2. residual alignment;
3. consolidation through the curriculum→original handoff.

Each is a retention intervention, not a new architecture and not a KDA/Phase/MLA step. See
`NEXT_VALIDATION_LADDER.md`. None of these is started in this phase.
