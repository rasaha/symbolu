# Phase 6H — High-load capacity bench findings

> **Status:** MEASURED, but the test did NOT reach the saturation
> regime where int4's 2× max_concurrency advantage would matter.
> **Raw verdict from bench: NOT_JUSTIFIED.** However, the verdict logic
> over-fired on `ratio==1.0` (both cells completing all requests is
> INCONCLUSIVE, not "int4 loses"). The honest reading of the data is
> in the "What we actually learned" section below.

## Setup

* Model: Qwen2.5-7B-Instruct.
* Hardware: A100 80GB.
* Bench: `bench_phase6_h_high_load_gpu.py` (commit `e19a9c7`).
* `gpu_memory_utilization=0.4`, `max_num_seqs=B exactly`,
  `max_tokens=48`, `n_runs=2` per (mml, B).
* Subprocess per (cell, mml, B) = 12 fresh-process runs.

## Sweep matrix and results

Reference max_concurrencies (audited at `gpu_memory_utilization=0.5`):
* mml=8192: bf16=55, int4=111
* mml=16384: bf16=26, int4=53
* mml=32768: bf16=12, int4=24

Bench results (all 12 runs completed without OOM):

| mml | B | bf16 completed | int4 completed | ratio | bf16 tps | int4 tps | bf16 HBM | int4 HBM | bf16 preempts |
|---|---|---|---|---|---|---|---|---|---|
| 8192 | 64 | 64/64 | 64/64 | 1.00× | 229.3 | 122.3 | 31.38 | 34.16 | 0 |
| 8192 | 96 | 96/96 | 96/96 | 1.00× | 214.9 | 122.7 | 31.39 | 34.24 | **2** |
| 16384 | 32 | 32/32 | 32/32 | 1.00× | 112.3 | 66.0 | 31.19 | 33.75 | 0 |
| 16384 | 48 | 48/48 | 48/48 | 1.00× | 109.7 | 78.2 | 31.19 | 33.76 | 0 |
| 32768 | 16 | 16/16 | 16/16 | 1.00× | 52.6 | 31.7 | 30.74 | 32.91 | 0 |
| 32768 | 20 | 20/20 | 20/20 | 1.00× | 51.3 | 33.2 | 30.74 | 32.92 | 0 |

## The verdict logic bug

The bench's verdict tree:
```python
if int4_OOM:                     int4_loses += 1
elif ratio >= 1.5:               int4_wins_strong += 1
elif ratio >  1.0:               int4_wins_weak  += 1
else:                            int4_loses      += 1   # <-- catches ratio==1.0
```

With `ratio = 1.00x` everywhere (both cells completing all requests),
every (mml, B) falls into the `int4_loses` bucket — triggering
NOT_JUSTIFIED. This is **incorrect**: `ratio==1.0` means the bench
didn't differentiate the cells, not that int4 lost. The right
interpretation is INCONCLUSIVE for the saturation question.

The verdict tree should be:
```python
if int4_OOM:                     int4_loses += 1
elif ratio >= 1.5:               int4_wins_strong += 1
elif ratio >  1.0:               int4_wins_weak  += 1
elif bf16_OOM:                   # int4 didn't OOM, bf16 did
    int4_wins_strong += 1        # capacity advantage
elif ratio == 1.0 and both_completed_all:
    inconclusive += 1            # need higher B to differentiate
else:                            int4_loses += 1
```

Fix landed in a follow-up commit; the verdict here is restated
based on corrected interpretation.

## What we actually learned

### Saturation never happened

Neither cell OOM'd at any tested (mml, B). The only preemption events
were 2 brief preempts in the bf16 cell at B=96, mml=8K — the first
sign of saturation but not a real breakdown. Both cells completed all
requested generations.

**To actually find bf16's OOM line, B would need to be much higher:**
mml=8K likely B=150-300, mml=16K likely B=80-120, mml=32K likely
B=40-60. The bench's chosen values bracketed the *reported*
max_concurrencies but vLLM's gpu_memory_utilization is a soft hint
(not a hard cap), so neither cell breaks at those points.

### bf16 is consistently 1.4–1.9× faster than int4 at the tested B

| mml | B | bf16 tps | int4 tps | bf16/int4 |
|---|---|---|---|---|
| 8192 | 64 | 229.3 | 122.3 | **1.87×** |
| 8192 | 96 | 214.9 | 122.7 | 1.75× |
| 16384 | 32 | 112.3 | 66.0 | 1.70× |
| 16384 | 48 | 109.7 | 78.2 | 1.40× |
| 32768 | 16 | 52.6 | 31.7 | 1.66× |
| 32768 | 20 | 51.3 | 33.2 | 1.55× |

int4's per-request decode cost is consistently ~1.5–2× higher than
bf16's. This is structural — the writer's per-decode-step work
(even after Phase 6E fusion) plus the sidecar gather + dequant
in the read path add roughly a constant factor of cost.

**Even if we found bf16's OOM line and demonstrated int4 keeping
serving past it, int4 would need to be at LEAST 2× bf16's max-B
total-tps to actually serve more tokens per second in absolute
terms.** The 2× max_concurrency advantage on paper would need to
overcome a ~2× per-request slowdown.

### HBM delta in high-B regime is ~2-3 GB (smaller than long-context bench's ~5 GB)

