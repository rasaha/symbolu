# Phase 5B.4c — write + read path design (architecture lock)

> Phase 2.6 GREEN (commit `b37e199`): kernel-side V INT4 packing
> verified (cosine 0.9999595 vs Phase 5A; K-only regression bit-equal).
> V-lossiness blocker resolved. This doc locks the write + read path
> architecture for 5B.4c before any code lands. Read after
> `KERNEL_6C3C_PHASE5B4C_PLAN.md` (which framed the four options) and
> `KERNEL_6C3C_PHASE2_6_V_PACK_DESIGN.md` (which locked the V pack
> shape).

## Late-binding constraint (discovered during 5B.4c.2 read-path design)

**Kernel `kInt4GroupSize = 32` is a compile-time constexpr** — not a
runtime parameter. The Phase 2.4.1b kernel was only instantiated at
G=32. The kernel reads `k_scale` at stride `S / 32`; passing a
`packed_group_size=16` tensor (with stride `S / 16`) silently produces
wrong results.

Mitigation: require **vLLM `block_size=32`** at LLM construction so
`block_size == kernel kInt4GroupSize == 32`. PHASE5B5C_DESIGN.md Q2's
"G=16=block_size" lock was incorrect (it didn't check the kernel
constraint). Real lock: **G = block_size = kInt4GroupSize = 32**.

Cost: one user-visible config requirement (`block_size=32` instead of
the typical default 16). num_blocks halves at the same memory budget,
but block_table indirection halves too — net wash.

Alternative (deferred): rebuild the kernel with G=16 by editing the
constexpr + reinstantiating. ~1-2 hours of CUDA work + recompile.
Not required for v1.

## TL;DR — four locks

1. **K sidecars external, parallel to block_table.** K_scale, K_xmin,
   K_protect_bf16 live OUTSIDE vLLM's paged tensor, in per-layer
   tensors indexed by global `block_id`.
2. **Block-to-contiguous bridge = gather per decode step.** Use
   `block_table` to assemble a contiguous `(1, S, H_kv, D/2)` view
   per call, then invoke the existing Phase 2.4.1b/2.6.2 packed
   kernel unchanged. Block-table-aware kernel path is deferred to
   a later perf polish phase.
3. **K partial-group reads = hybrid (packed full + bf16 staging
   tail).** For the last < G tokens that haven't filled a group,
   build the contiguous K from packed nibbles for the complete
   region ∪ in-RAM staging buffer dequantized to bf16 for the
   partial tail. No re-quantization, no provisional scales.
4. **All quantization sidecars external — none in slot.** vLLM's
   paged uint8 cache holds ONLY nibbles (first 64 of the 128 bytes
   per K|V slot per kv-head). Scale, xmin, protect tensors are
   external. Cleaner Python, simpler kernel input prep.

## Per-layer external sidecar shapes

For a layer at `num_blocks=NB`, `block_size=BS=16`, `H_kv`,
`head_dim=D=128`, `n_protect` (frozen per model), `v_group_size=32`,
`v_n_groups = D / v_group_size = 4`:

| Tensor | Shape | dtype | Bytes |
|---|---|---|---|
| `k_scale_ext`   | `(NB, H_kv, D)`              | bf16 | NB · H · D · 2 |
| `k_xmin_ext`    | `(NB, H_kv, D)`              | bf16 | NB · H · D · 2 |
| `k_protect_ext` | `(NB, BS, H_kv, n_protect)`  | bf16 | NB · BS · H · n_p · 2 |
| `v_scale_ext`   | `(NB, BS, H_kv, v_n_groups)` | bf16 | NB · BS · H · v_ng · 2 |
| `v_xmin_ext`    | `(NB, BS, H_kv, v_n_groups)` | bf16 | NB · BS · H · v_ng · 2 |

