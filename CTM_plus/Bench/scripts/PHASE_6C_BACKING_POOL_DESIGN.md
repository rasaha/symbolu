# Phase 6C — `PagedKVWriter` backing pool redesign

> **Status:** Plan-of-record only. No code shall land on this plan
> until the kernel-side verification step is done and the gate is
> approved.
>
> **One-sentence goal:** Shrink `_bf16_k_backing_pool` /
> `_bf16_v_backing_pool` from `(n_slots, max_S=4096, H, D)` to
> `(n_slots, BS=32, H, D)` — a 128× memory reduction — so the
> int4_protected captured cell uses LESS HBM than stock vLLM bf16,
> and the captured-graph read bandwidth at high B drops by the same
> factor.
>
> **Why now:** Phase 6B.4 measured int4_protected captured at 61.68 GB
> vs stock bf16 at 38.52 GB (60% MORE memory than the thing we're
> trying to beat). Throughput followed: 0.44× → 0.15× of bf16 across
> B ∈ [1, 32]. Root cause is the bf16 backing pool, which stores
> full-precision K and V for the entire sequence history when the
> kernel only needs them for the in-flight partial block.

## Background — what the bf16 backing pool is supposed to do

The int4_protected backend stores K and V in three places per layer:

1. **`kv_cache`** — int4-quantized 32-token block storage (4 bits / element + sidecars). This is the "saved memory" of int4_protected vs stock bf16.
2. **`k_protect_ext`** + similar protect-side ext tensors — full-precision bf16 for the model-frozen "protected" head dimensions (~4% of D per head, calibrated offline). Small.
3. **`_bf16_k_backing_pool` / `_bf16_v_backing_pool`** — full-precision bf16 K/V. **Today these store the entire sequence history.**

Why does (3) exist? Because decode happens one token at a time, and a `kv_cache` block only commits to int4 storage when it fills with `BS=32` tokens. While a block is partially filled (decode tokens 1..31 of a new block), the tokens haven't been quantized yet — the kernel needs their full-precision K/V from somewhere. The bf16 backing pool was added to provide it.

**The design bug:** the pool was sized for "the entire sequence" defensively, but the kernel only ever needs the LAST `BS=32` positions (the current partial block). Once a block fills and commits to int4, the bf16 copy of those positions is dead weight.

## What the kernel actually does today (verification needed)

The kernel signature (`flash_attn_with_int4_kvcache` in the forked
`vllm-flash-attn`) receives BOTH:

- `bf16_k_batch` — full-precision K, shape `(B, S_padded, H, D)`
- `k_packed_int4` (+ scale + xmin + protect_bf16 + protect_slot) — int4-quantized K with sidecars

There are three possible kernel implementations:

| Variant | Description | What happens if we shrink bf16 to BS |
|---|---|---|
| (a) **Tail-only-bf16** | Use bf16 for positions `last_block_start..cache_seqlens`; dequantize int4 for `0..last_block_start`. | **Works as-is.** The kernel was always reading only the tail of bf16. We just stop allocating the body. |
| (b) **Always-bf16** | Use bf16 for all `0..cache_seqlens`; int4 is unused. | Kernel breaks. The proposed change requires a kernel-side update to add the int4 dequant path. |
| (c) **Tail-bf16 + index from absolute** | Use bf16 for tail, but indexed at absolute seq_pos (not tail-relative). | The kernel reads `bf16_k_batch[:, seq_pos, ...]`; if our shrunken pool is tail-relative `bf16_k_batch[:, seq_pos % BS, ...]`, the indices don't match. Need a kernel update. |

**Verification step (gate, no code change yet):** read the relevant
kernel CUDA/CUTLASS code in `vllm_flash_attn` to determine which
variant we're in. The verification should produce a one-paragraph
finding answering:

- Does the kernel read `bf16_k_batch` at positions ≥ `last_block_start`
  (= the partial tail)? If yes → variant (a) or (c).
- Does the kernel read `bf16_k_batch` at positions < `last_block_start`
  (= older committed blocks)? If yes → variant (b) — kernel needs an
  update before we can shrink.

The verification is mechanical (reading `~100-200 lines` of kernel
code in `_vllm_fa2_C.abi3.so`'s source, which lives at
`/workspace/dev/vllm-flash-attn-dev/` per the install script). One
session.

## Proposed change (variant a — the optimistic path)

Assuming variant (a) — the kernel correctly reads only the tail of
`bf16_k_batch` — the Python-side change is small and entirely
contained in `phase5b_4c_paged_writer.py` and
`phase5b_backend_install.py`. No kernel code changes.

### Edit 1: shrink the pool allocation

`phase5b_4c_paged_writer.py` `_lazy_alloc`:

```python
# OLD
self._bf16_k_backing_pool = torch.zeros(
    (n_slots, max_S, H, D), dtype=torch.bfloat16, device=device,
)
self._bf16_v_backing_pool = torch.zeros(
    (n_slots, max_S, H, D), dtype=torch.bfloat16, device=device,
)

# NEW
self._bf16_k_backing_pool = torch.zeros(
    (n_slots, BS, H, D), dtype=torch.bfloat16, device=device,
)
self._bf16_v_backing_pool = torch.zeros(
    (n_slots, BS, H, D), dtype=torch.bfloat16, device=device,
)
self._bf16_window_size = BS    # documented invariant
```

