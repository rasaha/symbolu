# Confirmatory replication — retention analysis

Retention categories are explanatory diagnostics defined **before** training; they never override the
formation classifier. Source: `experiments/bindingslots_confirmatory/results/retention_diagnostics.json`.

## CR1 needle@d96 trajectories (steps 0 / 60 / 120 / 300 / 600 / 900 / 1200)

| seed | 0 | 60 | 120 | 300 | 600 | 900 | 1200 | category |
|---|---|---|---|---|---|---|---|---|
| 13 | 0.00 | 0.01 | 0.13 | **1.00** | 0.96 | 0.09 | **0.00** | FORMED_THEN_COLLAPSED |
| 14 | 0.00 | 0.03 | 0.39 | **1.00** | 0.91 | 0.32 | **0.00** | FORMED_THEN_COLLAPSED |
| 15 | 0.00 | 0.03 | 0.59 | 0.98 | 0.99 | 0.98 | **1.00** | FORMED_AND_RETAINED |
| 16 | 0.00 | 0.03 | 0.84 | 1.00 | 1.00 | 1.00 | **1.00** | FORMED_AND_RETAINED |
| 17 | 0.00 | 0.01 | 0.38 | 0.84 | 0.91 | 0.95 | **1.00** | FORMED_AND_RETAINED |

- **FORMED_AND_RETAINED: 3** (15, 16, 17)
- **FORMED_THEN_COLLAPSED: 2** (13, 14)
- NEVER_FORMED / LATE_FORMATION / TRANSIENT_RECOVERY: 0

## The recurring retention-collapse signature

Seeds 13 and 14 follow the **same** trajectory the merged Stage B flagged for seed 9: needle rises to
**1.000 by step 300**, holds through step 600 while the alignment coefficient λ is still decaying to
0, then **decays to 0.000 across steps 900→1200** — after λ = 0 (step 600) and the curriculum handoff
back to the original ABC_MIX distribution (step 700). The scaffold builds the circuit; removing the
scaffold and returning to the original distribution lets it decay.

In the merged run this happened on **1/5** fresh seeds (seed 9). Here it happens on **2/5** (seeds
13, 14). Across the two independent five-seed sets, the post-scaffold retention failure is now
observed on **3/10** seeds, always with the same shape.

## Conservative mechanistic statement

The trajectories are **consistent with retention instability after scaffold removal**: the alignment
scaffold reliably drives early formation (all five CR1 seeds reach ≥ 0.84 by step 300), but on a
subset of seeds the circuit is not retained once λ → 0 and the distribution reverts. This is the
primary driver of the confirmatory failure (2 of the 2 non-formers are collapses, not
never-formers).

This does **not** conclusively establish architectural bistability from a few trajectories. It does
establish that the retention failure is **reproducible and not seed-9-specific**, which is the
evidence that motivates the retention-development next phase — a motivation, not a change to CR1 in
this phase.
