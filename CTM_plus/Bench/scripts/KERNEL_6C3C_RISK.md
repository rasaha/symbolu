# Kernel 6c.3C — phase progress + risk framing (stakeholder view)

> Stakeholder-facing snapshot of where 6c.3C stands. Reduces the
> per-commit engineering detail in `KERNEL_6C3C_RUNBOOK.md` to a
> 6-phase narrative + an honest risk register. Update when phase
> status or risk-deltas change.
>
> Companion docs: `KERNEL_6C3C_RESUME.md` (engineering session
> snapshot), `KERNEL_6C3C_DESIGN.md` (architecture), runbook (per-
> phase plan).

## The bet

vLLM 0.7.3 supports FP8 KV cache (`kv_cache_dtype="fp8"`) and FP16 KV
cache (default) for long-context decode. We want a third option,
**INT4 KV with protected-K**, that:

1. Recovers FP16 quality at long context (per §20.4.3, this works
   offline at S=32k on Qwen2.5-7B).
2. Compresses the KV cache 3-4× vs FP16 (so longer context fits in
   the same HBM budget OR more concurrent sequences fit).
3. Decodes at speed at least competitive with FP8 KV (so the
   compression isn't paid for in throughput).

The previous attempt (6c.3A "model-level bypass") shipped, was
measured at §20.6.3, and lost — our Triton kernel was 4-8× slower
than vLLM's bundled FA. The 6c.3C pivot replaces the bypass with a
fork of vLLM's FA itself: add INT4 dequant **inside** the attention
kernel, not as a wrapper around it.

## The 6 phases

| Phase | Status | What "done" means |
|---|---|---|
| **1.** Cloned FA entry point compiles + behaves like stock | ✅ DONE (commit `200196d`) | `flash_attn_with_int4_kvcache` exists in our forked wheel, routes through a parallel C++ entry + parallel splitkv dispatch + identical kernel template, and produces output bit-equal to stock FA on Qwen2.5-7B shapes. The dev build/install loop works without breaking vLLM at the engine level. |
| **2.** INT4 KV read/dequant works inside FA | ⏳ NOT STARTED | Inside the kernel's per-row computation, K is read from memory, dequantized to BF16, and the attention math runs as normal. Verified against the existing offline oracle (`kernel_6c_gpu_test.py::CASES`) with cosine ≥ 0.999. Same for V. |
| **3.** Protected-K side channel works | ⏳ NOT STARTED | The ~4% top-magnitude K channels per layer are stored in BF16 in a compact sidecar; the kernel blends them in with the INT4-dequant K before the qK dot. §20.4.3 validates this algorithmically; this phase verifies the in-kernel implementation. |
| **4.** vLLM paged KV allocation/storage works in INT4 | ⏳ NOT STARTED | A new vLLM attention backend allocates paged INT4 KV blocks (plus the BF16 sidecar + per-block scales/offsets). Prefill writes FP16; at the prefill→decode boundary, one bulk quantize converts to INT4 + freezes the protect mask. End-to-end `LLM(..., kv_cache_dtype="int4_protected").generate(prompts)` completes successfully. |
| **5.** Quality still holds end-to-end | ⏳ NOT STARTED | §20.4.3's 32k-needle pass-rate on Qwen2.5-7B with the new backend, n=24. Pass-rate within ±2% of the FP16 baseline. Algorithm proof carries over from §20.4.3; this is the *delivery vehicle* verifying the algorithm survives the kernel implementation. |
| **6.** Throughput + memory beat FP8 at long context | ⏳ NOT STARTED | Measured on real vLLM. At S=32k, B=1, decode=128 on Qwen2.5-7B, tokens/sec is ≥ FP8 baseline (cell B from §20.1). KV memory ratio vs FP16 ≤ 0.30. If E/A ≥ 1.0 (vs FP16 cell A): clean win. If E/A < 1.0 but E/B ≥ 1.0: partial win on compression-with-throughput-parity-against-FP8. If both miss: route-A repositions as compression-only and 6c.3C is documented as a measured failure. |

**Progress: 1 of 6 phases done.** Phase 1 took several sessions to
land (~2 weeks elapsed counting design + iteration). Phases 2-6 are
each meaningful engineering work, not gimmes.

## Risk framing — through Phase 2.2

| Risk | Previous | Current | Movement |
|---|---|---|---|
| **Algorithm** | mostly reduced | **mostly reduced** | Unchanged. §20.4.3 stands. **Caveat:** not yet re-verified through the new kernel — Phase 5 confirms. |
| **Quality** | substantially reduced (tested long-context retrieval) | **substantially reduced** | Unchanged, same caveat. |
| **Kernel** | medium/high | **medium** | Slight reduction. **What derisked:** the build/install/dev loop, dispatch routing, template instantiation, linking, vLLM-vendored .so swap pattern — all confirmed working through ~17 commits with no toolchain or ABI surprises. **What's still medium-high:** the cooperative reduce-max-abs + quant/dequant inside `compute_attn_1rowblock_splitkv` with route-B's exact rounding convention (Phase 2.3). Then real INT4 HBM layout with a custom copy atom (Phase 2.5). |
| **vLLM integration** | high | **high** | Unchanged. Phase 2.2 doesn't touch the vLLM block manager. Phase 4 (in your numbering) is the test; chunked-prefill, prefix-cache reuse, per-block side-channel keying, and sequence-completion cleanup are all real complexity. |
| **Commercial proof** | open until FP8 comparison measured | **open, with the bar higher than it looked** | The §20.6.3 close removed the §20.6.2 microbench's "1.30× faster than FP16" claim from the evidence pile — that was vs a weak SDPA baseline, not real FA. Beating FP8 (≈1.18× of FP16 per §20.1) now requires our FA-fork kernel to deliver ≈1.4× of stock FP16 FA at S=32k decode. KIVI/KVQuant/Atom achieve this on similar setups, so it's plausible — but it's not "already proven by a microbench." Phase 6 settles it. |

**One-line read:** algorithm + quality stay green at the algorithm
level; kernel-mechanic risk has come down meaningfully (we know we
can build, route, and link); kernel-numerics and vLLM-integration
risks haven't actually been tested yet and are the dominant
uncertainty. Commercial proof is gated entirely on Phase 6.

## What would move each risk

| Risk | Trigger | Move |
|---|---|---|
| Kernel → **low** | Phase 2 (your numbering) Phase 2.3 (runbook) — NO-OP transform proof — lands with cosine ≥ 0.9999 on `kernel_6c_gpu_test.py::CASES`. | medium → low. The cooperative reduction + quant/dequant primitives are correct; remaining kernel work is integration. |
| vLLM integration → **medium** | Phase 4 (your numbering) Phase 5.1 + 5.2 (runbook) — new attention backend exists AND a single prompt completes end-to-end through `kv_cache_dtype="int4_protected"`. | high → medium. The hard parts (block manager extension + prefill hook) work; remaining is scaling to multi-sequence / prefix-cache concerns. |
| Commercial proof → **settled** | Phase 6 (your numbering) Phase 6.1-6.3 (runbook) — measured tok/s + measured KV memory on real vLLM at S=32k, B=1. | open → either clean win, partial win, or measured failure (each is publishable as the honest result). |

## Effort to ship the remaining 5 phases

| Phase | Engineer-day estimate | Risk-weighted likely calendar |
|---|---:|---|
| 2 (INT4 K + V dequant in FA) | 7-10 days | 2-3 weeks elapsed |
| 3 (protected-K sidecar) | 2-3 days | 1 week elapsed |
| 4 (vLLM paged INT4 storage) | 5-7 days | 2-3 weeks elapsed (this is the wildcard) |
| 5 (quality re-run) | 1 day | 2-3 days elapsed |
| 6 (throughput + memory) | 2 days | 3-5 days elapsed |
| **Total** | **17-23 days** | **6-9 weeks elapsed** |

Estimates assume the runbook stays the runbook. Any architectural
surprises in Phase 4 (vLLM block manager) could extend that by
weeks.

## Bail-out conditions

The plan includes explicit exit ramps:

* If Phase 2 NO-OP transform fails to hit cosine ≥ 0.999 within ~2
  weeks of attempted iteration, that signals the route-B rounding
  convention cannot be matched bit-exactly in CUDA without
  substantial rework. Decision: switch to a *measured* drift budget
  (e.g. cosine ≥ 0.99 with explicit re-validation of §20.4.3
  quality through the new kernel) instead of bit-exactness.
* If Phase 4 vLLM integration takes >3 weeks elapsed, that's a
  signal the block manager extension is more invasive than scoped.
  Decision: scope down to a non-paged contiguous cache for v1
  (matches 6c.3A's shadow cache; loses the production-shape
  validation but ships measured numbers). v2 lifts to paged.
* If Phase 6 measures E/A < 1.0 AND E/B < 1.0 (both fail), the
  honest outcome is published as §20.6.4 (parallel to §20.6.3's
  6c.3A close). Route-A repositions as compression-only — the §20.4.3
  algorithm result + the measured KV memory savings are still real
  deliverables.

## Honest framing for a partner conversation

What we have today (Phase 1 done): a working dev-loop on a forked
FA wheel that routes a new entry point through a parallel kernel
path. **Bit-equal to stock.** No regressions on vLLM.

What we don't have yet: any INT4 work in the actual kernel body,
any vLLM-level paged INT4 storage, or any measured throughput
numbers vs FP8.

The §20.4.3 quality result is real and reproducible offline. The
6c.3A close + microbench in §20.6.3 was a useful negative result
— it killed a wrong-shaped architecture (model-level bypass) and
forced us into the right one (FA-fork). That negative result was
itself valuable: in §20.6.3 we measured an FP8 baseline behavior
that grounds the §20.6 narrative honestly. We are no longer
claiming 1.30× faster than FP16 on the basis of a microbench
that compared against the wrong baseline.

The next checkpoint that genuinely moves the picture is Phase 2
(your numbering) landing — the first time INT4 dequant runs
inside the FA kernel and the cosine check passes. That single
result reduces kernel risk to "low," lets us start Phase 3-6, and
keeps the project on the path described above. If it lands within
~3 weeks of focused work, the project is on track. If not, the
bail-out conditions above kick in.
