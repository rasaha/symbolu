# Phase 6 long-context HBM crossover bench: findings

> **Status:** MEASURED. Verdict drives Phase 6G + 6H scoping; Phase
> 6F kernel surgery remains halted per the stated decision criterion.
>
> **One-sentence result:** int4_protected captured does NOT win HBM
> at any tested `max_model_len` (8K/16K/32K) at low B (1-8), losing
> by ~5 GB consistently; but vLLM's `max_concurrency` reports int4 =
> 2× bf16 at every length — the 2× advantage is real for high-load
> deployments and unmeasured at the bench's swept B values.

## Setup

* Model: Qwen2.5-7B-Instruct.
* Hardware: A100 80GB SXM.
* Bench: `bench_phase6_long_context_gpu.py` (commits `2781ea5` +
  `41afcb9` + `1fb05f6`).
* Cells: stock vLLM bf16 (`enforce_eager=False`) vs int4_protected
  captured (`enforce_eager=False` + `PHASE6E_FUSED_WRITER=1`).
* Sweep: `max_model_len ∈ {8192, 16384, 32768}`, `B ∈ {1, 2, 4, 8}`,
  `n_runs=3`, `max_tokens=32`, `gpu_memory_utilization=0.5`,
  `max_num_seqs=16`.

The bench's first attempt (`gpu_memory_utilization=0.85`,
`max_num_seqs=256` defaults) OOM'd during int4 captured-graph
capture at every `max_model_len`. Root cause:
`_read_decode_packed_batched`'s `kv_cache[0][block_ids_long]`
gather materializes a `(B, max_blocks_per_seq, BS, H, D)` uint8
intermediate at every captured shape. At B=256, max_model_len=8K:
`256 × 256 × 32 × 4 × 128 = 1 GB` per gather, blowing the budget.
Fix: lower `gpu_memory_utilization` to 0.5 and bound
`max_num_seqs` to 16 (the bench only sweeps B≤8). Re-run succeeded.

## Results

### HBM after init

| max_model_len | bf16 (GB) | int4 (GB) | delta | int4 wins HBM? |
|---|---|---|---|---|
| 8192  | 39.13 | 44.22 | **+5.09** | no |
| 16384 | 38.04 | 42.72 | **+4.68** | no |
| 32768 | 35.85 | 40.51 | **+4.66** | no |

int4 uses MORE measured HBM than bf16 at every length. The delta
is roughly constant (~5 GB) and not strongly context-dependent.

### vLLM `max_concurrency` (reported by engine init)

| max_model_len | bf16 | int4 | ratio |
|---|---|---|---|
| 8192  | 55.3 | 110.6 | **2.0×** |
| 16384 | 26.4 | 52.8  | **2.0×** |
| 32768 | 12.0 | 23.9  | **2.0×** |

