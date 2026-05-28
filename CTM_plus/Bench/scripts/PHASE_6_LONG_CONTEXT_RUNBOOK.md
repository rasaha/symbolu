# Phase 6 — long-context HBM crossover bench: runbook

## Purpose

Find the `max_model_len` at which int4_protected captured becomes
HBM-cheaper than stock vLLM bf16, if such a crossover exists.

Decides whether **Phase 6F kernel optimization** is justified or whether
the project should be reframed as a memory/quality backend instead.

## Run

On the GPU pod (A100 80GB):

```bash
source /workspace/venv-vllm/bin/activate
cd /workspace/symbolu

# Default sweep: max_model_len ∈ {8K, 16K, 32K}, B ∈ {1, 2, 4, 8}.
# Two cells (bf16 + int4 captured). 2 cells × 3 max_model_len = 6
# subprocess invocations, each loading the model fresh. Allow ~30-45 min.
PHASE6E_FUSED_WRITER=1 python CTM_plus/Bench/scripts/bench_phase6_long_context_gpu.py
```

The `PHASE6E_FUSED_WRITER=1` env enables the Phase 6E fused kernels
for the int4 captured cell. The bf16 cell ignores it.

### Smaller smoke run (if pod budget is tight)

```bash
# Single max_model_len, single B, both cells — about 10 min.
PHASE6E_FUSED_WRITER=1 python CTM_plus/Bench/scripts/bench_phase6_long_context_gpu.py \
    --max-model-lens 16384 \
    --batch-sizes 1,4 \
    --n-runs 2
```

### Single-worker (one cell + one mml) — internal/debug

```bash
PHASE6E_FUSED_WRITER=1 python CTM_plus/Bench/scripts/bench_phase6_long_context_gpu.py \
    --worker --cell captured --max-model-len 16384 \
    --output /tmp/cap_16k.json --batch-sizes 1,2,4,8
```

## What gets collected per (cell, max_model_len)

* **HBM**: pre-load + post-init + peak during sweep + delta. Both
  `allocated` and `reserved` are captured; `used` (= total - free
  from CUDA's `mem_get_info`) is what the verdict report uses.
* **vLLM KV cache config**: `num_gpu_blocks`, `block_size`,
  `max_concurrency` (= blocks × block_size / max_model_len — the
  "Y x" number vLLM prints at init: "Maximum concurrency for N tokens
  per request: Y x").
* **Throughput per B**: median wall_s + n_output_tokens + agg_tps over
  n_runs (default 3).
* **Preemption/swap events**: from vLLM's scheduler counters before
  and after the sweep. Best-effort across vLLM versions.
* **Quality sanity**: long synthetic prompt contains "1742" as the
  embedded answer (the year a fictional town's library was founded).
  Each run checks "does ANY output in the batch contain '1742'".
  Reported as `quality_passes / n_runs` per (cell, max_model_len, B).
  Greedy decode, max_tokens=16; a miss usually means KV cache fidelity
  has degraded (not a guarantee, since 16 tokens of decode may not
  reach the answer even with perfect KV).

## How to interpret the verdict

The driver writes `long_context_report.txt` and emits a one-word verdict:

| Verdict | Meaning | Next step |
|---|---|---|
| `JUSTIFIED` | int4 wins HBM at some `max_model_len` with quality intact AND throughput within 0.5× of bf16 at B=8 at that length. | **Phase 6F kernel optimization is justified.** Close the throughput gap; the memory story holds. |
| `NOT_THROUGHPUT_ACCELERATOR` | int4 wins HBM (quality OK) but throughput is below 0.5× of bf16 at the crossover point. | Reframe the project as a long-context **quality + memory** backend, not a throughput accelerator. 6F kernel work is still possible but the protect-mask story stands on memory alone. |
| `QUALITY_DEGRADED` | int4 wins HBM but the quality sanity check fails at the crossover length. | Investigate the quality regression before claiming the memory win. Could be a long-context-specific bug in the writer / reader, or a sidecar precision issue. |
| `NOT_JUSTIFIED` | int4 NEVER beats bf16 on HBM across the sweep. | **Do not pursue Phase 6F kernel work yet.** The protect-mask design hasn't demonstrated a memory advantage to motivate the engineering cost. |

## Decision tree

```
                  int4 wins HBM at some mml?
                    /                      \
                  no                        yes
                  |                          |
        NOT_JUSTIFIED              quality intact at crossover?
       (halt 6F kernel work)        /                       \
                                  no                        yes
                                  |                          |
                          QUALITY_DEGRADED        cap_tps / bf16_tps ≥ 0.5
                          (debug quality first)    at B=8 at crossover?
                                                  /                      \
                                                no                        yes
                                                |                          |
                                  NOT_THROUGHPUT_ACCELERATOR        JUSTIFIED
                                  (memory-only narrative)       (proceed with 6F)
```

## Expected HBM behavior (priors)

At `max_model_len=4K` (Phase 6E throughput bench result):
* bf16: 38.52 GB
* int4 captured: 45.22 GB
* int4 is **6.7 GB HEAVIER** — losing on HBM.

The int4 cache stores the SAME number of uint8 bytes as bf16 (the
unified `(NB, BS, H, D)` uint8 layout reserves D bytes per token regardless
of whether int4 uses only the first D/2). Int4 adds sidecars
(`v_scale_ext`, `v_xmin_ext`, `k_scale_ext`, `k_xmin_ext`,
`k_protect_ext`) which are per-block per-head fixed overhead. At
short context the sidecar overhead dominates; at long context the
linearly growing KV cache should make int4 cheaper IF the layout
actually shrinks at long context (TBD).

If int4 doesn't crossover by `max_model_len=32K`, the conclusion is:
the current cache layout (uint8 D bytes per token, half wasted under
int4) needs structural fixing — vLLM's cache allocator would need to
actually allocate D/2 bytes per token when `kv_cache_dtype="int4_protected"`
is set. That's a separate workstream (vLLM core change, not in the
Phase 6 plan).

## Pod cost estimate

Default sweep: 6 subprocess invocations (3 mml × 2 cells). Each:
* Model load: 14-50s (captured cells include CUDA graph capture).
* Warmup: ~5s.
* Sweep (4 B's × 3 runs × prompt-time): 30-180s depending on
  max_model_len.
* Total per subprocess: ~1-4 min.

**Full sweep: 10-25 minutes of pod time.** A100 80GB at ~$2/hr
amortized is **<$1**.

## Output

```
bench_out/phase6_long_context/
├── cell_bf16_mml8192.json
├── cell_bf16_mml16384.json
├── cell_bf16_mml32768.json
├── cell_captured_mml8192.json
├── cell_captured_mml16384.json
├── cell_captured_mml32768.json
├── long_context_report.json     # machine-readable verdict + tables
└── long_context_report.txt      # human-readable verdict + tables
```

The driver exit code:
* `0` → verdict is `JUSTIFIED`, `NOT_THROUGHPUT_ACCELERATOR`, or `QUALITY_DEGRADED`.
* `1` → verdict is `NOT_JUSTIFIED`. Halt Phase 6F.

## Per the user spec

> Do not edit the VC brief until the long-context crossover data lands.

The verdict from this bench is the gating signal for whether the
brief should claim throughput parity (NOT_JUSTIFIED or NOT_THROUGHPUT_ACCELERATOR
means "no"), or whether to invest in kernel surgery to close the
throughput gap (JUSTIFIED means "yes").
