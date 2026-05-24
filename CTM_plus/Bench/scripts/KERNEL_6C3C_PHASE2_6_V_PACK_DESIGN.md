# Phase 2.6 — V INT4 packing (now a Phase 5B.4 prerequisite)

> Originally specified as the V-side mirror of Phase 2.4 (K packing).
> Phase 5B.4 made this REQUIRED for v1 ship: vLLM's `get_kv_cache_shape`
> returns ONE shape per layer for both K and V. K-only compression
> with bf16 V can't fit cleanly in a shared smaller slot (5B.4b set
> per-slot bytes to D × 1 = 128 bytes — enough for packed K but only
> half of bf16 V). Phase 2.6 lets V live in the same smaller slot,
> resolving the blocker.

## 1. Why Phase 2.6 is now required

Phase 5B.4 chose uint8 storage at `get_kv_cache_shape = (2, NB, BS, H_kv, D=128)`.
Per-slot budget = D × 1 byte = 128 bytes. The leading `2` dim is K|V;
both halves get IDENTICAL per-slot byte count by vLLM's API contract.

| Use | Needs | 128 byte budget |
|---|---|---|
| Packed INT4 K | 64 bytes nibbles + ~26 bytes scale/xmin/protect | **Fits with room** |
| BF16 V | D × 2 = 256 bytes | **Does NOT fit — half lost** |

Three escape paths fail:
- **Lossy V at half-D bf16** — V holds the value vectors that softmax-attention
  sums; losing half a value vector tanks output quality.
- **Shape ×2 (256 bytes per slot)** — eliminates the memory benefit;
  same as stock bf16 total.
- **Revert to bf16** — undoes 5B.4b's 2× capacity gain.

Only **packing V too** lets the uint8 D=128 slot hold both K and V
correctly. This is what Phase 2.6 delivers.

Ship-path candidate (locked):
- K: protected INT4 (Phase 2.4 + protect-K outlier sidecar).
- V: INT4 (this phase). No protect-V outlier sidecar (KIVI paper found
  V outliers don't dominate attention output the way K outliers do —
  V values are bounded by softmax weighting, not pre-softmax dot products).

## 2. V quantization layout

### Group axis

For K: group along SEQ (group_size=32 tokens per group). Each token's
K vector contributes to a per-(seq-group, h_kv, channel) scale.

For V: group along HEAD_DIM (v_group_size=32 channels per group). Each
token's V vector is independently quantized. Within a token, channels
fall into D/v_group_size = 4 groups, each with its own scale + xmin.