At `n_slots=64`, layers=28: drops from 28 × 64 × 4096 × 4 × 128 × 2 = **29 GB** to 28 × 64 × 32 × 4 × 128 × 2 = **~225 MB**. A **~130× reduction**.

### Edit 2: change writes to be tail-relative

The bf16 backing now stores only positions in the current partial
block. Writes happen at `seq_pos % BS`, not `seq_pos`.

`phase5b_4c_paged_writer.py` `_write_into_state` (prefill / legacy):

```python
# OLD
state.bf16_k_backing[0, state.seq_pos:state.seq_pos + n_real] = real_key

# NEW
# Write each token at (seq_pos + i) % BS within the BS-sized window.
# If n_real spans a block boundary, that's fine because the kernel
# will see fully-committed older blocks via int4 + protect; only the
# last partial-block tail needs bf16.
for i in range(n_real):
    pos_in_block = (state.seq_pos + i) % BS
    state.bf16_k_backing[0, pos_in_block] = real_key[i]
    state.bf16_v_backing[0, pos_in_block] = real_value[i]
```

(Loop is at most BS=32 iterations; this is a fix, not a hot path. The
true hot path is `write_decode_batched`, below.)

`phase5b_4c_paged_writer.py` `write_decode_batched` (captured region):

```python
# OLD
seq_pos_t = self._seq_pos_pool[slot_idx_t].long()
self._bf16_k_backing_pool[slot_idx_t, seq_pos_t] = key
self._bf16_v_backing_pool[slot_idx_t, seq_pos_t] = value

# NEW — same scatter, but the destination position is wrapped to BS.
seq_pos_t = self._seq_pos_pool[slot_idx_t].long()
pos_in_block_t = seq_pos_t % BS                    # device-side modulo
self._bf16_k_backing_pool[slot_idx_t, pos_in_block_t] = key
self._bf16_v_backing_pool[slot_idx_t, pos_in_block_t] = value
```

The `% BS` is a fused device op (no host sync); captured-graph-safe.

### Edit 3: change reads to return the partial tail only

`phase5b_4c_paged_writer.py` `get_bf16_backing_batched_by_slots`:

```python
# OLD
def get_bf16_backing_batched_by_slots(self, slot_idx_tensor, S_padded):
    max_S = self._bf16_k_backing_pool.shape[1]
    if S_padded > max_S:
        raise RuntimeError(...)
    bf16_k = self._bf16_k_backing_pool[slot_idx_tensor, :S_padded]
    bf16_v = self._bf16_v_backing_pool[slot_idx_tensor, :S_padded]
    return bf16_k, bf16_v

# NEW — the pool IS the partial-block window. Return it as-is per slot.
def get_bf16_backing_batched_by_slots(self, slot_idx_tensor, S_padded):
    # S_padded is no longer used to slice; it indicates the kernel's
    # tile budget but the actual bf16 covers only the last BS tokens.
    bf16_k = self._bf16_k_backing_pool[slot_idx_tensor]   # (B, BS, H, D)
    bf16_v = self._bf16_v_backing_pool[slot_idx_tensor]   # (B, BS, H, D)
    return bf16_k, bf16_v
```

Caller (`phase5b_backend_install.py:_read_decode_packed_batched`) needs the kernel call updated:

```python
# OLD
out = flash_attn_with_int4_kvcache(
    query_q,
    bf16_k_batch, v_for_kernel,        # both (B, S_padded, H, D)
    cache_seqlens=cache_seqlens_i32,
    ...
)

# NEW — pass tail-window K/V; kernel infers tail as
# bf16_k_batch[:, (cache_seqlens-1) % BS, :, :] backwards
# (or however the kernel indexes the partial tail — TBD at verify).
out = flash_attn_with_int4_kvcache(
    query_q,
    bf16_k_batch, v_for_kernel,        # both (B, BS, H, D) — the partial-block window
    cache_seqlens=cache_seqlens_i32,
    ...
)
```

If the kernel takes a new `bf16_window_size=BS` parameter (variant c), add it.

### Edit 4: backwards-compat env flag

Keep the old behavior reachable for a release cycle while we verify:

```python
# In _lazy_alloc:
if _bf16_backing_window_mode() == "full":
    # Legacy: full-history bf16 backing (Phase 5/6 default).
    ...
else:  # default: "partial_block"
    # Phase 6C: BS-window only.
    ...
```

Env override: `PHASE6C_BF16_BACKING_WINDOW=full` reverts to legacy. Default is `partial_block`. Same bisection-primitive pattern as `PHASE6B1_USE_DECODE_BATCHED`, `PHASE6B2_INSTALL_HOOK`, `PHASE6B3_FORCE_EAGER`.

## CPU test plan (gate before GPU)

