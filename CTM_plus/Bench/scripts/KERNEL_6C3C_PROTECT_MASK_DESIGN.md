# Kernel 6c.3C — §7.Q1 protect-mask provenance (design note)

> Closes §7.Q1 of `KERNEL_6C3C_DESIGN.md` (where does the static
> protect-mask come from at decode time). Also revises §5.5 (compact
> vs dense protect-K sidecar layout) — the memory math forces
> compact, not the v1 dense default the runbook had penciled in.
>
> **Scope guard.** Algorithm is unchanged from §20.4.3 — static
> per-sequence-per-layer top-`protect_fraction` channels by max-abs
> magnitude, frozen at end of prefill, never updated during decode.
> This note covers *delivery*, not algorithm.

## 1. The §7.Q1 sub-questions

1. **Is the mask computed during prefill, after prefill, or offline?**
2. **Which object owns it?**
3. **Is it per request, per sequence, per layer, or model-static?**
4. **How does decode retrieve it?**
5. **How does it map to `Flash_fwd_params`?**
6. **What changes in Phase 1 / 2 / 5 depend on it?**

## 2. How route-A v1 currently does it (reference)

`ProtectedKINT4Cache.freeze_protect_mask()` in
`kv_policy/int4_protected_k_cache.py:429`:

```python
# (s_curr, H_kv, D) -> (H_kv, D) max-abs
mag = self.k_fp16_buf[: self._s_curr].abs().amax(dim=0).float()
n_protect = max(1, round(self._protect_fraction * H_kv * D))
idx = torch.topk(mag.reshape(-1), n_protect).indices
flat = torch.zeros(H_kv * D, dtype=torch.int8, device=self._device)
flat[idx] = 1
mask = flat.reshape(H_kv, D)
```

Called lazily on first `kernel_inputs()` (i.e. first decode step) via
the shadow contiguous cache. The shadow cache is per-layer
per-sequence — `INT4CacheKVRouteA._caches: Dict[int, ProtectedKINT4Cache]`
(`int4_cache_kv_route_a.py:222`), keyed by layer id.

Key observations for the 6c.3C port:

- The compute reads the full prefill K (`k_fp16_buf[:s_curr]`),
  produces a `(H_kv, D)` int8 mask, then `k_fp16_buf` is no longer
  needed at full size — only the *protected* channels are kept.
- Lifetime: lives until the sequence completes / cache is reset.
- One-shot work — no streaming/incremental computation.

## 3. 6c.3C native paged design

### 3.1 When (Q1)

**At end of prefill, per-sequence, one-shot.** Same as route-A v1.

- Offline calibration (per-model mask): RULED OUT for v1 — §20.4.3
  validated *per-sequence-static*, not offline-static. The outlier
  channels do correlate with model structure (RoPE, layer-norms),
  but committing to offline calibration without measuring it is
  outside v1 scope. Revisit in v2 once we have v1 numbers.
- Streaming during prefill: RULED OUT — adds complexity for no
  measured gain.

Concretely: at the boundary where the last prefill chunk lands in
the cache and the first decode token's K isn't yet computed, our
attention backend runs the mask-compute pass over the prefill K
that's just been written into vLLM's paged blocks.

### 3.2 Owner (Q2)

**`Int4ProtectedKVAttentionBackend`** — the new attention backend
introduced in Phase 5.1 of the runbook. It holds a per-sequence
state dict.

Not in `AttentionMetadata` (per-step, wrong lifetime). Not in the
paged KV cache (which is per-block, not per-sequence). Not in the
`Sequence` object (we don't want to touch core vLLM data classes if
we can avoid it).

```python
# Roughly, inside Int4ProtectedKVAttentionBackend
self._protect_state: Dict[int, ProtectSeqState] = {}

@dataclass
class ProtectSeqState:
    # (num_layers, H_kv, D) int8 — the static masks
    masks: torch.Tensor                 # device
    # (num_layers, H_kv, n_protect) int32 — channel indices (compact)
    protect_indices: torch.Tensor       # device
    # (num_layers, S, H_kv, n_protect) bf16 — compact sidecar grow-buffer
    k_fp16_protect: torch.Tensor        # device, allocated lazily
    n_protect: int
```

Keyed by `seq_id`. Lifetime tied to the sequence — freed via a hook
on sequence completion (vLLM's `Scheduler.free_finished_seq_groups`
or the equivalent path).

### 3.3 Granularity (Q3)

**Per-sequence × per-layer.** Not per-request (request → multiple
sequences in beam search), not model-static.

- Per-sequence: matches §20.4.3 algorithm.
- Per-layer: each of Qwen2.5-7B's 28 attention layers has its own
  K-channel magnitude distribution; masks are independent.

Memory per sequence:
- Masks: `28 × 4 × 128 × 1 = 14 KB` (negligible).
- Protect indices: `28 × 4 × n_protect × 4 bytes` — at
  `protect_fraction=0.04, D=128`, `n_protect ≈ 21` (note: this is
  channels-per-head, not total). So `28 × 4 × 21 × 4 = 9 KB`.
