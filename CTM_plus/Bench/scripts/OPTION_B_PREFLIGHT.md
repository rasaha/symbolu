# Option B (CUDA Graphs) — pre-flight + integration plan

> Multi-day project. This is the implementation roadmap derived from
> the decode-path phase profile (see `PHASE6_PERF_REPORT.md` §"DECODE
> PHASE PROFILE").

## Why

The phase profile showed read path is ~10% of per-step decode budget
at B=8. The other ~170 ms / step is launch overhead in the model
forward + write path + vLLM scheduling, dominated by
`enforce_eager=True`. Compute itself is <10 ms / step on H100.
CUDA graphs collapse the launch overhead by recording the whole
forward into a replay-once graph.

**Realistic upside:** 2-3× agg_tps at B=8. Push past 100 tok/s
aggregate from the current 42-43.

## Why it's not a one-session change

CUDA graphs are unforgiving about:

- **Host syncs** — `.cpu()`, `.item()`, `.tolist()` cannot be captured.
  The replayed graph runs entirely on device; if the host needs a
  value computed in the graph, that value isn't materializable until
  after replay.
- **Data-dependent control flow** — `if seqlens[i] % BS != 0` is
  recorded as the branch taken at capture time. The replay re-uses
  that branch regardless of current data.
- **Variable shapes** — captured graphs are fixed-shape. vLLM handles
  this via multi-shape capture (captures at multiple discrete sizes,
  dispatches by current shape).
- **Pointers** — the captured graph references the SAME memory
  addresses at every replay. Tensors used as inputs must be at stable
  addresses; dict lookups returning fresh tensor handles break this.

The current `Int4ProtectedAttentionImpl.forward` read path violates
all four:

| Violation | Where | Why |
|-----------|-------|-----|
| Host sync | `cache_seqlens_orig.cpu().tolist()` | metadata in Python ints |
| Host sync | `block_table[:, 0].cpu().tolist()` | seq_id Python ints for dict lookup |
| Data branch | `if any(active_mask)` | skips splice when no tails |
| Data branch | `if seqlens[i] % BS != 0` | per-seq tail check |
| Dict lookup | `writer.get_seq_state(seq_ids[i])` | seq_id → SeqState dict |
| Pointer churn | `state.k_stage` per call | each SeqState owns its own tensor |
| Pointer churn | `state.bf16_k_backing` per call | same |

The write path (`PagedKVWriter.write`) has the same violations.
A pre-flight refactor must eliminate ALL of them.

## Phased plan

### Phase 6 v2 Option B Pre-flight (3-5 days)

**Goal:** read + write paths use only device tensors and
data-independent control flow. Verify gates stay GREEN. No perf
expectation — this is structural prep.

#### B-pre-1: Unify the seq-state storage on writer — **LANDED**

The current `PagedKVWriter._seq_states: Dict[Any, SeqState]` was the
biggest blocker. Refactor landed in this commit. The new layout:

```python
class PagedKVWriter:
    # Fixed-size pool tensors, indexed by SLOT (small int).
    self._k_stage_pool       : Tensor  # (max_slots, BS, H, D) sidecar_dtype
    self._bf16_k_backing_pool: Tensor  # (max_slots, max_S, H, D) bf16
    self._bf16_v_backing_pool: Tensor  # (max_slots, max_S, H, D) bf16
    # Python-side seq_id → slot map (NOT on device — resolved before capture).
    self._slot_map          : Dict[Any, int]
    self._free_slots        : List[int]
    self._max_active_slots  : int     # env $PHASE6_MAX_ACTIVE_SLOTS, default 8

class SeqState:
    self._writer, self.slot_idx,
    self.k_stage_count, self.k_stage_block_id, self.seq_pos
    # Tensor accessors (k_stage, bf16_k_backing, bf16_v_backing) are
    # properties returning views into the pool tensors at slot_idx.
```

What changed:
- Pool tensors live on the writer at stable addresses (no per-seq
  re-allocation). Critical for graph capture.
- `ensure_seq_state(seq_id, device)` pops a free slot and creates a
  SeqState wrapper. Raises if the pool exhausts. DEFAULT_SEQ_ID is
  NOT pre-allocated — it gets a slot lazily on first write via the
  no-arg writer.write(...) entry point (legacy single-seq callers).
  Pre-reserving the default slot cost a slot of pool capacity, which
  surfaced as exhaustion at the B=8 ship target when none of vLLM's
  8 fresh seq_ids equaled 0. Fixed in the same B-pre-1 commit.
- `evict_sequence(seq_id)` returns the slot to the pool.
- `reset_sequence("all")` evicts EVERY seq (including the lazy
  default if it was allocated) — restores pool to fully free for
  the next workload. Earlier iteration KEPT the default, but if a
  prior B=8 workload happened to allocate id=0 (block_id 0 as first
  block for one of its 8 seqs), that "kept" default would eat a
  slot of pool capacity across resets and cause exhaustion in the
  next B=8 workload. Legacy single-seq callers use
  `reset_sequence()` no-args which preserves the default slot.
- New device-indexed read API on the writer:
  - `slot_indices_for(seq_ids) -> list[int]` — Python-side resolution
    (the one host operation per call before captured region).
  - `get_bf16_backing_batched_by_slots(slot_idx_t, S_padded)` —
    ONE device gather from `_bf16_k_backing_pool` /
    `_bf16_v_backing_pool` instead of `torch.stack` over per-seq
    backings.
  - `get_k_stage_by_slots(slot_idx_t)` — ONE device gather from
    `_k_stage_pool` instead of `torch.stack` over per-state
    `k_stage` views.
- `_splice_k_partial_tail_batched_vectorized` accepts both the
  legacy seq_states_list path (back-compat for tests / verifies) and
  a new preflight path that takes `active_slot_idx_t` (device long
  tensor) + `active_batch_idx_t` + `active_last_block_t`. Math is
  bit-equivalent between the two paths.
- `_read_decode_packed_batched` was rewired: after resolving
  seq_ids → slot_idx_t once, the splice and bf16_backing phases use
  the slot-tensor path exclusively. No more `torch.stack` over
  per-seq state tensors, no more dict lookups inside the read path.

Backward compatibility:
- `PagedKVWriter._seq_states` dict still exists with the same
  semantics for external callers.
- SeqState's external API (`state.k_stage`, `state.bf16_k_backing`,
  etc.) is unchanged — properties return tensor views.
