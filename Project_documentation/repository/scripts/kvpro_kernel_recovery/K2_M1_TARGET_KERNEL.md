# K2-M1 Phase A — the exact target kernel (frozen)

> **Target:** the single production INT4 **packed** split-K decode-attention specialization exercised
> by Qwen2.5-7B-Instruct on A100 at long context. Everything below is either read from in-repo patch
> source (cited `file:line`) or flagged **[POD]** = must be confirmed on the pod by
> `extract_target_kernel.sh` (the base `flash_fwd_kernel.h` and the compiled `.so` are pod-only).
> We optimize **only this specialization** in M1 — not the other template variants.

## 1. Kernel identity

- **Op:** `torch.ops._vllm_fa2_C.fwd_kvcache_int4` → C++ `mha_fwd_kvcache_int4` → `run_mha_fwd` →
  (3-way dispatch, packed > int4 > stock) → `run_mha_fwd_splitkv_dispatch_int4kv_packed`.
- **CUDA kernel:** `flash::flash_fwd_splitkv_kernel<Kernel_traits, Is_causal, Is_local, Has_alibi,
  Is_even_MN, Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed>` — the stock
  flash split-KV kernel with **two added template bools** (`Is_int4kv`, `Is_int4kv_packed`) threaded
  through (`apply_phase2_5_patches.py:117-159`, `apply_phase2_4_1b_patches.py:463-477,634-676`).
- **Target specialization (the one to optimize):** `Is_int4kv=true, Is_int4kv_packed=true`,
  `Is_causal=false` (production passes `causal=False`, `phase5b_backend_install.py:665`),
  `Split=true` at long ctx (auto flash-decoding split). The **last two template bools = `true,true`**
  are what distinguish the target symbol from the ~30 stock/causal variants in the cuobjdump dump.
  **[POD]** `extract_target_kernel.sh` demangles and isolates exactly this symbol's resource usage.

## 2. Tiling / launch geometry

| knob | value | source |
|---|---|---|
| head dim (`kHeadDim`) | 128 | `apply_phase2_4_1b_patches.py:513-518`; runtime gate `kHeadDim==128` `:592-609` |
| `kBlockM` (query tile) | **64** | `:528-533` (`constexpr int kBlockM = 64`) |
| `kBlockN` (key tile) | **128** (hdim≤128 branch) | `:528` (`Headdim<=128 ? 128 : 64`) |
| warps (`kNWarps`) | **4** (→ 128 threads/block) | `:528-533` |
| elem type | `cutlass::bfloat16_t` | gate `is_same_v<elem_type,bfloat16_t>` `:592` |
| GQA | inherited flash `h_h_k_ratio` (H_q=28,H_kv=4, ratio 7); **kernel does NOT re-specialize on H_kv** | map §5 |
| `num_splits` | wrapper default **0 → auto** flash-decoding split | `phase5b_backend_install.py` sets none; `run_mha_fwd` branches on `params.num_splits<=1` (`apply_phase2_2_patches.py:140`) |
| launch grid / block dims | **[POD]** (base `flash_fwd_launch_template.h`) | — |
| **actual num_splits @ 16K / 32K, B∈{1,8,32}** | **[POD]** (depends on seqlen + heuristic) | — |
| arch | `sm_80` (`TORCH_CUDA_ARCH_LIST=8.0`) | `kernel_provenance.json:52` |

## 3. Source files

**In-repo (string literals — the INT4 additions):**
- reconstruction (primary/packed): `apply_phase2_4_1b_patches.py` → writes `csrc/flash_attn/src/int4_packed_load.h`
  (load `:266-274`, scale/xmin `:279-311`, protect `:314-336`, **transform `:355-370`**) + the packed
  `.cu` `:405-419`; K-load wiring into `flash_fwd_kernel.h` `:771-812`; base-ptr setup `:739-758`.