For Qwen2.5-7B at NB=19054, H_kv=4, D=128, n_protect=5, BS=16:
- k_scale_ext, k_xmin_ext: 19 MB each per layer
- k_protect_ext: 12 MB per layer
- v_scale_ext, v_xmin_ext: 10 MB each per layer
- Total per layer: ~70 MB
- Total 28 layers: ~1.95 GB

This sidecar overhead is real — must be reported honestly in 5C
acceptance accounting.

## Per-slot byte usage in vLLM's paged cache

For each `(slot, h_kv)` slot in `kv_cache[0]` (K half):
```
bytes 0..63    : K packed nibbles (D/2 = 64)
bytes 64..127  : unused (64 bytes)
```

For each `(slot, h_kv)` slot in `kv_cache[1]` (V half):
```
bytes 0..63    : V packed nibbles (D/2 = 64)
bytes 64..127  : unused (64 bytes)
```

The "unused" 64 bytes per K|V slot is wasted vs an ideal layout, but
- keeps the shared (2, NB, BS, H_kv, D) shape contract clean,
- preserves the locked 5B.4b shape (no further allocator surgery),
- defers in-slot packing as a Phase 6 micro-optimization.

## Honest per-token memory math (v1 ship config)

| Storage class | Bytes/equivalent-token |
|---|---|
| vLLM paged cache (uint8 D=128, K+V both halves at 2× capacity) | 256 (= 128 K-slot + 128 V-slot for the 2× capacity unit) |
| External K_scale (NB-shape, amortized per-token) | ~16 (= H·D·2 / BS per block-token = 1024 / 16 = 64; ÷ 4 for H_kv → 16 per-head-token; report H-rolled at 64) |
| External K_xmin | same as K_scale |
| External K_protect (n_protect=5) | 10 (= n_protect·2 per slot) |
| External V_scale (v_n_groups=4) | 8 |
| External V_xmin | 8 |

Net (rolled across H_kv): vLLM 256 bytes/token + externals ~158
bytes/token = ~414 bytes/token vs stock bf16 512 bytes/token.

**Net savings: ~19% per equivalent stored token.**

Effective KV reserve growth: vLLM still allocates ~24 GiB for the
uint8 paged cache (same reserve as stock at same gpu_memory_utilization).
That reserve holds 2× as many tokens as stock bf16. Externals add
~2 GB on top. **Net result: 2× context-or-batch capacity at +2 GB
total cost vs stock.**

The 60% savings claim in `KERNEL_6C3C_PHASE5B5C_DESIGN.md:99-103`
omits the H_kv multiplier in K_scale/xmin sizing. Real number is ~55%
once you count externals correctly. v1 ship copy must reflect.

## Write-path mechanics (5B.4c.1)

`Int4ProtectedAttentionImpl.forward` replaces
`torch.ops._C_cache_ops.reshape_and_cache_flash(...)` with a call to
`PagedKVWriter.write(key, value, kv_cache, slot_mapping)`.

For each new K/V token `t` mapped to `slot = slot_mapping[t]`:

1. Compute `block_id = slot // BS`, `pos = slot % BS`.
2. **V (per-token, vectorized over H_kv, D):**
   - Quantize value[t] using `v_group_size=32` (4 groups along D).
   - Write packed nibbles to `kv_cache[1, block_id, pos, :, :D//2]`.
   - Write per-token (h, group) scale to `v_scale_ext[block_id, pos]`.
   - Write per-token (h, group) xmin to `v_xmin_ext[block_id, pos]`.
3. **K (staged):**
   - Extract protected-channel values via gather to
     `k_protect_ext[block_id, pos]`.
   - Place `key[t]` into `k_stage[pos]` (staging buffer).
   - Track `k_stage_block_id = block_id`.
   - When `pos == BS - 1` (block boundary), the group is complete:
     - Compute per-(h, d) scale/xmin over the 16 staged tokens.
     - Quantize all 16 tokens, pack nibbles.
     - Write the (16, H, D/2) packed nibbles to
       `kv_cache[0, block_id, :, :, :D//2]`.
     - Write (H, D) scale/xmin to `k_scale_ext[block_id]`,
       `k_xmin_ext[block_id]`.