- `get_bf16_backing_batched(seq_ids, S_padded)` legacy entry point
  still exists; now delegates to `_by_slots`.
- Write path is untouched (it goes through SeqState's properties,
  which already write into the pool via in-place ops).

Verify (must all stay GREEN after this commit):
- `verify_phase6_b_pre1_splice_slots_equiv.py` (NEW) — asserts the
  preflight splice + bf16_backing-by-slots paths produce
  tensor-equal output to the legacy paths, plus exercises slot
  recycling via evict_sequence.
- `verify_phase5b_6_batch.py` — main regression gate (multi-batch
  end-to-end output).
- `verify_phase5b_4c_1_write.py` — write-path math unchanged.
- `verify_phase5b_4c_3_e2e.py` — full int4_protected generation.
- `bench_phase6_decode_phase_profile.py` — phase timings still
  reported correctly.

Memory cost at default `_max_active_slots=8`:
- ~256 MB per writer (8 slots × 4 MB K backing + 8 slots × 4 MB V
  backing at max_S=4096). Times 28 layers = ~1.8 GB total. Matches
  the current per-seq-lazy-alloc footprint at peak B=8 usage — net
  zero memory change vs pre-B-pre-1.

#### B-pre-2 + B-pre-3: device metadata + unconditional splice — **LANDED (bundled)**

Originally scoped as two separate steps. The first attempt at B-pre-2
in isolation (`ec7253b`, reverted in `4868f3d`) caused a -2% agg_tps
regression at B=8 because moving metadata to device tensors introduced
3 implicit syncs from boolean indexing in the splice path
(`slot_idx_t[active_mask_t]` etc.) plus a separate `n_blocks_max
.item()` sync that couldn't pipeline with `block_table[:, 0].cpu()`.

Lesson: B-pre-2 and B-pre-3 are tightly coupled. Device-side metadata
only pays off when splice is also unconditional (no bool-indexing).
Re-landed together in this commit.

What's in `_read_decode_packed_batched`:
- KEPT the working coalesced CPU sync for seqlens + seq_ids (one
  stacked `.cpu().tolist()` of both rows). `n_blocks_max` stays a
  Python int from `max(seqlens_cpu_derived)`. This is the cheapest
  way to get both the gather size and the slot-resolution input.
- ADDED device-side metadata (cheap fused ops, no extra sync):
  - `n_blocks_per_seq_t   = (cache_seqlens_orig + (BS - 1)) // BS`
  - `last_block_indices_t = n_blocks_per_seq_t - 1`
  - `active_mask_t        = (cache_seqlens_orig % BS) != 0`