- in-register (secondary/unpacked-K) path: `apply_phase2_3_patches.py` → `int4_inline.h`
  (`int4_quant_dequant_K_block_inplace`, affine `:296-303`); protected skip `apply_phase4_patches.py:94-131`.
- V dequant: `apply_phase3_patches.py` (`int4_quant_dequant_V_block_inplace`); packed-V `apply_phase2_6_2_patches.py`.
- OOB/dispatch fixes that also touch the kernel: `apply_phase6k2_int4_load_oob_fix.sh`,
  `apply_phase6k7_int4_dispatch_fix.sh`, `apply_phase6_cpasync_skip_k_prologue.py`.

**[POD] only (base @ 720c948 — NOT in this repo):** `flash_fwd_kernel.h` (the main loop that HOSTS the
transform at the K-wait/K-load sites), `flash_fwd_launch_template.h`, `flash.h`, `flash_api.cpp`,
`flash_api_torch_lib.cpp`, and the compiled `_vllm_fa2_C.abi3.so`. **The M1 register/latency behavior
is governed by this loop, so it must be extracted before the Phase D patch is written.**

## 4. Launcher / kernel args (the numerical contract to preserve exactly)

`phase5b_backend_install.py` `flash_attn_with_int4_kvcache(...)` (batched `:658-681`, single `:819-841`):
`query`, `bf16_k` **dummy** (zeros, content unused — `_ensure_dummy_kv:863-882`), `v`, `cache_seqlens`,
`protect_mask`, `n_protect`, `softmax_scale`, `causal=False`, `window_size`, `alibi_slopes`, `softcap`,
`k_packed_int4`, `k_packed_scale`, `k_packed_xmin`, `k_packed_protect_bf16`, `k_packed_protect_slot`,
`packed_group_size=BS`, `packed_n_protect` (≤8, `TORCH_CHECK` `apply_phase2_4_1b_patches.py:596`),
+ packed-V kwargs. Paging: `block_table`, `S_padded=n_blocks_max*BS`. **M1 must not change any of these.**

## 5. Current static resources (measured) + what's [POD]-pending

- cuobjdump (2026-07-17, `runs/cuobjdump_resusage_20260717.txt`): **all** `flash_fwd_splitkv_kernel`
  variants **REG 254–255, STACK 0–120 B, SHARED 0**; combine pass REG 56–62. → 12% theoretical
  occupancy at 255 regs. **Caveat:** that dump did not isolate the `int4kv_packed=true,true` symbol from
  the stock/causal ones (many 255-reg lines are `Is_causal=true, int4=false` — stock). **[POD]**
  `extract_target_kernel.sh` reports the EXACT target symbol's regs/stack/local + its SASS `LDL/STL`
  (local load/store) count = the real spill evidence (nonzero STACK alone is not proof of HBM spill).
- **Current target-kernel latency @ 16K and 32K (B∈{1,8,32})**: **[POD]** — measured by the Phase H
  harness on the current build before any change (the baseline the ≥20% gate is measured against).

## 6. Build target

Base SHA `720c94869cf2e0ff5a706e9c7f1dce0939686ade`; `TORCH_CUDA_ARCH_LIST=8.0`; CUDA 12.x; torch
2.5.1; py3.12; patch order per `k0_build.sh`. M1 adds one patch on top (Phase D), built as an
**isolated** wheel preserving the known-good production wheel (`build_k2_m1.sh`).

## 7. Frozen-target statement

> The M1 optimization target is the single specialization
> `flash_fwd_splitkv_kernel<Flash_fwd_kernel_traits<128,64,128,4,false,false,bf16>, /*causal*/false,
> …, /*Split*/true, …, /*Is_int4kv*/true, /*Is_int4kv_packed*/true>` at hdim128 / kBlockM64 / kBlockN128
> / 4 warps / sm_80, driven by the packed reconstruction in `int4_packed_load.h:355-370`. No other
> template variant, no format change, no quality-threshold change. Register count is a signal, **not**
> the gate — the gate is measured kernel latency (≥20% @16K,32K) then e2e TPS (≥15%).
