# KVPro V3 — production `int4_protected` decode-path AUDIT + attribution

> **HEADLINE: the shipped decode kernel is the EXTERNAL forked-vLLM `flash_attn_with_int4_kvcache`,
> and it reads the COMPACT protected sidecar (`n_protect=5` channels), NOT a full BF16 K tensor.
> The 0.973 ms in measurement #1 was a DIFFERENT kernel — the in-repo Triton route-A
> `fused_protected_k_decode_attention` (which does read full fp16 K) — so that α is not
> production-representative.** The production code-region attribution was already measured (6M.4);
> the requested *sub-kernel* split (QK/PV/split-K/combine/GQA) is **UNAVAILABLE** because the shipped
> kernel is closed external CUDA (no in-repo source to ablate). Recommendation: **REBUILD_PRODUCTION_KERNEL**
> (bounded), with the honest ceiling below. **No implementation — stopped after attribution.**

## 1. Trace: `kv_cache_dtype="int4_protected"` → the decode kernel call  [code-traced]

```
kv_cache_dtype="int4_protected"
  └─ CacheConfig REJECTS the dtype (phase5b_backend_install.py:14-16) — no native backend registration
  └─ install_int4_protected_backend(model) POST-INIT class-swaps each layer's `.impl`
       to Int4ProtectedAttentionImpl(FlashAttentionImpl)          [phase5b_backend_install.py:261]
  └─ .forward()                                                    [:884]  use_paged_writer = (dtype=="int4_protected")
       └─ decode → _read_decode_packed()                           [:442]
            ├─ B==1 (eager) → _read_decode_packed_one()            [:744]
            └─ B>1 / capture → _read_decode_packed_batched()       [:496]
                 └─ from vllm.vllm_flash_attn import flash_attn_with_int4_kvcache   [:507]
                 └─ out = flash_attn_with_int4_kvcache(...)        [:659]   ← THE SHIPPED DECODE KERNEL
```

`flash_attn_with_int4_kvcache` is defined **only** in the fork-patch scripts
(`CTM_plus/Bench/scripts/apply_phase*_patches.py`) — it is an **external forked-vLLM CUDA kernel**
(`fwd_kvcache_int4`), applied to the vLLM wheel on the pod. There is **no in-repo Python/Triton source**.

## 2. Tensor arguments to the shipped kernel  [code-traced, phase5b_backend_install.py:659-681]

| arg | shape | dtype | storage role |
|---|---|---|---|
| `query_q` | (B, 1, H_q, D) | bf16 | decode query (1 token) |
| `bf16_k_batch` / `dummy` | (1, S, H, D) | bf16 | **DUMMY — zeros, content UNUSED** (`_ensure_dummy_kv`:863; shape/seqlen contract only) |
| `v_for_kernel` | (1, S, H, D) or packed | bf16 | V: bf16 backing (`_bf16_v_mode`) **or** packed int4 (`v_packed_int4/scale/xmin`) |
| `cache_seqlens` | (B,) | int32 | per-seq length |
| `protect_mask` | (B, H, D) | int8 | which K channels are protected |
| `n_protect` | scalar | int | **5** (Qwen2.5-7B) |
| `k_packed_int4` | (B, S, H, D/2) | uint8 | packed int4 K nibbles |
| `k_packed_scale` | (B, S, H, D) | fp16 | K scale, per-block (`packed_group_size=BS=32`) |
| `k_packed_xmin` | (B, S, H, D) | fp16 | K xmin (asymmetric affine) |
| `k_packed_protect_bf16` | **(B, S, H, n_protect)** | bf16 | **COMPACT protected-K sidecar — 5 of 128 channels** |
| `k_packed_protect_slot` | (H, D) | int | slot table (protected channel → sidecar index) |
| `packed_group_size` | scalar | int | BS = 32 |
| `packed_n_protect` | scalar | int | 5 |

## 3. Definitive: does production decode read full BF16 K or the compact sidecar?  [DEFINITIVE]

