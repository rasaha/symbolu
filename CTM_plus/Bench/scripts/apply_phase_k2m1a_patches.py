#!/usr/bin/env python3
"""K2-M1A — separately-compiled Is_m1 int4-packed decode kernel (register/spill probe).

Adds a NEW, independently-compiled kernel specialization selected at runtime by
`KVPRO_K2_M1=1`, default OFF, that differs from the production int4-packed decode kernel
by ONE thing: the Phase F reconstruction loop in the K loader is bounded-unrolled instead
of fully unrolled, to cut the measured register spill (baseline LDL 223-1218 / STL 118-427,
K2_M1_BASELINE_MEASURED.md). Numerically bit-identical (same math, less unroll).

Why a template split and not a runtime branch: register allocation is per-compiled-kernel,
so a runtime `if (use_m1)` would keep BOTH loop bodies live and the full-unroll body's
pressure would dominate -> zero spill reduction. The M1 kernel must be its own binary.

Selection: flash_api.cpp reads getenv("KVPRO_K2_M1"); if set (and the wheel was built with
KVPRO_K2_M1_BUILD, defined in flash.h by this patch) it dispatches the Is_m1=true kernel;
if requested but not built it fails loudly (TORCH_CHECK). Production path is byte-identical
and default.

Idempotent. POD-ONLY (patches the /workspace/dev fork tree). Applied by build_k2_m1.sh.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

DEV_ROOT = Path(os.environ.get("FA_DIR", "/workspace/dev/vllm-flash-attn-dev"))
SRC = DEV_ROOT / "csrc" / "flash_attn" / "src"
API = DEV_ROOT / "csrc" / "flash_attn" / "flash_api.cpp"
LAUNCH = SRC / "flash_fwd_launch_template.h"
KERNEL = SRC / "flash_fwd_kernel.h"
FLASH_H = SRC / "flash.h"
PACKED_LOAD = SRC / "int4_packed_load.h"
PACKED_CU = SRC / "flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu"

MARK = "K2-M1"


def _sub(src: str, old: str, new: str, label: str, count: int = 1) -> str:
    if old not in src:
        raise SystemExit(f"[k2m1] ANCHOR NOT FOUND: {label}\n  looked for:\n{old[:400]}")
    n = src.count(old)
    if count and n != count:
        raise SystemExit(f"[k2m1] anchor '{label}' found {n}x, expected {count}")
    return src.replace(old, new)


# ---------------------------------------------------------------------------
# Patch 1: flash.h — build macro, params flag, _m1 fwd decl
# ---------------------------------------------------------------------------
def patch_flash_h():
    src = FLASH_H.read_text()
    if MARK in src:
        print("  SKIP flash.h (already patched)"); return
    # (a) params flag right after is_int4kv_packed
    src = _sub(src, "    bool is_int4kv_packed = false;",
               "    bool is_int4kv_packed = false;\n"
               "    bool k2m1_enabled = false;  // K2-M1: getenv KVPRO_K2_M1 -> Is_m1 kernel",
               "flash.h k2m1_enabled field")
    # (b) build macro + _m1 dispatch fwd decl, anchored on the packed fwd decl
    anchor = ("template<typename T, int Headdim, bool Is_causal> void "
              "run_mha_fwd_splitkv_dispatch_int4kv_packed(Flash_fwd_params &params, cudaStream_t stream);"
              "  // 6c.3C Phase 2.4.1b")
    src = _sub(src, anchor,
               "#define KVPRO_K2_M1_BUILD 1  // K2-M1 present in this build\n"
               + anchor +
               "\ntemplate<typename T, int Headdim, bool Is_causal> void "
               "run_mha_fwd_splitkv_dispatch_int4kv_packed_m1(Flash_fwd_params &params, cudaStream_t stream);"
               "  // K2-M1",
               "flash.h _m1 fwd decl")
    FLASH_H.write_text(src); print("  PATCHED flash.h")


# ---------------------------------------------------------------------------
# Patch 2: int4_packed_load.h — derive int4_packed_load_K_block_m1 (bounded unroll)
# ---------------------------------------------------------------------------
def patch_packed_load():
    src = PACKED_LOAD.read_text()
    if "int4_packed_load_K_block_m1" in src:
        print("  SKIP int4_packed_load.h (already has _m1)"); return
    sig = "void int4_packed_load_K_block("
    si = src.find(sig)
    if si < 0:
        raise SystemExit("[k2m1] int4_packed_load_K_block not found")
    tmpl = src.rfind("template <", 0, si)
    if tmpl < 0:
        raise SystemExit("[k2m1] loader template line not found")
    brace = src.find("{", si)
    depth, i = 0, brace
    while i < len(src):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    func = src[tmpl:i + 1]
    m1 = func.replace("int4_packed_load_K_block(", "int4_packed_load_K_block_m1(")
    # bound the Phase F outer unroll: the single lever targeting the measured spill.
    pf_old = "    #pragma unroll\n    for (int i0 = 0; i0 < size<0>(tKsK)"
    if pf_old not in m1:
        raise SystemExit("[k2m1] Phase F outer-unroll anchor not found in loader")
    m1 = m1.replace(
        pf_old,
        "    // K2-M1: bound the outer unroll to cut simultaneously-live Phase F state\n"
        "    // (baseline spill LDL 223-1218). Numerically identical to the full-unroll loader.\n"
        "    #pragma unroll 1\n    for (int i0 = 0; i0 < size<0>(tKsK)", 1)
    # insert the derived _m1 loader just before the loader we copied.
    src = src[:tmpl] + "// K2-M1 derived loader (bounded Phase F unroll):\n" + m1 + "\n\n" + src[tmpl:]
    PACKED_LOAD.write_text(src); print("  PATCHED int4_packed_load.h (+int4_packed_load_K_block_m1)")


# ---------------------------------------------------------------------------
# Patch 3: flash_fwd_launch_template.h — thread Is_m1 + add _m1 dispatch
# ---------------------------------------------------------------------------
def patch_launch():
    src = LAUNCH.read_text()
    if MARK in src:
        print("  SKIP flash_fwd_launch_template.h (already patched)"); return
    # (a) run_flash_splitkv_fwd template: + Is_m1 (trailing default)
    src = _sub(src,
        "template<typename Kernel_traits, bool Is_causal, bool Is_int4kv = false, "
        "bool Is_int4kv_packed = false>",
        "template<typename Kernel_traits, bool Is_causal, bool Is_int4kv = false, "
        "bool Is_int4kv_packed = false, bool Is_m1 = false>  // K2-M1",
        "launch run_flash_splitkv_fwd template")
    # (b) kernel instantiation inside run_flash_splitkv_fwd: pass Is_m1
    src = _sub(src,
        "Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed>;",
        "Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed, Is_m1>;  // K2-M1",
        "launch kernel instantiation")
    # (c) DEFINE_FLASH_FORWARD_KERNEL: + Is_m1 param + pass to compute_attn_splitkv
    src = _sub(src,
        "DEFINE_FLASH_FORWARD_KERNEL(flash_fwd_splitkv_kernel, bool Is_causal, bool Is_local, "
        "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, bool Split, "
        "bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed) {",
        "DEFINE_FLASH_FORWARD_KERNEL(flash_fwd_splitkv_kernel, bool Is_causal, bool Is_local, "
        "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, bool Split, "
        "bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed, bool Is_m1) {  // K2-M1",
        "launch DEFINE macro")
    src = _sub(src,
        "compute_attn_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, "
        "Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed>(params);",
        "compute_attn_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, "
        "Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed, Is_m1>(params);  // K2-M1",
        "launch DEFINE compute_attn_splitkv call")
    # (d) add the _m1 dispatch after the existing packed dispatch
    anchor = ("void run_mha_fwd_splitkv_dispatch_int4kv_packed(Flash_fwd_params &params, "
              "cudaStream_t stream) {\n"
              "    constexpr static int kBlockM = 64;\n"
              "    constexpr static int kBlockN = Headdim <= 64 ? 256 : (Headdim <= 128 ? 128 : 64);\n"
              "    run_flash_splitkv_fwd<Flash_fwd_kernel_traits<Headdim, kBlockM, kBlockN, 4, false, "
              "false, T>, Is_causal, /*Is_int4kv=*/true, /*Is_int4kv_packed=*/true>(params, stream);\n}")
    m1_dispatch = anchor + """