- K_fp16 protect sidecar (the dominant cost): see §3.6 below.

### 3.4 Decode retrieval (Q4)

Decode batch step:

1. vLLM's scheduler builds a decode batch with `seq_ids = [s0, s1, ...]`.
2. For each attention layer in the model's forward pass:
   - `Int4ProtectedKVAttentionBackend.forward(..., attn_metadata)` is called.
   - Backend reads `attn_metadata.seq_ids` and the current `layer_id`.
   - For each `seq_id`, the backend looks up
     `self._protect_state[seq_id].masks[layer_id]` and
     `.protect_indices[layer_id]` and `.k_fp16_protect[layer_id, :seq_len[i]]`.
   - Concatenate across the batch into:
     - `protect_mask_batch: (B, H_kv, D) int8`
     - `protect_indices_batch: (B, H_kv, n_protect) int32`
     - `k_fp16_protect_batch: (B, S_padded, H_kv, n_protect) bf16` — padded to
       max-seqlen-in-batch (FA already does this for the FP16/INT4 KV).
3. Pass these to `flash_attn_with_int4_kvcache(...)`.

The mask itself is small enough that the per-call cat is cheap (~14 KB
× B). The sidecar `k_fp16_protect` cat is the same cost-shape as
vLLM's regular KV cat — same FA pattern.

### 3.5 Flash_fwd_params mapping (Q5)

Extension fields in `csrc/flash_attn/src/flash.h`:

```cpp
struct Flash_fwd_params {
    // ... existing fields ...

    // Protect-mask: which channels are FP16-protected.
    // Shape (batch_size, H_kv, D), int8 with 1 at protected channels.
    const int8_t * __restrict__ protect_mask_ptr;
    int protect_mask_batch_stride;       // typically H_kv * D
    int protect_mask_h_stride;            // typically D

    // Protect-index list (compact layout, per Section 4 below).
    // Shape (batch_size, H_kv, n_protect), int32.
    const int32_t * __restrict__ protect_indices_ptr;
    int protect_indices_batch_stride;
    int protect_indices_h_stride;
    int n_protect;                        // number of protected channels per head

    // FP16 sidecar: the protected channels' real values.
    // Shape (batch_size, S_padded, H_kv, n_protect), bf16/fp16.
    const void * __restrict__ k_fp16_protect_ptr;
    int k_fp16_protect_batch_stride;
    int k_fp16_protect_seq_stride;
    int k_fp16_protect_h_stride;

    // INT4 K/V (existing INT4 params not repeated)
    bool is_int4kv;                       // gates the new dispatch
};
```

Inside the kernel (Phase 4 work):

```cpp
// Pseudo-code for the K read in compute_attn_1rowblock_splitkv
// (the INT4 _int4kv clone variant).
//
// For each (token_in_block, head, d):
//   if (protect_mask[head, d]) {
//       // Find this d's position in protect_indices for this head,
//       // load from k_fp16_protect.
//       int local_idx = lookup_protect_idx(head, d);
//       k_val = k_fp16_protect[token_in_block, head, local_idx];
//   } else {
//       k_val = dequant_int4(k_packed[token_in_block, head, d/2],
//                            k_scale[..., d], k_offset[..., d]);
//   }
//   // K then participates in qK dot as usual.
```

In practice the kernel would precompute a per-head "is_d_protected"
register-resident bitmap from the `(H_kv, D)` mask once per
threadblock, and use it to gate the load path. The lookup-by-index
for the protected case adds one indirection per protected channel.

### 3.6 Memory budget — compact vs dense sidecar (revises §5.5)

The runbook had penciled `**dense** (num_blocks, page_block_size, H_kv, D)`
as the v1 layout default. The math doesn't work at long context:

- Dense FP16 sidecar at S=32k, H_kv=4, D=128, 28 layers:
  `28 × 32 768 × 4 × 128 × 2 = 917 MB per sequence`. Wastes 96% on
  the unprotected channels. **Not OK** for any usable concurrency.

