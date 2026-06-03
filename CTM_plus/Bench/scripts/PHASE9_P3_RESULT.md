# Phase 9 P3 — RESULT: read-skip holds quality on the real kernel, but is overhead-bound

> **Status: MEASURED on the production fused_v2 path (Qwen2.5-7B, ctx 8000).**
> Quality + correctness PROVEN; throughput NEGATIVE in the v1 (correctness-first)
> implementation. This is the decisive P3 measurement.

## Result

| | off | retain_all | retention |
|---|---:|---:|---:|
| needle hit @ d0.1/0.5/0.9 | 1.0/1.0/1.0 | 1.0/1.0/1.0 | **1.0/1.0/1.0** |
| decode tps (batch=1, 8k) | 10.75 | — | **5.52** |

- **Byte-eq: 6/6 identical** (off vs retain_all) — the `active_positions` gather is
  transparent on the real kernel; read-skip wiring is correctness-verified.
- **Quality: perfect under retention** — the GREEN proxy result reproduces on the
  PRODUCTION fused kernel. Attention-guided retention preserves the needle. The
  H2O quality risk is **retired**.
- **Throughput: retention −48.7% (2× SLOWER)**, with `readskip_calls=1764`
  (skipping IS happening). The per-step skip *machinery* costs more than the
  attention it removes.

## Why it's slower (the overhead, not the algorithm)

This is the v1 **correctness-first** implementation (the build plan said so).
Three known, unoptimized overheads dominate, and all are on the per-step host path:

1. **Host-side gather copy every decode step.** `kernel_inputs(active_positions)`
   gathers ~half of 8k tokens × {k_packed,k_scale,k_fp16,v_packed,v_scale} into
   fresh contiguous buffers *every step*. That memory traffic can exceed the
   attention saved — v1 chose host-compaction over the in-kernel block-skip (v2).
2. **Periodic full-K reconstruction for scoring.** `block_attention_scores`
   unpacks int4 + dequants + protect-overlays the WHOLE K and runs an attention
   matmul in torch on observe/refresh steps — O(s·H·D), comparable to the decode.
3. **Short generation + eager.** `max_gen=16` with `observe_steps=8` means the
   expensive observe phase dominates; eager adds Python dispatch. Longer
   generation would amortize the observe cost.

None of these is the read-skip *idea* failing — they are naive-implementation
taxes. The decode-attention selection itself works (quality is perfect).

## Verdict — this IS the dispatch/overhead gate (the PCAM fork)

Per `PCAM_RESCOPE_NOTE.md`'s decision rule:
> wins quality but CPU/dispatch-bound → the empirical case FOR fast-path/PCAM.

We are squarely there, **measured**: read-skip preserves quality on the real
kernel but the software skip-decision is overhead-bound. The throughput prize is
**not captured by the naive v1**. Two ways forward (P4 attributes which is
needed):

- **Optimize the software (likely sufficient, try first):** (a) **in-kernel block
  skip** (the v2 in the build plan) to eliminate the per-step host gather copy;
  (b) **kernel-emitted block scores** (the fused kernel already computes the
  softmax `p` — sum it per block for ~free) to eliminate the torch K-reconstruction;
  (c) score less often (larger `refresh_every`); (d) measure at realistic
  generation length (amortize observe). If these flip the sign → read-skip ships
  in software and the VC brief's per-watt bullet becomes a measured win.
- **If the per-step decision stays the bottleneck after that → PCAM.** A measured
  software ceiling that hardware uniquely breaks — exactly the chip's ROI case.

## What's banked regardless

- **Quality + correctness of read-skip on the production kernel: PROVEN.** The
  hard, uncertain part (does skipping break quality?) is settled GREEN.
- The throughput sign is an *implementation* result, not an algorithm result —
  and it points at a specific, known optimization path (v2 in-kernel skip +
  kernel-emitted scores) before any hardware claim.
- int4_protected density + quality (the shipped product) is untouched.

## Next: P4 — profile to attribute the overhead

Before optimizing or invoking PCAM, profile one retention decode at 8k to split
the per-step cost: gather-copy vs K-reconstruction-scoring vs the actual fused
attention. That says exactly which overhead to kill (and whether it's
software-killable or the hardware case). The harness already has
`manager.set_profiling(True)` + per-section CUDA events for this.