Partial-group invariant at end of step: the LAST partial group's
true bf16 K values live in `k_stage[0:k_stage_count]`. The paged
cache's K nibbles for that block are stale until the group fills.

Per-layer state (batch=1 v1):
- `k_stage`: `(BS, H_kv, D)` bf16 staging buffer
- `k_stage_count`: int 0..BS-1
- `k_stage_block_id`: which block_id we're filling
- `k_scale_ext`, `k_xmin_ext`, `k_protect_ext`, `v_scale_ext`,
  `v_xmin_ext`: lazy-allocated on first forward (need `kv_cache.shape`)

Multi-batch (Phase 5B.5+): per-sequence staging buffers keyed by a
sequence ID we get from `attn_metadata`. Out of 5B.4c scope.

## Read-path mechanics (5B.4c.2)

Replaces `flash_attn_varlen_func(prefill ...)` and
`flash_attn_with_kvcache(decode ...)` with
`flash_attn_with_int4_kvcache(...)`.

### Gather to contiguous per decode step

For a sequence with `block_table = [b0, b1, ..., b_{n-1}]`, build:

```python
# Pseudocode — kv_cache[0/1] shape (NB, BS, H_kv, D=128) uint8
k_blocks = kv_cache[0][block_table]   # (n, BS, H_kv, D) uint8
v_blocks = kv_cache[1][block_table]   # (n, BS, H_kv, D) uint8

# Extract nibbles slice (first D/2 bytes of each slot)
k_nibbles_paged = k_blocks[..., :D//2].view(1, n*BS, H_kv, D//2)
v_nibbles_paged = v_blocks[..., :D//2].view(1, n*BS, H_kv, D//2)

# Sidecars — gather by block_id, reshape to kernel-expected layout
k_scale_paged = self.k_scale_ext[block_table].unsqueeze(0)   # (1, n, H_kv, D)
k_xmin_paged  = self.k_xmin_ext [block_table].unsqueeze(0)   # (1, n, H_kv, D)
k_prot_paged  = self.k_protect_ext[block_table]              # (n, BS, H_kv, n_p)
k_prot_paged  = k_prot_paged.view(1, n*BS, H_kv, n_protect)
v_scale_paged = self.v_scale_ext[block_table].view(1, n*BS, H_kv, v_n_groups)
v_xmin_paged  = self.v_xmin_ext [block_table].view(1, n*BS, H_kv, v_n_groups)
```

### Hybrid partial-group splice

The last partial group's K nibbles in `kv_cache[0]` are stale. Splice
in the bf16 staging buffer for the partial tail:

```python
s_total = cache_seqlen_for_this_seq        # known from attn_metadata
n_complete_groups = s_total // BS           # groups that have filled
tail_len = s_total % BS                     # 0..BS-1 partial tokens

# Build "as-if-packed" K for the tail by quantizing on the fly
if tail_len > 0:
    tail_bf16 = writer.k_stage[:tail_len]   # (tail_len, H_kv, D) bf16
    tail_packed, tail_scale, tail_xmin = quantize_one_group(tail_bf16)
    # Overwrite the last block's first tail_len slots in our gathered tensors
    last_block_in_gather = n_complete_groups   # 0-indexed block in seq
    k_nibbles_paged[0, last_block_in_gather*BS : last_block_in_gather*BS + tail_len] = tail_packed
    k_scale_paged[0, last_block_in_gather] = tail_scale
    k_xmin_paged [0, last_block_in_gather] = tail_xmin
```

V's partial-group situation is identical to its full-group — V is
quantized per-token and committed each step. No staging buffer for V,
no splice. The gather just reads `v_scale_ext` / `v_xmin_ext` for
all blocks including the partial-tail block. Tail tokens' scale/xmin
are already correctly populated.

