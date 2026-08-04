# BindingSlots Confirmatory Replication

Single independent confirmatory replication of the merged, frozen **CR1** BindingSlots intervention
(PR #1319, `PROVISIONALLY_STABILIZED`) on **five previously-unused seeds (13–17)**, with **no
further tuning**.

## What this is

The next preregistered gate after the merged slot-formation-stabilization result. It answers one
question: does frozen CR1 reproducibly increase **causally slot-dependent** retrieval-circuit
formation on independent fresh seeds? A pass classifies
`REPLICATED_SLOT_FORMATION_STABILIZATION` and unlocks *designing* (not implementing) the next
validation ladder. A fail classifies `CONFIRMATORY_REPLICATION_FAILED` and keeps KDA validation
blocked.

## Contents

| File | Purpose |
|---|---|
| `preregistration.md` / `.json` | frozen protocol (committed before training) |
| `frozen_cr1_config.json` | byte-recovered merged CR1 config + all frozen source hashes |
| `fresh_seeds.json` | seeds 13–17, selection rule, independence proof |
| `classifier.json` | frozen gates C1..C11 + confirmatory verdict mapping |
| `*.schema.json` | run-manifest / seed-result / aggregate-result schemas |
| `verify_confirmatory_prereg.py` | torch-free integrity gate (run before training + in CI) |
| `run_confirmatory.py` | orchestrator: A+/B0/CR1 × seeds 13–17, resumable, idempotent |
| `classify_confirmatory.py` | mechanical classifier (reuses frozen Stage B per-seed rules) |
| `retention.py` | frozen retention-trajectory categorizer (diagnostic only) |
| `results/` | curated per-seed + aggregate + gate artifacts |

## Reproduce

```bash
# 1. integrity (torch-free)
python experiments/bindingslots_confirmatory/verify_confirmatory_prereg.py

# 2. train (requires torch; ~1000 s / B0 or CR1 seed, resumable)
python experiments/bindingslots_confirmatory/run_confirmatory.py

# 3. classify + curate
python experiments/bindingslots_confirmatory/classify_confirmatory.py \
    --results-dir experiments/bindingslots_confirmatory/results/seeds \
    --out experiments/bindingslots_confirmatory/results/aggregate_result.json
```

## Non-negotiables

- Frozen CR1 config, curriculum, alignment schedule, optimizer, task distribution, training budget,
  classifier, causal gates, quality gate, and distance gate are **unchanged**.
- No Phase / KDA / MLA / quadratic / N×N / new inference-time op.
- No best-checkpoint selection, no outcome-based seed replacement, no threshold changes.
