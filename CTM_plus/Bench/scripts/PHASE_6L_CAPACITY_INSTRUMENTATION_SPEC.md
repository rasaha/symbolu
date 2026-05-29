# Phase 6L — KV block capacity instrumentation and live-concurrency demo

> **Status:** instrumentation implemented in `phase6l_capacity_demo.py`;
> selftest 7/7 PASS. GPU capture pending — this is the only open claim in the
> VC brief. Everything else (quality, correctness, slot lifecycle) is locked.

## Claim under test

> "Protected int4 is quality-positive and **capacity-density-positive**: despite a
> +4.7 GB sidecar tax, it demonstrates approximately ~1.8× live long-context
> concurrency per GB before KV block starvation compared with bf16."

The `~1.8×` is currently a **vLLM block-budget calculation** (phase6k14's
`density_ratio`), not a measured serving result. This phase makes it empirical.

## Why block-budget ≠ demonstration

`vLLM max_concurrency = (num_gpu_blocks × block_size) / mml` is a static
calculation from the block allocator at init time. It does not prove that:

1. **Sequences were actually resident simultaneously** — `llm.generate(B)` is a
   blocking call that queue-drains in scheduling waves if B > allocatable
   concurrency; peak submitted B tells you nothing about peak live concurrency.
2. **The block pool was the binding constraint** — if max_tokens is small,
   sequences complete before the pool fills and no pressure is ever observed;
   `peak_live = B` would be spurious.
3. **The density ratio holds under decode pressure** — sidecars are allocated
   per-sequence during prefill; the tax must be observed in real block accounting.

**CEILING_NOT_REACHED**: if a run completes with `peak_util < 90%` and no
waiting/swapping/preemption, the block limit was never approached. `peak_live`
from such a run is **not demonstrated** — it is only a floor.

## What phase6k14 already measures (reused directly)

Phase 6K.14's `_StepProbe` wraps `LLMEngine.step` and samples after every
decode step: `n_running`, `n_waiting`, `n_swapped`, `blocks_free`,
`blocks_total`. It computes:

- `peak_live` — max simultaneous sequences in `scheduler.running`
- `avg_live` — mean live seqs across steps
- `peak_util` — max fraction of block pool in use
- `saturation_observed` — `peak_util ≥ 0.90 OR preempts > 0 OR OOM`
- `resident_fit` — estimated max simultaneously resident seqs for this workload

Phase 6L reuses these unchanged. All that's needed is the analysis layer.

## What phase6l adds

### `seq_per_kblock` density metric

```
seq_per_kblock = demonstrated_live_seqs / (total_blocks / 1000)
```

`total_blocks` already reflects the KV memory budget (vLLM allocates as many
blocks as fit in `gpu_memory_utilization × HBM`; sidecars reduce this for
protected). So `seq_per_kblock` is proportional to `seq / GB of KV capacity`
without needing per-quant-type byte arithmetic. It accounts for the sidecar tax
through `total_blocks` alone.

### `demonstrated_density_ratio`

```
demonstrated_density_ratio = prot_seq_per_kblock / bf16_seq_per_kblock
```

Computed only when **both** cells have `saturation_observed=True` (both hit the
block limit). If either has `CEILING_NOT_REACHED`, the ratio is None and the
claim is inconclusive.

### Acceptance criteria

| condition | outcome |
|---|---|
| `demonstrated_density_ratio` in `[1.5, 2.5]`, both cells saturated | **DEMONSTRATED** ✓ |
| ratio computed but outside `[1.5, 2.5]` | **MEASURED — outside expected window** |
| either cell CEILING_NOT_REACHED | **INCONCLUSIVE — raise B / max_tokens** |
| slot-exhaustion in any run | **INVALID — 6K.14 regression** |

The claim is validated if ratio ≈ 1.8× (`[1.5, 2.5]` window).
The claim is falsified if ratio is measured and < 1.5× (the sidecar tax erases
the block-packing advantage on this model / mml).

## Run protocol

```bash
# Phase 6L capacity demo — both cells, resident-pressure mode.
# max-tokens=512 is the minimum to hold sequences resident long enough to
# observe block pressure. Use 1024 if the pool still doesn't saturate at 512.
# B-list should straddle the estimated bf16 max_conc and 2× that.
# At mml=8192, gpu_util=0.5: bf16 est~55, so straddle 48–160.
PHASE6K10_AUTO_HOOK=0 python CTM_plus/Bench/scripts/phase6l_capacity_demo.py \
  --compare \
  --model Qwen/Qwen2.5-7B-Instruct \
  --mml 8192 \
  --max-tokens 512 \
  --prompt-frac 0.95 \
  --gpu-util 0.5 \
  --b-list 48,72,96,128,160 \
  --out-dir /tmp/phase6l \
  2>&1 | tee /tmp/phase6l.log

# CPU only — selftest:
python CTM_plus/Bench/scripts/phase6l_capacity_demo.py --selftest

# Re-print table from saved JSONs (no re-run):
python CTM_plus/Bench/scripts/phase6l_capacity_demo.py \
  --from-jsons /tmp/phase6l/*.json
```

## Expected outcomes

**If DEMONSTRATED (ratio ≈ 1.8×):**
```
Final claim: "Protected int4 is quality-positive and capacity-density-positive:
despite a +4.7 GB sidecar tax, it demonstrates ~1.8× live long-context
concurrency per GB before KV block starvation compared with bf16."
```

**If NOT DEMONSTRATED (ratio < 1.5× or CEILING_NOT_REACHED):**
```
Final claim: "Protected int4 improves quality (+20.4 pt token-agreement over
naive int4). The live serving-density claim is not demonstrated; the vLLM
block-budget estimate did not translate into observed sustained concurrency."
Fall back to density framing (~1.8× seq/GB from block budget) as a
theoretical estimate, not an empirical result.
```

## Files

- `CTM_plus/Bench/scripts/phase6l_capacity_demo.py` — analysis layer + GPU
  driver (subprocess-calls phase6k14's `--worker`); `--selftest` (CPU),
  `--compare` (GPU), `--from-jsons` (CPU re-print).
- `CTM_plus/Bench/tests/test_phase6l_capacity_demo.py` — pytest-collectable
  CPU regression (7 cases; mirrors the `--selftest` but with independent data).
- `CTM_plus/Bench/scripts/phase6k14_saturation.py` — unchanged; provides
  `_StepProbe`, `run_worker` (called via subprocess), `_analyze`.
- Output: `/tmp/phase6l/*.json` (one per cell×B) + `/tmp/phase6l/report.json`.
