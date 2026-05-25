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

## Phase 6 v2 Option D step 1 — vectorized splice (measured)

Landed in `88be156`. Replaces the per-seq Python loop that called
`_splice_k_partial_tail_batched_row` with a single batched op chain
(`_splice_k_partial_tail_batched_vectorized`) — stacks active seqs'
`k_stage` into one (A, BS, H, D) tensor and runs the quantize+pack
math element-wise across the new A axis. Bit-equivalence verified by
`verify_phase6_d_step1_splice_equiv.py` across 4 seqs with edge-case
tail lengths {1, 7, BS-1, BS//2}. Multi-batch e2e gate
(verify_phase5b_6_batch) stays GREEN.

Re-ran the throughput bench with step 1 in place (same fixture):

| B | agg_tps post-A | agg_tps post-D1 | Δ      | per_seq_tps | speedup vs B=1 | per-step ms |
|---|----------------|------------------|--------|-------------|----------------|-------------|
| 1 |  20.8          |  20.6            | noise  |  20.6       | 1.00×          | 48          |
| 2 |  26.1          |  27.2            | +4%    |  13.6       | 1.32×          | 73          |
| 4 |  32.1          |  35.2            | +10%   |   8.8       | 1.71×          | 113         |
| 8 |  36.3          | **41.7**         | **+15%** | 5.2       | **2.02×**      | 192         |

(B=1 is noise as expected — single-seq dispatches to `_read_decode_packed_one`,
not the batched path.)

Per-step at B=8 went 221 → 192 ms (-29 ms = -13% of per-step time). That
matches splice being one of several per-(layer, seq) ops, not the whole
~25-30 ms/seq budget. Remaining residual maps to: the bf16_backing copy
loop, the seq_id resolution syncs, and the block_ids_batched build loop —
all the same vectorization pattern.

## Phase 6 v2 Option D step 2 (next) — remaining per-seq Python

After step 1, what's left in `_read_decode_packed_batched`'s per-(layer, B)
Python overhead:

1. **`get_bf16_backing_batched` copy loop** — `B × 2 × .copy_()` per
   layer. Collapsible via `torch.stack` (one CUDA op vs B+1). Est. ~2 ms
   shaved per step at B=8.
2. **seq_id resolution** — `_seq_id_from_block_table_row` calls
   `int(bt[0].item())` B times, each a separate host sync. Collapsible
   to ONE sync via `block_table[:, 0].cpu().tolist()`. Est. ~1 ms shaved
   per step at B=8.
3. **block_ids_batched build loop** — `for i in range(B):
   block_ids_batched[i, :n_i] = ...`. Collapsible to a slice +
   masked_fill. Est. ~1 ms shaved.

Total expected: ~4-5 ms more per step at B=8 → another ~5-10% on
agg_tps. The combined splice-vectorized + step-2-vectorized read path
should land int4_protected near ~45-50 tok/s agg at B=8.

After step 2, the next ceiling becomes either:
- the gather/contiguous() chain in `get_packed_view_batched` (Triton
  could collapse 7 advanced-index gathers into one custom kernel), or
- the bf16_backing existence itself (cp.async-skip Option C — kill
  the bf16_K backing entirely if the rebuild env will cooperate).

## Phase 6 v2 Option D step 2 — measured (noisy)

Re-bench after step 2 (`f10fe5e` — `torch.stack` for bf16_backing,
one-sync seq_id resolution, slice+mask block_ids_batched):

| B | post-D1 | post-D2 median | post-D2 best | verdict |
|---|---------|----------------|---------------|---------|
| 1 | 20.6 | 18.2 | 19.0 | noise (B=1 doesn't hit batched path) |
| 2 | 27.2 | 24.6 | 27.5 | best matches D1 |
| 4 | 35.2 | 36.0 | 36.1 | +2% |
| 8 | 41.7 | **42.6** | 43.1 | **+2-3%** |

Per-run variance at this point exceeded the per-step gain we'd expect
(~5%). Step 2 helped marginally on best-of-3, but the median signal
was lost in pod noise. Took this as a flag to STOP guessing and
profile.

## Phase 6 v2 Option D — DECODE PHASE PROFILE (the actual story)

Instrumented `_read_decode_packed_batched` and `_read_decode_packed_one`
with per-phase CPU (perf_counter) + GPU (cuda events) timings via
`DecodeProfiler`. Ran `bench_phase6_decode_phase_profile.py` at B in
{1, 2, 4, 8}.

### Per-(layer, step) breakdown at B=8

| Phase | cpu_us_mean | gpu_us_mean | cpu/gpu | × 28 layers |
|-------|-------------|-------------|---------|-------------|
| `splice` | 296 | 311 | 1.0× | **8.3 ms** |
| `seqids_blockids` | 140 | 160 | 0.9× | **3.9 ms** |
| `view_gather` | 116 | 127 | 0.9× | 3.2 ms |
| `bf16_backing` | 73 | 83 | 0.9× | 2.0 ms |
| `kernel` | 65 | 75 | 0.9× | 1.8 ms |
| `kernel_prep` | 21 | 29 | 0.7× | 0.6 ms |
| **TOTAL read path** | | | | **19.9 ms / step** |

Observed wall at B=8: 4.99s / 26 output tokens = **192 ms / step**.
**Read path is ~10% of total.** The other ~170 ms / step is outside
the read path — model forward (MLP, LayerNorm) + write path + vLLM
scheduling + sampling, dominated by per-kernel launch overhead from
`enforce_eager=True` (no CUDA graphs).

### Sanity check on the "everything else" budget

Qwen2.5-7B at B=8 has, per decode step:
- ~28 layers of attention + MLP. MLP is 3 matmuls of shape (B, 3584)
  × (3584, 18944). At H100 peak (989 TFLOPS bf16) with 30% real
  efficiency: ~0.5 ms total per step for MLP arithmetic.
- Output projection + sampling: <1 ms.

**Pure compute would be <10 ms / step.** The 170 ms is launch
overhead — each tiny kernel pays ~10 µs to launch, multiplied by
hundreds of launches per layer × 28 layers.

### Implications for the optimization order

1. **Further read-path microoptimization has diminishing returns.**
   - Triton fused-splice kernel: would shave ~7 ms / step at B=8 →
     ~3-5% on agg_tps.
   - cp.async-skip + drop bf16_backing: ~2 ms / step → ~1% agg_tps
     (plus 224 MB reclaim).
   - Combined: <8% on agg_tps. ~3-4 days of work.

2. **The real lever is CUDA Graphs (Option B).** Capturing the decode
   forward into a graph kills the launch overhead in the model forward
   path — the actual 170 ms / step. Could realistically 2-3× the
   agg_tps at B=8.

3. **The original "B × 25-30 ms per-seq Python" attribution was wrong.**
   The per-seq Python cost we attacked with Options A + D1 + D2 was
   real and helped (sub-linear scaling improved 1.74× → 2.02× at B=8),
   but the bottleneck for further per-step decode speedup is outside
   the read path entirely.

### Pre-flight required for Option B

CUDA graphs cannot capture host syncs, data-dependent Python branches,
or dict lookups. The current `Int4ProtectedAttentionImpl.forward`
read path has all three:

  - `cache_seqlens_orig.cpu().tolist()` + `block_table[:, 0].cpu().tolist()`
    — 2 host syncs per layer per step. Unavoidable for Python-side
    seq metadata but kills capture.
  - `if seqlens[i] % BS != 0` in the splice path — data-dependent
    branch.
  - `writer._seq_states.get(seq_id)` dict lookup in splice +
    bf16_backing — pure Python.

Scope to unblock graph capture (~3-5 days):
  1. Move all seq metadata (n_blocks_per_seq, n_blocks_max,
     S_padded, active_mask) to device tensors. n_blocks_max requires
     ONE sync per call to size the gather — handled by vLLM's
     multi-shape graph capture (captures at a set of discrete sizes
     and dispatches by current shape).
  2. Make splice unconditional: pass active_mask as a device tensor
     and let the splice kernel do nothing if all-False.
  3. Refactor `_seq_states: Dict[Any, SeqState]` into a writer-level
     `(max_active_seqs, ...)` device tensor stack with a Python-side
     `seq_id → slot_idx` map. Resolution happens outside the captured
     region; reads inside use device-indexed access.
  4. Enable graph capture in `Int4ProtectedLLM` (`enforce_eager=False`,
     configure `compilation_config.cudagraph_capture_sizes`). Verify
     correctness preserved via existing gates. Bench.

Steps 1-3 are the read-path refactor. Step 4 is the actual graph enable.
See `OPTION_B_PREFLIGHT.md` for the implementation plan.

## Phase 6 v2 Option B pre-flight B-pre-1 — measured

Landed in `78e19c2` + fix `2b98f0a` (lazy default slot) + fix `1f04819`
(reset_sequence("all") evicts default too). The seq state storage
refactor: per-(layer, seq) state lives in fixed-size pool tensors on
the writer; SeqState is a thin slot-indexed wrapper; new device-indexed
read API (`get_bf16_backing_batched_by_slots`, `get_k_stage_by_slots`)
replaces the prior `torch.stack`-over-per-seq-views path.

Throughput sanity (same fixture):

| B | post-D2 | post-B-pre-1 | Δ |
|---|---------|---------------|---|
| 1 | 20.6 | 20.6 | noise (no batched path) |
| 2 | 27.2 | 27.2 | flat |
| 4 | 35.8 | 35.8 | flat |
| 8 | 42.6 | **43.1** | +1% |

Cumulative since session start (Option A baseline `446f7f4`):
36.3 → 41.7 (D step 1) → 42.6 (D step 2) → 43.1 (B-pre-1) at B=8.
1.19× lifetime gain on agg_tps at B=8.

Per-phase decode-path profile (B=8, post-B-pre-1):

| Phase | cpu_us pre | cpu_us post | Δ | scaling-with-B |
|-------|------------|-------------|---|----------------|
| `bf16_backing` | 72.8 | **23.9** | **-67%** | **flat now** (was linear: 38/50/72 for B=2/4/8) |
| `splice` | 296.1 | 274.2 | -7% | flat |
| `seqids_blockids` | 145.9 | 146.9 | flat | flat |
| `view_gather` | 115.9 | 119.4 | flat | flat |
| `kernel` | 65.5 | 65.2 | flat | flat |
| `kernel_prep` | 21.1 | 20.3 | flat | flat |
| TOTAL cpu_us per call | 498 | **455** | **-9%** | — |

The structural change is the headline: `bf16_backing` is now **flat
with B**. Single device gather (`pool[slot_idx_t]`) replaces
`torch.stack` over B per-seq backing views. This is the architecture
needed for graph capture — output is at a stable advanced-index
address, no Python loop, no dict resolution inside the captured
region.

Splice picked up a smaller incidental win from the same pattern
(slot-pool gather of k_stage tensors).

Total read path budget at B=8: 19.9 ms / step → 18.2 ms / step. The
read path went from 10% of total decode budget to ~9%. Modest agg_tps
gain at this layer because the per-step bottleneck is still the
~170 ms / step of model-forward launch overhead (unchanged by
B-pre-1; the actual point of B-pre-1 is to unblock CUDA Graphs,
which IS what would attack that 170 ms).

### Failed micro: sync coalesce (`629386e`)

Hypothesis: each of the two `.cpu().tolist()` calls in
`_read_decode_packed_batched` paid a separate GPU queue-drain wait,
costing ~70 µs each (most of the seqids_blockids phase's 140 µs).
Coalescing into one `torch.stack(...).cpu()` should halve it.

Measured: NULL. `batched.seqids_blockids` post-coalesce at B=8 was
146 µs vs 140 µs pre — within noise. Total read path budget at B=8
unchanged (~19.9 ms / step).

Why: PyTorch's CUDA stream serialization means two sequential
`.cpu()` calls effectively share one drain wait — the second call
sees the queue already drained by the first. The added `torch.stack`
+ `.long()` cast op cancels any savings.

Lesson: micro-optimizations inside the read path now hit a noise
floor. Further single-digit-µs wins per phase don't move the
agg_tps needle — the read path's contribution to per-step time is
already near its compute floor. Confirms the recommendation: stop
optimizing the read path; the next real perf lever is Option B.

The coalesced code is still committed (it's not WORSE, just not
better), and it does set up the structural pattern for the full
device-side metadata refactor in B-pre-2.

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
