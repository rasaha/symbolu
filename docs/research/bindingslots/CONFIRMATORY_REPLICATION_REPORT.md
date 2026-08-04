# BindingSlots Confirmatory Replication — report

**Primary verdict:** `CONFIRMATORY_REPLICATION_FAILED`
**Slot formation:** `SLOT_FORMATION_NOT_REPLICATED` · **KDA readiness:** `KDA_VALIDATION_BLOCKED`

The single independent confirmatory replication of the merged, frozen **CR1** BindingSlots
intervention on five previously-unused seeds (13–17), with no tuning, **did not reproduce** the
merged 4/5 holdout result.

## Provenance

| Item | Value |
|---|---|
| Merged prerequisite PR #1300 | MERGED, merge commit `5f0cbe45` |
| Merged prerequisite PR #1319 | MERGED, merge commit `ba665e42` |
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Starting commit | `ba665e42` |
| **Pre-registration commit (pushed before training)** | `1886363b` |
| Working branch | `claude/bindingslots-confirmatory-replication-d117c1` |
| Fresh seeds | **13, 14, 15, 16, 17** (proof: `FRESH_SEED_PROOF.*`) |

## Frozen configuration (unchanged)

CR1 = curriculum (boundaries 300/700/1200; final 500 steps original ABC_MIX) + temporary write-read
alignment (λ 0.10 → 0 by step 600; label-free; no inference-time op). Architecture: hidden 128 ·
heads 4 · layers 4 · local window 64 · **slots 32** · slot-key 64 · seq 160 · batch 16 · **1200
steps** · AdamW lr 2e-3 · wd 0.01 · warmup 60 · clip 1.0 · fp32. Slot arm **2 000 104** params; A+
control **2 000 392**; architecture signature `6e8672bd…`. Full frozen config + 15 verified source
hashes: `experiments/bindingslots_confirmatory/frozen_cr1_config.json`.

## Results (needle@d96, chance ≈ 0.02)

| seed | A+ | B0 | **CR1** | forms | causal | retention |
|---|---|---|---|---|---|---|
| 13 | 0.000 | 0.000 | 0.000 | ✗ | — | FORMED_THEN_COLLAPSED |
| 14 | 0.000 | 0.000 | 0.000 | ✗ | — | FORMED_THEN_COLLAPSED |
| 15 | 0.000 | 0.000 | 1.000 | ✓ | clean | FORMED_AND_RETAINED |
| 16 | 0.008 | 0.000 | 1.000 | ✓ | **unclean** | FORMED_AND_RETAINED |
| 17 | 0.000 | 0.000 | 1.000 | ✓ | clean | FORMED_AND_RETAINED |
| **formed** | 0/5 | **0/5** | **3/5** | | | |

Mean(CR1−A+) d96 **0.598**, median **0.992**, paired wins vs A+ **3/5**.

## Mechanical classifier

| gate | result | | gate | result |
|---|---|---|---|---|
| C1 form ≥ 4/5 | **FAIL (3/5)** | | C7 distance | PASS |
| C2 form > B0 | PASS (3>0) | | C8 slots-off | PASS |
| C3 wins ≥ 4/5 | **FAIL (3/5)** | | C9 randomized-address | **FAIL (seed 16)** |
| C4 mean margin | PASS (0.598) | | C10 integrity+param | PASS |
| C5 median margin | PASS (0.992) | | C11 no deviation | PASS |
| C6 quality | PASS | | | |

**Two independent scientific failures:** formation reliability (C1/C3) and causal cleanliness (C9).
Details in `CONFIRMATORY_REPLICATION_RESULTS.md`, `CONFIRMATORY_CAUSAL_ANALYSIS.md`,
`CONFIRMATORY_RETENTION_ANALYSIS.md`.

## Causal-ablation results (forming seeds)

| seed | baseline | slots-off | randomized-address | gate |
|---|---|---|---|---|
| 15 | 1.000 | 0.000 | 0.000 | clean |
| 16 | 1.000 | 0.017 | **0.450** | **unclean** |
| 17 | 1.000 | 0.000 | 0.000 | clean |

## Distance & quality

- Distance: d16 no material regression; all 3 formed-and-retained seeds keep positive CR1−A+ at
  d220 (`distance_gate_output.json`).
- Quality: mean CR1 ppl@256 **135.55** ≤ 1.20 × A+ **142.10**; 0/5 exceed A+ by > 25 %
  (`quality_gate_output.json`).

## Retention trajectories

Seeds 13 & 14 peaked at 1.000 (step 300), held at step 600, then decayed to 0.000 by step 1200 after
λ → 0 and the curriculum handoff — the **same signature** as the merged seed 9, now on 2/5 fresh
seeds. Full trajectories: `CONFIRMATORY_RETENTION_ANALYSIS.md` /
`results/retention_diagnostics.json`.

## Integrity

- Confirmatory pre-registration integrity: **30 checks, 0 failures** (before and after training).
- Frozen `abc.json` `b31989a3…` **unchanged** before and after (recorded in `results/manifest.json`).
- Lab verifier 81/0; historical-artifact protection 8/0; 31 confirmatory tests pass.
- **Protocol deviations: none.** No schedule/architecture/optimizer/task/threshold change. No
  best-checkpoint selection. No outcome-based seed replacement. 1 orchestrator start event, 0
  infrastructure restarts.

## Environment

Python 3.11.15, torch 2.2.2+cu121, CPU, fp32, threads=4. The merged run used a different torch build;
the frozen protocol pins the optimizer/schedule, not the torch build, and the seeds are new, so this
is recorded as a documented environment factor, **not** a `CONFIRMATORY_ENVIRONMENT_MISMATCH`. The
environment was fully capable of running the frozen fp32 CPU code; the failure is scientific, not
infrastructural.

## Final scientific claim

> Under the frozen synthetic retrieval protocol, the merged CR1 intervention **did not
> independently replicate** its 4/5 slot-formation result on an independent five-seed set (13–17): it
> forms-and-retains only 3/5, one of the three formers is not cleanly slot-causal, and the
> post-scaffold retention-collapse mode recurred on 2/5 seeds.

## Explicit non-claims

This result does **not** show that CR1 never works (it retains clean slot formation on 2/5 seeds), and
does **not** prove general LM benefit, natural-language transfer, production readiness,
architecture-wide stabilization, long-horizon retention, transfer across slot count / sequence length
/ model scale, KDA superiority, or any inference-speed or memory benefit. It is **not** reframed as
success because some seeds formed transiently. See `CONFIRMATORY_LIMITATIONS.md`.

## Next phase

`KDA_VALIDATION_BLOCKED` → **BindingSlots Retention Development** (new preregistered comparison of
slower λ decay, residual alignment, and consolidation, under the same causal gate). Not started here.
See `KDA_READINESS_DECISION.md` and `NEXT_VALIDATION_LADDER.md`.

## Metadata note

For the record, the merged compiler package state is **distribution 0.2.0 / product 0.2.0 /
workflow_ir.v1 digest semantic identity 0.1.0** (no stale compiler documentation was copied into this
phase).
