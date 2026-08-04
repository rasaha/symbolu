# Classifier specification

The confirmatory classifier (`experiments/bindingslots_confirmatory/classify_confirmatory.py`)
**imports the frozen Stage B per-seed rules directly** from the merged
`classify_stage_b.py` (sha256 `3ca1e75f…`, pinned and verified). Only the fresh-seed set (13–17) and
the final confirmatory verdict mapping are new; **no threshold is changed**.

## Per-seed rules (inherited byte-identically)

- **Formation** `forming(S, A+)` = `d96(S) ≥ 0.075` ∧ `d96(S) − d96(A+) ≥ 0.050` ∧ `d96(S) ≥ 0.07`.
- **Causal** `causal_ok(S, A+)` = for k ∈ {slots_off, randomized_address}:
  `drop_abs = baseline − ablated ≥ 0.050` ∧ `(drop_abs ≥ 0.5·gain if gain>0 else True)` ∧
  `ablated ≤ max(A+_d96 + 0.030, 0.050)`; `gain = baseline − A+_d96`.

## Aggregate gates (C1..C11)

| gate | condition | Stage B origin |
|---|---|---|
| C1 | CR1 forms ≥ 4/5 | b1 |
| C2 | CR1 formation > B0 formation | b5 |
| C3 | CR1 d96 > A+ d96 on ≥ 4/5 | b4 |
| C4 | mean(CR1 − A+) d96 ≥ 0.080 | b2 |
| C5 | median(CR1 − A+) d96 ≥ 0.050 | b3 |
| C6 | mean ppl256 ≤ 1.20×A+ ∧ ≤ 2/5 exceed A+ by >25% | b7 |
| C7 | d16 no material regression ∧ ≥3 forming keep +d220 | b9 |
| C8 | every forming seed collapses under slots-off | b8 |
| C9 | every forming seed collapses under randomized-address | b8 |
| C10 | integrity + parameter match | b6/b10/b11 |
| C11 | no protocol deviation | — |

## Verdict mapping

- all C1..C11 → `REPLICATED_SLOT_FORMATION_STABILIZATION` → `ELIGIBLE_FOR_NEXT_VALIDATION_LADDER`
- any scientific gate (C1..C9) fails → `CONFIRMATORY_REPLICATION_FAILED` → `KDA_VALIDATION_BLOCKED`
- C11 false → `CONFIRMATORY_PROTOCOL_VIOLATED`; C10 false → `CONFIRMATORY_INTEGRITY_FAILED`;
  incomplete results → `CONFIRMATORY_RESOURCE_BLOCKED`; env incompatible →
  `CONFIRMATORY_ENVIRONMENT_MISMATCH`.

The classifier uses **only the step-1200 evaluation** — no best-checkpoint selection. Validated
against 5/5-pass, 4/5-pass, 3/5-fail, 4/5-with-one-causal-failure, quality-fail, distance-fail,
protocol-deviation, and integrity-failure cases (see `tests/`).
