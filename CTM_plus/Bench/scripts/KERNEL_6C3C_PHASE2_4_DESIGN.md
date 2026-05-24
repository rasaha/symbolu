# Phase 2.4 — REAL INT4 K HBM read (the memory-savings step)

> **The flagship blocker.** Phase 5A proves the kernel + algorithm work
> end-to-end on real Qwen2.5-7B, but K and V still live in HBM as BF16.
> No memory savings are realized yet. Phase 2.4 changes K's HBM layout
> from BF16 → packed uint8 (2 INT4 values per byte) plus a side
> channel of scales/offsets/protect-K BF16 values. The kernel reads
> packed K + side channel directly from HBM, dequantizes in registers,
> blends with the protected channels, runs attention. **First phase
> with a real memory-savings claim.**
>
> V stays BF16 in HBM through Phase 2.4 v1 (in-register Phase 3
> quant still runs). Adding V to the packed path is Phase 2.6
> (same surface as K, decoupled to bound risk).

## What Phase 2.4 must deliver

| Requirement | Definition of done |
|---|---|
| **Packed INT4 K in HBM** | Sidecar tensor `(1, max_seqlen, H_kv, D/2) uint8` populated at prefill end by packing the original BF16 K |
| **Kernel reads packed K** | `flash_attn_with_int4_kvcache` (or a new `_packed` variant) loads packed uint8 + scales + offsets from HBM, unpacks in-register, dequantizes, runs attention |
| **Protect-K side channel** | Separate BF16 sidecar `(1, max_seqlen, H_kv, n_protect)` carrying the top-fraction outlier channels at full precision; blended in-register before the qK dot |
| **Scale/offset layout** | Per-(group, H_kv, D) BF16 scale + BF16 offset; group_size_k=32 along seq |
| **Correctness vs Phase 5A** | Cosine ≥ 0.9995 vs Phase 5A's BF16-K path (it's the same algorithm; only WHERE the bits live differs) |
| **Memory measurement** | Real HBM byte accounting via `nvidia-smi` + `torch.cuda.max_memory_allocated` before/after the sidecar swap |
| **Throughput measurement** | Decode tok/s with packed K vs Phase 5A's BF16 sidecar (Phase 5A's 2.8× slowdown should narrow because the sidecar bandwidth drops 4×) |

## Memory accounting — honest numbers

Qwen2.5-7B at S=32k, 28 layers, H_kv=4, D=128, BF16:

| Storage | Bytes per element | Total for K (B=1, S=32k) | Total for V (B=1, S=32k) |
|---|---|---|---|
| **FP16/BF16 baseline** | 2.0 | ~1.84 GB / layer-stack | ~1.84 GB |
| Phase 5A sidecar | 2.0 (FP16) | ~1.84 GB | ~1.84 GB |
| **Phase 2.4 K-packed sidecar** | | | |
|   `k_int4` uint8 | 0.5 (1 byte / 2 elem) | ~0.46 GB | — |
|   `k_scale` BF16 per group | 2 / 32 = 0.0625 | ~0.057 GB | — |
|   `k_offset` BF16 per group | 0.0625 | ~0.057 GB | — |
|   `k_protect_bf16` (top-4%, ~5/128) | 2.0 × 0.039 | ~0.072 GB | — |
|   `protect_indices` int32 (one-time) | — | ~14 KB | — |
|   **K sidecar total** | | **~0.65 GB** | — |
|   V FP16 (unchanged in v1) | 2.0 | — | ~1.84 GB |
| **Sidecar total (K+V)** | | | **~2.5 GB** |

**Phase 5A → Phase 2.4 sidecar shrink: 3.7 GB → 2.5 GB** (33% reduction).

**Vs vLLM stock FP16 paged cache (3.7 GB):** Phase 2.4 sidecar at 2.5 GB
is **still HIGHER**. Why? Because vLLM's paged K cache is still
populated during prefill (we call the original `forward`), so we have
BOTH the packed sidecar AND vLLM's BF16 paged cache. **Dual storage.**

To realize true savings vs stock FP16, **Phase 2.4.b** frees vLLM's
paged K cache after prefill (we don't need it — our sidecar is the
truth). This is decoupled because it requires touching vLLM's block
manager, which the runbook scopes as a separate substep.

