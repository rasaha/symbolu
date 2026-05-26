# Phase 6B.1 — Write-path preflight (design doc, no code yet)

> **Status:** Design doc only. CPU-first per discipline rule #4. No
> code lands without explicit user approval of this design.
>
> **Scope:** ONLY Phase 6B.1 of `PHASE_6B_CUDA_GRAPHS_PLAN.md`.
> Phases 6B.2 / 6B.3 / 6B.4 stay gated on separate approvals each.
>
> **Acceptance gate:** G_PRE-WRITE (see "Acceptance criteria" below).
>
> **Mental model:** mirror the read-path preflight (B-pre-1..4) on
> the decode write path. The read-path preflight refactored
> `_read_decode_packed_batched` so the captured region uses only
> device tensors + unconditional ops. The write path's
> `_derive_write_partitions` → per-seq `writer.write(...)` loop is
> the unmodified analogue — it crashes graph capture at
> `_seq_id_from_block_table_row()`'s `.item()` (B-1 in
> `OPTION_B_PREFLIGHT.md`). We mirror the four read-path patterns:
> B-pre-1 (slot pool storage), B-pre-2/3 (device metadata +
> unconditional batched op), B-pre-4 (pointer-stable persistent
> buffers).

---

## 1. Inventory of capture-hostile patterns (write path)

Same taxonomy as `OPTION_B_PREFLIGHT.md` §"Why it's not a one-session
change": host sync (HS), data branch (DB), dict lookup (DL), pointer
churn (PC). For each: file:line, current code shape, what rule it
violates, and decode vs prefill scope.

### 1a. The B-1 crash site (the one that actually fired)

| # | File:line | Pattern | Code | Violation | Decode? | Prefill? |
|---|---|---|---|---|:-:|:-:|
| W-1 | `phase5b_backend_install.py:1025` | `_seq_id_from_block_table_row()` | `return int(bt_row[0].item())` | **HS** | ✓ | — |
| W-2 | `phase5b_backend_install.py:974` | decode `_derive_write_partitions` loop | `[(_seq_id_from_block_table_row(dec_meta.block_tables[i]), slice(i, i+1)) for i in range(B)]` — Python list comp, B host syncs | **HS** (×B) + **DB** (per-i) | ✓ | — |
| W-3 | `phase5b_backend_install.py:731-738` | `for seq_id, sl in partitions:` calling `writer.write(seq_id=...)` | Python loop over B partitions; each call into `writer.write` → `ensure_seq_state(seq_id, ...)` | **DL** (×B) + **DB** (loop) + **PC** (key[sl], value[sl] allocations per iter) | ✓ | ✓ |

### 1b. `_derive_write_partitions` prefill branches (NOT in decode capture scope but listed for completeness)

| # | File:line | Pattern | Violation | Decode? | Prefill? |
|---|---|---|---|:-:|:-:|
| W-4 | `phase5b_backend_install.py:983` | `qsl_cpu = qsl.cpu().tolist()` | HS | — | ✓ |
| W-5 | `phase5b_backend_install.py:989` | `int(slot_mapping_flat[start].item())` | HS | — | ✓ |
| W-6 | `phase5b_backend_install.py:1000` | `int(slot_mapping_flat[j].item())` in `for j in range(n)` | HS + DB | — | ✓ |

