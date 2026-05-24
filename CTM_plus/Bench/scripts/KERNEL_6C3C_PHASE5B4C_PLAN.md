# Phase 5B.4c — plan + V-lossiness decision

> Phase 5B.4b is GREEN at commit `13066c3`. Per-block bytes halved,
> num_blocks doubled. The uint8 storage is in place but generation
> is intentionally broken (FA kernels read uint8 as bf16 → garbage).
>
> 5B.4c is supposed to fix generation by replacing the write + read
> paths with our INT4-aware equivalents. Before writing code, this
> doc surfaces an architectural blocker that needs an explicit
> decision.

## The blocker: V-lossiness under vLLM's single-shape constraint

5B.4b set `get_kv_cache_shape = (2, NB, BS, H_kv, D=128)` uint8.
Per slot = 128 bytes. The leading `2` dim is K|V; both halves get
identical per-slot byte counts.

Per-slot budget analysis:

| Use | Needs | 128 byte budget |
|---|---|---|
| K INT4 packed | 64 bytes (D/2 nibbles) + protect (~10) + maybe scale/xmin | **Fits with room** |
| V bf16 full | 256 bytes (D × 2) | **DOES NOT FIT** — only 64 of 128 V elements |

The leading-2-dim shape design assumes K and V have THE SAME per-slot
storage. If K is half-byte and V is full-byte, vLLM's API can't
express it.

## Four options

| | K | V | Memory benefit | Output quality |
|---|---|---|---|---|
| **A** | INT4 (fits) | bf16 lossy (half D) | 2× capacity (5B.4b) | **V corrupted** |
| **B** | INT4 (more waste) | bf16 full D, shape=(...,256) uint8 | None (same total as stock bf16) | Correct |
| **C** | revert to stock bf16 | bf16 full D | None | Correct |
| **D** | INT4 + protect-K | INT4 + protect-V (advance Phase 2.6) | Real (~4× on K, similar on V) | Correct after 2.6 lands |

5B.4c as originally specified implicitly assumed option A worked. It
doesn't — V loses half its precision before kernel work even begins.

## Recommendation: pursue Option D (merge Phase 2.6 into 5B.4c)

Rationale:
- Option A's lossy V will likely tank decode quality (V holds value
  information; partial V → softmax-weighted-sum is meaningless).
- Option B keeps the architecture nice but gives ZERO memory benefit.
- Option C is a regression — undoes 5B.4b's win.
- Option D is the most work but is also the only path to a real,
  shippable v1 quality + memory story.

**Cost:** Phase 2.6 was estimated at ~2-3 days separately. Merging
into 5B.4c puts the total Phase 5B.4 effort at ~5-8 days (was 4-6
without 2.6).

**Benefit:** v1 ships with both K and V packed → real memory
savings (~3-4× on KV) AND correct output. The packed-V kernel
mirrors the packed-K kernel (same arithmetic, just along the
head_dim axis), so the work is mostly mechanical replication.

## Sub-sub-sub-phase split (assuming Option D)

### 5B.4c.0 — V quantization (Phase 2.6 work, ahead of 5B.4c)

- Mirror Phase 2.4.0/2.4.1b for V:
  - `pack_v_for_phase2_6(v_bf16, group_size=32) -> packed dict`
  - Kernel: `flash_attn_with_int4_kvcache_packed_v` — reads packed V
    with per-(group, h, d) scale/xmin. No protect mask for V
    (V doesn't have the outlier-channel phenomenon K has).
- Standalone tests: round-trip pack/unpack bit-equal.
- CUDA: extend `int4_packed_load.h` with a V-side helper. Phase 2.4.1b
  patterns transfer ~directly.

**Estimate: 2-3 days.** This is essentially Phase 2.6 (algorithm
+ kernel + Python) being done now as a prerequisite.

**Acceptance:** Standalone pack/unpack test PASS. Kernel-level cosine
≥ 0.9995 vs Phase 5A V baseline.

### 5B.4c.1 — write path replacement

- Replace `reshape_and_cache_flash` call with our own writer.
- New K tokens → PartialGroupQuantizer (Phase 5B.1) writes packed
  bytes to the K paged cache at slot_mapping.
- New V tokens → V-side PartialGroupQuantizer writes packed bytes
  to the V paged cache at slot_mapping.
- Per-layer scale/xmin/protect-mask sidecars (NOT in vLLM's paged
  management — managed by our backend install). Sized:
  per-(group, H_kv, D) bf16 × num_layers × num_groups ≈ ~50 MB total.

**Estimate: 1-2 days.**

**Acceptance:** Engine init succeeds. Forward writes complete without
crash. Sidecars correctly populated (verifiable by introspection).
Generation still corrupts (read path not yet replaced).

### 5B.4c.2 — read path replacement

- Replace `flash_attn_with_kvcache` and `flash_attn_varlen_func`
  calls with the Phase 2.4.1b packed kernel.
- Bridge to vLLM's block_table: either (a) gather per-sequence blocks
  to a contiguous tensor per decode step, or (b) adapt the kernel
  to use block_table directly.
- Option (a) is simpler — gather is a single CUDA index op, then call
  the existing kernel.

**Estimate: 1-2 days.**

**Acceptance:** Generation correct end-to-end. Cosine vs stock vLLM ≥
0.995 (algorithm drift, not bug-level). Needle test passes.

### 5B.4c.3 — quality re-acceptance

- Run Phase 6.4-style needle test with the new layout.
- Lock the protect_fraction at the lowest value holding 100% needle.

**Estimate: ~0.5 day.**

## Total estimate: 5-8 engineer-days

This is a multi-session push. Each sub-sub-sub-phase commits its own
verify; project never sits in a "broken everything" state.

## What's NOT in 5B.4c

- Actual reserve-line shrink (still requires patching profile_run —
  5C scope OR new 5B.4d).
- Multi-batch dispatch correctness (Phase 5B.5).
- First-class config polish (Phase 5C).

## Why pause this session

- 5B.4c.0 alone (V packing — algorithm + kernel + Python) is a multi-day
  push needing a fresh context to think clearly about V's scale/xmin
  layout, group axis (head_dim vs seq?), and correctness criteria.
- The V-lossiness blocker is the kind of architectural decision that
  benefits from a fresh look — not a rushed scope under context pressure.
- Phase 5B.4b is a clean stopping point with verified state.

**Next session start instructions:**
- Read this doc + KERNEL_6C3C_PHASE5B4_DESIGN.md.
- Confirm Option D direction (or pick a different option).
- If D: start with 5B.4c.0 (V packing as advance Phase 2.6 work).
- If A: skip 5B.4c.0; go straight to write/read path replacement and
  measure quality degradation in 5B.4c.3 (likely needs higher
  protect_fraction to compensate).

## What's in the repo today

| | |
|---|---|
| `kv_policy/phase2_4_packed_kv.py` | K-side pack/unpack helpers (Phase 2.4.0) |
| `kv_policy/phase5b_streaming_quantizer.py` | K-side PartialGroupQuantizer (Phase 5B.1) |
| `kv_policy/phase5b_backend_install.py` | Backend + impl + install (5B.2/3a/4a/4b) |
| `Bench/scripts/calibrate_phase5b_protect_mask.py` | Per-model mask calibration (5B.0) |
| Phase 2.4.1b CUDA kernel | Packed K reader (in the dev FA tree) |

Missing for 5B.4c (option D):
- V pack/unpack helpers (Phase 2.6.0 equivalent)
- V streaming quantizer
- V kernel-side reader
