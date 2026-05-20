# Kernel 6c.3 — vLLM end-to-end integration & measurement runbook

Status: 6c.2 closed **GREEN for kernel viability** (§20.6.2). 6c.3 is
the gate that converts the one-layer-microbenchmark win into an
end-to-end product claim — or surfaces that it doesn't translate.

Until 6c.3 lands, *"protected-K beats FP8"* remains unproven.

## Goal

Measure whether the §20.6.2 single-attention-layer FP16-parity-at-16k /
win-at-32k–64k translates to real vLLM serving. Specifically:

1. End-to-end **decode tokens/sec** for four cells: vLLM FP16, vLLM
   FP8, route-A protected-K (naive dequant fallback), and route-A with
   the fused 6c.2 kernel.
2. **Actual peak GPU memory** + KV bytes/token/layer at multiple
   context lengths.
3. **Long-context quality sanity** — re-run the §20.4 needle harness on
   the real vLLM-with-kernel pipeline; confirm 100% needle still holds.

## Scope

**In:**
- Wire kernel 6c.2 into route-A's `Attention.forward` replacement.
- Add a runtime flag to select the kernel path.
- GPU-verify route-A on Qwen2.5-7B (§20.5 Days 4–5 pending).
- The §20.1-style four-cell throughput comparison.
- §20.4 needle eval on the real vLLM-route-A-fused pipeline (16k + 32k tokens).
- Memory measurement.

**Out (per "no algorithm changes until 6c.3 lands"):**
- New algorithmic features — decode-stability calibration,
  query-relevance mask, pre-RoPE, Hadamard rotation, QJL/TurboQuant,
  hybrid bit-width.
- More kernel micro-optimisation rounds (e.g. short-context tuning at
  S_kv ≤ 4k).
- FP4/NVFP4 work (no Blackwell access).
- Models beyond Qwen2.5-7B (Mistral / Llama come after the primary
  Qwen numbers land cleanly).

## Prerequisites

- **venv-vllm** environment: vLLM 0.7.3, transformers 4.48.3 (per
  `ROUTE_A_VLLM_CACHE_KV_PLAN.md` and the §20.1 `FP8_INT4_THROUGHPUT_RUNBOOK.md`).
  The kernel itself also needs Triton + a recent torch on CUDA — verify
  the venv-vllm env has Triton (it should, via the torch wheel).
- **A100 80 GB** strongly recommended — FP16 baseline at S_kv = 32k tokens
  on Qwen2.5-7B with vLLM's full KV pool exceeds 40 GB once weights are
  loaded.
- The §20.4.3-validated static protect_mask. For 6c.3 v1, derive it
  per-sequence from the prefill (the §20.4.3 path); a true
  offline-corpus-calibrated mask (Roadmap Exp 5) stays deferred.

## Integration plan — what to wire

### 1. Extend `INT4CacheKVRouteA` with a `kernel_backend` choice

In `CTM_plus/KVPolicy/kv_policy/int4_cache_kv_route_a.py`, add a
constructor param `kernel_backend: str` with two options:

- `"dequant_fallback"` (current behaviour) — unpack INT4 → dequant →
  FP16 → FlashAttention. The no-kernel route-A baseline ("naive" in
  §20.6.x).
- `"fused_v2"` — call `fused_protected_k_decode_attention` from
  `int4_fused_attention_kernel.py`.

Thread the option through `install_int4_cache_kv_route_a(...)` and the
vLLM runner (`runner_vllm_streaming.py`).

### 2. Plumb the static protect_mask through the cache

The kernel needs a `(H_kv, D)` int8 protect mask per layer. For 6c.3 v1:
on each layer's first `update()` (prefill), compute top-4% by max-abs
and freeze — exactly the §20.4.3 per-sequence-static path. Cache the
mask on the layer's `INT4CacheKVRouteA` instance.

### 3. Handle the `block_size` / `group_size_k` alignment

vLLM default `block_size = 16`; kernel's `GS_k = 32`. Two options
(blueprint §3 "Watch the known snag"):

- **Preferred (cleanest):** run vLLM with `block_size = 32` so groups
  align cleanly to blocks.
- Alternative: compute `group_idx = (block_idx * block_size +
  token_idx_in_block) // GS_k` and pass that through the kernel's
  scale-indexing — straightforward but more error-prone.

For 6c.3 v1, set `block_size = 32` and document.

### 4. Plumb the kernel call

In route-A's monkey-patched `Attention.forward`:

- **Prefill** path: keep the current behaviour. The kernel is
  decode-only.
