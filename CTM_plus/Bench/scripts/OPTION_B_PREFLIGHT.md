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

#### B-pre-1: Unify the seq-state storage on writer (1-2 days)

The current `PagedKVWriter._seq_states: Dict[Any, SeqState]` is the
biggest blocker. Refactor to:

```python
class PagedKVWriter:
    # Fixed-size device tensor stacks, indexed by SLOT (small int 0..max-1).
    self.k_stage_pool       : Tensor  # (max_slots, BS, H, D) sidecar_dtype
    self.bf16_k_backing_pool: Tensor  # (max_slots, max_S, H, D) bf16
    self.bf16_v_backing_pool: Tensor  # (max_slots, max_S, H, D) bf16
    # Per-slot counters (small device tensors).
    self.seq_pos_pool       : Tensor  # (max_slots,) int32 — written tokens per slot
    self.k_stage_count_pool : Tensor  # (max_slots,) int32
    self.k_stage_block_id_pool: Tensor # (max_slots,) int32
    # Python-side seq_id → slot map (NOT on device — resolved before capture).
    self._slot_map          : Dict[Any, int]
    self._next_free_slot    : int
```

API changes:

- `write_for_seq(seq_id, ...)` and `read_for_seq(seq_id, ...)`
  resolve seq_id → slot via `_slot_map` (Python-side, pre-capture)
  and pass the slot int to a graph-capturable inner method that
  uses device-indexed accesses.
- `reset_sequence(seq_id)` zeros the slot's k_stage and resets its
  counters in-place. Frees the slot back to the pool.
- `evict_sequence(seq_id)` removes from `_slot_map`, returns slot
  to pool.

Verify: `verify_phase5b_4c_1_write.py`, `verify_phase5b_6_batch.py`
all PASS unchanged.

#### B-pre-2: Move metadata to device (~0.5 day)

In `_read_decode_packed_batched`:

- `seqlens` already on device as `cache_seqlens_orig`.
- `n_blocks_per_seq_t = (cache_seqlens_orig + (BS - 1)) // BS` — device.
- `n_blocks_max = int(n_blocks_per_seq_t.max())` — ONE unavoidable
  sync per call to size the gather. vLLM's multi-shape capture
  handles this by maintaining graphs for multiple discrete sizes.
- `last_block_indices_t = n_blocks_per_seq_t - 1` — device.
- `active_mask_t = (cache_seqlens_orig % BS) != 0` — device.
- `slot_idx_t = torch.tensor([slot_map[bid] for bid in block_table[:, 0].cpu().tolist()])`
  — ONE host sync to resolve, then device tensor. Resolution is
  done in the pre-capture region (Python orchestration), graph
  captures the device tensor reads.

#### B-pre-3: Unconditional splice (~0.5 day)

Make `_splice_k_partial_tail_batched_vectorized` always execute
(no `if any(active_mask):` branch). Inside the kernel, use the
active_mask_t to NO-OP positions where mask is False (multiply
the write by mask, or use `where`). Cost when all-False is
unconditional work but on small tensors — negligible.

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

- Pre-flight: **not started**. This doc is the scoping artifact.
- Profile data justifying the project: `PHASE6_PERF_REPORT.md`
  §"DECODE PHASE PROFILE", commit `1f4157e`.
- Phase 5B.6 multi-batch + correctness gates: all GREEN, locked.
- Current ship narrative (pre-Option-B): "42 tok/s agg at B=8".