- REPLACED the conditional splice path with a NEW helper
  `_splice_k_partial_tail_batched_unconditional` that processes ALL
  B seqs uniformly. The path:
  - Single device gather of all B k_stages from the slot pool.
  - Quantize + pack on all B (extra work for inactive seqs is
    negligible — typical steady-state decode has A ≈ B).
  - Read-modify-write under `active_mask_t` via `torch.where(mask,
    new, old)` — inactive positions self-write their original
    value, preserving the previously-finalized block contents.
- REMOVED Python branches (`if any_active:`) and bool indexing
  (`slot_idx_t[active_mask_t]` etc.) from the splice path.

Net structural effect: the splice region inside
`_read_decode_packed_batched` is now data-dependent-branch-free,
sync-free (the mask, slot_idx_t, batch_idx_t, last_block_indices_t
are all pre-existing device tensors), and shape-stable across calls
of a given B. Ready for graph capture except for the two unavoidable
pre-capture trips (seq_id → slot lookup and n_blocks_max sizing).

Correctness gates:
- `verify_phase6_b_pre23_unconditional_splice_equiv.py` (NEW) —
  asserts unconditional splice produces tensor-equal mutations to
  the active-only legacy path across mixed active/inactive seqs,
  and confirms inactive slots are byte-preserved.
- `verify_phase5b_6_batch.py` — main regression gate.
- `verify_phase6_d_step1_splice_equiv.py` — legacy per-row splice
  equivalence (unchanged, still PASS).
- `verify_phase6_b_pre1_splice_slots_equiv.py` — preflight
  active-only path equivalence (still PASS; helper kept).

The legacy `_splice_k_partial_tail_batched_vectorized` is RETAINED
unchanged for the existing equivalence verifies and for any callers
that prefer the conditional path. New code should call the
unconditional variant.

#### B-pre-4: Pointer stability (~0.5 day)

Ensure all tensors passed to the kernel are at stable addresses
across calls:

- `bf16_k_batch`, `bf16_v_batch` from `get_bf16_backing_batched`
  currently allocated fresh via `torch.stack`. Replace with a
  pre-allocated `(max_B, max_S_padded, H, D)` buffer indexed via
  the slot tensor and the n_blocks_max shape bucket.
- `view` tensors from `get_packed_view_batched` — same treatment.

Once all of B-pre-1 through B-pre-4 land, the read path should run
entirely in device-only operations after a single sync to resolve
n_blocks_max + slot_idx.

### Phase 6 v2 Option B Capture-enable (1-2 days)

#### B-1: Enable graph capture in Int4ProtectedLLM

- Change `Int4ProtectedLLM` defaults: `enforce_eager=False`.
- Configure `compilation_config.cudagraph_capture_sizes` with a
  curve of discrete (B, n_blocks_max) sizes that cover the workload.
  Conservative starter: `[(1, 1), (1, 4), (1, 16), (1, 64), (2, 64),
  (4, 64), (8, 64), (8, 128)]`.
- The graph is captured on first hit of each shape; subsequent calls
  at that shape replay.

#### B-2: Correctness gate

Re-run ALL gates with graphs enabled:
- `verify_phase5b_4c_1_write.py`
- `verify_phase5b_4c_2_read.py`
- `verify_phase5b_4c_3_e2e.py`
- `verify_phase5b_5_needle.py`
- `verify_phase5b_6_batch.py`
- `verify_phase5c_api.py`
- `verify_phase6_d_step1_splice_equiv.py`

All must stay GREEN. Any output divergence vs eager mode means a
captured-graph correctness bug — most likely a pointer churn or
data-dependent branch we missed.

#### B-3: Bench + lock the new ship narrative

Re-run `bench_phase6_batched_throughput.py`. Expect:
- B=1: ~30-40 tok/s (1.5-2× current)
- B=8: ~80-100 tok/s aggregate (2-2.5× current)

If we hit those numbers, the v1.x ship narrative becomes
"**int4_protected sustains ~100 tok/s aggregate at B=8** with 4×
concurrent-sequence capacity" — competitive with bf16 on per-seq
latency, ahead on aggregate.

## Risks + open questions

1. **vLLM 0.7.3 V0 engine has graph capture limits.** The compilation
   config above is from V1 / newer vLLM. V0's capture is more limited
   — may need to bump to V1 first, which is a separate migration.
2. **Sidecar growth.** vLLM's graph capture allocates memory for each
   captured shape. Our sidecars (k_scale_ext, etc.) are already big;
   adding multi-shape captures may strain the 80 GB budget. Mitigation:
   conservative capture-size list, monitor cuda mem.
3. **Slot churn cost.** If sequences come and go rapidly,
   `_slot_map` resolution + slot allocation may dominate. Profile
   after pre-flight to confirm slot churn isn't a new bottleneck.