**Why differ:**
- K values vary mostly per-token (a position's content); pooling
  adjacent tokens gives more samples for a stable per-channel scale.
- V values vary mostly per-channel within a token (different channels
  encode different "meanings" with different magnitudes); pooling
  channels of a token preserves token-by-token resolution.
- Matches KIVI's `v_per_token` recommendation (§20.4.2 reference).

### Storage layout (per layer)

```
v_int4 : (1, S, H_kv, D/2)            uint8   — packed nibbles
v_scale: (1, S, H_kv, D/v_group_size) bf16    — per-(token, group_of_channels) scale
v_xmin : (1, S, H_kv, D/v_group_size) bf16    — per-(token, group_of_channels) x_min
```

**No protect-V sidecar.** Per algorithmic decision above.

### Per-token byte cost

At D=128, v_group_size=32, n_groups=4:

| Tensor | Bytes/token |
|---|---|
| v_int4 (D/2 nibbles) | 64 |
| v_scale (4 bf16) | 8 |
| v_xmin (4 bf16) | 8 |
| **V per-token total** | **80** |

Stock bf16 V: 256 bytes/token. **Savings: 3.2× on V alone.**

### Map to vLLM KV slot shape

The shared (2, NB, BS, H_kv, D=128) uint8 slot has 128 bytes per
(token, h_kv) for K and another 128 bytes for V.

| Use | Needs | Budget | Slack |
|---|---|---|---|
| K (packed INT4 + scale/xmin sidecars external + 10 byte protect_bf16 + cross-block scale share) | ~74 bytes/slot in-slot | 128 | 54 bytes |
| V (packed INT4 + scale + xmin in-slot) | 80 bytes/slot | 128 | 48 bytes |

Both K and V FIT in the 128-byte slot with per-slot waste of
40-50% of the slack budget. Total waste per slot per (K|V) ≈ 50 bytes
× 2 = 100 bytes ≈ 39% of the 256-byte slot. Acceptable for v1.

**Decision: keep v_scale/v_xmin co-located in the V slot** (not
sidecar like K's per-group scale). Per-token simpler than per-group;
no cross-block bookkeeping.

For K, scale/xmin are per-(seq-group, channel) which span multiple
tokens. Those stay in PER-BLOCK sidecars (one scale entry per
group × D channels per block). That's the existing Phase 2.4.0
layout.

## 3. V write path

### Prefill V

Each layer's prefill V tensor `(T_prompt, H_kv, D)`:
```
v_grouped = v.float().view(T, H_kv, n_groups, v_group_size)
x_max = v_grouped.amax(dim=-1)
x_min = v_grouped.amin(dim=-1)
scale = ((x_max - x_min) / 15.0).clamp(min=1e-8)
q = ((v_grouped - x_min[..., None]) / scale[..., None])
       .round().clamp(0, 15).to(uint8)            # (T, H_kv, n_groups, G)
q_flat = q.view(T, H_kv, D)
even = q_flat[..., 0::2]
odd  = q_flat[..., 1::2]
v_int4_packed = (even & 0x0F) | ((odd & 0x0F) << 4)  # (T, H_kv, D/2)
```

Writes to `(NB, BS, H_kv, D)` uint8 paged cache at slot_mapping positions
(or in our case, write the packed nibbles + scale + xmin into the
designated byte ranges within each slot's 128 bytes).

### Decode V (incremental)

**Crucial simplification vs K:** V grouping is purely along head_dim,
so each new decode token's V is INDEPENDENTLY quantized. NO partial-
group accumulator. NO staging buffer.

```
def quantize_v_token(v_token):       # (H_kv, D) bf16
    v_grouped = v_token.float().view(H_kv, n_groups, v_group_size)
    x_max = v_grouped.amax(dim=-1)
    x_min = v_grouped.amin(dim=-1)
    scale = ((x_max - x_min) / 15.0).clamp(min=1e-8)
    q = ((v_grouped - x_min[..., None]) / scale[..., None]).round().clamp(0,15).to(uint8)
    q_flat = q.view(H_kv, D)
    packed = (q_flat[..., 0::2] & 0x0F) | ((q_flat[..., 1::2] & 0x0F) << 4)
    return packed, scale, x_min
```

Three pure functional outputs per new token. Writes directly to the
target slot.

### Streaming pack equivalence

Token-by-token V quantization MUST equal batch V quantization because
there's no cross-token state. Streaming pack equivalence test is
mostly degenerate — just confirms we wrote the per-token loop
correctly.

### Helper reuse

**`PartialGroupQuantizer` (Phase 5B.1, K-side) does NOT generalize cleanly to V.** It maintains a partial-group BF16 staging buffer
across decode steps, which V doesn't need.

**Lock: new `ValueGroupQuantizer` class** (simpler — no staging,
no protect handling). Mirrors `pack_v_for_phase2_6(...)` for batched
use; `append_token(v_new)` for streaming.

## 4. V read path in kernel

### Current FA kernel V load site

V is loaded LATER than K in the FA loop:
1. Load K block → sK.
2. GEMM Q @ K^T → S.
3. Softmax(S) → P.
4. **Load V block** → sV (cp.async from k_cache[1] in current path).
5. GEMM P @ V → O accumulation.

Phase 3 added an in-register V INT4 quant transform AFTER step 4
(quantize→dequant on the cp.async'd bf16 V, writing back to sV).
This is the NO-OP V transform — same numerical result as bf16, just
exercises the INT4 path.

### Phase 2.6 kernel changes

Same pattern as Phase 2.4.1b for K:

1. **Skip the V cp.async from k_cache[1].** Replace with direct HBM
   load of packed V bytes + scales + xmins.
2. **Per-thread fragment iteration over sV:**
   For each (n, d) in tVsV:
     - g = d / v_group_size
     - byte_idx = d / 2
     - shift = (d & 1) * 4
     - nibble = (smem_v_packed[n, byte_idx] >> shift) & 0x0F
     - scale = smem_v_scale[n, g]
     - xmin = smem_v_xmin[n, g]
     - x_hat = nibble * scale + xmin
     - write bf16 x_hat to sV[(i0, i1, i2)]
3. `__syncthreads()` before PV GEMM consumes sV.

The GEMM downstream is unchanged — it reads standard bf16 sV.

### Safety choice: write dequantized BF16 V to smem first (mirror K)

**Lock: write dequantized BF16 V to smem.** Same pattern as Phase 2.4.1b
K. The PV GEMM reads sV as bf16 like always. No surgery on downstream
kernel code.

Alternative — dequantize closer to the PV multiply — saves smem
bandwidth but requires kernel surgery on the GEMM. Defer to a
perf-polish phase (Phase 2.6.1?) after correctness lands.

### Template gating

Extend the existing `Is_int4kv_packed` template to gate BOTH K and V
packed loads (they're always together in v1; no asymmetric path).

Alternatives considered:
- Separate `Is_int4_k_packed` + `Is_int4_v_packed` templates: doubles
  the kernel matrix, no real use case for asymmetric.
- Same `Is_int4kv_packed`: simpler, one path. Lock.

The Phase 2.4.1b instantiation
(`flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu`) will get
extended in 2.6 to include V load support. No new .cu file needed —
just additions to the existing kernel header.

### Interaction with Phase 3 in-register V transform

Phase 3's in-register V transform (`int4_quant_dequant_V_block_inplace`)
runs UNDER `Is_int4kv && !Is_int4kv_packed`. When `Is_int4kv_packed=true`,
the V cp.async + Phase 3 transform are REPLACED by our packed V load.

Same template-gating pattern Phase 2.4.1b used for K (replaces Phase 2.3's
K transform under the packed path).

## 5. Correctness oracle

Same gate structure as Phase 2.4.1b:

| Test | Gate |
|---|---|
| a. Synthetic V pack/unpack equivalence | unpack(pack(V)) per-element err ≤ ~scale (per-group LSB) |
| b. Streaming V pack equals batch V pack | Bit-equal (no cross-token coupling) |
| c. Kernel output cosine vs Phase 3 in-register V reference | ≥ 0.9995 |
| d. Real Qwen smoke | Needle retrieval + 0 fallbacks |

Note: Phase 3's V transform was numerically idempotent (quant→dequant
of bf16 → bf16). Phase 2.6's packed V should match Phase 3 within
~1e-5 cosine (the BF16 scale/xmin roundtrip vs in-register FP32).

## 6. Memory math

Per-token byte cost summary (Qwen2.5-7B, D=128, group_size=32,
n_protect=5 for K's protect-K):

| Configuration | K bytes | V bytes | Total K+V | vs stock |
|---|---|---|---|---|
| Stock BF16 | 256 | 256 | **512** | 1.00× |
| FP8 (vLLM's existing) | 128 | 128 | **256** | 0.50× |
| Protected INT4 K + BF16 V | 106 | 256 | **362** | 0.71× |
| **Protected INT4 K + INT4 V (Phase 2.6)** | 106 | 80 | **186** | **0.36×** |

Side tensors (per layer, S=2048 tokens, H_kv=4):

| Sidecar | Bytes/layer | Notes |
|---|---|---|
| K scales (per-group) | (S/G) × H_kv × D × 2 = 64 × 4 × 128 × 2 = 64 KB | In-block in Phase 5B.4 |
| K xmins | 64 KB | In-block |
| K protect_bf16 | S × H_kv × n_protect × 2 = 2048 × 4 × 5 × 2 = 80 KB | In-block |
| K protect_slot | H_kv × D = 512 bytes | Static after prefill |
| V scales (per-token) | S × H_kv × n_groups × 2 = 2048 × 4 × 4 × 2 = 64 KB | In-block (per token) |
| V xmins | 64 KB | In-block |

All side tensors fit within the 128-byte-per-slot budget after careful
allocation.

### Configuration that fits vLLM's shared shape cleanly

The Phase 2.6 packed K + packed V configuration fits in the
`(2, NB, BS, H_kv, D=128)` uint8 layout. Per (K|V) slot 128 bytes:
- K: 64 (int4) + 10 (protect_bf16) + scale/xmin handled across-block
- V: 64 (int4) + 8 (scale) + 8 (xmin) + spare

Both halves of the leading-2 dim are correct interpretations of their
contents. **5B.4b's locked shape becomes correct.**

## 7. Integration with Phase 5B.4

Phase 2.6's V packing resolves the V-lossiness blocker. With both K
and V packed:

- Same shape `(2, NB, BS, H_kv, D)` uint8 fits both halves correctly.
- num_blocks doubles vs bf16 (5B.4b verified).
- Generation correctness recovers (kernel reads packed K + packed V
  properly).

New Phase 5B.4 target after 2.6 lands:
- 5B.4c.1: write path replacement — K via `PartialGroupQuantizer`
  (5B.1), V via `ValueGroupQuantizer` (2.6).
- 5B.4c.2: read path replacement — extended Phase 2.4.1b kernel
  reads both packed K + packed V from paged uint8 cache.
- 5B.4c.3: end-to-end correctness verify + memory-savings claim.

**Phase 5B.4c blocks on Phase 2.6 correctness.** Specifically:
- 5B.4c.1 needs ValueGroupQuantizer working (2.6 Python helpers).
- 5B.4c.2 needs the kernel to read packed V (2.6 kernel work).

So Phase 2.6 is the gate. Do it first.

## 8. Scope exclusions

NOT in Phase 2.6:
- Dynamic V masks.
- Pre-RoPE V quantization.
- FP4 / NVFP4 alternatives.
- Split K/V cache layout (different shapes/dtypes).
- Multi-sequence / batch > 1 work (Phase 5B.5+).
- Speculative decoding.
- Performance micro-optimization before correctness (in-kernel direct
  dequant, FP32 scale storage, etc.).

V protection mask is OUT OF SCOPE per the design — KIVI paper +
§20.4.3 say V doesn't need protect-K-style outlier handling.

---

## Implementation assessment

**Is the implementation straightforward?** Mostly yes, with one
medium-risk piece:

### Straightforward (high confidence)
- **Python pack/unpack helpers.** Direct mirror of Phase 2.4.0,
  axis flipped from seq to head_dim. ~150 LOC. ~half a day.
- **Streaming V quantizer (`ValueGroupQuantizer`).** SIMPLER than
  Phase 5B.1's `PartialGroupQuantizer` — no staging buffer, no
  cross-token coupling. ~80 LOC.
- **Kernel-side V load helper** (`int4_packed_load_V_block`).
  Direct mirror of `int4_packed_load_K_block` (Phase 2.4.1b),
  group axis along head_dim instead of seq, no protect logic.
  ~150 LOC of CUDA.
- **Verify scripts.** Mirror existing K-side patterns.

### Medium risk (one careful step)
- **Locating the V cp.async site in the FA kernel** and wiring our
  packed V load in its place. Phase 2.4.1b found 3 K-load sites;
  V has its own set that we need to grep. The replacement is
  template-gated under `Is_int4kv_packed`, same pattern as 2.4.1b
  on K.
- **Reuse vs replication of the existing instantiation file**
  (`flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu`). Probably
  the cleanest is to extend the existing kernel header
  (`int4_packed_load.h`) with the V helper, keep one .cu file. Saves
  a fresh template/instantiation cycle.

### Low risk but non-zero
- **Cosine ≥ 0.9995 vs Phase 3.** Phase 2.4.1b hit 0.9999792 vs
  Phase 5A. The V path is structurally simpler (no protect blend),
  so similar precision is expected. If it falls short, FP32 scale
  fallback (like K's Q3) is available.

### NEW kernel-side blocker that came up during this design?

**None identified.** The V kernel pattern transfers from Phase 2.4.1b
with the axis change. Phase 3's in-register V transform shows the
existing kernel ALREADY had V quant logic — we're just moving where
the data comes from (paged uint8 cache instead of paged bf16 cache).

The one item to verify before kernel work: confirm the FA kernel's
V cp.async sites are findable (we know there are sV writes; need to
inspect `compute_attn_1rowblock_splitkv` for the V-side analog of
K's three load sites).

## Implementation plan (post-design)

1. **Phase 2.6.0** — Python V pack/unpack helpers + round-trip test.
   ~0.5 day. Standalone, no kernel work.
2. **Phase 2.6.1** — `ValueGroupQuantizer` streaming class + round-trip
   test. ~0.5 day.
3. **Phase 2.6.2** — kernel-side V load helper. Probe the FA kernel
   for V cp.async sites first. ~1-2 days including kernel iteration.
4. **Phase 2.6.3** — verify_phase2_6_v_pack.py end-to-end gate.
   ~0.5 day.

Total Phase 2.6 estimate: ~3 engineer-days. Within the design doc's
2-3 day estimate.

Then 5B.4c.1/2/3 can resume (~1-2 days each).

Cumulative remaining for v1 ship: **Phase 2.6 (3 days) + 5B.4c (3-5 days) = 6-8 days.**

## Recommendation

Proceed to implementation:
1. Phase 2.6.0 (V pack/unpack) — start next.
2. Phase 2.6.1 (streaming quantizer) — same session.
3. Phase 2.6.2 (kernel) — separate session with probe + iteration time.
4. Phase 2.6.3 (verify) — wraps it up.

The design is clean. The V-lossiness blocker resolves naturally with
Phase 2.6. No new architectural concerns surfaced during design.
