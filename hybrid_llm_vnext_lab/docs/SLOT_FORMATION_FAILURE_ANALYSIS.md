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

## Evidence and verdict

**Supported mechanism: `WEAK_EARLY_ROUTING_SIGNAL` compounded by `ARCHITECTURAL_BISTABILITY`.**
`OPTIMIZER_SENSITIVITY` and `SLOT_SYMMETRY_FAILURE` are **refuted** by the evidence.

| mechanism | evidence | status |
|---|---|---|
| OPTIMIZER_SENSITIVITY | O1 & O2 (slot-specific LR/warmup) both *regressed* s6 and rescued nothing | **refuted** |
| SLOT_SYMMETRY_FAILURE | baseline keys already orthogonal (off-diag cosine ≈ 0); K1 no reliability gain | **refuted** |
| WEAK_EARLY_ROUTING_SIGNAL | init overlap ≈ chance, routing gradients ≈ 0; alignment (R1/CR1) that injects early routing gradient is the only thing that works | **supported** |
| ARCHITECTURAL_BISTABILITY | K1 *relocates* which seed forms; fresh seed 9 forms then unwinds post-scaffold | **supported** |

**Per-arm outcome (development seeds 3/6/7):**
- **O1, O2:** 0/3, regressed s6, rescued neither non-former.
- **K1:** rescued s3 (0→0.125) but broke s6 (0.075→0.017); net 1/3 — pure basin reshuffling.
- **C1:** 3/3 on the metric but **causally invalid** — slots-off leaves 0.575 (s6) and rand-address
  0.90/0.33 (s6/s7): the multi-layer local-window pathway does the retrieval, not the slots.
- **R1:** 2/3, rescued s7, causally clean.
- **CR1:** 3/3, rescued s3 **and** s7, causally clean — selected candidate.

**Fresh-seed confirmation (8–12):** CR1 formed 4/5 (vs baseline B0 3/5), all forming seeds causally
clean. The single miss (seed 9) is the **retention** signature of bistability: needle peaked 1.000
at step 300 then decayed to 0.000 after the scaffold was removed (λ→0 at step 600; curriculum→
original at step 700), while seeds 8/10/11 dipped at step 900 and recovered. The circuit *can* form
on seed 9 — it is not retained without the scaffold's continued pressure.

**Implication (unproven hypothesis, next-phase):** since the alignment scaffold demonstrably forms
the circuit even on hard seeds, the residual failure is a **consolidation/handoff** problem. A
slower λ decay, a small residual alignment term through the curriculum→original transition, or a
retention/EMA-consolidation step are the indicated next levers — not a new intervention family, and
not any architecture change. Any such change must be re-run under this same causal gate.

## Discipline
A rescued diagnostic seed is a development observation, **not** generalization. Any mechanism claim
is argued from routing trajectories (overlap-before-needle, correct-slot rank, per-group gradient
norms), never from aggregate utilization.