vLLM 0.7.3 V0 captures DECODE forwards, NOT prefill (confirmed in
`OPTION_B_PREFLIGHT.md` §B-1: "vLLM 0.7.3 V0 attempted to capture
decode forwards at 35 batch sizes"). W-4..W-6 fire only on prefill →
**out of 6B.1 scope; legacy path keeps them.**

### 1c. `PagedKVWriter.write` / `_write_into_state` — captured per-seq today

These fire B times during the decode write path (once per partition).
Each one independently violates capture rules.

| # | File:line | Pattern | Violation |
|---|---|---|---|
| W-7 | `phase5b_4c_paged_writer.py:783` | `n_real = int(non_padding_gpu.sum().item())` | **HS** |
| W-8 | `phase5b_4c_paged_writer.py:855` | `n_full_blocks = int(full_mask.sum().item())` | **HS** + downstream **DB** (`if n_full_blocks > 0:`) |
| W-9 | `phase5b_4c_paged_writer.py:870` | `if n_full_blocks < unique_blocks.shape[0]:` (uses Python int) | **DB** |
| W-10 | `phase5b_4c_paged_writer.py:944` | `if state.k_stage_block_id in full_block_ids.cpu().tolist():` | **HS** + **DB** + uses `state.k_stage_block_id` (Python int) |
| W-11 | `phase5b_4c_paged_writer.py:969` | `partial_set = set(unique_blocks[~full_mask].cpu().tolist())` | **HS** + bool indexing |
| W-12 | `phase5b_4c_paged_writer.py:974-975` | `block_ids_cpu = block_ids.cpu().tolist()` + `positions_cpu = positions.cpu()` | **HS** (×2, coalesce-able) |
| W-13 | `phase5b_4c_paged_writer.py:977-984` | `for b in block_ids_cpu: ... ordered_partials.append(b)` | **DB** (Python loop, data-dep set membership) |
| W-14 | `phase5b_4c_paged_writer.py:986-1006` | `for pb in ordered_partials:` per-partial-block loop, with mask `(block_ids == pb)`, conditional finalize | **DB** + **DL** (state.k_stage etc.) |
| W-15 | `phase5b_4c_paged_writer.py:1000` | `max_pos = int(positions_for_pb.max().item()) + 1` inside W-14 loop | **HS** |
| W-16 | `phase5b_4c_paged_writer.py:993,994,996,1001,1002,1005,1007` | mutations of `state.k_stage_block_id` / `state.k_stage_count` (Python ints) | **DB** (CPU-side mutation; the *next* call's `is new_block?` branch reads it) |

### 1d. `ensure_seq_state` / `_slot_map` (the dict-lookup root)

| # | File:line | Pattern | Violation |
|---|---|---|---|
| W-17 | `phase5b_4c_paged_writer.py:374-417` | `ensure_seq_state(seq_id, device)` reads + mutates `self._seq_states: Dict[Any, SeqState]` + `self._slot_map: Dict[Any, int]` | **DL** (per `writer.write()` call) |
| W-18 | `phase5b_4c_paged_writer.py:447` | `slot_indices_for(seq_ids)` — `[self._slot_map[sid] for sid in seq_ids]` | **DL** (×B) — already a Python-side resolution; suitable for pre-capture hook |

W-18 is **already** the read-path's pre-capture-hoistable resolution
(B-pre-1 lesson). For 6B.1 we re-use it for the write path — same
`slot_idx_t` serves both. 6B.2 hoists the resolution OUT of the
captured region via a vLLM hook.

### 1e. Per-seq state mutations that don't survive capture (the new ones we have to fix)

These are NOT host syncs themselves but they're Python-int mutations
of `SeqState.k_stage_block_id`, `.k_stage_count`, `.seq_pos`. The
captured replay would see STALE values. Cataloged for the refactor:

| Field | Today | Refactor |
|---|---|---|
| `state.seq_pos`         | Python int, per-SeqState   | `(max_slots,) int32` device tensor `_seq_pos_pool[slot]` |
| `state.k_stage_count`   | Python int, per-SeqState   | `(max_slots,) int32` device tensor `_k_stage_count_pool[slot]` |
| `state.k_stage_block_id`| Python int, per-SeqState   | `(max_slots,) int64` device tensor `_k_stage_block_id_pool[slot]` (-1 sentinel for unstaged) |

Python-int access stays as a backward-compat shim (legacy
`writer.seq_pos` property reads slot-0 of the device tensor → CPU on
read). Internal hot paths go device-side.

---

## 2. Refactor strategy — B-pre-1..4 mirror

For each captured-region violation, name the B-pre-* pattern it
mirrors and the write-path equivalent.

### 2a. B-pre-1 mirror — pool-based slot routing

**Read-path pattern (recap, B-pre-1 LANDED):** seq state lives in
fixed-address pool tensors (`_k_stage_pool`, `_bf16_k_backing_pool`,
`_bf16_v_backing_pool`) indexed by `slot_idx`. `_slot_map: Dict` is
the only Python-side dict, resolved ONCE pre-capture into a device
`slot_idx_t`.

**Write-path equivalent:** the **storage** pools (B-pre-1) are
**already** in place — the writer's `_k_stage_pool` /
`_bf16_*_backing_pool` are shared between read and write paths today.
The write path just doesn't use the pool-indexed access pattern; it
goes through `state.k_stage` (property view into the pool) per-seq.

What 6B.1 adds:
1. **No new pool for KV data.** Reuse `_k_stage_pool` /
   `_bf16_k_backing_pool` / `_bf16_v_backing_pool` as-is.
2. **NEW pool: per-slot counter tensors** (see §1e above) —
   `_seq_pos_pool: (max_slots,) int32`,
   `_k_stage_count_pool: (max_slots,) int32`,
   `_k_stage_block_id_pool: (max_slots,) int64`.
   Lazy-allocated alongside the existing pools in `_lazy_alloc`.
   Memory cost: 8 × (4 + 4 + 8) = 160 B per writer × 28 layers ≈
   4.5 KB total. Negligible.
3. **`slot_idx_t` is reused from the read path's resolution.**
   The impl's existing
   `_phase5b_slot_idx_buf` (B-pre-4, populated via `.copy_()`) is
   the canonical persistent buffer; the write path consumes it on
   the same call.

**Address W-17 / W-18:** dict lookup in `ensure_seq_state` becomes
"already resolved Python-side via `slot_indices_for(seq_ids)`",
exactly as the read path does today. The captured region only sees
the device `slot_idx_t`.

### 2b. B-pre-2 + B-pre-3 mirror — unconditional batched write op

**Read-path pattern (recap, LANDED bundled):**
`_splice_k_partial_tail_batched_unconditional` processes ALL B
sequences uniformly. Inactive seqs read-modify-write to themselves
under `torch.where(active_mask_t, new, old)`. No `if any_active:`
branch, no bool indexing.

**Write-path equivalent:** a **new** `PagedKVWriter.write_decode_batched`
method that processes all B decode tokens uniformly:

```
def write_decode_batched(
    self, key, value, kv_cache, slot_mapping, slot_idx_t,
):
    # key, value:     (B, H, D) bf16     — one new token per seq
    # slot_mapping:   (B,) long          — global slots from attn_metadata
    # slot_idx_t:     (B,) long          — pool slot per seq (pre-resolved)
    # Returns None; mutates kv_cache + sidecar tensors + pool counters.
```

**Pipeline (all ops device-only, fixed-shape per (B,) bucket):**

1. **Active mask.** `active_mask_t = (slot_mapping >= 0)`. Decode
   typically has all B active; padding handled uniformly.

2. **BF16 backing scatter.** Read per-slot `seq_pos` from the pool
   counter, scatter `key` / `value` into the backing pool at
   `(slot_idx_t, seq_pos_t)`. Update counter via masked `index_add`.
   No Python-int read; the captured region only sees device
   tensors.

   ```
   seq_pos_t = self._seq_pos_pool[slot_idx_t]              # (B,) int32
   self._bf16_k_backing_pool[slot_idx_t, seq_pos_t] = key  # scatter
   self._bf16_v_backing_pool[slot_idx_t, seq_pos_t] = value
   self._seq_pos_pool.index_add_(
       0, slot_idx_t, active_mask_t.to(torch.int32),
   )
   ```

3. **V quantization (unchanged math).** Vectorized over B; same
   group/pack chain as today's `_write_into_state`. Scatter into
   `kv_cache[1, block_ids, positions]` + `v_scale_ext`, `v_xmin_ext`.
   No `.item()` needed; all shape derivations are static (`n_real
   = B` since decode always writes exactly one token per seq).

4. **K protect gather + scatter (unchanged math).** Vectorized.

5. **K staging — UNCONDITIONAL re-quantize.** This is the heart of
   the refactor. Replaces the current FULL-vs-PARTIAL branching
   (W-8..W-16) with a single uniform op chain that, for every B
   slot, **always**:
   - Detects "is new block?" via device tensor equality with
     `_k_stage_block_id_pool[slot_idx_t]`.
   - Conditionally zeros the slot's `_k_stage_pool` row using
     `torch.where` (no Python branch).
   - Writes the new token at `(slot_idx_t, positions, h, d)`.
   - Re-quantizes the full BS-token staging buffer for each B
     slot (wasted work for non-block-boundary steps but graph-safe).
   - Scatters packed nibbles + scale + xmin into kv_cache + sidecars
     at `block_ids`.
   - Updates `_k_stage_block_id_pool[slot_idx_t] = block_ids` and
     `_k_stage_count_pool[slot_idx_t] = positions + 1` (masked).

   **Correctness argument:** legacy code only re-quantizes the
   staging buffer on partial-block writes; full-block finalizes
   come via the batched path. For decode (1 token per seq per step),
   EVERY write goes through the partial path until the block fills.
   The "wasteful" re-quant on a full block reads `_k_stage_pool[slot]`
   which holds all BS tokens of the block (accumulated across BS
   steps); re-quantizing produces the same scale/xmin/packed nibbles
   as the legacy `_finalize_k_group_from_state`. Bit-equivalent.

   The block-boundary case (token N transitions to a new block):
   legacy zeros staging then writes token at position 0;
   refactored detects new block via tensor compare, masks-zero the
   slot's pool row, writes token at position 0. Same end state.

   The `scale = ((x_max - x_min) / 15.0).clamp(min=1e-8)` math
   already includes zeros in the unfilled positions (legacy splice
   does this too — see `_splice_k_partial_tail_batched_vectorized`
   amax over `dim=1` of the full BS rows). Bit-equivalent.

**Address W-7 / W-8 / W-9 / W-10 / W-11 / W-12 / W-13 / W-14 / W-15
/ W-16:** all collapse into the unconditional pipeline above.

### 2c. B-pre-4 mirror — pointer stability for the new buffers

**Read-path pattern (recap, LANDED):** persistent `(max_B,)` device
buffers (`_phase5b_slot_idx_buf`, `_phase5b_batch_idx_arange`,
`_phase5b_cache_seqlens_i32`, `_phase5b_protect_mask_bhd_buf`) live
on the impl and are populated per-call via `.copy_()`. Stable
addresses across calls.

**Write-path equivalent:**

| Tensor used inside `write_decode_batched`'s captured region | Strategy |
|---|---|
| `slot_idx_t` (B,) long | **REUSE** `self._phase5b_slot_idx_buf[:B]` from B-pre-4. Already populated by the read path's `_ensure_index_bufs` earlier in `forward()`. |
| `active_mask_t` (B,) bool | Computed inside via `(slot_mapping >= 0)`. The `slot_mapping` is passed in fresh per call by vLLM but is a pointer-stable view of `attn_metadata.slot_mapping` once vLLM's capture's memory pool is active (empirically tame in graph capture per B-pre-4 audit's CYCLE/CHURN observation). No new persistent buffer needed. |
| `block_ids`, `positions` (B,) long | Derived element-wise from `slot_mapping`. Outputs of `//` and `%` ops; graph capture pools their backing store (same as read path's `n_blocks_per_seq_t`). |
| `seq_pos_t` (B,) int32 | Result of `_seq_pos_pool[slot_idx_t]` gather. Backing is a stable-address pool entry; output is a fresh tensor per call (advanced indexing always materializes a copy). Graph capture's memory pool reuses the same address across replays — same pattern as read-path `bf16_k_batch`. |
| New pool counters (`_seq_pos_pool`, `_k_stage_count_pool`, `_k_stage_block_id_pool`) | Allocated once in `_lazy_alloc`. Stable addresses. |
| Quantization scratch (`buf_f`, `x_max`, `x_min`, `scale`, `q`, `packed`) | Same pattern as today's V-quant path — fresh per call; allocator pool reuses inside captured region. Audit confirms (B-pre-4) this is tame in vLLM's graph context. |

**New audit:** `audit_phase6_b_pre5_write_pointer_stability.py` —
clone of `audit_phase6_b_pre4_pointer_stability.py` but instruments
the write path's "what tensors does the captured region read/write"
surface (the scatter targets). Same reporting taxonomy (STABLE /
CYCLE-N / CHURN). Run pre-G_PRE-WRITE to confirm no surprise
churn from the new pool counters.

### 2d. The dispatch in `Int4ProtectedAttentionImpl.forward`

Today (line 728-738):

```
BS = int(kv_cache.shape[2]) if kv_cache.numel() > 0 else 32
partitions = _derive_write_partitions(attn_metadata, slot_mapping_flat, BS)
for seq_id, sl in partitions:
    writer.write(key=key[sl], value=value[sl], kv_cache=kv_cache,
                 slot_mapping=slot_mapping_flat[sl], seq_id=seq_id)
```

After 6B.1:

```
BS = int(kv_cache.shape[2]) if kv_cache.numel() > 0 else 32
if _is_pure_decode_write(attn_metadata, key.shape[0]):
    # Graph-capture-friendly path.
    # slot_idx_t is the SAME persistent buffer the read path
    # uses below — resolved from the same coalesced .cpu().tolist().
    writer.write_decode_batched(
        key=key, value=value, kv_cache=kv_cache,
        slot_mapping=slot_mapping_flat,
        slot_idx_t=slot_idx_t,
    )
else:
    # Prefill: legacy partition + per-seq write (eager only).
    partitions = _derive_write_partitions(
        attn_metadata, slot_mapping_flat, BS,
    )
    for seq_id, sl in partitions:
        writer.write(
            key=key[sl], value=value[sl], kv_cache=kv_cache,
            slot_mapping=slot_mapping_flat[sl], seq_id=seq_id,
        )
```

`_is_pure_decode_write` is a module-level helper that returns True
iff `attn_metadata.decode_metadata` is set, `prefill_metadata` is
None, and `key.shape[0] == decode_meta.block_tables.shape[0]` (one
token per seq, no spec-decode-style multi-token). All checks are
metadata-existence checks (no `.item()` calls on the host).

**Coordination with the read path:** the read path's existing
`_seqlens_and_seqids = torch.stack([...]).cpu().tolist()` (line
387-390) is the source of truth for `seq_ids` and is already
pre-capture-hoistable. We HOIST it to run BEFORE the write block
in `forward()` (small reorder; same op, earlier position), so its
result is available for the write path. `slot_idx_t` is then
populated once (via `_ensure_index_bufs` + `.copy_()`) and reused
by both write and read. **No new host sync introduced.**

**Address W-1 / W-2 / W-3:** the decode path no longer goes through
`_derive_write_partitions`'s decode branch (W-2) or
`_seq_id_from_block_table_row` (W-1) or the per-seq `writer.write`
Python loop (W-3). All three are bypassed.

---

## 3. Pool / buffer ownership

| Buffer | Owner | Rationale |
|---|---|---|
| `_seq_pos_pool` (NEW) | `PagedKVWriter` (per-layer) | Per-sequence state; lives with the KV pools it indexes; sized by `_max_active_slots` (already env-tunable). |
| `_k_stage_count_pool` (NEW) | `PagedKVWriter` | Same as above; co-owned with `_k_stage_pool`. |
| `_k_stage_block_id_pool` (NEW) | `PagedKVWriter` | Same. -1 sentinel for "not yet staged" matches the legacy `state.k_stage_block_id = -1` initial value. |
| `_phase5b_slot_idx_buf` (EXISTING from B-pre-4) | `Int4ProtectedAttentionImpl` (per-impl) | Persistent index buffer; one per attention layer. Reused for write path. |
| Pool 32-bit `int32` views | `PagedKVWriter` | int32 chosen for `seq_pos` and `k_stage_count` (matches kernel `cache_seqlens` int32 contract; small RAM). |

**Why writer-side, not impl-side, for the NEW pool counters:**
- The bf16/int4 KV state lives in pool tensors on the writer (B-pre-1).
  Counters that describe pool-slot state are co-owned with the data
  they describe.
- The impl already owns the *indexing* persistent buffers
  (`_phase5b_slot_idx_buf`, etc.) — those are kernel-arg-shaped.
- A future writer-quantizer redesign that swaps the K-staging
  algorithm should be able to do so without touching the impl. The
  counters are an internal concern of the staging algorithm.

**No new pool needed for KV data.** The B-pre-1 storage pools
(`_k_stage_pool` / `_bf16_*_backing_pool`) are already the canonical
write-path destination; we just need the COUNTER pool tensors that
encode "where in those pools is each slot's current position".

---

## 4. Test plan

### 4a. `verify_phase6_b_pre5_write_path_capture_safe.py`

CPU-only verifier. Two checks: AST (static) + runtime instrumentation.

#### AST check

Parse `phase5b_4c_paged_writer.py` and `phase5b_backend_install.py`
with `ast.parse`. Walk the body of:

- `PagedKVWriter.write_decode_batched` (NEW method)
- All helpers it calls (resolved by walking
  `ast.Call` → `ast.Attribute(self, ...)` references one level deep)
- `Int4ProtectedAttentionImpl._read_decode_packed_batched` (the
  captured-region body; same module, included for completeness)

Assert these nodes do NOT appear:

| Forbidden | AST shape |
|---|---|
| `.item()` calls | `ast.Call(func=ast.Attribute(attr='item'))` |
| `.cpu()` calls | `ast.Call(func=ast.Attribute(attr='cpu'))` |
| `.tolist()` calls | `ast.Call(func=ast.Attribute(attr='tolist'))` |
| Subscripts on dict attrs | `ast.Subscript(value=ast.Attribute(attr='_seq_states' / '_slot_map'))` |

**Exempt:** the ONE host sync the read path already preserves
(`torch.stack([...]).cpu().tolist()` at line 387-390) is allowed —
it's the pre-capture-hoistable resolution point, the same one
6B.2's hook will move. The AST check identifies it by file:line and
exempts that specific node (sentinel comment `# CAPTURE-EXEMPT:
pre-capture-hoistable seqlens+seq_ids sync`).

#### Runtime instrumentation check

Monkey-patch on a CPU PagedKVWriter to intercept `.item()`,
`.cpu()`, `.tolist()`, and `dict.__getitem__` on `_seq_states` /
`_slot_map`. Run `write_decode_batched` in a tight loop (B=4,
64 steps), assert the patched counters stay at 0. The exempt host
sync is patched separately and asserted to fire exactly 1× per call
to `forward()` (the coalesced read).

#### Why CPU is sufficient for capture-safety

The AST check is hermetic. The runtime check exercises the captured
code path WITHOUT actually capturing — it just confirms the code
doesn't try to do the forbidden things. `torch.cuda.graph()` enforces
the same rules at runtime; the runtime check confirms code never tries
them at all. GPU graph capture in 6B.3 is the integration test.

### 4b. `verify_phase6_b_pre5_write_equiv.py`

Byte-identical KV-cache-state legacy vs refactored, B ∈ {1, 2, 4, 8},
64-step decode. CPU-runnable (PyTorch's CPU backend supports the
ops we need — no kernel; the write path is pure Python/Torch).

**Fixture:** synthetic per-layer write driver (no full vLLM stack
needed; mirrors `verify_phase5b_4c_1_write.py`'s pattern):

1. Build a synthetic protect mask artifact (5 channels protected
   per head, deterministic via `torch.manual_seed(...)`).
2. For each B ∈ {1, 2, 4, 8}:
   a. Build two PagedKVWriters (one "legacy", one "refactored").
      Identical seeds, identical `_lazy_alloc` shapes.
   b. Generate a deterministic workload: B sequences, each with a
      32-token prefill + 64-token decode. seed=0xC0FFEE.
   c. Run prefill via `writer.write(seq_id=..., ...)` (legacy
      single-seq path; UNCHANGED for both writers — prefill stays
      eager).
   d. Run 64 decode steps. Each step:
      - Legacy: `writer.write(seq_id=..., key=k_i, value=v_i,
        kv_cache=..., slot_mapping=slot_i)` (B times, in a loop).
      - Refactored: `writer.write_decode_batched(key=stacked_k,
        value=stacked_v, slot_mapping=stacked_slots,
        slot_idx_t=slot_idx_t, kv_cache=...)`.
   e. Compare across writers:
      - `kv_cache` (the paged uint8 byte buffer): `torch.equal`
        bitwise.
      - `k_scale_ext`, `k_xmin_ext`, `k_protect_ext`,
        `v_scale_ext`, `v_xmin_ext`: `torch.equal` bitwise.
      - `_k_stage_pool`, `_bf16_k_backing_pool`, `_bf16_v_backing_pool`:
        `torch.equal` bitwise (after the equivalent slot remap).
      - Pool counters: legacy `state.seq_pos` Python int ==
        refactored `_seq_pos_pool[slot]` value (same after mapping).

**Cells to test, per B:**

| Cell | Workload | Asserts |
|---|---|---|
| `equiv_B{B}_step0`     | Single decode step, no block boundary | All extensions + kv_cache nibbles bitwise-equal |
| `equiv_B{B}_step31`    | 31 decode steps (one shy of block boundary) | Same |
| `equiv_B{B}_step32`    | Block boundary fires on the 32nd step | Same — partial → full transition |
| `equiv_B{B}_step64`    | 2 full blocks worth of decode | Same |

**Total: 4 cells × 4 batch sizes = 16 bitwise checks.**

### 4c. Integration with existing verifies

| Existing verify | What changes |
|---|---|
| `verify_phase5b_4c_1_write.py` | UNCHANGED behavior. The legacy single-seq `writer.write(seq_id=DEFAULT)` path is preserved for back-compat. This verify exercises the legacy path. |
| `verify_phase5b_4c_2_read.py` | UNCHANGED. Read path is not modified. |
| `verify_phase5b_4c_3_e2e.py` | UNCHANGED. End-to-end Qwen-7B decode test. |
| `verify_phase5b_5_needle.py` | UNCHANGED. |
| `verify_phase5b_6_batch.py` | UNCHANGED behavior; the batched path now goes through `write_decode_batched`. The gate assertions (determinism, prefix overlap) remain identical. |
| `verify_phase6_b_pre1_splice_slots_equiv.py` | UNCHANGED. |
| `verify_phase6_b_pre23_unconditional_splice_equiv.py` | UNCHANGED. |
| `verify_phase6_d_step1_splice_equiv.py` | UNCHANGED. |

**TIER5A orthogonality gate:**

| Sub-gate | Expected impact |
|---|---|
| G5a (class fingerprint) | PASS. We do not add/remove methods on `Int4ProtectedAttentionImpl`. We DO modify the body of `forward()` (adding the `if _is_pure_decode_write: ... else: ...` dispatch), but G5a pins only `class name + bases + method names + decorator kind` — body edits are by design ignored. |
| G5b (TIER5A AST walk) | PASS. TIER5A modules aren't touched. |
| G5c (file SHA pin) | **REGENERATE.** Authorized changes to `phase5b_backend_install.py` (the dispatch) + `phase5b_4c_paged_writer.py` (the new `write_decode_batched` + pool counters). Regen is the canonical "authorized change" pattern (precedent: TIER5A.3's wheel-baseline freeze). The Phase 6B.1 commit lands the regen alongside the code. |
| G6a (in-tree CUDA SHA) | PASS. No CUDA edits. |
| G6b (forked-wheel SHA pin) | Skipped on CPU CI per the plan (`vllm_flash_attn not importable`). Re-verified on the GPU pod at the G_PRE-WRITE smoke. |

**The G5c regen MUST be reviewable by the user.** Pattern: the
6B.1 commit includes the new `int4_protected_files_baseline.json`
diff, with a "regenerated for Phase 6B.1 write-path preflight"
note in the JSON. The user sees the diff in the PR-style review.

### 4d. CPU test suite additions

| Test file | Tests | What it covers |
|---|---|---|
| `Bench/tests/test_paged_writer_decode_batched.py` (NEW) | ~20 | Unit tests for `write_decode_batched`: shape contract, active-mask semantics, pool-counter updates, block-boundary detection, bit-equivalence vs legacy on tiny fixtures. CPU. |
| `Bench/tests/test_derive_write_partitions.py` (UPDATE if exists, otherwise NEW) | ~6 | The legacy `_derive_write_partitions` is preserved (prefill path); verify its output is unchanged for prefill metadata shapes. |
| `Bench/tests/test_paged_writer.py` (existing if any; check) | UNCHANGED | Existing tests on `PagedKVWriter.write` (single-seq) stay GREEN. |

Test target: ALL existing tests on `phase5b_4c_paged_writer` /
`phase5b_backend_install` stay GREEN. New tests cover the new code
path.

---

## 5. Anticipated equivalence-verifier shape

(Detail expanded from §4b.)

```python
# verify_phase6_b_pre5_write_equiv.py — sketch
def run_cell(B: int, n_decode_steps: int, *, seed: int):
    torch.manual_seed(seed)
    writer_legacy     = PagedKVWriter(layer_idx=0, ...)
    writer_refactored = PagedKVWriter(layer_idx=0, ...)
    kv_legacy     = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8, ...)
    kv_refactored = kv_legacy.clone()

    seq_ids = list(range(100, 100 + B))

    # Prefill — same on both writers (legacy path).
    for sid in seq_ids:
        prefill_k = torch.randn((PREFILL_LEN, H, D), ...)
        prefill_v = torch.randn((PREFILL_LEN, H, D), ...)
        prefill_slots = _alloc_block_slots(sid, PREFILL_LEN)
        for w, kv in ((writer_legacy, kv_legacy),
                      (writer_refactored, kv_refactored)):
            w.write(prefill_k, prefill_v, kv, prefill_slots, seq_id=sid)

    # Decode loop — diverge here.
    slot_idx_t = torch.tensor([
        writer_refactored._slot_map[s] for s in seq_ids
    ], dtype=torch.long)
    for step in range(n_decode_steps):
        # Stacked decode tensors at step.
        k_step = torch.randn((B, H, D), ...)
        v_step = torch.randn((B, H, D), ...)
        slot_mapping_step = _next_decode_slots(seq_ids, step)  # (B,) long

        # Legacy: per-seq Python loop.
        for i, sid in enumerate(seq_ids):
            writer_legacy.write(
                k_step[i:i+1], v_step[i:i+1], kv_legacy,
                slot_mapping_step[i:i+1], seq_id=sid,
            )

        # Refactored: single batched call.
        writer_refactored.write_decode_batched(
            key=k_step, value=v_step, kv_cache=kv_refactored,
            slot_mapping=slot_mapping_step,
            slot_idx_t=slot_idx_t,
        )

    # Bit-equivalence.
    asserts = [
        ("kv_cache",         torch.equal(kv_legacy, kv_refactored)),
        ("k_scale_ext",      torch.equal(writer_legacy.k_scale_ext, writer_refactored.k_scale_ext)),
        ("k_xmin_ext",       torch.equal(writer_legacy.k_xmin_ext,  writer_refactored.k_xmin_ext)),
        ("k_protect_ext",    torch.equal(writer_legacy.k_protect_ext, writer_refactored.k_protect_ext)),
        ("v_scale_ext",      torch.equal(writer_legacy.v_scale_ext, writer_refactored.v_scale_ext)),
        ("v_xmin_ext",       torch.equal(writer_legacy.v_xmin_ext,  writer_refactored.v_xmin_ext)),
        ("bf16_k_backing",   torch.equal(writer_legacy._bf16_k_backing_pool, writer_refactored._bf16_k_backing_pool)),
        ("bf16_v_backing",   torch.equal(writer_legacy._bf16_v_backing_pool, writer_refactored._bf16_v_backing_pool)),
        ("k_stage_pool",     torch.equal(writer_legacy._k_stage_pool,        writer_refactored._k_stage_pool)),
    ]
    return asserts
```

**Comparison method:** `torch.equal` — bitwise. The bf16 quantize
chain is deterministic given identical inputs; bit-equivalence is
the ONLY acceptable bar (we are not allowed even fp summation noise
since we're cloning the same op chain).

**Workload generator:** deterministic via `torch.manual_seed(seed)`.
Sequences allocated to non-overlapping block ranges. Seed=0xC0FFEE
matches `verify_phase6_b_pre1_splice_slots_equiv.py`.

**Block-boundary coverage:** by choosing PREFILL_LEN, n_decode_steps
intentionally:
- PREFILL_LEN ≡ 0 (mod BS), 64 decode steps → 2 full blocks during
  decode (steps 0-31 fill block N+1; step 32 starts block N+2; etc.).
- PREFILL_LEN ≡ BS-1 (mod BS), 64 decode steps → first decode step
  completes the prefill's partial block (block-boundary case
  immediately).
- PREFILL_LEN ≡ BS/2 (mod BS), 64 decode steps → first BS/2 decode
  steps complete prefill's partial block, then 2 more block boundaries.

These three sub-cells exercise the three failure modes the
refactor could surface:
- Mode A: full-block transition during pure decode
- Mode B: prefill→decode handoff at a block boundary
- Mode C: mid-block prefill→decode handoff

---

## 6. Risk areas + mitigations

### R-1: The unconditional re-quantize subtly diverges from legacy

**Concern:** legacy code's `_finalize_k_full_blocks_batched`
quantizes based on the (n_full, BS, H, D) keys passed in fresh.
Refactored unconditional re-quantize uses `_k_stage_pool[slot]`,
which is supposed to hold those same BS tokens (accumulated across
BS partial writes). The accumulation MUST be correct for
bit-equivalence to hold.

**Mitigation:**
- The new pipeline scatters each new token into `_k_stage_pool[slot,
  position]` BEFORE re-quantize. After BS steps that scatter all
  BS positions of a block, the pool slice equals the legacy
  `keys_grouped` for that block. Bit-equivalence proven by the
  cell `equiv_B{B}_step32` (one full block boundary).
- The equivalence verifier's Mode B sub-cell explicitly tests the
  prefill→decode handoff (legacy prefill leaves a partial block in
  staging; decode continues the same block via the new path).

### R-2: Pool-counter race in the equivalence verifier setup

**Concern:** the equivalence verifier needs IDENTICAL initial state
on both writers. After prefill (legacy single-seq path on both
writers), the pool counters are in identical states. But the slot
order may differ between writers (because the prefill writes happen
in different orders or hit different slots). If `slot_map` order
differs, the comparison `torch.equal(writer_legacy._k_stage_pool,
writer_refactored._k_stage_pool)` could fail even when math is
correct.

**Mitigation:**
- Prefill writes happen in the SAME order on both writers (same
  Python loop). With identical seeds + identical writes, slots
  get assigned deterministically (first-free-slot, popped in
  order). Slot order matches.
- The equivalence verifier asserts `writer_legacy._slot_map ==
  writer_refactored._slot_map` AS A PRECONDITION before the decode
  loop. If this assertion fails, the test setup is bad — not the
  refactor.

### R-3: `slot_mapping` from vLLM has -1 padding rows

**Concern:** for spec-decode-style multi-token decode, `slot_mapping`
can have -1 padding rows. The current `_write_into_state` filters
these via `non_padding_gpu = (slot_mapping >= 0)` (W-7), and the
filter is data-dependent.

**Mitigation:**
- `_is_pure_decode_write` (the dispatch gate) returns False for
  spec-decode-style writes (`max_decode_query_len > 1`), routing
  them through the legacy partition path (eager-only). Spec decode
  is already an `assert ... DECODER, "Only decoder-only models
  support max_decode_query_len > 1"` path; not part of our 6B.1
  scope.
- For pure decode (1 token per seq), -1 padding doesn't appear in
  V0 — `decode_meta.block_tables` has one row per active seq.
  But for graph-safety we still handle -1 via the
  `active_mask_t = (slot_mapping >= 0)` device-side mask. If the
  edge case fires, masking preserves correctness; if it doesn't,
  the mask is `(B,) all-True` and the masked ops are no-ops.

### R-4: vLLM 0.7.3 V0's actual graph-capture surface

**Concern:** B-1 first attempt failed at the write path's `.item()`
inside V0's capture loop. Even after fixing that, V0's capture may
have further constraints we haven't discovered.

**Mitigation:**
- Phase 6B.1 is STRUCTURAL PREP; we explicitly do NOT enable
  capture in this phase. The G_PRE-WRITE smoke at the end of 6B.1
  is a one-shot small B=2 decode in eager mode confirming the
  refactored write path produces unchanged output. Real capture
  is 6B.3's job.
- If 6B.2's hook integration surfaces a V0 limitation that's
  hard-blocked, the fallback is vLLM V1 port (Tier 2 v2 work, 1-2
  weeks). 6B.1's refactor is V1-compatible by construction —
  device-only ops, no V0-specific patterns.

### R-5: PyTorch CPU backend incompatibility for some ops

**Concern:** `verify_phase6_b_pre5_write_equiv.py` is CPU-only.
Some indexing patterns (e.g., `pool[slot_t, pos_t]` with int64
device tensors on CPU) may behave slightly differently than CUDA.

**Mitigation:**
- The current `_write_into_state` runs on CPU in
  `verify_phase5b_4c_1_write.py` today (without crashes). The new
  ops use the same primitives (advanced indexing, scatter,
  `torch.where`). No new exotic ops.
- If a specific op needs special-casing for CPU, the verifier will
  catch it via the Mode A/B/C cell coverage. Fixes land in 6B.1.

### R-6: Memory cost of the new pool counters

**Concern:** any extra HBM cost is undesirable.

**Mitigation:**
- 3 new pool tensors of shape `(max_slots,)` at int32/int64.
- 8 slots × (4 + 4 + 8) bytes = 160 B per writer × 28 layers = 4.5
  KB total. Trivially absorbed.

### R-7: Forward() body edit might surface a subtle prefill regression

**Concern:** adding the `if _is_pure_decode_write: ... else: ...`
dispatch around the write block might inadvertently change behavior
for some prefill or edge-case shape.

**Mitigation:**
- The `else:` branch is exactly the existing code (the partition
  + per-seq write loop), preserved verbatim. No behavior change
  for prefill.
- `verify_phase5b_4c_1_write.py` (single-seq prefill+decode write
  test) and `verify_phase5b_4c_3_e2e.py` (full int4_protected
  generation; prefill stages) MUST stay GREEN. They exercise the
  prefill path on real-shaped inputs.
- `verify_phase5b_6_batch.py`'s "0 fallback writes" gate catches
  unexpected fallbacks introduced by the dispatch.

### R-8: G5a (class fingerprint) trips unexpectedly

**Concern:** modifying `Int4ProtectedAttentionImpl.forward`'s body
shouldn't change G5a (which pins method names + base classes), but
if we accidentally add/remove a class-level helper method, G5a will
RED.

**Mitigation:**
- The dispatch helper `_is_pure_decode_write` is a MODULE-level
  function (not a class method). G5a doesn't see it.
- Refactor convention: write-path helpers live as module-level
  functions or on the writer (PagedKVWriter), not on the impl.
- Pre-implementation, run the gate on the current tree to capture
  the G5a baseline state. Post-implementation, re-run and confirm
  G5a unchanged. If it trips, that's a real regression — diagnose
  and revert.

---

## 7. Day-level timeline

Total: 2-3 engineer-days CPU + ~$0.02 GPU smoke (one B=2 decode at
G_PRE-WRITE gate verification, on the existing TIER5A pod or similar).

| Day | Deliverable | Acceptance |
|---|---|---|
| **Day 1 (CPU design + prototype)** | Land the new pool-counter tensors in `PagedKVWriter._lazy_alloc`. Land `write_decode_batched` skeleton + `_is_pure_decode_write` helper. Land the impl's `forward()` dispatch fork (keeping legacy `else:` path verbatim). | All existing unit tests stay GREEN. New `test_paged_writer_decode_batched.py` skeleton runs (may have failures on the equivalence subset; those are tomorrow's fix). |
| **Day 2 (equivalence + AST verifies)** | Land `verify_phase6_b_pre5_write_equiv.py` (16 cells: 4 B × 4 step counts). Iterate `write_decode_batched`'s K-staging unconditional re-quantize until bit-equiv. Land `verify_phase6_b_pre5_write_path_capture_safe.py` (AST + runtime instrumentation). | All 16 equivalence cells PASS. AST + runtime checks PASS. All existing verifies (`verify_phase5b_4c_*.py`, `verify_phase5b_6_batch.py`, `verify_phase6_b_pre*_*.py`) stay GREEN locally. |
| **Day 3 (orthogonality + smoke + finding)** | Run TIER5A orthogonality gate; regenerate G5c baseline with reviewable note. Land `audit_phase6_b_pre5_write_pointer_stability.py`. GPU smoke: B=2 single-prompt decode (eager mode, refactored path); confirm output unchanged vs pre-refactor reference. Land closure note in the plan-of-record (PHASE_6B_CUDA_GRAPHS_PLAN.md status snapshot). | G_PRE-WRITE GREEN: (1) AST + runtime check, (2) write equivalence 16/16, (3) all existing verifies GREEN, (4) G5a/G5b/G5c/G6a GREEN (G5c on regen baseline). GPU smoke confirms eager-mode unchanged output. |

**Day 3 GPU smoke spec:** Qwen-7B greedy decode on a known-fixed
prompt (the same one `audit_phase6_b_pre4_pointer_stability.py`
uses; the "Greendell" needle). Pre-refactor reference output is
captured in the same session BEFORE landing the writer changes
(so the comparison is hermetic to the pod's CUDA version etc.).
Eager mode only — `enforce_eager=True`. Confirms: refactored write
path produces byte-identical generated tokens for the reference
prompt.

If Day 3 surfaces any unexpected divergence (smoke != reference),
STOP and diagnose before regenerating G5c baseline. The baseline
regen is the FINAL step of the phase, gated on smoke GREEN.

---

## 8. Files touched (concrete list)

For user review of the orthogonality impact:

| Path | Change type | G5c impact | G5a impact |
|---|---|---|---|
| `CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py` | Add `write_decode_batched` + 3 pool counters + ~3 helpers (`_unconditional_kstage_re_quantize`, etc.). No removals from `PagedKVWriter` (`SeqState` etc. preserved for back-compat). | RED → regen | n/a (class not in G5a scope) |
| `CTM_plus/KVPolicy/kv_policy/phase5b_backend_install.py` | Edit `forward()` body to add dispatch fork. Add module-level `_is_pure_decode_write` helper. Don't touch `_derive_write_partitions` (legacy prefill path retained verbatim). Don't add/remove class methods on `Int4ProtectedAttentionImpl`. | RED → regen | GREEN (method list unchanged) |
| `CTM_plus/Bench/scripts/verify_phase6_b_pre5_write_path_capture_safe.py` | NEW | n/a | n/a |
| `CTM_plus/Bench/scripts/verify_phase6_b_pre5_write_equiv.py` | NEW | n/a | n/a |
| `CTM_plus/Bench/scripts/audit_phase6_b_pre5_write_pointer_stability.py` | NEW | n/a | n/a |
| `CTM_plus/Bench/tests/test_paged_writer_decode_batched.py` | NEW (≈20 CPU tests) | n/a | n/a |
| `CTM_plus/Bench/ctm_bench/scripts/int4_protected_files_baseline.json` | REGEN (authorized) | n/a (this IS the baseline) | n/a |
| `CTM_plus/Bench/scripts/PHASE_6B_CUDA_GRAPHS_PLAN.md` | Status snapshot row update: 6B.1 status → ✅ COMPLETE | n/a | n/a |

**Code NOT touched (orthogonality contract):**

- `kv_policy/int4_protected.py` — backend public API. Untouched.
- `kv_policy/int4_protected_k_cache.py` — protected-channel storage. Untouched.
- The forked `vllm_flash_attn` wheel — kernel. Untouched.
- The protected-channel splice logic in `_read_decode_packed_*`
  (read path). Untouched.
- `Int4ProtectedAttentionImpl`'s method list — only `forward()`'s
  body is edited; no new methods added or existing methods removed.
- Calibration scripts. Untouched.

---

## 9. Acceptance criteria — G_PRE-WRITE (from the plan-of-record)

Restated verbatim from `PHASE_6B_CUDA_GRAPHS_PLAN.md` §"Phase 6B.1
acceptance gate":

1. ✅ AST + runtime checks: zero `.item()` calls in the write
   path's captured region; zero per-call dict lookups.
2. ✅ Write equivalence: legacy and refactored write paths produce
   byte-identical KV state for a 64-step decode on B ∈ {1, 2, 4, 8}.
3. ✅ All existing verifies still GREEN
   (`verify_phase5b_4c_*.py`, `verify_phase5b_5_needle.py`,
   `verify_phase5b_6_batch.py`).
4. ✅ TIER5A orthogonality gate (G5 + G6) GREEN.
   The four in-tree tracks (G5a/G5b/G5c/G6a) MUST all PASS;
   G5c re-runs against the regenerated baseline.
   G6b will FAIL on CPU CI (vllm_flash_attn not importable) —
   expected; not a 6B.1 concern (the GPU pod re-verifies G6b
   at smoke time).

**Stretch acceptance (proactive proof for 6B.2):** the AST check
also greps for any *new* `.cpu()` / `.tolist()` / `.item()` in
`_read_decode_packed_batched` (read path) — confirming the
write-path refactor didn't inadvertently re-introduce a host sync
in the read path either. The single exempt coalesced sync stays
in place (until 6B.2 hoists it).

---

## 10. What this design does NOT cover (deferred to later phases)

- **vLLM hook for pre-capture seq_id resolution.** Phase 6B.2. The
  6B.1 design keeps the coalesced `.cpu().tolist()` inside the
  captured region (same status as the read path post-B-pre-3).
  Hoisting it via a vLLM hook is 6B.2's job.
- **`enforce_eager=False` flip + capture-enable.** Phase 6B.3.
- **Throughput re-measurement.** Phase 6B.4.
- **Prefill graph capture.** Out of scope across all of Phase 6B
  (vLLM 0.7.3 V0 doesn't capture prefill).
- **Tensor parallelism.** Tier 1 v2 item #3; independent of CUDA
  Graphs.

---

## 11. Decision point for the user

This design doc is the artifact the user reviews before any code
lands. Three options follow:

| Option | Action | Next step |
|---|---|---|
| **(A) Approve as written.** | I implement Day 1-3 per §7 timeline. Each day's deliverable lands as a small commit on `claude/phase-6b1-write-preflight-fjYee`. I report status at end of Day 1 and Day 2. Day 3 ends with G_PRE-WRITE GREEN and the GPU smoke result; that's the PR-ready state. | I proceed to Day 1. |
| **(B) Approve with modifications.** | User edits / questions on specific sections; I revise the design and re-submit. | I revise; user re-approves. |
| **(C) Reject / pause.** | A risk surfaced in §6 looks load-bearing (e.g., R-1 unconditional re-quantize correctness) that user wants to investigate before committing engineer-days. | I provide additional CPU-only proof on the specific risk (e.g., a hand-traced bit-equiv argument for R-1). |

Recommendation: **(A)**. The structural plan mirrors the
already-landed read-path preflight; the bit-equiv math (R-1) is
sound (legacy splice already includes zeros in scale/xmin); CPU
verifies catch any regressions before GPU spend. Discipline rule
#4 (CPU-first) means the GPU smoke at Day 3 is the only spend, and
it's bounded to ~$0.02 by the small B=2 single-prompt decode.

---

*This design doc, like all 6B work, is gated phase-by-phase. The
user approves this design before any code lands; 6B.2 / 6B.3 / 6B.4
get separate approvals each.*
