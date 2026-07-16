# KVPro V3 Step-0 — Part B: current decode pipeline map

Runtime path from scheduler block-table to final attention output, with code citations. There are **two**
decode kernels; Step-0 must not conflate them.

- **Production / shipping** decode = `flash_attn_with_int4_kvcache`, imported at runtime from
  `vllm.vllm_flash_attn` — an **external forked vLLM wheel, ABSENT from this repo** (only *patched/verified*
  by `CTM_plus/Bench/scripts/apply_phase*_patches.py`). The QK·softmax·PV int4 `.cu` is not present.
- **In-repo, real, GPU-runnable** decode = the **Triton** kernel
  `CTM_plus/KVPolicy/kv_policy/int4_fused_attention_kernel.py` (route-A read-fusion). It already does
  **in-kernel paged gather + inline dequant + protect overlay** — i.e. it is largely the "gather-fusion /
  store-as-consumed" design the next project proposes. **Profile this** (it needs no external fork).
- **In-repo CUDA** = WRITE path only (`CTM_plus/CUDA_int4_protected/csrc/fused_decode_write_{k,v}.cu`).

## Stage-by-stage (production vLLM-backend path)

| # | Stage | path:function (`/home/user/symbolu`) | Kind |
|---|-------|--------------------------------------|------|
| 0 | Backend entry / decode dispatch | `CTM_plus/KVPolicy/kv_policy/phase5b_backend_install.py:884` `Int4ProtectedAttentionImpl.forward` → `:1424` `_read_decode_packed` | host |
| 1 | int4 decode kernel call | `phase5b_backend_install.py:659,819` `flash_attn_with_int4_kvcache(` (import `:507`) | **external CUDA — ABSENT** |
| 2 | Block-table + paged gather | `phase5b_backend_install.py:455,570`; `phase5b_4c_paged_writer.py:2772` `kv_cache[0][block_ids]` | host (CUDA index) |
| 3 | Contiguous staging | `phase5b_4c_paged_writer.py:2778` `.contiguous()`; `phase5b_backend_install.py:670-677` per-arg `.contiguous()` | host |
| 4 | Partial-tail K splice | `phase5b_backend_install.py:1918,1997` `_splice_k_partial_tail*` (BS geom `:565`) | host |
| 5 | Protect mask + value load | `phase5b_4c_paged_writer.py:2785` `k_protect_ext[block_ids]`; overlay in absent kernel | host + external |
| 6 | Affine scale/xmin dequant | write: `phase5b_4c_paged_writer.py:35` `_ASYM_DIV=15.0`, `:1111`; decode dequant in absent kernel | external |
| 7 | QK / softmax / PV / writeback | inside absent kernel; copy-back `phase5b_backend_install.py:1431` | external CUDA |

## Same stages in the in-repo Triton route-A kernel (PRESENT)

`CTM_plus/KVPolicy/kv_policy/int4_fused_attention_kernel.py`, kernel `_fused_protected_k_decode_attn_splitk_kernel:57`:
- in-kernel gather `:117` `tl.load(gather_ptr + s)` · int4 unpack `:126` · dequant `:131` `kiv*k_sc` ·
  protect overlay `:141` `tl.where(pm, k_f16, k_dq)` · QK `:144` · online softmax `:148-152` · PV `:173` ·
  writeback via combine `:216`. CPU numeric oracle: `int4_fused_attention_sketch.py:174`
  `fused_int4_attention_reference`.

## Diagram

```
scheduler / block table
  → gather / page resolution        [stage 2]  query-dependent selection; host gather is an ARTIFACT
  → temporary packed representation  [stage 3]  ARTIFACT (contiguous staging)  ── removable
  →   + partial-tail splice          [stage 4]  ARTIFACT of per-block K quant  ── removable
  → dequant / protection handling    [5,6]      dequant INTRINSIC to int4; protect SCATTER is layout ARTIFACT
  → attention (QK·softmax·PV)        [7]        query-dependent, UNAVOIDABLE
  → output writeback                 [7]        UNAVOIDABLE
```

## Classification (drives the decision matrix)

| Operation | Class | Implication |
|-----------|-------|-------------|
| Block/page resolution | query-dependent, **movable into kernel** | route-A does it in-kernel |
| Host paged gather → contiguous temp | **implementation artifact** | removed by in-kernel gather + store-as-consumed |
| Partial-tail K splice | **implementation artifact** | store the tail block kernel-native at write time |
| Protect mask | query-independent (frozen) → **write-time** | already frozen on the writer |
| Protect value **scatter** | **layout artifact** | densify/coalesce (Part F P8 + dense stream) |
| Affine int4 dequant | **intrinsic to format** | only a format change removes it (out of scope) |
| QK / softmax / PV | query-dependent | **unavoidable** — sets the recovery ceiling |

**Takeaway for Step-0:** the removable surface is stages 2–5 (gather, staging, splice, protect-scatter).
Whether **gather+staging** or **protect-scatter** is the taller pole is exactly what the profile must
measure — the in-repo Triton route-A kernel already collapses stages 2–4, so the honest first experiment
is to **profile route-A vs the production host-gather path** and see what remains (likely protect-scatter +
attention proper). Do not assume; see `05_decision_matrix.py`.
