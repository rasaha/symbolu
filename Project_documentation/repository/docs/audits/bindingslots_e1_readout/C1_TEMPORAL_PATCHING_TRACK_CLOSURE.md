# C1 temporal-patching track — closure record

**The frozen C1 temporal-patching track is closed because minimal, capacity-fixed interventions did not
clear the latest-state gate.**

This record closes one narrow track only. It preserves, and does not touch:
`E1_TEMPORAL_TRANSFER_PARTIAL` · `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED` · `KDA_VALIDATION_BLOCKED`.

## What is closed
For **latest-state (T4) retrieval** on the temporal event-memory family, the following **frozen-C1,
capacity-fixed** approaches are now exhausted — each was tried and none cleared the gate:

- **null-threshold / null-gating adjustments** (learned or thresholded abstention correction);
- **minimal entity-retrieval residuals** (learned low-rank entity-matching added to the pooled read);
- **minimal temporal-ranking residuals** (learned query-conditioned position bias on the pooled read);
- **combinations of those factors** (all pairwise and the three-way cell of the 2³ factorial);
- **fixed-capacity add-ons to the pooled C1 read** in general (side-heads on top of the frozen mean-pooled
  dual-encoder score, base D/steps/lr/τ held fixed).

## Evidence chain
- **PR #1354 — `E1_TEMPORAL_TRANSFER_PARTIAL`:** the frozen C1 mechanism transfers for identity- and
  position-indexed retrieval but misses the latest-state gate (T4).
- **PR #1355 — T4 error analysis `INCONCLUSIVE`:** the T4 miss was not attributable to a single simple
  error class from the aggregate statistics alone.
- **PR #1356 — counterfactual attribution `T4_SHORTFALL_MIXED`:** zero-training oracle counterfactuals
  decomposed the T4 miss into abstention (~46%), entity-retrieval degradation (~22%), and within-entity
  latest ranking (~32%), with a clean value path and a strong *oracle* F1×F2 interaction.
- **PR #1358 — full 2³ factorial `T4_FACTORIAL_NO_INTERVENTION_SELECTED`:** minimal, non-oracle,
  capacity-fixed learnable factors targeting exactly those three components did not recover T4 — no cell
  reached T4 ≥ 0.85, none improved cell 000 by ≥ 0.05, 0/5 seeds passed. Only F1 (null gating) produced a
  positive effect (+0.034), reducing abstention (−0.059) but re-exposing addressing errors; F2 and F3 were
  ~0; the pre-flagged F1×F2 interaction did **not** reproduce with learnable factors (+0.001), showing the
  oracle-measured interaction depended on oracle entity identity.

## Mechanistic reason (why the track is closed)
Two ceilings bound the minimal factors: abstention (~0.30 of valid latest queries), which F1 only partially
relieves under the no-match false-accept constraint; and a **residual addressing ceiling** — even
null-excluded, the mean-pooled dual-encoder addresses the correct latest record only ~0.80 of the time, and
the minimal residuals do not lift that (they slightly lower it). The bottleneck is the **pooled read**, not
a tunable threshold — so no capacity-fixed patch on that read can be expected to clear 0.85.

## What this closure explicitly does NOT claim
- It does **not** claim that all temporal neural-memory architectures are exhausted.
- It does **not** claim the frozen representations lack the necessary information (that is the open question
  the drafted frozen-representation readout diagnostic is designed to test — not to build a successor).
- It does **not** validate temporal transfer, and it does **not** unblock KDA. The external-table
  reliability path remains the operational solution.

## Status after closure
`E1_TEMPORAL_TRANSFER_PARTIAL` stands. The next step in the record is a **draft-only** frozen-representation
readout **diagnostic** preregistration (`E1_FROZEN_REPRESENTATION_READOUT_DIAGNOSTIC_PREREGISTRATION.md`) —
documentation only, nothing implemented or executed, no successor architecture begun.
