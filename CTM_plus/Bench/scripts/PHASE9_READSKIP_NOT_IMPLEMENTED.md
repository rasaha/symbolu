# Phase 9 — read-skip mechanism: what exists vs what doesn't

> **Status: STRUCTURAL FINDING from a code audit (CPU, $0).** Reframes the
> experiment. Companion to `PHASE9_STEP1_SMOKE_RESULT.md`.

## ⚠ CORRECTION (supersedes the original framing below)

The original version of this doc concluded "read-skip is not implemented → Step 2
is a build." **That conflated two different things and was too strict.** The
precise line:

- **Read-skip FOR THROUGHPUT = eviction.** When a cold block is evicted, vLLM's
  paged attention reads only the *live* blocks in the block table — so a freed
  block is, by definition, a block that is no longer read. **H2O and StreamingLLM
  ARE eviction policies** (drop the cold tokens); the session's own simulator and
  `TWO_TIER_ARCHITECTURE_NOTE.md` use "eviction / read-skip" interchangeably for
  the throughput mechanism. This **exists** and is wired to attention:
  - `--ctm-plus` — attention-guided evictor (`CTMEvictorModern`)
  - `--phase3-attention` — the bridge that feeds real per-block attention to it
    (Day 5b proved it carries non-zero signal end-to-end on GPU)
  - `--phase4-cython-evictor` — `CTMEvictorModernC`, the Cython port that the
    Phase 8 audit said recovers the −20% dispatch tax (**the exact "without the
    dispatch tax" lever the session question asks about**)
  - `--phase4-fast-hooks` — further per-fire dispatch reduction
  - `--int4-kv-sink-size` + `--extended-pinning`/`--pin-first-n-blocks` — the
    StreamingLLM keep-set (sinks + pinned recent/prefix)
  - `--preemption-mode recompute` — actually FREES blocks under pressure (the
    smoke's default `swap` only swap-thrashes to CPU; it never exercised eviction)
- **What is genuinely NOT built** is the *keep-stored-in-int4 two-tier* variant:
  an evicted-but-later-needed token cannot be restored (it's gone, not demoted to
  a cold int4 tier). That is a **quality refinement** (it bounds the H2O
  information-loss risk) — it is **not required to MEASURE** read-skip's
  throughput, its quality cost, or the dispatch attribution.

**Consequence:** Step 2 IS a measurement after all, using the existing eviction
path with the right config (and `--phase4-cython-evictor` directly answers the
"without the −20% tax" half). The two-tier kernel build is only warranted **if**
eviction's measured quality cost fails the needle/MMLU bar. **Measure first.**

The scoped-build section below remains valid **only** as the fallback plan for
that keep-stored two-tier variant — not as the prerequisite for Step 2.

---

## (Original framing — kept for the record; see correction above)

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
