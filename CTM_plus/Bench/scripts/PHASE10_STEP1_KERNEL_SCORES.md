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

**Gate C — the cost decomposition (sharper than a blind A/B).** Before trusting a
kernel-vs-torch number, find out *where the −37% lives*. The `score_noskip` mode
(added with Step 1) scores on the normal cadence but ALWAYS reads all (no skip, no
gather) — so it isolates scoring cost with quality identical to `off`. Run four
cells in one warm engine:
```bash
# torch scoring (Step-0 path) decomposition:
python Bench/scripts/phase9_p3_fused_needle.py --ab \
  --ab-modes off,score_noskip,retain_all,retention \
  --context-tokens 32768 --max-model-len 34816 --ab-gen 128 \
  --seeds 1,2,3 --depths 0.1,0.5 --repeats 3 --warmup 2 \
  --out Bench/bench_out/PHASE10_AB/decomp_torch_ctx32k.json

# kernel scoring (Step-1 path) — same four cells:
INT4_READSKIP_KERNEL_SCORES=1 python Bench/scripts/phase9_p3_fused_needle.py --ab \
  --ab-modes off,score_noskip,retain_all,retention \
  --context-tokens 32768 --max-model-len 34816 --ab-gen 128 \
  --seeds 1,2,3 --depths 0.1,0.5 --repeats 3 --warmup 2 \
  --out Bench/bench_out/PHASE10_AB/decomp_kernel_ctx32k.json
```
Then the full sweep with kernel scores on:
```bash
INT4_READSKIP_KERNEL_SCORES=1 OUT=./Bench/bench_out/PHASE10_AB_KSCORES \
bash Bench/scripts/phase9_p3_ab_sweep.sh
```

## How to read Gate C (the decision tree)

The paired Δ% vs `off` decompose the cost directly:

| cell | Δ% vs off means |
|---|---|
| `score_noskip` | **scoring** overhead (this is what Step 1 attacks) |
| `retain_all` | **gather-all** tax (full host compaction, no skip) |
| `retention` | the **net** (scoring + gather − skip savings) |

Read it in this order:

1. **Is scoring the bottleneck?** Compare `score_noskip` Δ% with torch vs kernel.
   - torch `score_noskip` Δ% is large AND kernel `score_noskip` Δ% ≈ 0 → **Step 1
     works**: scoring *was* the cost and the kernel removed it. Go to (2).
   - torch `score_noskip` Δ% ≈ 0 already → scoring was *not* the bottleneck; Step 1
     can't help. The cost is the gather (`retain_all` Δ%) → skip to **Step 2**.
2. **With scoring cheap, is the net a win?** Look at kernel `retention` Δ%:
   - crosses **positive** at 16k/32k with quality green → read-skip ships as a
     per-watt-at-density win. (Ceiling: even a win over `off` is ~0.6× bf16 — a
     density play, never faster-than-bf16.)
   - still negative, and `retain_all` Δ% is large → the **host gather** is the
     floor → **Step 2** (in-kernel block-skip removes the gather). If that also
     fails, it's the measured PCAM case (a software floor only hardware breaks).

This is exactly ChatGPT's Stage-A isolation ("score-emission overhead vs baseline,
no blocks skipped") — `score_noskip` *is* that experiment, and it doubles as a safe
offline replay: it records the would-be skip fraction while reading all, so quality
cannot regress while we watch what selection *would* do.

## Caveats

- The Triton kernel is **GPU-unvalidated from the authoring box** (no CUDA here);
  Gate A is its first real test. The accumulation *math* is CPU-proven; the gate
  confirms the Triton port.
- `k_group_size==1` only (the production cache config); other groupings fall back
  to torch scoring automatically.
- Kernel scoring runs only on observe/refresh steps (where it's the cost); steady
  steps are unaffected.
