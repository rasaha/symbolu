# Phase 2.4 — measurement findings (post-2.4.1c)

> Recorded after `measure_phase2_4_breakdown.py` ran on Qwen2.5-7B at
> max_model_len=4096, gpu_memory_utilization=0.5. These findings
> reclassify Phase 2.4.b and inform the Phase 2.4.1d priority.

## Finding 1 — the packed kernel is FASTER than Phase 5A's kernel

Per-call mean time across 868 decode invocations:

| Kernel | Mean ms/call |
|---|---|
| Phase 5A in-register quant (BF16 K + Phase 2.3/4) | **0.801 ms** |
| Phase 2.4.1c packed (HBM read + unpack) | **0.434 ms** |

The packed path is **~46% faster per kernel call.** Reason: Phase 5A
runs a per-block 4-pass max/min reduction + INT4 quantize in-kernel on
every call. The packed path just `__ldg`s precomputed scales/xmins/nibbles
and unpacks — less compute, slightly more bandwidth (we have spare).

**Implication for v1 ship:** the kernel itself isn't a bottleneck.
Once the v0 repack overhead is gone (Phase 2.4.1d), Phase 2.4.1c will
be FASTER than Phase 5A end-to-end. The 22% slowdown we measured at
the throughput level is entirely the Python repack, not the kernel.

## Finding 2 — decode_repack dominates Phase 2.4.1c's per-decode time

Per-decode-step (Phase 2.4.1c, mean ms across 868 calls):

| Block | Mean ms | Share |
|---|---|---|
| `decode_append` | 0.108 | 8% |
| `decode_kernel` | 0.434 | 32% |
| **`decode_repack`** | **0.804** | **60%** |
| **Sum** | **1.347** | |

Phase 5A (no repack) at the same shapes: 0.954 ms (append + kernel).
Phase 2.4.1c is 0.393 ms slower per decode step → matches the
~22% throughput regression measured at the end-to-end level.

**Phase 2.4.1d is the speed priority.** Killing `decode_repack` brings
Phase 2.4.1c to ~0.54 ms/call — **~43% faster than Phase 5A** because
of Finding 1.

## Finding 3 — vLLM's "KV cache" is a preallocated reserve, not a fillable buffer

From the engine init log at LLM(...) construction:

```
model weights take 14.24 GiB
non_torch_memory takes 0.00 GiB
PyTorch activation peak memory takes 1.41 GiB
the rest of the memory reserved for KV Cache is 23.98 GiB
```

vLLM allocates **23.98 GiB upfront** for KV cache regardless of actual
sequence length. This is set at engine init via
`gpu_memory_utilization * total_HBM`. For our 33-token prompt + 32
decoded tokens at block_size=16, vLLM uses ~5-10 blocks per layer
(~10 MB out of the 24 GB). **The other ~24 GB is UNUSED CAPACITY,
not stale K data we can free.**

Peak HBM measured:
- Stock vLLM: 38.129 GB
- Phase 5A install: 38.455 GB (+0.326 GB wrapper sidecar)
- Phase 2.4.1c install: 38.516 GB (+0.387 GB sidecar)

Our wrapper overhead is 1% of total HBM. We are not the problem.

## Finding 4 — Phase 2.4.b as originally specified is a dead end

Original Phase 2.4.b spec (from `KERNEL_6C3C_PHASE2_4_DESIGN.md`):
> "Phase 2.4.b — Free vLLM's paged K cache after prefill. We don't
> need it (our sidecar is the truth)."

This presumes vLLM's paged K cache is a fillable-and-freeable structure
that holds active K data. **It's not** — it's a preallocated reserve
sized to maximize batch × seqlen at the configured
`gpu_memory_utilization`. We can't free what isn't holding our data;
it's just headroom.

**To actually shrink the reserve, you must change the reserve sizing
calculation** so vLLM allocates fewer/smaller blocks at the same
util. That means registering a custom `kv_cache_dtype` in vLLM's
`CacheEngine` that reports per-block byte cost using INT4 sizing.

That's **multi-week Phase 5B/5C work** — native vLLM integration,
not a quick free-after-prefill hook.

## Reclassification: Phase 2.4.b → Phase 5B/5C

| Old | Reclassified |
|---|---|
| Phase 2.4.b — "Free vLLM paged K after prefill" | **Deferred / merged into Phase 5B**. The free-after-prefill approach doesn't work because there's no per-sequence K cache to free; vLLM's reserve is preallocated headroom. |
| Real memory savings | **Phase 5B/5C: `kv_cache_dtype="int4_protected"` registration in vLLM's CacheEngine.** That's where the savings actually land — shrinking the per-block byte cost shrinks the preallocated reserve at the same util. |

The headline "v1 saves HBM vs stock vLLM" claim is now contingent on
Phase 5B landing. Phase 2.4 alone (the packed-K kernel + install)
proves the algorithm + correctness, not the memory savings.

## Implications for v1 narrative

Honest framing:
- **Phase 2.4 v1 delivers**: packed-K kernel that's faster than Phase
  5A's reference + correct end-to-end (cosine 0.9999792, needle
  retrieval works) + foundation for the memory-savings work.
- **Phase 2.4 v1 does NOT yet deliver**: actual HBM savings vs stock
  vLLM. The +0.387 GB overhead is small but real.
- **Phase 5B** is the real memory-savings step. Its scope (multi-week
  CacheEngine integration) makes it the true v1 ship blocker.

## What this changes for the runbook

Near-term:
1. **Phase 2.4.1d** — incremental per-group repack. Kills the 0.804
   ms/step. **Now the only near-term speed win.** Expected end-state:
   Phase 2.4.1c becomes faster than Phase 5A end-to-end. ~1 day.

Medium-term:
2. **Phase 2.6** — pack V (mirror of Phase 2.4 K work). Required for
   the full KV memory story. ~2-3 days.

Long-term:
3. **Phase 5B/5C** — register `kv_cache_dtype="int4_protected"` in
   vLLM's CacheEngine. Real memory savings + multi-batch support.
   Multi-week. **The v1 ship blocker.**

## Test discipline going forward

Don't ship claims that require Phase 5B. Specifically:
- "Saves 4× memory" — needs Phase 5B + Phase 2.6.
- "Faster than stock vLLM" — needs Phase 5B (kills our wrapper Python
  overhead).
- "Drop-in replacement for production vLLM" — needs Phase 5B.

DO ship:
- "Packed-K INT4 kernel correctness proof on Qwen2.5-7B" — done.
- "Real-data quality at 4% protect-K" — done.
- "Native FA kernel integration" — done.
- "Foundation for the production CacheEngine integration" — done.

## Numbers for the record

- Verify: `verify_phase2_4_1b.py` cosine 0.9999792 vs Phase 5A reference
- Verify: `verify_phase2_4_1c.py` PASS, 0 fallbacks, needle retrieved
- Throughput: Phase 2.4.1c 19.5 tok/s, Phase 5A 22.8 tok/s, stock 82 tok/s
- Memory: Phase 2.4.1c sidecar 0.257 GB (k_fp16 + v_fp16 + packed bundle)
- vLLM reserve: 23.98 GiB (preallocated)
