#!/usr/bin/env python3
"""K2-M1A — same-wheel unroll sweep for the int4-packed decode kernel (spill probe).

Adds, INTO ONE new wheel, a freshly-compiled CONTROL (kM1Unroll=0 = original full-unroll
loader) plus M1 variants that bound the Phase F reconstruction unroll (kM1Unroll ∈ {1,2,4})
to cut the measured register spill (baseline LDL 223-1218 / STL 118-427,
K2_M1_BASELINE_MEASURED.md). Selected at runtime by `KVPRO_K2_M1=<0|1|2|4>`, default 0.

Why a template split (int kM1Unroll threaded through the kernel), not a runtime branch:
register allocation is per-compiled-kernel; a runtime `if` keeps all loop bodies live and
the full-unroll pressure dominates -> zero spill reduction. Each unroll factor must be its
own compiled kernel.

Why a same-wheel control (kM1Unroll=0) and not "old wheel vs new wheel": the clean
comparison isolates the ONE compile-time difference (unroll factor). Comparing across wheels
would confound it with compiler/link/flag nondeterminism (per the review).

Numerics: the Phase F transform computes each tKsK element INDEPENDENTLY (no cross-element
accumulation), so changing the unroll cannot change any element's value; it is EXPECTED to be
bit-identical, but that is VERIFIED by the op-level test (bench_k2_m1_op.py), not promised.

Selection/plumbing: flash_api.cpp reads getenv -> params.k2m1_unroll, validates it is in
{0,1,2,4}, and dispatches the matching compiled kernel; flash.h defines KVPRO_K2_M1_BUILD
(all TUs) so a mis-built wheel fails loud (TORCH_CHECK). Production path byte-identical + default.

Idempotent, anchored to exact source. POD-ONLY (patches /workspace/dev). Run by build_k2_m1.sh.
"""
from __future__ import annotations
import os
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
FACTORS = (1, 2, 4)  # the small unroll sweep


def _sub(src: str, old: str, new: str, label: str, count: int = 1) -> str:
    if old not in src:
        raise SystemExit(f"[k2m1] ANCHOR NOT FOUND: {label}\n  looked for:\n{old[:400]}")
    n = src.count(old)
    if count and n != count:
        raise SystemExit(f"[k2m1] anchor '{label}' found {n}x, expected {count}")
    return src.replace(old, new)


def patch_flash_h():
    src = FLASH_H.read_text()
    if MARK in src:
        print("  SKIP flash.h (already patched)"); return
    src = _sub(src, "    bool is_int4kv_packed = false;",
               "    bool is_int4kv_packed = false;\n"
               "    int k2m1_unroll = 0;  // K2-M1: getenv KVPRO_K2_M1 (0=control, else unroll factor)",
               "flash.h k2m1_unroll field")
    anchor = ("template<typename T, int Headdim, bool Is_causal> void "
              "run_mha_fwd_splitkv_dispatch_int4kv_packed(Flash_fwd_params &params, cudaStream_t stream);"
              "  // 6c.3C Phase 2.4.1b")
    src = _sub(src, anchor,
               "#define KVPRO_K2_M1_BUILD 1  // K2-M1 present in this build\n"
               + anchor +
               "\ntemplate<typename T, int Headdim, bool Is_causal, int kM1Unroll> void "
               "run_mha_fwd_splitkv_dispatch_int4kv_packed_m1(Flash_fwd_params &params, cudaStream_t stream);"
               "  // K2-M1",
               "flash.h _m1 fwd decl")
    FLASH_H.write_text(src); print("  PATCHED flash.h")


def patch_packed_load():
    """Derive int4_packed_load_K_block_m1<..., int kUnroll> from the installed loader:
    add an int kUnroll template param and make the Phase F outer loop `#pragma unroll (kUnroll)`."""
    src = PACKED_LOAD.read_text()
    if "int4_packed_load_K_block_m1" in src:
        print("  SKIP int4_packed_load.h (already has _m1)"); return
    sig = "void int4_packed_load_K_block("
    si = src.find(sig)
    if si < 0:
        raise SystemExit("[k2m1] int4_packed_load_K_block not found")
    tmpl = src.rfind("template <", 0, si)
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
    # add the int kUnroll template parameter (explicit; kept before the deduced type params).
    if "int kMaxNProtect," not in m1:
        raise SystemExit("[k2m1] loader template param anchor 'int kMaxNProtect,' not found")
    m1 = m1.replace("int kMaxNProtect,", "int kMaxNProtect, int kUnroll,", 1)
    # bound the Phase F OUTER unroll with the template factor (constant expression).
    pf_old = "    #pragma unroll\n    for (int i0 = 0; i0 < size<0>(tKsK)"
    if pf_old not in m1:
        raise SystemExit("[k2m1] Phase F outer-unroll anchor not found")
    m1 = m1.replace(
        pf_old,
        "    // K2-M1: bound the outer unroll to cut simultaneously-live Phase F state\n"
        "    // (baseline spill LDL 223-1218). Per-element independent -> value-identical.\n"
        "    #pragma unroll (kUnroll)\n    for (int i0 = 0; i0 < size<0>(tKsK)", 1)
    src = src[:tmpl] + "// K2-M1 derived loader (templated Phase F unroll factor):\n" + m1 + "\n\n" + src[tmpl:]
    PACKED_LOAD.write_text(src); print("  PATCHED int4_packed_load.h (+int4_packed_load_K_block_m1<...,kUnroll>)")