### Call the packed kernel

```python
flash_attn_with_int4_kvcache(
    q=q,
    k_nibbles=k_nibbles_paged,
    v_nibbles=v_nibbles_paged,
    k_scale=k_scale_paged, k_xmin=k_xmin_paged,
    k_protect_bf16=k_prot_paged, protect_slot=writer.protect_slot,
    v_scale=v_scale_paged, v_xmin=v_xmin_paged,
    v_group_size=writer.v_group_size,
    cache_seqlens=cache_seqlens_tensor,
    softmax_scale=..., causal=True, ...
)
```

For prefill where `block_tables.numel() == 0`, the K/V come directly
from the live `key`/`value` tensors — no gather, no quantization,
just the normal varlen path. (Or we run them through the writer first
so the staging buffer is primed for the first decode step — TBD in
5B.4c.2.)

## Sub-sub-phase split with gates

| Phase | Scope | Gate |
|---|---|---|
| **5B.4c.1** | Write path only. `PagedKVWriter` class + integration into forward. | Per-layer sidecar tensors populated correctly on first forward; introspection-based verify (no generation correctness yet). Phase 2.4.1b verify still PASSES (the packed K path is independently verifiable). |
| **5B.4c.2** | Read path + hybrid splice. Replace varlen/with_kvcache with packed kernel + gather. | End-to-end generation produces correct decoded text. Cosine ≥ 0.995 vs stock vLLM on a 500-token reference prompt. 0 fallbacks. |
| **5B.4c.3** | Quality acceptance | Phase 6.4-style needle test PASS at chosen `protect_fraction`. Throughput report (acceptable if ≥ 50% of stock vLLM; full parity is later perf work). |

## What 5B.4c does NOT do

- Reserve-line shrink (Phase 5C; needs `profile_run` accounting patch).
- Multi-batch correctness (Phase 5B.5).
- In-slot scale packing (Phase 6 perf polish).
- Block-table-aware packed kernel (Phase 5B.6+ perf polish).
- Pre-RoPE quantization (out of 6c.3C v1 scope).
- FP4/NVFP4 (out of scope).
- Tensor parallelism (out of scope).

## Risk callouts

1. **Per-layer protect mask loading.** The frozen artifact is at
   `$PROTECT_MASK_PATH` (default `/workspace/dev/build-logs/qwen2_5_7b_protect_mask_4pct.pt`,
   override via env). Each `Int4ProtectedAttentionImpl` instance needs
   its own `layer_idx`. Resolved at install time by walking
   `model.named_modules()` and assigning sequential indices. If a
   layer's name parses as `model.layers.<N>.self_attn`, prefer that
   over walk-order to match the calibration script's indexing.

2. **Sidecar device + dtype mismatch.** `k_scale_ext` etc. are bf16
   on the kv_cache's device. The protect_mask artifact is int8 CPU;
   loaded once per layer at lazy-alloc time and `.to(device)`d.

3. **Per-token Python loop at prefill.** T_prompt can be 2k tokens.
   Per-token loop is correct but slow. For v1 correctness we accept
   this; vectorize in 5B.4c v2 if needed.

4. **Hybrid splice correctness.** The partial-group K bf16 staging
   buffer must be quantized with the SAME numerical convention as
   the full-group packed K so dequant in the kernel produces
   consistent values. Use the exact same per-group min/max/scale
   math as `PartialGroupQuantizer._finalize_group`.

5. **Cache-seqlens accounting.** `attn_metadata` provides cache
   seqlen per sequence — we use it to know `tail_len`. Off-by-one
   here breaks the hybrid splice. Verify carefully in 5B.4c.2.

6. **batch=1 v1 invariant.** Multi-sequence concurrent decode would
   corrupt the single per-layer staging buffer. We assert
   `batch_size==1` on forward entry and explicit-error if violated.
   5B.5 lifts.
