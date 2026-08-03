# Slot Routing Diagnostics

**Status:** EXPERIMENTAL. Development-set instrumentation. Not a validation result.

PR #1300 could not distinguish forming from non-forming seeds using **aggregate** slot utilization /
entropy. This phase therefore instruments the write→address→read loop **directly** on needle
fact/query pairs, and asks one central question:

> Does successful formation correspond to **rising fact-write / query-read overlap** *before* final
> needle performance rises — or does the routing stay at chance while the window path carries the
> task?

## Method (no architecture change, no N×N)
A forward-pre-hook recomputes each `BindingSlots` module's own `waddr`/`raddr` (softmax over the 32
slots) and write-gate from its **own** projections — the incubated class is never edited. For a
batch of needle pairs with known spans we read, per layer and averaged:

| field | meaning |
|---|---|
| `write_read_overlap` | Σ_m w_m·r_m at (fact value-token, query) — chance ≈ 1/32 = 0.031 |
| `read_prob_on_highest_write_slot` | how much the query reads the slot the fact wrote |
| `rank_of_highest_write_slot_under_read` | 0 = read's top choice; ≈ M/2 = random |
| `top1_slot_agreement` / `topk_slot_agreement` | argmax / top-3 overlap of write vs read |
| `write_entropy` / `read_entropy` | address concentration |
| `address_logit_margin` | read logit top1−top2 (pre-softmax) |
| `write_gate_at_fact` | gated write mass at the fact |
| `grad_norm_slot_keys / read_proj / write_proj` | per-component learning signal |

Captured at checkpoints **0, 60, 120, 300, 600, 900, 1200**, at distances **d16** and **d96**, plus
needle@d96 at each checkpoint. All quantities are bounded (M-dim); no [N,N] or [N,M,N] tensor is
formed. `grad_norm_probe` uses a throwaway backward that is immediately zeroed — it never reaches the
optimizer, so B0 reproduces the frozen path.

## Initialization-time reading (measured, seed-independent structure)
At step 0 the write/read addresses are **uncorrelated**: `write_read_overlap ≈ 0.031` (= chance),
`rank_of_highest_write_slot_under_read ≈ 16` (= M/2), and the **slot-key and read-projection
gradients are ≈ 0** while the write-value gradient is O(1). The routing circuit therefore receives
almost no early learning signal — consistent with a `WEAK_EARLY_ROUTING_SIGNAL` hypothesis that
Family 1 (optimizer) and Family 3 (alignment/curriculum) are designed to test. (This is an
init-structural reading, not a per-seed formation claim.)

## Trajectories (from `routing_diagnostics.json`)

**Central-question answer: yes — write-read overlap rises *before* needle@d96, and the alignment
objective is what makes it rise.**

- **Baseline B0 (slow, low-overlap formation):** e.g. fresh seed 9 overlap stays ≈ 0.15 throughout
  while needle climbs slowly to 0.58 by step 900. Formation is gradual and the address overlap never
  saturates — the slots form weakly.
- **Alignment arms (R1/CR1) drive overlap to ≈ 1.0 within 60–120 steps**, and needle follows within
  ~200 steps. This is the write→address→read loop being directly credited early, exactly the signal
  that is ≈ 0 at init (overlap ≈ 1/32 = 0.031, slot-key & read-projection gradients ≈ 0).

**The decisive C1-vs-CR1 contrast (development seeds):** both reach high needle, but only CR1's gain
survives slots-off / randomized-address. Curriculum alone (C1) trains the multi-layer local-window
pathway (its slots-off residual is 0.575 on s6); the alignment term forces the retrieval through the
slots (CR1 slots-off ≈ 0). Overlap-before-needle is therefore necessary but **not sufficient** —
causal collapse is the arbiter.

**Fresh seed 9 (retention trajectory):** overlap and needle both peak (~1.0) at step 300 under the
alignment scaffold, then **decay together** after λ→0 (step 600) and the curriculum handoff (step
700): needle 1.0 → 0.62 → 0.10 → 0.00, overlap 1.0 → 0.63. The routing loop *formed and then
unwound* — a post-scaffold retention failure, visible only because these trajectories were captured.

## Rule
The mechanism is argued from these trajectories, **never** from aggregate slot utilization/entropy
alone (per `ACCEPTANCE_GATES.json:mechanism_evidence_rule`).