def patch_launch():
    src = LAUNCH.read_text()
    if MARK in src:
        print("  SKIP flash_fwd_launch_template.h (already patched)"); return
    src = _sub(src,
        "template<typename Kernel_traits, bool Is_causal, bool Is_int4kv = false, "
        "bool Is_int4kv_packed = false>",
        "template<typename Kernel_traits, bool Is_causal, bool Is_int4kv = false, "
        "bool Is_int4kv_packed = false, int kM1Unroll = 0>  // K2-M1",
        "launch run_flash_splitkv_fwd template")
    src = _sub(src,
        "Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed>;",
        "Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed, kM1Unroll>;  // K2-M1",
        "launch kernel instantiation")
    src = _sub(src,
        "DEFINE_FLASH_FORWARD_KERNEL(flash_fwd_splitkv_kernel, bool Is_causal, bool Is_local, "
        "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, bool Split, "
        "bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed) {",
        "DEFINE_FLASH_FORWARD_KERNEL(flash_fwd_splitkv_kernel, bool Is_causal, bool Is_local, "
        "bool Has_alibi, bool Is_even_MN, bool Is_even_K, bool Is_softcap, bool Split, "
        "bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed, int kM1Unroll) {  // K2-M1",
        "launch DEFINE macro")
    src = _sub(src,
        "compute_attn_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, "
        "Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed>(params);",
        "compute_attn_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, "
        "Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed, kM1Unroll>(params);  // K2-M1",
        "launch DEFINE compute_attn_splitkv call")
    anchor = ("void run_mha_fwd_splitkv_dispatch_int4kv_packed(Flash_fwd_params &params, "
              "cudaStream_t stream) {\n"
              "    constexpr static int kBlockM = 64;\n"
              "    constexpr static int kBlockN = Headdim <= 64 ? 256 : (Headdim <= 128 ? 128 : 64);\n"
              "    run_flash_splitkv_fwd<Flash_fwd_kernel_traits<Headdim, kBlockM, kBlockN, 4, false, "
              "false, T>, Is_causal, /*Is_int4kv=*/true, /*Is_int4kv_packed=*/true>(params, stream);\n}")
    m1_dispatch = anchor + """

// K2-M1: identical dispatch, kM1Unroll>0 -> separately-compiled bounded-unroll kernel.
template<typename T, int Headdim, bool Is_causal, int kM1Unroll>
void run_mha_fwd_splitkv_dispatch_int4kv_packed_m1(Flash_fwd_params &params, cudaStream_t stream) {
    constexpr static int kBlockM = 64;
    constexpr static int kBlockN = Headdim <= 64 ? 256 : (Headdim <= 128 ? 128 : 64);
    run_flash_splitkv_fwd<Flash_fwd_kernel_traits<Headdim, kBlockM, kBlockN, 4, false, false, T>, Is_causal, /*Is_int4kv=*/true, /*Is_int4kv_packed=*/true, /*kM1Unroll=*/kM1Unroll>(params, stream);
}"""
    src = _sub(src, anchor, m1_dispatch, "launch _m1 dispatch")
    LAUNCH.write_text(src); print("  PATCHED flash_fwd_launch_template.h")