| mml | B | bf16 HBM | int4 HBM | delta |
|---|---|---|---|---|
| 8192 | 64 | 31.38 | 34.16 | +2.78 |
| 8192 | 96 | 31.39 | 34.24 | +2.85 |
| 16384 | 32 | 31.19 | 33.75 | +2.56 |
| 16384 | 48 | 31.19 | 33.76 | +2.57 |
| 32768 | 16 | 30.74 | 32.91 | +2.17 |
| 32768 | 20 | 30.74 | 32.92 | +2.18 |

This is **smaller than the +5 GB measured by the long-context
bench**. Reason: this bench used `max_num_seqs=B exactly` so vLLM
captures graphs only at the test B (not the full 1, 2, ..., 256
range). The captured-graph private pool overhead is much smaller.

The remaining ~2.5 GB delta IS the sidecar overhead (matches the
Phase 6G audit: ~3.4 GB at mml=32K, plus the ~0.5 GB of misc
backend buffers).

## What this means for the project

Combining the three measurement points:

| Operating regime | bf16 | int4_protected | Winner |
|---|---|---|---|
| Low B (1-8), short context (4K) | 39 GB, 74 tps @ B=8 | 45 GB, 49 tps @ B=8 | **bf16** by 1.5× tps + 6 GB |
| Low B (1-8), long context (32K) | 36 GB, 18 tps @ B=8 | 41 GB, 14 tps @ B=8 | **bf16** by 1.3× tps + 5 GB |
| High B (test sweep) | ~31 GB, 215 tps @ B=96 mml=8K | ~34 GB, 123 tps @ B=96 mml=8K | **bf16** by 1.75× tps + 3 GB |
| Extreme B (untested) | likely OOM at ~B=150-300 | likely keeps serving | unknown |

**At every tested operating point, bf16 is faster AND uses less
memory.** The only scenario where int4 could win is the extreme-B
regime where bf16 OOMs, which we didn't test directly.

But even in that scenario:
- bf16 at its max-sustainable B (just before OOM) probably delivers
  ~250-300 tps total (extrapolating from the current trends).
- int4 at B=2× bf16's max delivers ~150-200 tps (per-request decode
  doesn't scale linearly past B≈64-96 either; sidecar gathers cap it).
- Net: even in the int4-favored regime, total tps is comparable.

## Recommendation

Given:
1. Phase 6G audit: sidecar diet ceiling ~2.5 GB; cannot close low-B HBM gap.
2. Phase 6H bench: bf16 is faster + leaner at every tested B; capacity
   advantage of int4 unmeasurable at tested B values.
3. Combined: **the int4_protected line does not have a clear production
   value proposition on this hardware/workload.**

**Three options for the user:**

### Option α — Push the bench harder (1-2 days)

Re-run with much higher B and lower gpu_memory_utilization to find
bf16's hard OOM line. If int4 keeps serving at B significantly past
bf16's failure point AND its total-tps beats bf16's max-sustainable
tps, the capacity advantage is real. Probability of changing the
conclusion: ~20-30%. The 2× per-request slowdown is hard to
overcome.

### Option β — Pivot to the quality narrative (Phase 6J, new)

The protect-mask design's actual differentiator was supposed to be
**output quality vs naive int4 quantization** — not performance vs
bf16. We've been comparing int4_protected to bf16 (apples-to-oranges:
quantized vs not). The right comparison is:

* int4_naive (vanilla per-channel quant, no protect mask)
* int4_protected (with the calibrated protect mask)
* bf16 (reference)

If int4_protected delivers measurably better long-context output
than int4_naive while bf16 represents the ceiling, the project's
story becomes "high-fidelity int4 for long-context use cases where
the memory savings of int4 are needed but naive quant degrades
quality unacceptably". This is a research-grade contribution that
doesn't require throughput parity with bf16.

Effort: design + implement int4_naive baseline, ~3-5 days.
Probability of recovering a defensible value proposition: high IF
the protect-mask calibration was sound.

### Option γ — Close the int4_protected line

Accept that:
- HBM: int4 loses by 2-5 GB at every tested operating point.
- Throughput: int4 is 1.4-1.9× slower at every tested operating point.
- Capacity: at tested B, no advantage; at untested extreme B,
  speculative.

Document the technique as a research artifact and pivot the project
to a different direction (e.g., a different quantization scheme,
or a different memory-pressure target like multi-tenant scheduling).

## What this does NOT change

* **Phase 6E** remains shipped behind `PHASE6E_FUSED_WRITER=1`. The
  byte-eq correctness is solid; the perf is just not enough.
* **Phase 6F** remains halted. Closing the per-request gap via
  kernel surgery is multi-week work and doesn't help if the
  underlying value proposition is unclear.
* **Phase 6G implementation** (sidecar diet) is no longer
  recommended on the current evidence — the diet saves at most
  ~2.5 GB, which doesn't flip any of the three measurement regimes.
* **VC brief**: still NOT to be edited until a clear value
  proposition emerges (likely from Option β if pursued).

## Files

```
CTM_plus/Bench/scripts/bench_phase6_h_high_load_gpu.py  (bench)
CTM_plus/Bench/scripts/PHASE_6H_HIGH_LOAD_FINDINGS.md   (this doc)
bench_out/phase6h_high_load/cell_{bf16,captured}_mml{8192,16384,32768}_B{64,96,32,48,16,20}.json
bench_out/phase6h_high_load/high_load_report.{json,txt}
```