- **Decode** path (S_q = 1): dispatch to
  `fused_protected_k_decode_attention(...)`.
  - vLLM stores KV in paged blocks via the block table. The kernel's v1
    contract is *contiguous* per-sequence K/V (`KERNEL_6C_BLUEPRINT.md`
    §3, "v1 scope: non-paged"). For 6c.3 v1, **gather** the block-tabled
    cache into contiguous tensors per decode call (one extra
    allocation + a gather). v2 would have the kernel read paged
    directly — that is a 6c.3.2 follow-on, not v1.
  - The kernel inputs (`k_packed`, `k_scale`, `k_offset`, `k_fp16`,
    `v_packed`, `v_scale`, `v_offset`) are read straight from the
    `INT4CacheKVRouteA` block layout.

## Measurement plan — the four-cell throughput

Use the §20.1 four-cell pattern (`vllm_throughput_cell.py` and
`track_e_throughput.py`). Cells:

| Cell | Stack | KV format |
|---|---|---|
| A | vLLM 0.7.3 | FP16 (auto) — production baseline |
| B | vLLM 0.7.3 | FP8 (`--kv-cache-dtype fp8`) — current competitor |
| C | vLLM 0.7.3 + route-A | INT4 protected-K, **naive dequant** fallback |
| D | vLLM 0.7.3 + route-A | INT4 protected-K, **fused 6c.2 kernel** |

For each cell, measure:

- Decode **tokens/sec** at S_kv ∈ {4 096, 16 384, 32 768} tokens
  (vLLM works in tokens — careful: §20.4's needle harness used chars,
  these are tokens).
- Prefill-to-first-token latency.
- Actual **peak GPU memory** (`torch.cuda.max_memory_allocated()`).
- **KV bytes per token per layer** from vLLM's engine stats.

## Quality sanity — needle on the real pipeline

Re-run `track_e_long_context.py` against vLLM cell D at S_kv ≈ 16k and
32k tokens (the §20.4.2 / §20.4.4 contexts). Pass condition: needle
accuracy within noise of the §20.4 measurements (96–100%). A drop
indicates an *integration* numerical bug, not a kernel bug — the
kernel itself is validated by `scripts/kernel_6c_gpu_test.py`.

## Decision rules — what 6c.3 tells us

| Outcome | Read |
|---|---|
| Cell D > Cell A (FP16) **and** Cell D > Cell B (FP8) at long context | "Protected-K + fused kernel beats FP16 and FP8 end-to-end at long context." Strong product claim. **Update brief / pitch.** |
| Cell D ≈ Cell A and Cell D > Cell B at long context | Protected-K matches FP16 on speed and beats FP8 — a memory-capacity win plus parity on latency. Still a valid product claim, narrower phrasing. |
| Cell D > Cell C but < Cell A | Kernel beats the no-kernel route-A floor but the integration loses to FP16 directly. The route-A hook / paged-KV gather is the bottleneck, not the kernel. **Investigate before any product claim.** |
| Cell D ≤ Cell C | Integration regression — route-A overhead is killing the kernel's one-layer win. Profile the gather + monkey-patch overhead. |
| Cell D quality (needle) drops vs §20.4.2 / §20.4.4 measured | Integration numerical bug. Debug before any throughput claim — the kernel is validated against the reference; the bug is somewhere in vLLM plumbing. |

## Honest scope of even a maximally-successful 6c.3

- All measured on a single A100 / a fixed batch profile. Real serving
  sweeps batch sizes, sequence length distributions, prefix caching,
  scheduling. Deeper than 6c.3.
- **FP4/NVFP4 comparison still deferred** (no Blackwell). The §20.4.x
  framing says the protected-K finding is format-agnostic — that claim
  still rides whichever low-bit format ships.
- **Offline-corpus calibration** of the protected mask (Roadmap Exp 5)
  remains a low-risk formality, not blocking.

## What "done" looks like for 6c.3

1. Route-A v1 GPU-verified on Qwen2.5-7B (closes the §20.5 Days 4–5 gap).
2. The four-cell throughput table populated and committed as §20.6.3 /
   §20.7 in `PHASE4_GPU_FINDINGS.md`.
3. Needle quality table on the real pipeline confirming
   `cell D needle ≈ baseline` at 16k and 32k tokens.
4. A peak-memory table per cell.
5. A go / no-go call on the brief/pitch update, with the exact phrasing
   decided by the measured numbers, not extrapolated.

Until those five are committed, "protected-K beats FP8 end-to-end" stays
out of investor-facing docs.