| Stage | Total KV memory at S=32k | Vs stock FP16 |
|---|---|---|
| Stock FP16 (vLLM only) | 3.7 GB | 1.0× (baseline) |
| Phase 5A (BF16 sidecar + vLLM paged) | ~7.4 GB | 2.0× WORSE |
| **Phase 2.4.a** (packed sidecar + vLLM paged) | ~6.2 GB | 1.7× worse |
| **Phase 2.4.b** (packed sidecar, free vLLM K) | ~2.5 GB (K-only saved) | **0.68× = 1.5× better** |
| Phase 2.6 (also pack V) | ~1.3 GB | **0.35× = 2.85× better** |
| Phase 5B (real block-manager integration) | ~1.0 GB | **0.27× = 3.7× better** |

**The headline 4× memory savings claim from §20.4.3 doesn't fully land
until Phase 2.6 + Phase 5B.** Phase 2.4.b alone gets us to ~1.5×
better on K-only, which is the immediate Phase 2.4 deliverable.

## Architecture — sidecar layout

Replace Phase 5A's `Phase5ANativeCache` (FP16 K/V buffers) with a new
`Phase2_4PackedCache` with these fields per layer:

```
k_int4:           (1, max_seqlen, H_kv, D/2)            uint8
k_scale:          (1, max_seqlen/G, H_kv, D)            bf16    # G = 32
k_offset:         (1, max_seqlen/G, H_kv, D)            bf16
k_protect_bf16:   (1, max_seqlen, H_kv, n_protect)      bf16
protect_indices:  (H_kv, n_protect)                     int32   # static after prefill
v_fp16:           (1, max_seqlen, H_kv, D)              bf16    # Phase 2.4 v1: V stays FP16
s_curr:           int
mask_frozen:      bool
```

Sequential lifetime (same as Phase 5A — append on prefill, read on
decode). The `k_int4` + `k_scale` + `k_offset` together carry the
quantized K. `k_protect_bf16` carries the per-token values of the
top-`n_protect` channels at full precision (selected by the static
`protect_indices` computed at prefill end).

## Architecture — kernel read path

The current Phase 2.3 + 4 kernel:
1. Reads BF16 K from HBM via the CUTLASS atom (`gmem_tiled_copy_KV`).
2. In-register: computes per-group max/min, quantizes, dequantizes,
   skips protected channels.
3. Result in smem is BF16 K (mostly dequant'd, protected channels
   at original BF16).
4. GEMM consumes smem K via `smem_tiled_copy_K`.

Phase 2.4 replaces step 1+2:

1. **Custom HBM load for packed K.** Bypass CUTLASS (which can't type
   uint8 packed). Use `__ldg(reinterpret_cast<uint4*>(ptr))` for
   16-byte loads (= 16 uint8 = 32 INT4 values per load per thread).
   Compute the global pointer manually using scaled strides
   (`stride × group_size / 2` for the packed dim).
2. **Load scales/offsets via cp.async.** Per (group, H_kv) pair —
   smaller bandwidth than K itself. Stage to smem scratchpad,
   broadcast to threads.