| Test | Purpose | Pass criterion |
|---|---|---|
| `verify_phase6c_bf16_window_byte_equiv.py` | Show that with `PHASE6C_BF16_BACKING_WINDOW=full` (legacy), the writer + read produces byte-identical output to pre-6C state. | Same K/V trajectory on a deterministic 32-token decode for both modes. |
| `verify_phase6c_partial_block_bf16_correct.py` | Show that with the new default, the bf16 backing slice the kernel sees matches the last `cache_seqlens % BS` tokens written. | Tail-window contents match the absolute-positioned tokens at every step. |
| `verify_phase6c_g5c_orthogonality.py` | Regen G5c SHA baseline for the 2 modified int4_protected files; assert other 8 unchanged. | 2/10 SHAs change; 8/10 unchanged. |

All three must PASS GREEN on CPU before any GPU work.

## GPU verification gate (after CPU GREEN)

Re-run the existing 6B.4 bench on the same workload:

```bash
python CTM_plus/Bench/scripts/bench_phase6_b4_throughput_gpu.py
```

**G_BACKING_POOL_REDESIGN (Phase 6C acceptance):**

1. **HBM footprint:** captured cell HBM < bf16 cell HBM at `n_slots=64`, `max_model_len=4096`. Expected: ~34 GB vs bf16's 38.52 GB.
2. **No correctness regression:** 6B.3 smoke (semantic-eq gate) re-runs GREEN with no changes.
3. **Throughput restoration:** `cap/bf16` ratio at B=8 improves from current 0.26× to **≥ 0.5×** (still informational, not a hard gate — but signals the backing pool was the bottleneck).
4. **No throughput regression at low B:** `cap/eager` at B=8 stays ≥ 1.2× (current 1.42×). The captured-graph uplift must not disappear.

If (1) PASS and (2) PASS but (3) and (4) RED → diagnosis: the bandwidth pressure on bf16 backing wasn't the dominant factor at high B; the kernel itself is the bottleneck. Phase 6D: kernel investigation. The 6C work still ships because memory wins regardless.

If (1) RED → the writer state isn't the dominant memory consumer; revisit assumptions and re-profile HBM.

## Estimated effort

| Stage | Work | Time |
|---|---|---|
| Kernel verification | Read 100-200 lines of `vllm_flash_attn`'s int4 CUDA source; produce one-paragraph finding. | 0.5 day |
| Python implementation | The 4 edits above + env flag. | 0.5 day |
| CPU test suite | 3 verifiers, ~150 lines each. | 1 day |
| GPU verification + finding | Run bench; write `PHASE_6C_BACKING_POOL_FINDINGS.md`. | 0.5 day |
| **Total** | | **2.5 days + ~$0.10 GPU** |

## Risks

1. **Variant (b) — kernel always uses bf16 for everything.** If the kernel does NOT internally use int4 for older positions, shrinking the bf16 backing breaks correctness. Mitigation: the kernel verification step gates Python work. If (b), the kernel needs a small update to add the int4 dequant body path — outside Python-only scope; estimate +2-3 days kernel work.

2. **Variant (c) — kernel indexes bf16 at absolute seq_pos.** Similar to (b) but smaller fix — kernel needs to be told the bf16 buffer is tail-relative. Could be done by adding a `bf16_tail_start` kernel parameter. Estimate +1 day kernel work.

3. **Throughput regression at low B.** The `% BS` device op adds 1-2 µs per layer per decode step. At B=1 with 28 layers and 32 decode steps, that's ~1ms total — negligible. But if the captured graph's scheduler can't fuse it well, could hurt 6B.3's small-B win. Mitigation: the env flag lets us A/B compare immediately.

4. **Edge case: protect_bf16 buffer.** The k_protect_ext + sidecars are sized per-block in `kv_cache` (NOT per-slot history), so they don't need shrinking — but worth confirming during implementation that we don't accidentally also assume max_S indexing there.

## Files that will change (G5c SHA delta projection)

Only 2 of the 10 int4_protected files change in 6C:

* `KVPolicy/kv_policy/phase5b_4c_paged_writer.py` — pool allocation, `_write_into_state`, `write_decode_batched`, `get_bf16_backing_batched_by_slots`, env flag, prop changes.
* `KVPolicy/kv_policy/phase5b_backend_install.py` — `_read_decode_packed_batched` kernel call (only if the kernel needs a new `bf16_window_size` param).

All other 8 stay byte-identical. G5c baseline regen will reflect 2/10 SHA changes.

## Deferred (post-6C)

* **B=64+ scaling:** with the memory savings 6C delivers, the bench can extend to B=64, B=128. Likely shows where int4_protected meaningfully wins vs bf16 (high concurrency + memory-constrained hardware).
* **Long context (16K, 32K):** bf16 KV cache scales linearly with context; int4's int4 cache also scales but at 25% the rate. After 6C the bf16 backing is bounded at BS regardless. At 16K+ context, int4 should pull ahead on memory by a large margin.
* **The `_v_bf16_ext` lazy-alloc-in-graph bug** (from 6B.3 finding) is orthogonal and unaffected by 6C; fix on a separate work item.
* **Cross-family verification:** Mistral-7B-Instruct re-run post-6C to confirm portability.
