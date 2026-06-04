# Phase 10 Step 1 — kernel-emitted block scores (the measured bottleneck's fix)

> **Why:** the Step-0 sweep proved read-skip throughput is negative and gets
> **worse** with context (−31% @8k → −37% @32k), because the OBSERVE-step scorer
> `ProtectedKINT4Cache.block_attention_scores` reconstructs the **whole K** in eager
> torch (`unpack_int4` + dequant + protect-overlay + matmul over all `s`) — an
> O(s) cost that grows with length, on ~15 observe steps per 128-token decode.
> Step 1 replaces that with a **single fused Triton pass** that reuses the decode
> kernel's int4 unpack. This is the only remaining software lever; the bottleneck
> is exactly what it removes.

## What changed (CPU-side, committed)

- `int4_fused_attention_kernel.py`:
  - `fused_protected_k_block_scores(q, k_packed, k_scale, k_offset, k_fp16,
    protect_mask, …)` + the Triton `_protected_k_block_scores_kernel` — one program
    per (KV head, block), reads the cache's **native (S, H, *) buffers** (no
    permute/copy), unpacks int4 exactly like the decode kernel, and emits each
    block's **local** `(sum_exp, max)`.
  - `combine_block_scores(blk_sum, blk_max)` — host rescale by the per-head global
    max + normalise + sum over KV heads → the `block_attention_scores` contract.
  - **Correctness is by construction:** each block is scored block-locally, and
    the decomposition (per-block max+sum-exp → global rescale → normalise) is
    **exactly** a softmax-then-block-sum. Proven in numpy, no GPU:
    ```
    python CTM_plus/KVPolicy/kv_policy/int4_fused_attention_kernel.py
    # -> block-scores numpy proof (decomposition == direct softmax): PASS
    ```
- `int4_protected_k_cache.py`: `block_attention_scores(…, use_kernel=False)` — when
  `use_kernel` and CUDA/Triton are available (and `k_group_size==1`), takes the
  kernel path; **fail-open** to the torch reference on any error.
- `int4_cache_kv_route_a.py`: opt-in via env `INT4_READSKIP_KERNEL_SCORES=1`
  (read at install; surfaced in `manager.stats['readskip_kernel_scores']` and the
  `--ab` JSON/print).

## Validate on the pod (gates, in order)

**Gate A — kernel == torch (correctness).** Self-contained, no vLLM:
```bash
cd /workspace/symbolu && git pull origin claude/bold-johnson-rXAd4 && git log -1 --oneline
cd CTM_plus
python Bench/scripts/test_block_scores_gpu.py
# expect, per s in {200,2000,8000,16000}: maxdiff ~1e-3, top8_overlap=8/8 -> PASS
```
If `maxdiff` is large or the top-k overlap < 8/8, **stop** — the kernel diverges
from the reference; do not trust a throughput number from it.

**Gate B — quality holds with kernel scores.** Re-run the A/B at one length with
`INT4_READSKIP_KERNEL_SCORES=1`; retention quality must stay 1.0 where off is 1.0
(the kernel selection must match the torch selection):
```bash
INT4_READSKIP_KERNEL_SCORES=1 INT4_READSKIP_SINK=64 INT4_READSKIP_RECENT=512 INT4_READSKIP_BUDGET=512 \
python Bench/scripts/phase9_p3_fused_needle.py --ab \
  --context-tokens 16384 --max-model-len 18432 --ab-gen 128 \
  --seeds 1,2,3 --depths 0.1,0.5 --repeats 3 --warmup 2 \
  --out Bench/bench_out/PHASE10_AB/ab_ctx16384_kscores.json
# the [ab] header should print kernel_scores=True
```

**Gate C — does it move throughput?** Full sweep with kernel scores on, compared
to the Step-0 (torch-scoring) sweep:
```bash
INT4_READSKIP_KERNEL_SCORES=1 OUT=./Bench/bench_out/PHASE10_AB_KSCORES \
bash Bench/scripts/phase9_p3_ab_sweep.sh
```

## How to read Gate C (the decision)

Compare the paired Δ% trend vs the Step-0 (torch-scoring) baseline:

| ctx | Δ% torch-scoring (Step 0) | Δ% kernel-scoring (Step 1) |
|---|---:|---:|
| 8k | −31.2% | ____ |
| 16k | −34.0% | ____ |
| 32k | −37.2% | ____ |

- **Δ improves AND no longer worsens with length** → the observe scorer *was* the
  bottleneck; if it crosses to a WIN at 16k/32k with quality intact, read-skip
  ships as a per-watt-at-density software win. (Ceiling reminder: even a win over
  `off` lands ~0.6× bf16 — a density play, not faster-than-bf16.)
- **Δ still negative and still worsens with length** → the per-step decision /
  host gather is the floor, not the torch scorer. Then Step 2 (in-kernel
  block-skip, removes the host gather) is the last software lever; if that also
  fails, it's the measured PCAM case (a software floor only hardware breaks).

## Caveats

- The Triton kernel is **GPU-unvalidated from the authoring box** (no CUDA here);
  Gate A is its first real test. The accumulation *math* is CPU-proven; the gate
  confirms the Triton port.
- `k_group_size==1` only (the production cache config); other groupings fall back
  to torch scoring automatically.
- Kernel scoring runs only on observe/refresh steps (where it's the cost); steady
  steps are unaffected.
