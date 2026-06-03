# Phase 9 — DECISIVE FINDING: read-skip is not implemented (Step 2 is a build, not a measurement)

> **Status: STRUCTURAL FINDING from a code audit (CPU, $0).** Reframes the
> experiment. Companion to `PHASE9_STEP1_SMOKE_RESULT.md`.

## The finding

The session question — *"can attention-guided **read-skip** beat all-int4 via
Route-A?"* — presumes a read-skip mechanism exists to measure. **It does not.**
The repo implements only:

- **COMPRESSION** — `int4_cache_kv_route_a.py:388-504` (`round_trip_kv`): K/V
  quantized to int4 then dequantized; **every token is still read/attended every
  decode step.** This is what Day 5a/5b ran.
- **EVICTION** — `attention_evictor.py:419-456` (`select_victims`/`evict_block`):
  low-score blocks are **DELETED** from the cache. The bridge's attention scores
  feed *these delete decisions*.
- **Protected-K decode reads the FULL sequence** —
  `int4_protected_k_cache.py:467-530` (`kernel_inputs` slices `[:s_curr]`, the
  whole accumulated sequence). The `protect_mask` is a per-channel/per-head
  dequant mask (`int4_fused_attention_kernel.py:119`), **not** a block read mask.

**No block-level read-skip path exists** — no `skip_blocks` / `read_mask` /
`active_range` parameter into the kernel, no decode-time block selection, no
H2O/StreamingLLM sparse-read. The evictor decides what to *delete*, never what to
*skip reading while keeping stored*.

## Why this matters

The two-tier / read-skip prize (Step 0: ~1.9× at long context) depends on cold
tokens being **kept stored in int4 but not read every step**. The code can store
them in int4 (compression ✓) and can delete them (eviction ✓) — but it cannot
*keep-and-skip-the-read*, which is the exact mechanism Step 0 modeled and PCAM is
scoped to accelerate. So:

- **Step 2's "read-skip via Route-A" cell cannot be run as a measurement today.**
- "MEASUREMENT, not a build" (the session's discipline) means we **stop at the
  measurement boundary** and report it, rather than silently pivoting into a
  multi-day kernel build.

## What building read-skip would take (scoped, NOT a recommendation to build)

1. `kernel_inputs()` (`int4_protected_k_cache.py:467`): add a `skip_block_mask` /
   `active_seq_range` param; filter/slice K/V buffers before the kernel.
2. Route-A decode hook (`int4_cache_kv_route_a.py:~756-772`): after the evictor
   scores blocks, derive a *skip* set (sinks+recent kept, low-attention middle
   skipped) and pass it as the mask — instead of (or alongside) eviction.
3. Fused kernel (`int4_fused_attention_kernel.py:100-149`): extend the existing
   per-position `valid` mask to a per-block skip mask (−inf the skipped blocks
   pre-softmax).

This is a real Triton-kernel + plumbing build with its own byte-eq/quality gate —
the opposite of the cheap measurement this session was scoped to.

## The cheaper, decision-relevant experiment that IS available

Step 1's soft signal (instantaneous decode tps: bf16 ~144–208 > route-A int4
~50–110 > **CTM+ bridge ~18–27**) hints the **attention-capture/flush bridge
itself is CPU-dispatch-bound** — and that bridge is the *same per-step
orchestration read-skip would inherit*. So the PCAM gate (Step 3) can be probed
**without building read-skip**:

> Configure a clean, matched A/B (GPU_UTIL ~0.85, prefix-caching matched across
> cells, flusher concurrency bug fixed) and measure the **bridge orchestration
> overhead** of what already exists. If the per-step capture/flush is already
> eating the gain in Python (dispatch-bound), that is the empirical PCAM case —
> and it says building read-skip *in software* would inherit the same tax. If the
> bridge overhead is small once configured properly, then a software read-skip
> build is worth funding.

This tests the decisive Step-3 attribution cheaply, on the machinery that exists,
before committing to the read-skip build.

## Verdict

- **Step 0** (prize real at long ctx): DONE ✓
- **Step 1** (integration installs + bridge carries non-zero attention): DONE ✓
- **Step 2** (read-skip A/B): **BLOCKED — mechanism not implemented.** A
  measurement is impossible without first building read-skip.
- **Recommended next (cheap, gates the build):** profile the existing bridge's
  per-step dispatch overhead in a properly-configured A/B → answers the PCAM gate
  (dispatch-bound or not) and tells us whether a read-skip *software* build can
  even capture the Step-0 prize. Only build read-skip if that profile says the
  orchestration is NOT already dispatch-bound.
