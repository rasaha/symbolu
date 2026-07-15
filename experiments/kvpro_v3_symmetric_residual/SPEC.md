# KVPro V3 Gate-1 — format specification (current + candidates)

Code-cited. All paths under `CTM_plus/KVPolicy/kv_policy/`.

## Phase A — Current int4_protected representation (verified in code)

| Property | Value | Source |
|---|---|---|
| **K quant** | per-**block**(BS=32) per-(H,D): `scale=((amax-amin)/15).clamp(1e-8)`; `q=round((x-xmin)/scale).clamp(0,15)`; `x̂=q·scale+xmin` | `phase5b_4c_paged_writer.py:1108-1113` (+ splice `:2018-2030`) |
| **V quant** | per-**token** per-(H,group), `v_group_size=32` → `v_n_groups=D/32`: same affine per group | `phase5b_4c_paged_writer.py:2059-2068` |
| **Code range** | **unsigned [0,15]** (4-bit), 2 codes/byte, low nibble = even channel | `:2025`, `:2068` |
| **Scale granularity** | K: per-(block,H,D); V: per-(token,H,group) | `k_scale_ext (NB,H,D)`, `v_scale_ext (NB,BS,H,v_n_groups)` `:1304-1309` |
| **xmin granularity** | same as scale (K per-block; **V per-token** — the larger, un-amortized stream) | `k_xmin_ext`, `v_xmin_ext` |
| **Constants** | `_ASYM_DIV=15.0`, `_SCALE_CLAMP=1e-8` | `:35-36` |
| **Protection mask** | `(H_kv, D)` int8 **per layer** (full `(L,H_kv,D)`); **per-channel**; `n_protect=max protected/head` | `_build_protect_tables:780`, `load_protect_mask_for_layer:804` |
| **Protection scope** | **K only** (V never protected) | no `v_protect` anywhere |
| **Protection semantics** | protected channels **replace** the int4 dequant at read (`where(mask, protect, dequant)`); they are also int4-packed but overridden | gather `:2078-2080`; overlay in kernel/`int4_fused_attention_sketch.py` |
| **Protect value store** | bf16 (default) or uint8 (**prot-int8**, Phase 6N: static asym `/255`) | `_protect_store:1876`, `prot_int8_quantize:759` |
| **Sidecar dtype** | bf16 (2 B); protect bf16 (2 B) or int8 (1 B) | `:1785-1789` |
| **Partial blocks** | K staging pool re-quantized each decode step (splice); full blocks bypass staging | `_splice_k_partial_tail:1997` |
| **Snapshot deps** | 7 tensors: packed_k/v, k_scale, k_xmin, k_protect(bf16 view), v_scale, v_xmin + prot_format | `tier5b_snapshot.py` |

**Residual = the non-protected K channels + all V channels** — where int4 actually represents the data.

## Phase B — Candidate symmetric formats

Signed symmetric **[-7,7]** (15 levels), `scale=max(|x|)/7`, `q=clamp(round(x/scale),-7,7)`, `x̂=q·scale`.
Protected K channels are **unchanged** (kept exact) in every candidate, so the ONLY variable is the
residual scheme. Granularities match the current format (K per-block, V per-token-group).

| Cand | K | V | Bias | Removes | bytes/tok/head/layer (D=128) | Δ vs affine |
|---|---|---|---|---|---:|---:|
| affine (baseline) | affine | affine | — | — | 172.0 | 0% |
| **S1** | symmetric | symmetric | none | K_xmin + V_xmin | 156.0 | **−9.30%** |
| **S2** | symmetric | symmetric | per-channel/layer bias (amortized ~0/tok) | K_xmin + V_xmin (recovers mean) | 156.0 | **−9.28%** |
| **S3** | affine | symmetric | none | V_xmin only | 164.0 | −4.65% |
| **S4** | symmetric | affine | none | K_xmin only | 164.0 | −4.65% |

*(Full accounting incl. instruction/ops removed and Llama-3.1-8B in `accounting.py`.)*

**Crux (analytical, MEASURED-by-arithmetic — NOT a TPS claim):** dropping **both** xmins (S1/S2) removes
**~9.3%** of decode read-bandwidth; dropping **one** (S3/S4) removes **~4.65%** — **below the 5% floor**.
Read-bandwidth is the throughput-relevant proxy only because decode is bandwidth-bound; the protected
(scattered) stream remains and likely becomes the next metadata bottleneck after xmin removal.

## Instruction / systems notes
- Symmetric removes the per-element `+xmin` affine add (K and/or V) and the xmin metadata load; adds a
  cheap sign-handling on unpack. `S2` adds a per-channel bias load amortized over the whole context
  (~0 B/token at long context).
- Dropping xmin changes the **snapshot format** → a version bump (the tier5b guard already refuses
  mismatched geometry/format).
