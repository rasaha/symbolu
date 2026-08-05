# Frozen-readout diagnostic track — closure record

**The tested bounded frozen-representation readouts did not recover sufficient latest-state signal. No
further C1 or frozen-readout intervention is authorized.**

Documentation-only. Preserves, and does not touch: `E1_TEMPORAL_TRANSFER_PARTIAL` ·
`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.

## What is closed
Within this **bounded diagnostic scope**, the following readouts over the frozen temporal-E1
representations are exhausted for latest-state (T4) retrieval:

- **mean pooling** (R0, the existing C1 read);
- **learned single-attention** readout (R1);
- **learned dual-head attention** readout (R2);
- the **tested structural-prior** readout (R3).

None reached the preregistered PRESENT or PARTIAL bars on the reserved cohort (R1 Δ +0.003, R2 Δ −0.003,
R3 Δ +0.033 over R0; conclusion `FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND`).

## Evidence chain
- **PR #1354 — `E1_TEMPORAL_TRANSFER_PARTIAL`:** frozen C1 transfers for identity/position-indexed
  retrieval but misses the latest-state gate (T4).
- **PR #1356 — `T4_SHORTFALL_MIXED`:** the T4 miss decomposes (via zero-training oracle counterfactuals)
  into abstention / entity-retrieval / within-entity latest ranking, with a clean value path.
- **PR #1358 — no minimal three-factor intervention selected** (`T4_FACTORIAL_NO_INTERVENTION_SELECTED`):
  minimal, capacity-fixed learnable factors targeting those components did not recover T4.
- **PR #1360 — bounded frozen readouts did not recover sufficient signal**
  (`FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND`): mean-pool, single-attention, dual-head, and a
  structural-prior readout over the frozen representations did not clear the latest-state bars.

## What this closure explicitly does NOT claim
- It does **not** prove that all temporal information is absent from the frozen representations (R3 moved the
  diagnosed components — abstention 0.279→0.219, correct-entity 0.695→0.760 — but insufficiently and without
  generalizing from dev to the reserved cohort).
- It does **not** prove that all temporal neural-memory architectures are exhausted.
- A **richer or newly trained architecture** would be a separate **capacity-bearing research program**
  requiring a new preregistration and explicit authorization; **no successor architecture is authorized by
  this record.**
- **T5** predecessor/successor reasoning remains **unresolved and outside** this closure.

## Operational status
The **external-table path remains the operational reliability solution** for temporal facts. E1 is retained
for semantic retrieval. `E1_TEMPORAL_TRANSFER_PARTIAL` stands; the original BindingSlots neural-routing
question remains unresolved; **KDA stays blocked**. No `E1_TEMPORAL_TRANSFER_VALIDATED`,
`E1_STRUCTURAL_TRANSFER_CONFIRMED`, `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`, or `KDA_VALIDATION_ELIGIBLE` is emitted.