vLLM reports int4 has exactly 2× the concurrency capacity of bf16
at every length. This is the per-token-cache-cost halving (int4's
`block_size=32` vs bf16's `block_size=16` at the same byte budget).

### Throughput (median agg_tps at B=8)

| max_model_len | bf16 | int4 | int4/bf16 |
|---|---|---|---|
| 8192  | 74.2 | 48.6 | 0.66× |
| 16384 | 38.1 | 28.5 | 0.75× |
| 32768 | 18.0 | 14.0 | 0.78× |

int4 is consistently 0.66-0.78× of bf16. **The ratio improves with
context length** (0.66× at 8K → 0.78× at 32K) — better than the
0.20× we saw at `max_model_len=4K` in the Phase 6E throughput
bench. At long context, the relative per-token cost difference
matters less; the writer's fixed overhead is amortized.

### Quality sanity

Both cells produced 0/3 quality passes (containing the embedded
answer "1742") at every (mml, B). bf16 fails identically to int4
→ this is **a measurement artifact, not a quality signal**.
Greedy decode at `max_tokens=32` produces elaboration without
reaching the year. Not informative either direction.

### Preemption events

Zero across the sweep. B=8 is far below the smaller cell's
(bf16's) max_concurrency at every length, so vLLM never enters
the saturation regime where preemption fires.

## Root cause of the HBM delta

vLLM's KV cache budget tracks only `kv_cache[0]` and `kv_cache[1]`
(the `(NB, BS, H, D)` uint8 tensors). The int4_protected writer's
`_lazy_alloc` adds five per-layer sidecar tensors **on top of**
that budget:

* `v_scale_ext`: `(NB, BS, H, n_groups=4)` bf16 — per-token per-group
* `v_xmin_ext`: same — per-token per-group
* `k_scale_ext`: `(NB, H, D)` bf16 — per-block per-D (smaller)
* `k_xmin_ext`: same — per-block per-D
* `k_protect_ext`: `(NB, BS, H, n_protect=5)` bf16 — per-token
  per-protect-channel

Aggregate at NB≈26K, 28 layers (Qwen-7B): **~3.9 GB** of sidecars.
With vLLM's working buffers + activation differences, total
delta lands at the observed ~5 GB.

## The contradictory-looking result, explained

vLLM thinks int4 has 2× concurrency because the BLOCK SIZE
(`block_size=32` for int4 vs 16 for bf16) is 2× at the same
byte budget. Each int4 block holds twice as many tokens'-worth
of packed data. This is correct per-token.

But the **same number of bytes** are allocated to the KV cache in
both cells. int4's logical-per-token saving is offset by the
sidecars, and the sidecars sit outside vLLM's accounting. Net: int4
LOSES on measured HBM at low B (where sidecar overhead dominates
the per-token savings) but WINS in vLLM's bookkeeping (which only
counts the cache, where the per-token cost is half).

**At high B (saturation):**
* bf16 max_concurrency = 55 at 8K. At B=55 max-len requests, the
  bf16 cache is 100% utilized.
* int4 max_concurrency = 110 at 8K. At B=110, int4 cache is also
  100% utilized — but it's serving 2× the requests in the same
  KV bytes.

So **at saturation**, int4 serves 2× the requests with the same
cache budget, plus the fixed ~5 GB sidecar overhead. **At low B**,
int4 serves the same handful of requests but pays the fixed
overhead. The crossover depends on B; the bench's low-B sweep
sits on the wrong side of it.

## Verdict per the user's stated decision tree

> If int4 does not win HBM even at long context, do not pursue
> heavy kernel work yet.

**NOT_JUSTIFIED.** Halt Phase 6F kernel surgery.

But the result is more nuanced than "int4 loses":

* **At low B (chatbot, single-user inference)**: int4 loses on
  both HBM and throughput. The protect-mask sidecars dominate.
* **At high B (production-scale serving)**: int4 should win on
  capacity (concurrent requests per GB of KV budget) — but we
  haven't measured this directly.

## Next priorities

Two follow-on workstreams, both scoped before any kernel work:

1. **Phase 6G (Sidecar diet)** —
   `PHASE_6G_SIDECAR_DIET_DESIGN.md`. Tensor-by-tensor audit
   followed by stack of reductions (group_size, n_protect, fp8
   sidecars) to shrink the ~5 GB delta. Acceptance: int4 measured
   HBM ≤ bf16 at 16K/32K, or ≥40% sidecar reduction with quality
   intact.

2. **Phase 6H (High-load capacity bench)** —
   `PHASE_6H_HIGH_LOAD_CAPACITY_DESIGN.md`. Bench at B values near
   and above bf16's max_concurrency to test whether int4's
   reported 2× translates to actual completed-load capacity, or
   whether the sidecars cause it to OOM at the same B bf16 does.
   Acceptance: int4 completes ≥1.5× the requests bf16 does at
   high B. Run BEFORE and AFTER Phase 6G to measure both
   baselines.

## What this does NOT change

* **Phase 6E remains shipped** behind `PHASE6E_FUSED_WRITER=1`.
  Byte-eq correctness gate still holds.
* **VC brief**: do not edit until 6G + 6H both land measured
  outcomes.
* **No HBM win claim** until 6G data is in.
* **Phase 6F**: halted; restart only after 6G + 6H evidence.

## Bench artifact

* `bench_out/phase6_long_context/cell_bf16_mml{8192,16384,32768}.json`
* `bench_out/phase6_long_context/cell_captured_mml{8192,16384,32768}.json`
* `bench_out/phase6_long_context/long_context_report.{json,txt}`

These contain the full per-B metrics + scheduler stats for both
cells. The next session can rerun with diet-applied builds and
diff against these baselines.
