# Slot Formation — Failure-Mode Analysis

**Status:** EXPERIMENTAL. Mechanism analysis on the development set; not a validation result.

## Prior evidence (PR #1300, not reclassified)
The S circuit forms in only 3/5 holdout seeds. When it forms the effect is real, large (up to
0.408), causally slot-dependent (collapses under slots-off and randomized-address), quality-
preserving (PPL 117.8 < A+ 139.8), and distance-robust. **Only formation reliability fails.**
Non-forming seeds (3, 7) were **not** distinguishable by aggregate slot diagnostics — pointing to an
optimization/initialization sensitivity rather than a dead-slot or gate-collapse pathology.

## Candidate mechanisms (pre-registered labels)
| label | prediction if true | intervention that would help |
|---|---|---|
| `DELAYED_FORMATION` | overlap/needle rise late; more steps would help | (out of scope — no longer training) |
| `OPTIMIZER_SENSITIVITY` | slot-routing needs a different LR/warmup than the backbone | O1 / O2 |
| `SLOT_SYMMETRY_FAILURE` | slots start too similar; identities never separate | K1 |
| `WEAK_EARLY_ROUTING_SIGNAL` | routing gradients ≈ 0 early; write/read never couple | R1 / C1 / O-family |
| `ARCHITECTURAL_BISTABILITY` | seeds fall into a stable non-routing basin; no training tweak flips them | none (would classify NO_STABILIZATION_CANDIDATE) |
| `NO_IDENTIFIED_MECHANISM` | interventions do not separate the mechanisms | — |

## Structural finding surfaced by the audit (Family 2 has little headroom)
The frozen `BindingSlots.__init__` **already** applies `nn.init.orthogonal_(keys)` (because
num_slots 32 ≤ key_dim 64) and row-normalizes. Measured off-diagonal pairwise cosine of the baseline
slot keys is **exactly 0.0**; the K1 QR-orthonormal init is also 0.0. **Slot symmetry is already
broken at initialization in the baseline.** So `SLOT_SYMMETRY_FAILURE` is largely excluded a priori,
and K1 is expected to be near-null — pre-registered as such, not concluded after the fact. K1 still
runs, and its initialization audit (`initialization_audit.json`) quantifies the (tiny) difference.

## Early-signal finding (measured at step 0)
Write/read slot addresses start uncorrelated (overlap ≈ chance, correct-slot rank ≈ M/2) and the
**slot-key and read-projection gradients start at ≈ 0** while the write-value gradient is O(1). The
routing loop is thus starved of early learning signal — the concrete reading behind
`WEAK_EARLY_ROUTING_SIGNAL`, which O1/O2 (slot-specific schedule) and R1/C1 (early routing scaffold)
are designed to test.

## Evidence and verdict (populated from artifacts)
_Per-arm: whether it rescued seed 3 and/or seed 7, whether seed 6 stayed formed, causal-ablation
outcomes, and which mechanism the routing trajectories support. Filled from
`diagnostic_classification.json` + `routing_diagnostics.json`._

<!-- RESULTS:MECHANISM_VERDICT -->

## Discipline
A rescued diagnostic seed is a development observation, **not** generalization. Any mechanism claim
is argued from routing trajectories (overlap-before-needle, correct-slot rank, per-group gradient
norms), never from aggregate utilization.
