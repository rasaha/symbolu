# Kernel 6c — implementation blueprint (fused protected-K INT4 decode attention)

This is the **detailed implementation spec** — the document the kernel is
built from. `KERNEL_6C_DESIGN.md` is the one-page brief (goal, stages,
gates); this blueprint is the authoritative engineering reference. It
synthesises the in-house plan and the external (ChatGPT) action plan;
§14 lists what was incorporated and corrected.

---

## 1. Goal & non-goals

**Goal.** A fused decode-attention kernel that reads protected-K INT4 KV
from HBM, dequantizes inline in registers, and computes
`softmax(QKᵀ)·V` — no INT4→FP16 round trip through HBM — turning the
measured §20.4.2–4 quality/compression result into decode throughput.

**Non-goals (v1 / 6c.1).** No prefill kernel. No dynamic channel
selection. No vLLM paging. No multi-token speculative decode. No CUDA
(Triton first). These arrive in 6c.2 / 6c.3.

---

## 2. v1 scope decisions (locked for 6c.1)

| Decision | v1 choice | Rationale |
|---|---|---|
| Language | **Triton** | writable/iterable; ~70% of CUDA perf; CUDA-promote only if Triton overhead vs FP16 > 5% |
| Paging | **non-paged** — KV is one contiguous tensor per sequence | paging (block tables) is 6c.3; isolates kernel correctness from vLLM layout |
| Decode | **single token** (S_q = 1) | the decode case; multi-token batching is 6c.2 |
| Protected-K layout | **Option A — overlay** (full-D INT4 tensor + FP16 side-tensor + mask) | clean rectangular tensors; the channel-partitioned layout is a 6c.2 optimisation |
| Quant mode | **asymmetric + symmetric**, selected by a `constexpr` flag | §18.3 ships asymmetric; symmetric is a cheap branch and the reference supports both |
| dtype | Q / output / protected-K / accumulator-output **FP16**; softmax accumulator **FP32** | matches `fused_int4_attention_reference` and FlashAttention's numeric contract |

---

## 3. Data model — exact tensors

All for **one layer, one decode step**. `B` = batch, `H_q` = query heads,
`H_kv` = KV heads, `G = H_q // H_kv` (GQA factor), `D` = head_dim,
`S_kv` = cached sequence length. Qwen2.5-7B: H_q=28, H_kv=4, G=7, D=128.

### Inputs