def patch_kernel():
    src = KERNEL.read_text()
    if MARK in src:
        print("  SKIP flash_fwd_kernel.h (already patched)"); return
    tmpl_old = ("bool Split, bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed, typename Params>"
                "  // 6c.3C Phase 2.4.1b: + Is_int4kv_packed")
    tmpl_new = ("bool Split, bool Append_KV, bool Is_int4kv, bool Is_int4kv_packed, int kM1Unroll, "
                "typename Params>  // K2-M1")
    src = _sub(src, tmpl_old, tmpl_new, "kernel compute_attn templates (x2)", count=2)
    src = _sub(src,
        "compute_attn_1rowblock_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, "
        "Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed>(params, bidb, bidh, "
        "m_block, n_split_idx, num_n_splits);",
        "compute_attn_1rowblock_splitkv<Kernel_traits, Is_causal, Is_local, Has_alibi, Is_even_MN, "
        "Is_even_K, Is_softcap, Split, Append_KV, Is_int4kv, Is_int4kv_packed, kM1Unroll>(params, bidb, bidh, "
        "m_block, n_split_idx, num_n_splits);  // K2-M1",
        "kernel compute_attn_splitkv -> 1rowblock call")
    call_old = """            FLASH_NAMESPACE::int4_packed_load_K_block<
                Kernel_traits, kInt4GroupSize, kPackedMaxNProtect>(
                tKsK, tKVcKV, smem_packed_box,
                gmem_k_packed_base, gmem_k_scale_base, gmem_k_xmin_base,
                gmem_k_protect_base, gmem_protect_slot_base,
                bidh, params.seqlen_k, params.h_k, packed_n_protect,
                n_block * Kernel_traits::kBlockN, binfo.actual_seqlen_k);"""
    call_new = """            if constexpr (kM1Unroll > 0) {  // K2-M1: bounded-unroll loader (separately compiled)
                FLASH_NAMESPACE::int4_packed_load_K_block_m1<
                    Kernel_traits, kInt4GroupSize, kPackedMaxNProtect, kM1Unroll>(
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


def patch_api():
    src = API.read_text()
    if MARK in src:
        print("  SKIP flash_api.cpp (already patched)"); return
    if "#include <cstdlib>" not in src:
        src = src.replace('#include "flash.h"', '#include <cstdlib>\n#include "flash.h"', 1)
    src = _sub(src, "    params.is_int4kv = _int4kv_dispatch;",
        "    params.is_int4kv = _int4kv_dispatch;\n"
        "    {  // K2-M1: opt-in via env, default 0 (control). Valid: 0/1/2/4.\n"
        "        const char* _k2m1 = std::getenv(\"KVPRO_K2_M1\");\n"
        "        params.k2m1_unroll = (_k2m1 != nullptr) ? atoi(_k2m1) : 0;\n"
        "        TORCH_CHECK(params.k2m1_unroll == 0 || params.k2m1_unroll == 1 ||\n"
        "                    params.k2m1_unroll == 2 || params.k2m1_unroll == 4,\n"
        "                    \"KVPRO_K2_M1 must be 0, 1, 2, or 4; got \", params.k2m1_unroll);\n"
        "#ifndef KVPRO_K2_M1_BUILD\n"
        "        TORCH_CHECK(params.k2m1_unroll == 0, \"KVPRO_K2_M1 set but this wheel lacks \"\n"
        "            \"K2-M1. Rebuild via build_k2_m1.sh.\");\n"
        "#endif\n"
        "    }",
        "api getenv + validate + fail-loud")
    src = _sub(src,
        "                            run_mha_fwd_splitkv_dispatch_int4kv_packed<elem_type, kHeadDim, "
        "Is_causal>(params, stream);",
        "                            switch (params.k2m1_unroll) {  // K2-M1 same-wheel control + sweep\n"
        "                              case 1: run_mha_fwd_splitkv_dispatch_int4kv_packed_m1<elem_type, kHeadDim, Is_causal, 1>(params, stream); break;\n"
        "                              case 2: run_mha_fwd_splitkv_dispatch_int4kv_packed_m1<elem_type, kHeadDim, Is_causal, 2>(params, stream); break;\n"
        "                              case 4: run_mha_fwd_splitkv_dispatch_int4kv_packed_m1<elem_type, kHeadDim, Is_causal, 4>(params, stream); break;\n"
        "                              default: run_mha_fwd_splitkv_dispatch_int4kv_packed<elem_type, kHeadDim, Is_causal>(params, stream);\n"
        "                            }",
        "api packed dispatch switch")
    API.write_text(src); print("  PATCHED flash_api.cpp")


def patch_cu():
    src = PACKED_CU.read_text()
    if "run_mha_fwd_splitkv_dispatch_int4kv_packed_m1" in src:
        print("  SKIP .cu (already has _m1)"); return
    anchor = ("template void run_mha_fwd_splitkv_dispatch_int4kv_packed<cutlass::bfloat16_t, 128, false>(\n"
              "    Flash_fwd_params &params, cudaStream_t stream);")
    insts = "\n".join(
        f"template void run_mha_fwd_splitkv_dispatch_int4kv_packed_m1<cutlass::bfloat16_t, 128, false, {f}>(\n"
        f"    Flash_fwd_params &params, cudaStream_t stream);" for f in FACTORS)
    src = _sub(src, anchor, anchor + "\n\n// K2-M1 instantiations (unroll sweep)\n" + insts,
               "cu _m1 instantiations")
    PACKED_CU.write_text(src); print(f"  PATCHED .cu (+_m1 factors {FACTORS})")


def main():
    if not SRC.is_dir():
        raise SystemExit(f"[k2m1] fork src tree not found at {SRC} — run k0_build.sh first")
    print(f"[k2m1] patching {DEV_ROOT}  (control + unroll sweep {FACTORS})")
    patch_flash_h()
    patch_packed_load()
    patch_launch()
    patch_kernel()
    patch_api()
    patch_cu()
    print("[k2m1] done. Build: bash scripts/kvpro_kernel_recovery/build_k2_m1.sh")


if __name__ == "__main__":
    main()
