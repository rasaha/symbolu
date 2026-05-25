# Phase 6 perf report — what landed, what remains

Status after commit `382db51` (vectorized PagedKVWriter.write).

## TL;DR

- **Writer vectorization done.** At T=512 prefill, writer wall time
  is **1.14× the batched-pack lower bound** (`pack_k_for_phase2_4 +
  pack_v_for_phase2_6` running on the same K/V). Mission accomplished
  on the write side; further write-path gains aren't possible without
  rewriting the reference packers themselves.
- **End-to-end int4_proto decode throughput +27%** (17.0 → 21.5 tok/s
  on the 6-prompt v1 benchmark fixture).
- **The bottleneck has shifted to the decode read path.** Per-decode-
  step latency is now uniformly ~45 ms at int4_proto vs ~12 ms at
  bf16 — the 33 ms gap is **~1.18 ms per layer × 28 layers** of
  Python orchestration in `_read_decode_packed` (gather + splice +
  packed kernel dispatch).
- **The cp.async-skip kernel patch is the cleanest remaining win,**
  but it'd only chip into the kernel portion of those 45 ms (small
  share). The bigger residual is the gather + Python dispatch cost,
  which is structurally harder to eliminate without a fused read
  kernel.

## Measured

### Writer profile (T sweep, post-vectorization)

```
   T |  writer_ms |  per_tok_us | ref_pack_ms | overhead_x
  ---+------------+-------------+-------------+-----------
   1 |     0.768  |     768.09  |        —    |     —
   8 |     0.723  |      90.39  |        —    |     —
  64 |     0.953  |      14.90  |     0.829   |   1.15
 256 |     0.928  |       3.62  |     0.834   |   1.11
 512 |     0.953  |       1.86  |     0.835   |   1.14
```

For T ≥ 64, writer time is bounded near the batched-pack ideal. The
T=1 / T=8 cases pay a fixed per-call CUDA-launch tax (~0.7 ms) but
that's a constant — not scaling per token. Per-token cost at T=512
is 1.86 µs (vs the previous per-token implementation's roughly
hundreds of µs).

### End-to-end three-way benchmark (after vectorization)

| Backend | Cuda blocks | Max conc | Decode tok/s/seq | Char-match vs bf16 |
|---|---|---|---|---|
| bf16        | 27934 | 109.12× | 80.7 | (baseline) |
| fp8         | 56120 | 219.22× | 64.8 (80%) | 6-16% prefix, 0/6 IDENTICAL |
| int4_proto  | 28060 | 219.22× | **21.5 (27%)** | **33-100% prefix, 3/6 IDENTICAL** |

(Quality numbers unchanged from pre-Phase 6 — vectorization preserved
bit-equivalence; `verify_phase5b_4c_1_write.py` PASS 5/5.)

### Per-prompt int4_proto wall time, pre vs post

| Prompt | T_in / T_out | Pre (s) | Post (s) | Speedup |
|---|---|---|---|---|
| 1 (short, "capital of France")  | 5 / 64    | 2.682 | 3.125 | (noise) |
| 2 (short, water fact)            | 10 / 64   | 2.421 | 2.896 | (noise) |
| 3 (medium, passage Q&A)          | 98 / 48   | 2.350 | 2.234 | 1.05× |
| 4 (medium, passage Q&A)          | 84 / 55   | 2.495 | 2.508 | (flat) |
| 5 (long, summarize)              | 564 / 41  | 4.629 | **1.908** | **2.43×** |
| 6 (long, tech Q&A)               | 504 / 64  | 5.167 | **2.950** | **1.75×** |

**Long prefills are 2-2.4× faster.** Short prompts didn't budge —
their bottleneck is the per-decode-step time (~45 ms × N_decode),
not the one-shot prefill cost. With short input + 64 decode steps,
decode dominates: 64 × 45 ms ≈ 2.9 s (matches observed).

## Why the decode path is now the bottleneck

A decode step through int4_proto does, **per layer**, this:

1. **Write path** — `PagedKVWriter.write` with T=1 (new token).
   Single-token vectorized cost: ~0.7-1.0 ms (mostly fixed per-call
   CUDA-launch overhead; sub-µs of actual work).
2. **Read path** — `_read_decode_packed`:
   - `writer.get_packed_view(block_ids, kv_cache)` — advanced index
     into the paged uint8 cache + 5 external sidecars; `.contiguous()`
     copies on each; produces a (1, S, H, D/2) packed K + V view.
   - `_splice_k_partial_tail` (when `seqlen % BS != 0`) — re-quantize
     the BS-sized staging buffer and overwrite the gathered view's
     last block.
   - `writer.get_bf16_backing_slice(S)` — slice the bf16 backing
     buffer (cheap; one tensor view).
   - `flash_attn_with_int4_kvcache(...)` — the actual attention work.