4. **Triton-fused-splice as a parallel track.** If graph capture
   doesn't deliver the expected 2-3×, fusing splice into one Triton
   kernel becomes the next move (saves ~7 ms / step at B=8).

## Status

- **B-pre-1: COMPLETE.** Landed in `78e19c2` + sized via `2b98f0a`
  (lazy default slot) + `1f04819` (reset_sequence("all") evicts
  default too). Pool tensors + slot map + device-indexed read API.
  Measured at B=8: bf16_backing cpu_us went linear-with-B → flat,
  agg_tps 36.3 → 43.1 (1.19× since session start).
- **B-pre-2 + B-pre-3: COMPLETE (bundled).** Landed in `7f1a168`
  after a failed isolated attempt at B-pre-2 (`ec7253b`, reverted in
  `4868f3d`). Device-side metadata + unconditional splice with
  torch.where-masked writes. All gates GREEN on pod:
    - verify_phase6_b_pre23_unconditional_splice_equiv.py: PASS
      (mixed active/inactive seqs; inactive slots byte-preserved)
    - verify_phase5b_6_batch.py: GREEN (7/7)
    - verify_phase6_d_step1_splice_equiv.py: PASS (legacy path
      kept for back-compat)
    - bench_phase6_batched_throughput.py at B in {1,2,4,8}: clean,
      agg_tps 20.5/26.4/35.0/42.6
  Measured eager-mode cost: -1.2% on agg_tps at B=8 (43.1 → 42.6).
  This is the price of admission for graph capture — the +47 µs
  cpu_us/call comes from extra dispatch ops in the unconditional
  RMW pattern. Under graph capture, those dispatches happen ONCE
  at capture time and replay is dispatch-free, so the cost should
  vanish.
  Structural goal achieved: splice region has no Python branches,
  no bool indexing, no data-dependent shapes, all metadata on
  device. Read path is now graph-capturable.
- **B-pre-2..4: not started.** Remaining preflight blockers (host
  syncs in seqids_blockids, data-dependent splice branch, fully
  stable pointer story).
- **B-1..3 (capture enable + verify + bench): not started.** Will
  resume after the rest of the preflight is in.
- Profile data justifying the project: `PHASE6_PERF_REPORT.md`
  §"DECODE PHASE PROFILE", commit `1f4157e`.
- Phase 5B.6 multi-batch + correctness gates: all GREEN, locked.
- Current ship narrative (pre-Option-B): "42 tok/s agg at B=8".

## Remaining preflight blockers (post-B-pre-1, post-B-pre-2+3)

| Violation | Where | Status |
|-----------|-------|--------|
| Host sync | coalesced `.cpu().tolist()` of seqlens + seq_ids | KEPT (pre-capture-hoistable; one coalesced trip serves both gather-sizing and slot-dict-lookup needs) |
| Data branch | `if any(active_mask):` in batched splice | **resolved** — splice is unconditional, uses `torch.where(active_mask_t, ...)` |
| Data branch | `if seqlens[i] % BS != 0` per-seq | **resolved** — `active_mask_t` is now a device bool tensor |
| Bool indexing | `slot_idx_t[active_mask_t]` etc. (3×) | **resolved** — splice consumes the full B-sized slot/batch/last_block tensors and masks writes |
| Dict lookup | `writer._slot_map[seq_id]` per call | **moved out of read path**, runs once Python-side; OK for graph capture if invoked pre-capture |
| Pointer churn | `state.k_stage` per call | **resolved** — now a stable pool view |
| Pointer churn | `state.bf16_k_backing` per call | **resolved** — pool view |
| Pointer churn | `bf16_k_batch` from torch.stack | **resolved** — single device gather, output addr = stable pool advanced-index |

What remains for graph capture:

1. The coalesced `.cpu().tolist()` and the Python int derivations
   (`n_blocks_per_seq`, `n_blocks_max`, `S_padded`) need to be
   HOISTED OUT of the captured region. This is a vLLM integration
   point — vLLM's prepare-inputs phase would resolve these on the
   host and the captured graph would consume the resulting device
   tensors. (B-pre-4 territory, but really vLLM-integration work.)
2. The captured graph captures at a discrete `n_blocks_max` size;
   vLLM's multi-shape capture dispatches to the right captured
   graph based on the current shape bucket.

Once these are addressed in vLLM integration (B-1), the read path
itself is structurally ready. The Python remaining in this region
after capture would be just the resolution + dispatch boilerplate,
which runs once per shape change rather than per layer per step.