| Name | Shape | dtype | Meaning |
|---|---|---|---|
| `q` | (B, H_q, D) | fp16 | current decode token's query |
| `k_packed` | (B, H_kv, S_kv, D//2) | uint8 | INT4-packed K, **all D channels** (head_dim packed 2/byte) |
| `k_scale` | (B, H_kv, n_grp_k, D) | fp16 | K scale per (seq-group, head, dim); `n_grp_k = ceil(S_kv/GS_k)` |
| `k_offset` | (B, H_kv, n_grp_k, D) | fp16 | K offset (asymmetric only; else unused) |
| `k_fp16` | (B, H_kv, S_kv, D) | fp16 | FP16 K originals; only the **protected** lanes are read |
| `protect_mask` | (H_kv, D) | int8/bool | **static** — 1 where the (head,dim) channel is FP16-protected |
| `v_packed` | (B, H_kv, S_kv, D//2) | uint8 | INT4-packed V |
| `v_scale` | (B, H_kv, S_kv, n_grp_v) | fp16 | V scale per (token, head, dim-group); `n_grp_v = ceil(D/GS_v)` |
| `v_offset` | (B, H_kv, S_kv, n_grp_v) | fp16 | V offset (asymmetric only) |

Scalars / `constexpr`: `softmax_scale` (float, default `1/sqrt(D)`),
`GS_k` (K group size, 32), `GS_v` (V group size, 32), `ASYMMETRIC` (bool),
`BLOCK_N` (KV-seq tile, tunable — start 64).

### Output

| Name | Shape | dtype |
|---|---|---|
| `attn_out` | (B, H_q, D) | fp16 |

### v1 simplification

`k_fp16` is the full (B,H_kv,S_kv,D) tensor (the kernel reads only masked
lanes) — this exactly matches the reference and is the simplest v1. 6c.2
replaces it with a compact `(B,H_kv,S_kv,n_protect)` side-tensor + an
index list.

---

## 4. Quantization & dequant math (exact — must match `int4_per_channel_kv.py`)

### INT4 unpack (byte → signed value)

`k_packed` / `v_packed` store two 4-bit values per byte along head_dim:

```
byte b at position d//2 holds dims (2*(d//2)) and (2*(d//2)+1):
    low_nibble  = b & 0x0F           # even dim
    high_nibble = (b >> 4) & 0x0F    # odd dim
    nibble      = low if (d & 1)==0 else high
    iv          = int8(nibble) - 8   # signed INT4 value, range [-8, +7]
```

### Dequant

```
asymmetric:  x = iv * scale + offset
symmetric:   x = iv * scale
```

(Matches `dequantize_per_channel_int4` / `dequantize_per_token_int4`.)

### Group-scale indexing

- **K** is per-channel along the **seq** axis, grouped by `GS_k`:
  for token `s`, head `h`, dim `d`: `g = s // GS_k`;
  `scale = k_scale[b, h, g, d]`, `offset = k_offset[b, h, g, d]`.
- **V** is per-token along the **head_dim** axis, grouped by `GS_v`:
  for token `s`, head `h`, dim `d`: `g = d // GS_v`;
  `scale = v_scale[b, h, s, g]`, `offset = v_offset[b, h, s, g]`.

---

## 5. Protected-K overlay (exact)

Per (KV head `h`, dim `d`), `protect_mask[h,d]` is **static** — fixed
offline by calibration (§20.4.3 validated a frozen set), never recomputed
in the kernel. Reconstruction of a K element:

```
k_int4_dq = dequant(unpack(k_packed[b,h,s,d//2], d), k_scale, k_offset)
k_eff     = k_fp16[b,h,s,d]  if protect_mask[h,d]  else  k_int4_dq
```

This is exactly `_restore_outlier_channels` (route-B) and the
`k_fp16`/`k_protect_mask` path of `fused_int4_attention_reference`.
**V is never protected** — V channels are always INT4.

---

## 6. The fused algorithm — precise pseudocode

Per `(batch b, query head hq)`; `hkv = hq // G`. FlashAttention-style
online softmax, FP32 accumulators, never materialise a full dequantized
K or V tensor:

```
q_vec   = q[b, hq, :]                       # (D,) fp16
acc     = zeros(D, fp32)                     # output accumulator
m       = -inf                               # running max logit
l       = 0.0                                 # running sum of exp

for s0 in range(0, S_kv, BLOCK_N):
    tile = [s0 .. min(s0+BLOCK_N, S_kv))      # KV positions in this tile

    # --- reconstruct K tile, fused (no HBM round trip) ---
    for s in tile, for d in 0..D:
        iv   = unpack(k_packed[b,hkv,s,d//2], d)
        g    = s // GS_k
        kdq  = iv*k_scale[b,hkv,g,d] (+ k_offset[b,hkv,g,d] if ASYMMETRIC)
        k_tile[s,d] = k_fp16[b,hkv,s,d] if protect_mask[hkv,d] else kdq

    # --- QKᵀ for the tile ---
    scores = (q_vec @ k_tileᵀ) * softmax_scale         # (len(tile),) fp32

    # --- online softmax update ---
    m_new = max(m, max(scores))
    p     = exp(scores - m_new)                         # (len(tile),) fp32
    alpha = exp(m - m_new)
    l     = l*alpha + sum(p)

    # --- reconstruct V tile, fused ---
    for s in tile, for d in 0..D:
        iv  = unpack(v_packed[b,hkv,s,d//2], d)
        g   = d // GS_v
        v_tile[s,d] = iv*v_scale[b,hkv,s,g] (+ v_offset[b,hkv,s,g] if ASYM)

    # --- accumulate ---
    acc = acc*alpha + (p @ v_tile)                      # (D,) fp32
    m   = m_new

attn_out[b, hq, :] = (acc / l).to(fp16)
```

GQA is handled implicitly: `hkv = hq // G`, so the G query heads sharing a
KV head each run this loop against the same K/V — no explicit broadcast.

---

## 7. Triton kernel structure

- **Grid:** `(B * H_q,)` — one Triton program per `(batch, query-head)`.
  Decode is one query token, so per-program work is the §6 loop.
- **Per-program tiles:**
  - `q_vec`: (D,) — loaded once into registers (D=128 fits).
  - KV loop: `ceil(S_kv / BLOCK_N)` iterations; each loads a
    `(BLOCK_N, D//2)` uint8 K-packed tile and a same-shape V tile.
- **INT4 unpack in Triton:** load the `(BLOCK_N, D//2)` uint8 tile;
  `low = tile & 0xF`, `high = (tile >> 4) & 0xF`; interleave low/high into
  a `(BLOCK_N, D)` tile (Triton: build via two strided stores into a
  `(BLOCK_N, D)` buffer, or `tl.interleave` if available); subtract 8.
- **Scales:** broadcast-load — K scale indexed by `s//GS_k` (so each
  group of `GS_k` rows in the tile shares a scale row when the tile
  straddles a group boundary, handle per-row); V scale indexed by
  `d//GS_v`.
- **Masking:** tail tile where `s0+BLOCK_N > S_kv` — mask the out-of-range
  rows so they contribute `-inf` to `scores` (→ 0 after softmax).
- **`@triton.jit` signature (sketch):**

```
@triton.jit
def fused_protected_k_decode_attn(
    q_ptr, k_packed_ptr, k_scale_ptr, k_offset_ptr, k_fp16_ptr,
    protect_mask_ptr, v_packed_ptr, v_scale_ptr, v_offset_ptr,
    out_ptr,
    B, H_q, H_kv, S_kv, D,
    stride_* (one per tensor dim),
    softmax_scale,
    GS_k: tl.constexpr, GS_v: tl.constexpr,
    D: tl.constexpr, BLOCK_N: tl.constexpr, ASYMMETRIC: tl.constexpr,
): ...
```

---

## 8. Numerical contract & tolerances

Oracle: `fused_int4_attention_reference(..., k_fp16=, k_protect_mask=)` in
`int4_fused_attention_sketch.py`. Pass conditions, kernel vs reference,
random inputs:

- cosine similarity ≥ **0.999**
- max-abs-diff < **1e-3** (FP16)
- no NaN / Inf
- output dtype fp16, shape (B, H_q, D)

---

## 9. Edge cases (must all pass layer-2 tests)

1. `S_kv` not a multiple of `BLOCK_N` — tail-tile masking.
2. `S_kv` not a multiple of `GS_k` — last K group is partial.
3. `D` not a multiple of `GS_v` — last V group is partial (Qwen: 128/32 ok;
   keep general).
4. `protect_mask` all-zero — degenerates to uniform INT4 (must equal the
   no-protection reference).
5. `protect_mask` all-one — degenerates to FP16-K (output = FP16-K
   attention with INT4 V).
6. `S_kv = 1` — first decode step.
7. Symmetric mode (`ASYMMETRIC=False`, offsets unused).
8. GQA boundary — query heads at `hq = G-1` and `hq = G` map to KV heads
   0 and 1 respectively.

---

## 10. Test plan — the GPU test script

`tests/test_kernel_6c.py` (GPU-only; skip if no CUDA). For each shape in
the matrix:

1. Build random Qwen-shape `k_fp16`, `v_fp16`, `q` (fp16).
2. Quantize K/V via the route-B ops (`quantize_per_channel_int4`,
   `quantize_per_token_int4`, `pack_int4`) → the kernel's INT4 inputs.
3. Build a static `protect_mask` (top-fraction by max-abs).
4. `ref = fused_int4_attention_reference(..., k_fp16=, k_protect_mask=)`.
5. `out = fused_protected_k_decode_attn[grid](...)`.
6. Assert cosine ≥ 0.999, max-abs < 1e-3 (§8).

Shape matrix: `B ∈ {1,4}`, `S_kv ∈ {1,16,64,256,2048,4096}`,
`H_q/H_kv ∈ {28/4 (Qwen), 32/8 (Mistral)}`, `protect_fraction ∈
{0.0, 0.04, 1.0}`, `ASYMMETRIC ∈ {True, False}`, `GS_k=GS_v=32`. Plus the
§9 edge cases as explicit cases.

Layers 3–5 (end-to-end needle quality, throughput, profiling) are run via
the existing §20 harness + the §20.1 throughput cells once the kernel is
integrated — see `KERNEL_6C_DESIGN.md` §6 and `THROUGHPUT_EXP6_RUNBOOK.md`.

---

## 11. Phasing — concrete deliverables & exit criteria

**6c.1 — correctness kernel.** The §6 algorithm in Triton, §2 v1 scope.
*Exit:* layer-1 + layer-2 tests (§8–§10) green on GPU.

**6c.2 — optimised decode kernel.** Vectorised INT4 unpack; coalesced
loads; channel-partitioned protected layout (compact FP16 side-tensor +
index list); shared-memory staging; `BLOCK_N` tuned for 16k–64k context;
multi-token decode. *Exit:* within ~5–10% of FP16 FlashAttention decode
latency (profiler-guided); layer-1/2 still green.

**6c.3 — vLLM integration.** Paged KV (block tables — mind the
`block_size` vs `GS_k` alignment), the route-A `Attention.forward` hook,
the runtime flag (`--kv-cache-dtype protected_int4 --protected-k-fraction
0.04 --protected-k-mask static --attention-backend protected_k_fused`).
*Exit:* layer-3 needle quality matches §20.4.2–4; layer-4 throughput cells
measured.

---

## 12. Open decisions for the implementer

1. `BLOCK_N` — start 64; tune in 6c.2 against context length.
2. One program per `(b, hq)` vs splitting the KV loop across programs
   (split-K / FlashDecoding style) — v1 = one program per `(b,hq)`;
   revisit in 6c.2 for long context where one program serialises all of
   `S_kv`.
3. Whether to keep `k_fp16` full vs compact in 6c.2 (compact saves HBM but
   needs a gather).
4. `block_size` for 6c.3 paging — vLLM default 16 vs `GS_k=32`
   misalignment: either `block_size=32` or exact group-index math.
5. Triton → CUDA promotion — only if 6c.2 Triton overhead vs FP16 > 5%.

---

## 13. Risks

- **Register pressure / occupancy:** the inline dequant adds ALU + holds a
  `(BLOCK_N, D)` K tile. If occupancy drops, throughput suffers — layer-5
  profiling catches it; mitigation is smaller `BLOCK_N` or split-K.
- **INT4 unpack cost:** the nibble interleave is not free; for short
  context the dequant ALU may not fully hide under memory latency.
- **Protected-K branch:** the per-dim select can serialise warps if not
  warp-uniform; `protect_mask` is per-(head,dim) and uniform across the
  tile's tokens, so the select *is* warp-uniform within a head — keep it
  that way.
- **Group-boundary straddle:** a `BLOCK_N`-tile that crosses a `GS_k`
  boundary needs per-row scale lookup — get the indexing exact (edge case
  §9.2).
- **Remote-iteration cost:** every kernel revision is a GPU run on the
  user's pod; no local compile-check. Expect multiple rounds.

---

## 14. ChatGPT review — incorporated & corrected

**Incorporated** (the external action plan, 2026-05): the static-mask
insistence (no runtime selection); the memory-layout decomposition; the
load-Q → fused-logits → online-softmax → fused-V computation path; the
6c.1/6c.2/6c.3 phasing; the correctness/quality/throughput/memory test
split; the success-gate table; the "what not to do" list; the vLLM flag
names. These match the in-house plan closely.

**Corrected:** the external plan put "route-B protected-K" in the
*throughput* comparison table. Route-B is the HF `DynamicCache`
**quality-measurement vehicle** — it stores FP16 and has no throughput
meaning. Route-B's protected-K *result* is the kernel's **numerical
oracle** (the reference function); the **throughput** baselines are
route-A's naive dequant fallback, FP16, and FP8. This blueprint uses that
corrected framing throughout.

---

## 15. Format-agnosticism & NVFP4 (forward-looking)

The protected-K *finding* (§20.4.1) is about **4-bit precision on the K
channels** breaking long-context addressability — it is **not specific to
INT4**. Any 4-bit KV format (INT4, FP4/NVFP4) must reckon with it. The
durable framing of this work is *"protected-key low-bit KV serving"* — the
key-addressability fix rides whichever low-bit format the hardware favours.

The kernel structure already isolates this: the **INT4 unpack + dequant**
(§4) is the *only* format-specific stage. The protected-channel overlay
(§5), online-softmax attention (§6), GQA, and the static-mask machinery
are all format-independent. A future NVFP4 variant swaps **only** the
unpack stage.

**Scope — 6c.1–6c.3 target INT4** and stay INT4. INT4 is the format with
no hardware-native KV path on Hopper/Ampere, so it is the one that needs a
custom kernel. Do **not** re-architect 6c.1 into a multi-backend kernel —
get one format correct first. An NVFP4-backend variant is a **post-6c
item, deferred pending Blackwell GPU access.**

**Competitive baselines, honestly stated:** FP8 is the production baseline
on Hopper-class GPUs; NVFP4 becomes the hardware-native competitor on
Blackwell (Tensor Core support). Two honest caveats: (1) NVFP4 as a *KV
cache* format — as opposed to NVFP4 for weights/GEMM, which is mature — is
itself an emerging area, not a turnkey competitor. (2) Whether protected-K
is *needed* for FP4 — i.e. whether FP4-K breaks addressability the way
INT4-K does — is **unmeasured**: FP4's E2M1 exponent handles outlier
channels differently from INT4's per-channel scale, so FP4-K could be more
*or* less fragile. That is a hypothesis to test once Blackwell hardware is
available, not a current finding.