3. **Load protect sidecar via cp.async.** Per-token BF16 for the
   `n_protect` channels. Bandwidth is small (~4% of K's bandwidth).
4. **In-register: unpack int4 from uint8** (`nibble & 0x0F`,
   `nibble >> 4`), cast to int8 in [-8, 7], dequantize via
   `x_hat = q_unsigned * scale + offset_minus_eight_scale` per
   the route-B convention (matches Phase 2.3's helper math byte-
   for-byte).
5. **Blend protect channels in-register.** For channels in
   `protect_indices`, replace the dequant'd value with the BF16
   sidecar value. Equivalent to Phase 4's mask-based skip, just
   re-architected for the HBM-loaded protect tensor.
6. **Write BF16 result to smem.** GEMM proceeds unchanged.

The new kernel template parameter `bool Is_int4kv_packed` selects
between Phase 2.3+4 path (BF16 K from HBM, in-register quant) and
Phase 2.4 path (packed K from HBM, no in-register quant). When
`false`, Phase 2.5's template gating still applies (zero stock cost).

## Scale/offset arithmetic — must match route-B exactly

Same numerical convention as Phase 2.3 (`int4_inline.h`):

```
# At pack time (Python, prefill end):
x_max = group_max(K)
x_min = group_min(K)
scale = max((x_max - x_min) / 15.0f, 1e-8f)
q_unsigned = round((x - x_min) / scale).clamp(0, 15)  # 4 bits each
# Pack: pair adjacent d-channels into a uint8 byte
#   byte = q_unsigned[d_even] | (q_unsigned[d_odd] << 4)
# Side channel: scale + offset stored as bf16

# At read time (CUDA kernel):
byte = load uint8 from HBM
q_even = byte & 0x0F     # low nibble
q_odd  = byte >> 4       # high nibble
# Per-channel dequant:
x_hat = q * scale + x_min  # x_min = offset - 8*scale (encoded form)
```

The arithmetic is bit-identical to Phase 2.3's in-register path —
Phase 2.4 just moves the quantization from "compute in-register every
call" to "compute once at prefill end, read from HBM every call."

**Critical:** the packing function on the Python side and the unpack
function in the kernel MUST mirror exactly. Off-by-one in the nibble
order, the [0,15] vs [-8,7] convention, the (scale, offset) encoding
— any drift between pack and unpack tanks the cosine. Cosine vs
Phase 5A path is the gate (target ≥ 0.9995).

## Correctness target

Phase 5A's output IS the correctness reference. The math is identical
(same algorithm, same per-group scale/offset, same protect-K skip).
The only difference is bit-storage order. Concretely:

| Test | Gate |
|---|---|
| `verify_phase2_4_packed.py` cosine vs Phase 5A on Qwen2.5-7B at S=4k | ≥ 0.9995 |
| Same `XYZ123` smoke prompt as Phase 5A | output should match Phase 5A bit-for-bit modulo ~1e-5 cosine |
| Memory measurement: K sidecar bytes | ≤ 0.7 GB at S=32k (target ~0.65 GB) |

(The Phase 5A vs FP16 cosine of ~0.997 is the algorithm floor. Phase
2.4 doesn't change the algorithm, so cosine vs FP16 should also be
~0.997. Cosine vs Phase 5A should be ~1.0.)

## Implementation sub-phases

Five sub-steps. Total effort: ~3-5 engineer-days.

### Phase 2.4.0 — Python pack/unpack helpers (~0.5 day)

Standalone Python functions in `kv_policy/phase2_4_packed_kv.py`:
- `pack_k_to_int4(k_bf16, group_size_k=32, protect_indices) -> (k_int4, k_scale, k_offset, k_protect_bf16)`
- `unpack_k_from_int4(k_int4, k_scale, k_offset, k_protect_bf16, protect_indices) -> k_bf16` (for round-trip validation)
- Tests: `assert torch.allclose(unpack(pack(k)), k, atol=...)` on random Qwen-shaped K.

### Phase 2.4.1 — Custom HBM-load CUDA path (~2-3 days, the hard one)

In `csrc/flash_attn/src/`:
- New helper `int4_packed_load.h`: `load_unpack_dequant_K_block_into_smem<...>(packed_ptr, scale_ptr, offset_ptr, protect_ptr, protect_indices_ptr, smem_K)`.
  - Compute per-thread packed K pointer offset.
  - `__ldg` 16-byte vector load (32 INT4 values per thread).
  - Unpack to int8 in registers.
  - cp.async scales + offsets to a smem scratchpad (4 KB).
  - cp.async protect channels to a smem scratchpad (~0.5 KB at n_protect=5).
  - Dequantize per-channel, blend protect.
  - Write BF16 to smem K tile.
- Wire into `flash_fwd_kernel.h` at the same 3 K-load sites, gated on a new template param `bool Is_int4kv_packed`. When true, REPLACE the existing cp.async (gmem_tiled_copy_KV) + Phase 2.3 in-register transform with this packed-load helper. When false, Phase 2.3 behavior unchanged.

### Phase 2.4.2 — Python install integration (~0.5 day)

In `kv_policy/phase5a_native_install.py` (extend) or new
`kv_policy/phase2_4_native_install.py`:
- New cache class `Phase2_4PackedCache` with the layout above.
- At prefill end: pack K via Phase 2.4.0 helpers, store in the new cache.
- At decode: call `flash_attn_with_int4_kvcache_packed(q, k_int4, k_scale, k_offset, k_protect, protect_indices, v_fp16, cache_seqlens, ...)`.
- Same monkey-patch pattern as Phase 5A.

### Phase 2.4.3 — Correctness verification (~0.5 day)

`verify_phase2_4_packed.py`:
- Load Qwen2.5-7B.
- Same `XYZ123` prompt as Phase 5A smoke.
- Run via Phase 5A install (BF16 K) — capture output text + intermediate attention outputs.
- Run via Phase 2.4 install (packed K) — capture same.
- Compare: cosine ≥ 0.9995, output text matches.

### Phase 2.4.4 — Memory + throughput measurement (~0.5-1 day)

`measure_phase2_4_memory.py`:
- Load Qwen2.5-7B.
- Pre-install snapshot: `torch.cuda.max_memory_allocated()`.
- Run Phase 5A install + generate, snapshot.
- Run Phase 2.4 install + generate, snapshot.
- Compute K sidecar bytes (Phase 2.4 should be ~5× smaller than Phase 5A's).
- Decode throughput: tok/s for both paths at S=4k decode.

## Key design questions to lock BEFORE code

These are the four-way design choices the implementation will commit
to. I want your decision on each before writing the patcher.

1. **Sidecar layout — separate tensors or one fat allocation?**
2. **vLLM paged K cache — keep both (simpler), or free after prefill (real savings, but more invasive)?**
3. **V cache — stay BF16 sidecar in Phase 2.4, or also pack now?**
4. **Custom load atom or full bypass?**

I'll ask these via `AskUserQuestion` once you've signed off on the
scope above (you can override the design doc's recommendations there).

## Risk callouts

1. **Custom HBM load is the project's hardest remaining unknown.** The
   risk brief in `KERNEL_6C3C_PHASE12_CODEREAD.md` flagged this
   originally as Phase 2's biggest concern. The runtime gate is "can
   we compute the right page-aware pointer arithmetic and unpack
   correctly". Mitigation: standalone unit test for pack/unpack
   round-trip before integrating.

2. **Three concurrent cp.async streams** (K_int4, K_scale,
   K_protect). Bandwidth contention. May need to pipeline carefully
   or accept some serialization.

3. **Scale/offset accuracy.** BF16 scale has 7 bits of mantissa. For
   small groups (G=32), this could introduce drift vs Phase 2.3's
   in-register FP32 arithmetic. Mitigation: verify cosine vs Phase 5A
   at ≥ 0.9995 (if FP16 scale is insufficient, fall back to FP32
   scale at 4× the scale-bytes cost — still negligible).

4. **vLLM paged cache duplication** = Phase 2.4 doesn't actually
   shrink HBM vs stock vLLM until 2.4.b lands. The user-facing
   "memory saved" claim needs Phase 2.4.b. Phase 2.4.a alone is the
   technical milestone.

5. **Template explosion.** Now we have `Is_int4kv` and
   `Is_int4kv_packed` as two template params on the splitkv kernel.
   3 specializations: stock, Phase 2.3+4 (BF16-K + in-register
   quant), Phase 2.4 (packed-K + HBM load). Wheel size grows.
   Mitigation: keep the int4 specializations narrow (hdim=128, bf16,
   non-causal only).

## Scope DEFERRALS (not in Phase 2.4 v1)

- **V cache packed.** Phase 2.6 — mirrors Phase 2.4 for V (per-token
  quant, group along head_dim). Roughly the same effort. Decoupled
  so K can ship/measure on its own.
- **Free vLLM paged K cache.** Phase 2.4.b — adds the actual HBM
  memory win vs stock. Currently outscoped because it touches vLLM
  block manager. Could go in Phase 2.4 if user accepts.
- **vLLM block manager integration.** Phase 5B — first-class
  `kv_cache_dtype="int4_protected"`, multi-sequence, prefix caching.
- **Throughput parity with FP16.** Phase 6.1 — requires Phase 2.4
  packed + Phase 2.4.b paged-cache freed + Phase 2.6 packed V.

## Acceptance — what must be GREEN to call Phase 2.4 done

1. `verify_phase2_4_packed.py` PASS — cosine vs Phase 5A ≥ 0.9995 on
   Qwen2.5-7B at S=4k.
2. Smoke test produces sensible decoded text (matches Phase 5A's
   `XYZ123XYZ123` correctly).
3. K sidecar memory measurement: packed sidecar ≤ 0.7 GB at S=32k
   (vs Phase 5A's ~1.84 GB on K alone).
4. Phase 5A smoke still GREEN (we don't break the BF16-K path).
5. Stock vLLM still GREEN (template gating from Phase 2.5 still
   isolates int4 from stock).

## What unlocks after Phase 2.4 GREEN

| Phase | Adds |
|---|---|
| **Phase 2.4.b** | Free vLLM paged K cache; net K-only savings vs stock |
| **Phase 2.6** | Pack V cache → full sidecar memory shrunk to ~1 GB at S=32k |
| **Phase 6.1-6.3** | Throughput + memory measurement at the full ship config — the headline v1 numbers |
| **Phase 5B** | Multi-sequence vLLM serving (batch > 1, `kv_cache_dtype` flag) |
| **Phase 6.4-native** | Run protect-fraction sweep through the packed path (transitive equivalence proof for the v1 claim) |