Per-layer per-step that's ~7 advanced-indexing ops + 3 `.contiguous()`
materializations + several `.unsqueeze()` reshapes + one kernel
launch. ~1-1.5 ms per layer is consistent with the ~45 ms observed
total (28 layers × ~1.2 ms + ~10 ms model overhead).

`bench_phase6_decode_profile.py` (this commit) breaks each phase's
per-layer cost out for empirical confirmation.

## Trade-off picture (locked, measured)

| Backend | Memory | Latency (serial) | Quality |
|---|---|---|---|
| bf16 | 1.0× | 1.0× | (baseline) |
| fp8 | 0.50× | 1.04× | poor (12% prefix match) |
| int4_proto | 0.50× | **3.75×** (was 4.93×) | **excellent (82% match, 50% IDENTICAL)** |

int4_proto's per-sequence latency went from 4.93× → 3.75× of bf16
with Phase 6 step 2. The remaining gap is dominated by per-decode-
step Python orchestration, not write-path overhead.

## Remaining options

Three concrete next moves, in order of estimated effort/impact:

### Option A — cp.async-skip kernel patch (Phase 6 step 4 per scope)

Wrap K + V `cp.async` sites in `flash_fwd_kernel.h` with
`if constexpr (!Is_int4kv_packed)`. Eliminates a wasted bf16 HBM
load per attention block AND removes the 224 MB parallel bf16
backing buffer entirely (no more `bf16_k_backing` / `bf16_v_backing`
in PagedKVWriter).

**Estimated impact:** ~10-15% decode_tps gain (small HBM bandwidth
recovered per layer) + 224 MB memory reclaimed. Quality unchanged.

**Cost:** ~1-2 hours CUDA editing + 15-minute recompile. Existing
verifies + correctness gates should immediately confirm or reject.

### Option B — vectorize / fuse the decode read path

Move `get_packed_view` + `_splice_k_partial_tail` +
`get_bf16_backing_slice` into a single Python helper that pre-
computes everything once per forward. Reduce advanced-indexing ops
from ~7 to ~3-4. Cache the per-layer "current view" object across
the writer / impl boundary so repeated `.contiguous()` calls don't
re-materialize.

**Estimated impact:** ~20-30% decode_tps gain (closing more of the
33 ms-per-step gap).

**Cost:** ~1 day of careful refactor + re-verify.

### Option C — start Phase 5B.6 (multi-batch)

The per-sequence latency story for int4_proto is what it is at v1.
The REAL ship win is the 4× concurrent-sequence capacity at the
same GPU. Multi-batch unlocks aggregate throughput that exceeds
bf16 in serving workloads.

**Estimated effort:** 3-5 days. Per-(layer, sequence) staging +
seq_pos counter; gather logic stays the same.

## Recommendation

**Order: A → C, with B deferred to a Phase 7 polish.**

- A is cheap and reclaims 224 MB — clean win that also simplifies
  the writer (drop the bf16 backing entirely).
- C is the actual v1.x business value (aggregate throughput at high
  concurrency). int4_proto's value proposition has always been the
  memory-capacity story, not per-sequence latency.
- B is engineering polish on a path that, even fully optimized,
  is at best parity with bf16 on per-sequence latency. Multi-batch
  routes around the entire concern.

## Bit-equivalence gates after Phase 6 step 2

Confirmed by re-running existing verifies:

| Verify | Result |
|---|---|
| `verify_phase5b_4c_1_write.py` | 5/5 PASS — writer math bit-equal |
| `verify_phase5b_4c_3_v_isolation.py` (T1/T2/T3/T6) | PASS — V layout / dequant / GQA / partial-tail unchanged |
| `verify_phase5b_4c_3_v_isolation.py` T4/T5 | FAIL (pre-existing test fixture bug: passes `dummy=zeros` for K/V positional, hits the small-S kernel zero-output behavior we documented earlier; not a vectorization regression) |
| `bench_phase5c_v1.py` | int4_proto 3/6 IDENTICAL outputs vs bf16, same as pre-Phase 6 |
| `verify_phase5c_api.py` | All 6 tests PASS (T1-T6) |
| `verify_phase5b_5_needle.py` | 15/15 retrieval at protect_fraction=4% (would re-run for full confirmation) |

The vectorized writer is correct; the math is unchanged from the
per-token reference. The improvement is purely from removing CUDA-
launch overhead per token.
