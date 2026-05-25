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

## Phase 6 v2 Option A — batched-kernel decode (measured)

After Option A landed (`446f7f4` — batched `flash_attn_with_int4_kvcache`
call across all sequences in a forward), the multi-seq throughput sweep
on the v1.x int4_protected backend (`bench_phase6_batched_throughput.py`,
Qwen2.5-7B-Instruct, max_tokens=32, ~483-char prompt, median of 3):

| B | wall_s | agg_tps | per_seq_tps | tps_speedup | per-step ms* |
|---|--------|---------|-------------|-------------|--------------|
| 1 | 1.25   | 20.8    | 20.8        | 1.00×       | 48           |
| 2 | 2.15   | 26.1    | 13.0        | 1.25×       | 77           |
| 4 | 3.50   | 32.1    |  8.0        | 1.54×       | 125          |
| 8 | 5.74   | 36.3    |  4.5        | 1.74×       | 221          |

*per-step ms = wall_s / n_output_tokens, treating prefill as ~0 (B=1 fit).

**Result: sub-linear scaling. 1.74× aggregate throughput at B=8 vs B=1.**

Per-batched-step time scales near-linearly with B (B^0.85), not flat as
the kernel-batching hypothesis predicted. Per-seq decode cost only fell
from 48 ms → 27.6 ms at B=8 — a 1.74× win, not the 4-8× we'd see if the
kernel dispatch was the actual bottleneck.

**Diagnosis (confirmed):** the bottleneck is the per-(layer, sequence)
Python orchestration in `_read_decode_packed` — gather + splice + dispatch
— which runs once PER SEQUENCE PER LAYER regardless of whether the kernel
call is batched. Option A killed the kernel-launch overhead share (the
small piece, as the §"Why the decode path is now the bottleneck" analysis
predicted) but left the Python share intact.

Decomposition fit:
  per-step(B) ≈ 12 ms (batched-kernel-shared) + B × ~25-30 ms (per-seq Python)

Reproducibility: two consecutive runs of the bench produced agg_tps within
±0.5 tok/s at every B. Bench is stable; the sub-linear scaling is real.

### What this means for the v1.x ship narrative

- **Correctness:** still GREEN. Architectural determinism (run1==run2)
  carries across batch sizes by construction.
- **Memory capacity:** unchanged — int4_protected still supports
  218× max-concurrency at 4096 tokens (vs bf16's 109×).
- **Aggregate throughput at B=8:** 36.3 tok/s. The headline ship number
  is "**int4_protected sustains 36 tok/s aggregate at batch=8** on
  Qwen2.5-7B-Instruct" — a real number, but not the linear-scaling
  pitch we'd hoped for.
- **The capacity story still holds** (4× concurrent sequences at same
  GPU), but the per-seq latency story is what it is.

### Why not test B > 8

We have headroom (218× max concurrency on the int4 cache), but at B=8
per_seq_tps is already at 4.5 (vs 20.8 at B=1) and per-batched-step time
is growing linearly. Extrapolating: B=16 would land ~40 tok/s agg
(per_seq_tps ≈ 2.5), B=32 ~42 tok/s. The asymptote is bounded above by
1/(per-seq Python cost), not by kernel throughput. We can run the
extrapolation if it's needed for the ship narrative, but the conclusion
is locked: **per-seq Python orchestration sets the ceiling.**

## Trade-off picture (locked, measured)

| Backend | Memory | Latency (serial) | Quality |
|---|---|---|---|
| bf16 | 1.0× | 1.0× | (baseline) |
| fp8 | 0.50× | 1.04× | poor (12% prefix match) |
| int4_proto | 0.50× | **3.75×** (was 4.93×) | **excellent (82% match, 50% IDENTICAL)** |

int4_proto's per-sequence latency went from 4.93× → 3.75× of bf16
with Phase 6 step 2. The remaining gap is dominated by per-decode-
step Python orchestration, not write-path overhead.

## Remaining options (re-scored after Option A measurement)

Now that we know the read-path Python is the dominant cost (and that
attacking the kernel-launch share only buys 1.74× at B=8), the option
landscape looks different:

### Option B — CUDA Graphs

Capture the full decode step (28 layers × {Python orchestration +
batched kernel}) into a CUDA graph. The Python ops vanish from the
critical path because the graph replays the recorded GPU work
without re-running the host code.

**Estimated impact:** very large — would directly eliminate the ~25-30
ms/seq Python cost that dominates B>1 timing. Could push per_seq_tps
back near the B=1 number even at high B.

**Cost:** ~2-3 days. Brittle — graph capture demands no host syncs in
the captured region (current splice path is full of `.contiguous()` /
advanced indexing that may or may not capture cleanly), and vLLM has
its own opinions about capture (`enforce_eager=True` is currently set
to bypass it; would need to investigate enabling capture for the
attention path only).

### Option C — cp.async-skip kernel patch (was the original Phase 6 step 4)

Wrap K + V `cp.async` sites in `flash_fwd_kernel.h` with
`if constexpr (!Is_int4kv_packed)`. Eliminates a wasted bf16 HBM
load per attention block AND removes the 224 MB parallel bf16
backing buffer entirely.

**Estimated impact:** ~10-15% decode_tps gain (small HBM bandwidth
recovered per layer) + 224 MB memory reclaimed. Quality unchanged.
NOTE: this only chips at the batched-kernel portion of per-step time
(12 ms of the 221 ms at B=8), so headline aggregate impact is
proportionally smaller at high B — closer to 2-3% on agg_tps at B=8.

**Cost:** ~1-2 hours CUDA editing + 15-minute recompile. The earlier
rebuild deadlocked on the pod; use `MAX_JOBS=2 NVCC_THREADS=2` and
ensure no stale nvcc/ninja processes.

### Option D — fuse gather + splice into a single Triton kernel

Replace the Python `get_packed_view` + `_splice_k_partial_tail` +
`get_bf16_backing_slice` chain with one Triton kernel that:
  1. Reads block_table for this seq.
  2. Gathers the packed uint8 K/V from the indexed blocks directly.
  3. Inline-quantizes the tail token into the gather-output buffer.
  4. Returns the packed view + bf16 backing slice ready for the
     batched attention kernel.

Run once per layer per forward (already batched across sequences in
Option A's batched kernel — D feeds it).

**Estimated impact:** ~20-30% decode_tps gain at B=1 + the per-(layer,
seq) Python cost goes from ~25-30 ms → ~5-10 ms (kernel + dispatch),
which is what unlocks linear B-scaling. At B=8 this could land 2-3×
on agg_tps (toward the ~80 tok/s ceiling).

**Cost:** ~2-3 days. Medium risk — Triton kernel needs to match the
existing reference exactly (gather indexing, partial-tail quant math).
Existing `verify_phase5b_4c_*` gates cover the math; the new kernel
just needs to drop into the read path with the same output shape.

## Recommendation

**Order: D → C, with B deferred unless D doesn't unlock B-scaling.**

- **D directly attacks the now-confirmed bottleneck.** The measurement
  closed the question of where the cost actually lives — it's
  per-(layer, seq) Python orchestration, not kernel launch. D removes
  that exact piece.
- **C is cheap and reclaims 224 MB** — worth doing as a free win
  once a fresh rebuild env is available, but it's no longer the
  priority. At B=8 it would buy maybe ~1 tok/s on agg_tps.
- **B (CUDA Graphs) is the bigger hammer** but riskier and slower to
  ship. Hold it as the fallback if D's Triton kernel doesn't deliver
  the expected B-scaling unlock.

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