**COMPACT sidecar only.** K is reconstructed *inside* the kernel from `k_packed_int4` + `k_packed_scale`
+ `k_packed_xmin`, with the protected channels overlaid from `k_packed_protect_bf16` — which is
**`(B, S, H, n_protect=5)`**, i.e. 5 of 128 channels (`k_protect_ext (NB,BS,H,n_protect)`,
phase5b_4c_paged_writer.py:1307/1787). The `bf16_k` argument is a **dummy zeros tensor whose content is
unused** (`_ensure_dummy_kv` docstring: *"content is unused on the packed path — verify_phase5b_4c_2_read
confirmed cosine is identical with zero, random, or real bf16 content"*). **There is no full-BF16-K read
in production.** (The full-fp16-K read is a property of the *route-A* Triton kernel only —
`int4_fused_attention_kernel.py:140` — which is NOT the shipped path.)

## 4. Which path produced the measured 0.973 ms?  [DEFINITIVE]

The **route-A in-repo Triton kernel** `fused_protected_k_decode_attention`, built via
`route_a_builder.make_kernel_inputs` (measurement #1). That kernel additionally loads a **full fp16 K**
(256 B/tok/head) for the overlay, so its time OVER-represents K-read cost versus the shipped kernel. **It
is not the production decode kernel.** The α=0.157 from measurement #1 therefore describes the route-A
proxy, not `flash_attn_with_int4_kvcache`. (The layout-equivalence STOP — page-local ≡ head-major — still
holds; it is pure layout arithmetic, independent of the kernel.)

## 5. Attribution of the SHIPPED kernel

**The requested sub-kernel split (QK-only / PV-only / split-K / combine / GQA padded-vs-useful) is
`UNAVAILABLE`** on the production kernel: `flash_attn_with_int4_kvcache` is a closed external CUDA fork
(no in-repo source), so its internal phases cannot be ablated, and `ncu` (which could split them) is
blocked (`ERR_NVGPUCTRPERM`). Reporting the route-A Triton kernel's internal split would be a *proxy for a
different kernel* — exactly the substitution error this audit exists to catch — so it is **not** offered
as production attribution.

**The production CODE-REGION attribution ALREADY EXISTS** — Phase 6M.4, long-context/saturation
(`PHASE_6M_ATTRIBUTION_FINDINGS.md`), the real operating point:

| region (decode self-CUDA) | share | removable? |
|---|--:|---|
| model GEMMs (shared with bf16) | ~66% | no (not the int4 tax) |
| **`fwd_kvcache_int4` decode attention kernel** | **~29%** | partly (int4 reconstruction is inherent) |
| **paged gather** (`index`/`index_elementwise`) | **~15%** | **yes** (fuse into the kernel) |
| **copy / contiguous** | **~6%** | **yes** (store-as-consumed removes it) |
| host syncs (`.item`/`nonzero`/DtoH) | <1% | already at lower bound |

6M.4's own conclusion: *"the lever is fuse the paged gather + sidecar + protected read into the attention
kernel (attack the ~15% gather + ~6% copy; tighten the ~29% dequant kernel) — bounded + multi-week,"*
gated on the compute-vs-bandwidth roofline. That roofline was ncu-blocked; **the Part-H two-half-kernel
probe resolved it: MEMORY-BOUND / bandwidth-bound-uncoalesced**, which *un-gates* the rebuild per the
frozen 6M.7 decision tree.

## Recommendation (exactly one) → `REBUILD_PRODUCTION_KERNEL`

Why not the others:
- **BUILD_COMPACT_PROTECT_KERNEL — MOOT.** Production *already* reads the compact `n_protect` sidecar
  (§3). The "full BF16 K read" it would fix exists only in the route-A proxy, not the shipped path.
- **OPTIMIZE_SPLIT_COMBINE / OPTIMIZE_GQA_TILING — NOT ACTIONABLE.** Split-K/combine and `G_PAD=16` are
  *route-A Triton* internals; the shipped kernel is closed external CUDA. Neither can be measured or
  changed without the fork's source (i.e., without rebuilding the kernel in-repo anyway).
- **NO_SINGLE_KERNEL_LEVER** is *nearly* right (3 of 5 options are moot/inactionable, and no single
  sub-phase tweak exists) — but the measured gather+copy (~21% of decode self-CUDA) IS recoverable, which
  projects to ~16–19% aggregate (clears the 15% bar), so a lever does exist: a full read-path rebuild.

**`REBUILD_PRODUCTION_KERNEL`**: replace the external `flash_attn_with_int4_kvcache` with an **in-repo
fused decode kernel** that does the paged **gather + compact-sidecar read + dequant + attention** in one
pass — capturing the ~15% gather + ~6% copy (fused away) and letting us tighten the ~29% dequant kernel.
This is the only option that is both **actionable** (we control the source) and **supported by the measured
attribution**, and it matches 6M.4's stated lever, now un-gated by the Part-H roofline.

**Honest ceiling (do not oversell):**
- Recovery is **bounded ~0.27–0.30×** (documented ceiling): int4 inherently reads more per token than bf16,
  and the GEMMs (~66%) are unchanged — so even a successful rebuild stays a **net loss vs bf16** (≈0.22× →
  ≈0.26–0.30×), it does not reach parity.
- It is **multi-week specialist CUDA work** (an in-repo fused paged int4 attention kernel).
- Therefore the real decision is strategic: fund the bounded rebuild, **or** pivot — **int8 KV**
  (native tensor-core, ~0.75× memory, far less decode tax) or position int4_protected as a **capacity /
  density play** (its proven, quality-locked win is 1.83× seq/GB) rather than a throughput play.

**No production kernel implementation performed. Stopped after attribution, as instructed.**