- Compact FP16 sidecar (`n_protect ≈ 0.04 × H_kv × D / H_kv = 5.12` →
  round up to 21 per head if we keep protect_fraction = 0.04 over
  the H_kv * D flattened mask; **actually:** the §20.4.3 algorithm
  takes top-fraction over the flattened `(H_kv * D)` so the *total*
  number of protected `(head, d)` pairs is
  `n_protect_total = round(0.04 × 4 × 128) = 20`. Some heads may
  have more protected channels than others.

  For storage, the cleanest representation is `(H_kv, n_protect_per_head)`
  with padding to the per-head maximum. At Qwen shapes:
  `28 × 32 768 × 4 × ~6 × 2 = 44 MB per sequence`. **OK.**

Decision: **LOCK compact for v1.** Revise §5.5 of
`KERNEL_6C3C_DESIGN.md` and Phase 4.1 of `KERNEL_6C3C_RUNBOOK.md` to
match.

Implementation note: the per-head padding to `n_protect_per_head =
max_h(number of protected channels in head h)` wastes a small amount
(uneven distribution between heads) but keeps the layout
rectangular — required for FA-style coalesced loads. Track the
actual per-head count in `protect_indices` (zero-pad with sentinel
indices that map to an unused load).

## 4. Phase impact

### Phase 1 (additive scaffolding) — minimal

- Add the new `Flash_fwd_params` fields from §3.5. ALL NULL / 0 by
  default. No new behavior.
- Plumb through `mha_fwd_kvcache_int4`. Default NULL.
- No vLLM-side code changes — `Int4ProtectedKVAttentionBackend`
  doesn't exist yet.

### Phase 2 (INT4 K read) — independent of mask

- INT4 path runs with mask = NULL. No protect blending. Kernel
  produces "as if no channels are protected" output, compared
  against an oracle that quantizes EVERY channel.
- This is the §20.4.3 algorithm's `protect_fraction=0.0` config —
  the existing `int4_fused_attention_reference` oracle covers it
  (case `qwen_protect0_s64` in `kernel_6c_gpu_test.py::CASES`).

### Phase 4 (protected-K sidecar) — full §7.Q1 in the kernel

- Implement the K-read blend in `compute_attn_1rowblock_splitkv_int4kv`.
- Test against the existing oracle on the 7 non-protect-0 cases in
  `CASES`. `protect_fraction=0.04` (`qwen_asym_s64` etc.) is the
  ship config.

### Phase 5 (vLLM integration) — most of the §7.Q1 work lives here

- **5.A: Identify prefill-end hook.** vLLM fires
  `Sequence.is_finished_with_prefill()` (or similar — exact name
  varies; v0.7.3 has `SequenceData.get_num_uncomputed_tokens()`-
  based check). The first decode step's `forward` is the natural
  hook — backend detects "first decode step for this seq_id" by
  absence in `self._protect_state` and computes the mask before
  proceeding.
- **5.B: Mask compute at prefill-end.** For each layer, gather the
  prefill K from the paged blocks (vLLM provides
  `kv_cache[layer_idx]` and the seq's block_table). Compute max-abs
  over the seq dim, topk, store mask + indices + initialize
  the `k_fp16_protect` grow-buffer with the protected channels'
  values from prefill K. **Important:** at this hook the K cache
  is *already INT4* (Phase 5.3's quantize hook ran). So mask
  computation needs the FP16 staging buffer from before the quantize
  step, OR we move the mask-compute to *before* the quantize hook
  (cleaner — both reads happen on the FP16 staging buffer in one
  pass).
- **5.C: Sequence-completion cleanup.** Hook into vLLM's
  `Scheduler.free_finished_seq_groups` (or equivalent) — when a
  `seq_id` is freed, drop from `self._protect_state`.
- **5.D: Decode batch concatenation.** At each decode forward,
  build the batch tensors per §3.4. For B=1 (our v1 target) this is
  a no-op view.

Phase 5's 4-step is now concrete enough to implement without further
design.

## 5. Out-of-scope (for v1)

- **Offline calibration** — per-model static mask computed once
  over a calibration set. Plausibly cheaper at runtime; needs a
  separate validation that quality holds vs per-sequence-static.
  v2 work.
- **Per-decode-step mask updates** — dynamic protection that
  adapts as decode generates new K. v2 work; §20.4.3 explicitly
  tested static and it works.
- **Cross-sequence mask sharing** — if multiple sequences in a
  beam derive from the same prefill, they share a mask. v2 — v1
  computes per-sequence even within a beam (small overhead, simple).
- **Dense sidecar layout** — not viable at long context, see §3.6.
- **Mask compute streaming** — incremental update of magnitude
  estimate during chunked prefill. v2.

## 6. Files this design touches

When Phase 4 + Phase 5 land:

- `csrc/flash_attn/src/flash.h` — new `Flash_fwd_params` fields
  (Phase 1).
- `csrc/flash_attn/src/flash_fwd_split_hdim128_bf16_int4kv_sm80.cu`
  — kernel-side blend logic (Phase 4).
- `csrc/flash_attn/flash_api.cpp` — mha_fwd_kvcache_int4 plumbs the
  new pointers from Python (Phase 1).
- `flash_attn/flash_attn_interface.py` —
  `flash_attn_with_int4_kvcache` Python signature accepts mask +
  indices + sidecar (Phase 1).
- `vllm/attention/backends/int4_protected.py` — NEW backend file
  with `Int4ProtectedKVAttentionBackend`, `ProtectSeqState`, the
  prefill-end hook (Phase 5).
- `KERNEL_6C3C_DESIGN.md` §5.5 — revise to LOCK compact (this note).
- `KERNEL_6C3C_RUNBOOK.md` Phase 4.1 — revise to LOCK compact (this
  note).
