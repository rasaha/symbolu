# Pre-Registration — Phase-Free Slot Formation Stabilization

**Committed before any Stage A training.** Machine-readable and integrity-checked by
`verify_preregistration.py` (fails if any pinned file or scalar drifts after results exist).

- Gates: `ACCEPTANCE_GATES.json`
- Arms / schedules / architecture: `EXPERIMENT_MATRIX.json`
- Selection rule: `SELECTION_RULE.json`
- Pinned hashes: `CONFIG_HASHES.json`
- Audit: `LIVE_STATE.md/json`, `SOURCE_INVENTORY.json`, `FROZEN_BASELINE_MANIFEST.json`

## Research question
Can **one** of three intervention families increase **reliable formation** of the existing
bounded-slot circuit **without** changing its architecture, degrading language quality, or
weakening causal slot dependence? The suspected failure is an optimization/initialization
sensitivity in the write→address→read routing loop. The phase must distinguish
`DELAYED_FORMATION` / `OPTIMIZER_SENSITIVITY` / `SLOT_SYMMETRY_FAILURE` /
`WEAK_EARLY_ROUTING_SIGNAL` / `ARCHITECTURAL_BISTABILITY` / `NO_IDENTIFIED_MECHANISM`, argued from
**routing diagnostics** (not aggregate utilization).

## Immutable starting point (not reclassified)
Frozen five-seed holdout (PR #1300): formation 3/5 → `PARTIALLY_STABLE` →
`NOT_READY_FOR_KDA_VALIDATION`. Verified from committed artifacts.

## Two stages
- **Stage A (development):** seeds **3, 6, 7** (non-former / marginal-former / non-former).
  Arms **B0, O1, O2, K1, C1, R1, CR1**. Selects a candidate; never reported as a fresh holdout.
- **Stage B (fresh validation):** seeds **8, 9, 10, 11, 12** (verified uncontaminated). Arms
  **A+, B0, selected candidate**, 1200 steps, no tuning.

## Intervention families (tested INDEPENDENTLY this round)
1. **Optimizer (O1/O2):** slot-routing parameter group gets its own LR + longer warmup (O1:
   slot LR 1e-3 / warmup 180; O2: slot LR 3e-3 / warmup 180; non-slot stays 2e-3 / 60).
2. **Init (K1):** deterministic orthogonal, unit-normalized, trainable slot-key init.
   *Pre-registered caveat:* the frozen `BindingSlots` already orthogonalizes keys at init
   (32 ≤ 64), so K1 has limited headroom; the init audit quantifies it.
3. **Scaffold (C1 curriculum / R1 alignment / CR1 both):** curriculum boundaries **300/700/1200**
   (final 500 steps = original distribution); alignment = label-free write-read overlap
   `L_align = -log(Σ_m w_m r_m + 1e-6)` with λ **0.10 → linear decay over 301–600 → 0** (zero
   after step 600 and during all evaluation). No fixed correct-slot label, no answer-token
   leakage, no N×N tensor, no inference-time op.

No cross-family combination in Stage A (CR1 combines only the two Family-3 scaffolds).

## Formation rule (inherited, unchanged)
`S_needle_d96 ≥ 0.075` **and** `S − A+ ≥ 0.050` **and** `S ≥ 0.07`. A seed at threshold is
*marginal* but counts as FORMED.

## Stage A eligibility (candidate gate) — all required
(1) forms ≥ 2/3 diagnostic seeds; (2) rescues ≥ 1 historical non-former (3 or 7); (3) seed 6 does
not regress below formation unless both 3 and 7 are rescued; (4) PPL quality passes; (5) every
newly-forming seed collapses under slots-off **and** randomized-address; (6) no N×N; (7)
parameters matched; (8) no Phase/KDA/MLA.

## Selection rule (mechanical, no override)
Among eligible arms rank by: (k1) #seeds formed, (k2) #rescued non-formers, (k3) highest **min**
per-seed S−A+ margin, (k4) highest **median** margin, (k5) lowest PPL, (k6) simplicity order
`O1|O2 → K1 → C1 → R1 → CR1`; ties → lexicographically first arm ID (documented). No eligible arm
→ `NO_STABILIZATION_CANDIDATE`.

## Stage B gates — all required
formation ≥ **4/5**; mean(S−A+) ≥ 0.080; median ≥ 0.050; S>A+ in ≥ 4/5; candidate formation >
B0 formation; params matched; PPL quality; causal collapse per forming seed; d16/d96/d220
distance; no N×N; bounded O(M·D) state; Phase/KDA/MLA absent. **A higher mean with < 4/5 does not
pass.**

## Classification & readiness
`NO_STABILIZATION_CANDIDATE` / `INTERVENTION_RESCUES_KNOWN_FAILURES_ONLY` /
`FRESH_HOLDOUT_UNSTABLE` / `PROVISIONALLY_STABILIZED` / `INVALID_EXPERIMENT` / `RESOURCE_BLOCKED`.
Even under `PROVISIONALLY_STABILIZED` the readiness is **NOT_READY_FOR_KDA_VALIDATION**; the next
gate is one independent confirmatory five-seed replication of the frozen winning intervention with
no further tuning.

## Discipline
Frozen S architecture, tasks, tokenizer, corpus, parameter count, inference path, read/write
equations, output head all unchanged. Only optimizer groups / warmup / initial slot-key values /
curriculum / temporary alignment loss / diagnostics may differ. The alignment objective adds no
inference-time parameter or operation. No thresholds change after viewing results.
