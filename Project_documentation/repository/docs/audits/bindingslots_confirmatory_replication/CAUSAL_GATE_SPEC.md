# Causal-gate specification

Every CR1 seed classified as **formed** must pass **both** causal interventions. The ablations are
computed at step 1200 by the frozen `evaluate.s_ablations` and stored in each seed record's
`ablation` block. The confirmatory classifier applies the frozen thresholds per seed and **never
averages across seeds** — one causally-unclean forming seed fails the whole replication.

## Slots-off

Disable the BindingSlots contribution during evaluation while keeping the rest of the model fixed
(frozen `s_ablations["slots_off"]`). Must satisfy, for the seed's `baseline` (post-train needle@d96)
and `gain = baseline − A+_d96`:

- `baseline − slots_off ≥ 0.050` absolute, **and**
- `baseline − slots_off ≥ 0.5 · gain` (≥ 50 % of the slot gain removed), **and**
- `slots_off ≤ max(A+_d96 + 0.030, 0.050)`.

## Randomized addressing

Randomize/disrupt slot addressing while preserving non-slot computation (frozen
`s_ablations["randomized_address"]`). Same three conditions as slots-off.

## Supplementary (recorded, not gating)

`shuffle_values`, `write_gate_zero`, `slot_keys_randomized` are also recorded per seed for the
shortcut-control analysis, using the existing PR #1319 controls.

## Invariant

```
for every forming CR1 seed s:
    slots_off_gate(s)          == PASS
    randomized_address_gate(s) == PASS
```

Failure on any forming seed → `CONFIRMATORY_REPLICATION_FAILED`. No averaging, no exclusion, no
threshold change.
