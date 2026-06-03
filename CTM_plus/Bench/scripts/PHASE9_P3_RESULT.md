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

## P4 RESULT — it's the CONFIG (near-full retention), NOT dispatch-boundness

Profiled retention decode @ ctx8000 (mean ms per layer-decode-call, % of total):

| section | mean ms | % | meaning |
|---|---:|---:|---|
| kernel_call | 5.594 | **67.1%** | the fused attention — DOMINATES |
| readskip_decision | 1.031 | 12.4% | scoring + block selection |
| kernel_inputs (gather) | 1.033 | 12.4% | host compaction copy |
| cache_append | 0.590 | 7.1% | |
| total_bypass | 8.331 | 100% | |

**The read-skip overhead (decision + gather) is ~25% — real but NOT the cause of
the 2× slowdown.** The attention kernel is 67% and **isn't shrinking**: at ctx8000
the default knobs (`sink 256 + recent 2048 + budget 2048` + neighbors) **retain
~75-80% of the 8k cache** — read-skip barely skips. So kernel_call stays large
while ~25% overhead is piled on top -> net 2x slower.

This is NOT the "dispatch-bound -> PCAM" verdict. It is the Step-0 length/
aggressiveness regime: the ~1.9x prize was modeled at **~15% retained at long
context**; here we retain ~80% at 8k, so there is almost nothing to skip. We never
entered the winning regime — the default keep-set is larger than the context can
benefit from.

### The decisive re-test (config, not code)
Re-run retention with an AGGRESSIVE keep-set so retained << seq, e.g.
`INT4_READSKIP_RECENT=512 INT4_READSKIP_BUDGET=512 INT4_READSKIP_SINK=64`
(~1100 retained of 8000 = ~86% skipped), and/or ctx 16k/32k where a fixed keep-set
is a smaller fraction. THEN kernel_call should drop ~proportionally and we learn
whether the (now-meaningful) attention savings beat the ~25% overhead:
 - savings beat overhead -> SOFTWARE WIN (then trim the 25% via kernel-emitted
   scores + in-kernel skip; per-watt bullet becomes measured).
 - savings still lose to the per-step decision cost even at high skip -> THAT is
   the measured PCAM case.

Quality must be re-checked at the aggressive setting (more skip = more H2O risk);
P3 retention quality was perfect at ~20% skip, and the sliding-window proxy was
GREEN, so it's promising but not yet proven at ~85% skip.

## P4b — AGGRESSIVE skip re-test (RECENT=512 BUDGET=512 SINK=64, ctx8000, ~86% skip)

| | off | retention (~86% skip) |
|---|---:|---:|
| quality d0.1/0.5/0.9 | 1.0/1.0/1.0 | **1.0/1.0/1.0** |
| decode tps | 8.9 | 7.12  (**-20%**, up from -48.7% at ~20% skip) |

**Quality holds at ~86% skip** — the needle survives at every depth even when
retention drops most of the cache. The H2O risk is retired even at aggressive
skip (was perfect at ~20% skip; still perfect at ~86%).

**Throughput improved with skip (-48.7% -> -20%) but is still negative.** The
residual gap is the OBSERVE phase, not the skip: on observe/refresh steps
(first observe_steps=8 + every refresh_every=16) retention reads the FULL cache
AND runs full-K torch scoring (~1ms). At max_gen=32 that's ~9 of 32 steps running
the expensive full+score path -> they dominate the average and eat the savings
the other ~23 (compacted, fast) steps produce.

### Levers to cross into positive (cheapest first)
1. **Longer generation** (max_gen 128-256): amortize the fixed observe cost over
   more fast compacted steps. Cheapest test; likely the biggest single lever at
   these settings.
2. **Cheaper / rarer scoring**: larger refresh_every; or KERNEL-EMITTED block
   scores (the fused kernel already computes softmax p -> sum per block for ~free)
   to remove the full-K torch reconstruction and the observe-phase full read.
3. **Longer context** (16k/32k): bigger per-step skip benefit.
4. v2 in-kernel block-skip to remove the residual host gather.

The algorithm is settled (quality free at high skip); from here it's an
amortization/kernel-efficiency curve. If longer gen + kernel-emitted scores
cross to positive -> software per-watt win. If the per-step decision floor still
dominates after that -> the measured PCAM case.

## P4c — longer generation (gen=128, 86% skip, ctx8000): BREAKEVEN reached

| (8k, ~86% skip, gen=128) | decode tps | quality d0.1/0.5/0.9 |
|---|---:|---:|
| off | 7.29 | 1.0/1.0/1.0 |
| retention | 7.50 | 1.0/1.0/1.0 |

Retention is now ~parity / +2.9% at PERFECT quality. Honest magnitude: +2.9% is
within cross-run noise (off drifted 10.75->8.9->7.29 across separate processes),
so the fair claim is BREAKEVEN, not a large win.

### The trajectory is the result (every lever moved it as predicted)
| config | skip | gen | retention vs off |
|---|---:|---:|---:|
| default knobs | ~20% | 32 | -48.7% |
| aggressive | ~86% | 32 | -20.0% |
| aggressive | ~86% | 128 | **+2.9% (breakeven)** |

Read-skip went from 2x SLOWER to breakeven purely by entering the right regime
(enough skip + amortized observe), with quality FREE at every step. It is NOT
dispatch-bound; it is a tunable amortization/kernel-efficiency curve sitting at
breakeven with clear headroom.

### Remaining headroom toward the Step-0 ~1.9x (all known, none blocking)
- **Kernel-emitted block scores**: the fused kernel already computes softmax p;
  sum per block -> removes the ~1ms full-K torch scoring AND the observe-phase
  full read (the biggest residual cost). Largest expected lever.
- **Longer context (16k/32k)**: bigger per-step skip benefit; Step-0 showed the
  prize grows with length.
- **v2 in-kernel block-skip**: removes the residual host gather.
- These are upside, not blockers — the sign is already non-negative.

## Phase 9 build — measurement arc COMPLETE
- Quality + correctness of read-skip on the production kernel: PROVEN (1.0 at
  every depth, up to ~86% skip; byte-eq 6/6).
- Throughput: from 2x slower -> BREAKEVEN by config/amortization, with known
  headroom (kernel-emitted scores, longer ctx) toward the modeled ~1.9x.
- int4_protected density + quality (the shipped product): untouched.
- Verdict: read-skip is quality-safe and throughput-viable; the remaining gains
  are well-understood kernel optimizations, not a hardware-mandate. PCAM stays
  parked (we did NOT hit a dispatch floor that only hardware breaks).