// K2-M1: identical dispatch, Is_m1=true -> separately-compiled bounded-unroll kernel.
template<typename T, int Headdim, bool Is_causal>
void run_mha_fwd_splitkv_dispatch_int4kv_packed_m1(Flash_fwd_params &params, cudaStream_t stream) {
    constexpr static int kBlockM = 64;
    constexpr static int kBlockN = Headdim <= 64 ? 256 : (Headdim <= 128 ? 128 : 64);
    run_flash_splitkv_fwd<Flash_fwd_kernel_traits<Headdim, kBlockM, kBlockN, 4, false, false, T>, Is_causal, /*Is_int4kv=*/true, /*Is_int4kv_packed=*/true, /*Is_m1=*/true>(params, stream);
}"""
    src = _sub(src, anchor, m1_dispatch, "launch _m1 dispatch")
    LAUNCH.write_text(src); print("  PATCHED flash_fwd_launch_template.h")


# ---------------------------------------------------------------------------
# Patch 4: flash_fwd_kernel.h — thread Is_m1 + branch the loader call
# ---------------------------------------------------------------------------
def patch_kernel():
    src = KERNEL.read_text()
    if MARK in src:
        print("  SKIP flash_fwd_kernel.h (already patched)"); return
    # (a) compute_attn_1rowblock_splitkv + compute_attn_splitkv templates: + Is_m1 (before typename Params)
    tmpl_old = ("bool Split, bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed, typename Params>"
                "  // 6c.3C Phase 2.4.1b: + Is_int4kv_packed")
    # no default on Is_m1: every caller (DEFINE macro, compute_attn_splitkv) passes it explicitly,
    # and a defaulted non-type param before a deduced `typename Params` is best avoided.
    tmpl_new = ("bool Split, bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed, bool Is_m1, "
                "typename Params>  // K2-M1")
    src = _sub(src, tmpl_old, tmpl_new, "kernel compute_attn templates (x2)", count=2)
    # (b) compute_attn_splitkv -> compute_attn_1rowblock_splitkv call: pass Is_m1
    src = _sub(src,
        "compute_attn_1rowblock_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, "
        "Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed>(params, bidb, bidh, "
        "m_block, n_split_idx, num_n_splits);",
        "compute_attn_1rowblock_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, "
        "Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed, Is_m1>(params, bidb, bidh, "
        "m_block, n_split_idx, num_n_splits);  // K2-M1",
        "kernel compute_attn_splitkv -> 1rowblock call")
    # (c) branch the two identical K-loader call sites on Is_m1
    call_old = """            FLASH_NAMESPACE::int4_packed_load_K_block<
                Kernel_traits, kInt4GroupSize, kPackedMaxNProtect>(
                tKsK, tKVcKV, smem_packed_box,
                gmem_k_packed_base, gmem_k_scale_base, gmem_k_xmin_base,
                gmem_k_protect_base, gmem_protect_slot_base,
                bidh, params.seqlen_k, params.h_k, packed_n_protect,
                n_block * Kernel_traits::kBlockN, binfo.actual_seqlen_k);"""
    call_new = """            if constexpr (Is_m1) {  // K2-M1: bounded-unroll loader (separately compiled)
                FLASH_NAMESPACE::int4_packed_load_K_block_m1<
                    Kernel_traits, kInt4GroupSize, kPackedMaxNProtect>(
                    tKsK, tKVcKV, smem_packed_box,
                    gmem_k_packed_base, gmem_k_scale_base, gmem_k_xmin_base,
                    gmem_k_protect_base, gmem_protect_slot_base,
                    bidh, params.seqlen_k, params.h_k, packed_n_protect,
                    n_block * Kernel_traits::kBlockN, binfo.actual_seqlen_k);
            } else {
                FLASH_NAMESPACE::int4_packed_load_K_block<
                    Kernel_traits, kInt4GroupSize, kPackedMaxNProtect>(
                    tKsK, tKVcKV, smem_packed_box,
                    gmem_k_packed_base, gmem_k_scale_base, gmem_k_xmin_base,
                    gmem_k_protect_base, gmem_protect_slot_base,
                    bidh, params.seqlen_k, params.h_k, packed_n_protect,
                    n_block * Kernel_traits::kBlockN, binfo.actual_seqlen_k);
            }"""
    src = _sub(src, call_old, call_new, "kernel K-loader call sites (x2)", count=2)
    KERNEL.write_text(src); print("  PATCHED flash_fwd_kernel.h")


# ---------------------------------------------------------------------------
# Patch 5: flash_api.cpp — getenv + fail-loud + dispatch branch
# ---------------------------------------------------------------------------
def patch_api():
    src = API.read_text()
    if MARK in src:
        print("  SKIP flash_api.cpp (already patched)"); return
    if "#include <cstdlib>" not in src:
        src = src.replace('#include "flash.h"', '#include <cstdlib>\n#include "flash.h"', 1)
    # (a) set k2m1_enabled from getenv + fail-loud, right after is_int4kv is set in run_mha_fwd
    src = _sub(src, "    params.is_int4kv = _int4kv_dispatch;",
        "    params.is_int4kv = _int4kv_dispatch;\n"
        "    {  // K2-M1: opt-in via env, default OFF\n"
        "        const char* _k2m1 = std::getenv(\"KVPRO_K2_M1\");\n"
        "        params.k2m1_enabled = (_k2m1 != nullptr && atoi(_k2m1) != 0);\n"
        "#ifndef KVPRO_K2_M1_BUILD\n"
        "        TORCH_CHECK(!params.k2m1_enabled, \"KVPRO_K2_M1=1 requested but this wheel was \"\n"
        "            \"not built with K2-M1. Rebuild via build_k2_m1.sh.\");\n"
        "#endif\n"
        "    }",
        "api getenv + fail-loud")
    # (b) branch the packed dispatch on k2m1_enabled
    src = _sub(src,
        "                            run_mha_fwd_splitkv_dispatch_int4kv_packed<elem_type, kHeadDim, "
        "Is_causal>(params, stream);",
        "                            if (params.k2m1_enabled) {  // K2-M1\n"
        "                                run_mha_fwd_splitkv_dispatch_int4kv_packed_m1<elem_type, kHeadDim, Is_causal>(params, stream);\n"
        "                            } else {\n"
        "                                run_mha_fwd_splitkv_dispatch_int4kv_packed<elem_type, kHeadDim, Is_causal>(params, stream);\n"
        "                            }",
        "api packed dispatch branch")
    API.write_text(src); print("  PATCHED flash_api.cpp")


# ---------------------------------------------------------------------------
# Patch 6: instantiation .cu — add the _m1 explicit instantiation
# ---------------------------------------------------------------------------
def patch_cu():
    src = PACKED_CU.read_text()
    if "run_mha_fwd_splitkv_dispatch_int4kv_packed_m1" in src:
        print("  SKIP .cu (already has _m1)"); return
    anchor = ("template void run_mha_fwd_splitkv_dispatch_int4kv_packed<cutlass::bfloat16_t, 128, false>(\n"
              "    Flash_fwd_params &params, cudaStream_t stream);")
    src = _sub(src, anchor,
        anchor + "\n\n// K2-M1 instantiation\n"
        "template void run_mha_fwd_splitkv_dispatch_int4kv_packed_m1<cutlass::bfloat16_t, 128, false>(\n"
        "    Flash_fwd_params &params, cudaStream_t stream);",
        "cu _m1 instantiation")
    PACKED_CU.write_text(src); print("  PATCHED .cu")


def main():
    if not SRC.is_dir():
        raise SystemExit(f"[k2m1] fork src tree not found at {SRC} — run k0_build.sh first")
    print(f"[k2m1] patching {DEV_ROOT}")
    patch_flash_h()
    patch_packed_load()
    patch_launch()
    patch_kernel()
    patch_api()
    patch_cu()
    print("[k2m1] done. Build with: bash scripts/kvpro_kernel_recovery/build_k2_m1.sh")


if __name__ == "__main__":
    main()
