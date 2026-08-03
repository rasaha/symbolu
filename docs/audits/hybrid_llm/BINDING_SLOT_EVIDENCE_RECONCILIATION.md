# Binding-Slot Evidence Reconciliation

**Date:** 2026-08-03 · Follows: Hybrid LLM audit PR #1294 (merged) · Machine-readable twin:
[`artifacts/binding_slot_evidence_reconciliation.json`](artifacts/binding_slot_evidence_reconciliation.json)

## Why this document exists

The merged audit correctly excluded **Phase** from packaging, but its wording created an
imbalance around **bounded binding slots**. The audit is **not** to be read as "slots failed."
Slots produced the **only demonstrated long-range retrieval improvement** in the internal
matched experiments, and the improvement was **causally attributable to the slots** — that is
meaningful positive evidence, not a null result.

**Corrected status:**

```
INTERNALLY_SUPPORTED_WORKING_CANDIDATE_AT_TESTED_SCALE
```

Do **not** classify bounded slots as failed / decorative / unsupported. Do **not** classify
them as production-ready / package-ready. Both are wrong.

## Demonstrated (from `experiments/phase_lc/results/abc.json`, 1200 steps, batch 16, 3 seeds)

| # | Demonstrated | Evidence |
|---|---|---|
| 1 | Slots improved long-range **single-fact** retrieval at the tested scale | C-arm needle@d96 mean **0.156** vs A/B ≈ 0.00; seed-0 **0.467** (chance ≈ 0.02) |
| 2 | The gain was **causally attributable to slots** | slots-off (`ablate='zero'`) seed-0 **0.467 → 0.017** |
| 3 | Disabling slots **removed** the capability | same (near chance) |
| 4 | Randomizing slot **addresses** removed the capability | `rand_keys` seed-0 **0.467 → 0.050** |
| 5 | Removing **Phase** did **not** remove the slot result | `phase_off` seed-0 **unchanged 0.475** — the learned addressable memory, not Phase, carried it |
| 6 | The mechanism used **no** global sequence-quadratic attention | `no_nxn_check.slots_builds_NN = false` in every record |
| 7 | Slot memory stayed **bounded** in sequence length | slot state = 16,384 floats (32 slots × 128 × 4 layers), independent of N |

This is exactly the causal signature the audit's own evidence ledger recorded (C6): the gain
appears with slots on, vanishes with slots off, vanishes with randomized addresses, and is
independent of Phase.

## Not yet demonstrated robustly

| Item | Evidence |
|---|---|
| Reliable formation across **all** seeds | needle@d96 per seed **0.467 / 0.000 / 0.000** → forms in **1 of 3** |
| Multi-entity binding | k=2/4/8 ≈ 0.089 / 0.025 / 0.036 (chance) |
| Supersession (learned) | current-acc 0.025 / stale-error 0.036 (chance) — *the mechanism supports it; the learned model did not realize it at this scale* |
| Source attribution (learned) | 0.047 (chance) |
| Contradiction / multi-hop | ≈ chance |
| Meaningful-scale LM training | max ~2M params, CPU, 1200 steps |
| Production inference / enterprise deployment | none |

**The limitation is scope and stability — single-fact, 1/3 seeds, relational tasks not yet
learned — not "slots did not work."**

## One correction of the record

The report's headline "**1800-step / batch-24 run → needle 1.00**" is **prose-only and
`NOT_FOUND`** as any saved artifact (the only saved A/B/C run is 1200 steps / batch 16). The
reproduction target is therefore the **saved 1200-step per-seed numbers**; the 1.00 figure is
explicitly **excluded** from the reproduction gate rather than treated as an established result.

## Mechanism vs learning (the honest boundary)

- The **discrete slot mechanics** — content addressing, supersession with version bump, source
  retention, LRU eviction, bounded O(M) state, and the no-`[N,N]` guarantee — are **reproduced
  deterministically** by the stdlib reference in `hybrid_llm_vnext_lab/` (36 tests pass here,
  no PyTorch). At the mechanism level, single-fact recall, multi-fact recall, supersession,
  source attribution, distractor resistance, and eviction **all pass**.
- Whether **SGD learns** the projections that realize those capabilities under training is the
  separate neural question: **single-fact partially demonstrated (1/3 seeds)**, relational
  capabilities **not yet**, and re-running it is **`RESOURCE_BLOCKED`** in this environment (no
  torch). The lab's reproduction harness pins the exact original parameters for that run.

**Corrected slot maturity:** `HISTORICAL_RESULT_ONLY` (neural) + `REPRODUCED` (discrete
mechanics). The next gate is **multi-seed stability** of the *learned* result — pre-registered
in the lab, to run only after neural reproduction parity.
