#!/usr/bin/env python3
"""apply_phase2_1_patches.py — 6c.3C Phase 2.1: dispatch arm + cloned kernel.

Adds 2 things to /workspace/dev/vllm-flash-attn-dev (no runtime change):

  * csrc/flash_attn/src/flash_fwd_launch_template.h — new templated
    function `run_mha_fwd_splitkv_dispatch_int4kv` placed right after
    the existing `run_mha_fwd_splitkv_dispatch`. INITIALLY identical
    body — Phase 2.2+ modifies it.
  * csrc/flash_attn/src/flash_fwd_split_hdim128_bf16_int4kv_sm80.cu
    — new file, explicit template instantiation of the _int4kv
    dispatch for bf16/hdim128/non-causal (Qwen2.5-7B target).
    Auto-picked by the flash_fwd_*.cu glob in CMakeLists.

Phase 2.1 acceptance criterion:
  * Build succeeds with the new .cu instantiation compiled and
    linked into _vllm_fa2_C.abi3.so (DEAD CODE — nothing calls it
    yet).
  * verify_phase1.py STILL passes — the active code path hasn't
    changed, so bit-equality with stock FA must hold.

Phase 2.2 will route mha_fwd_kvcache_int4 through the new dispatch
(requires cloning the ~200-line setup body of mha_fwd_kvcache), at
which point we get the FIRST runtime exercise of the new path.

Idempotent: re-running is a no-op.
"""

import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")


# ============================================================
# Patch 1: flash_fwd_launch_template.h
# ============================================================

DISPATCH_INT4KV = """
// 6c.3C Phase 2.1: INT4 KV dispatch (initially identical body).
// Phase 2.2+ will modify this function's body to use the INT4 K/V
// read path. The instantiation file is
// flash_fwd_split_hdim128_bf16_int4kv_sm80.cu; new hdim/dtype
// instantiations follow the same pattern.
template<typename T, int Headdim, bool Is_causal>
void run_mha_fwd_splitkv_dispatch_int4kv(Flash_fwd_params &params, cudaStream_t stream) {
    constexpr static int kBlockM = 64;
    constexpr static int kBlockN = Headdim <= 64 ? 256 : (Headdim <= 128 ? 128 : 64);
    run_flash_splitkv_fwd<Flash_fwd_kernel_traits<Headdim, kBlockM, kBlockN, 4, false, false, T>, Is_causal>(params, stream);
}
"""


def patch_launch_template_h(path: Path):
    src = path.read_text()
    if "run_mha_fwd_splitkv_dispatch_int4kv" in src:
        print(f"  SKIP (already patched): {path}")
        return
    # Anchor: the closing brace of run_mha_fwd_splitkv_dispatch.
    # That function is:
    #   void run_mha_fwd_splitkv_dispatch(...) {
    #       ...
    #       run_flash_splitkv_fwd<...>(params, stream);
    #   }
    # The last meaningful line before the close is the call to
    # run_flash_splitkv_fwd. Insert the new function RIGHT AFTER
    # the closing brace.
    anchor = (
        "    run_flash_splitkv_fwd<Flash_fwd_kernel_traits<Headdim, "
        "kBlockM, kBlockN, 4, false, false, T>, Is_causal>(params, "
        "stream);\n}"
    )
    if anchor not in src:
        raise RuntimeError(
            f"can't find run_mha_fwd_splitkv_dispatch closing-brace "
            f"anchor in {path}"
        )
    new_src = src.replace(anchor, anchor + "\n" + DISPATCH_INT4KV)
    path.write_text(new_src)
    print(f"  PATCHED: {path}")


# ============================================================
# Patch 2: new file flash_fwd_split_hdim128_bf16_int4kv_sm80.cu
# ============================================================

NEW_CU_CONTENT = """// Copyright (c) 2024, Tri Dao. 6c.3C Phase 2.1 — INT4 KV variant.
// Instantiates run_mha_fwd_splitkv_dispatch_int4kv for the Qwen2.5-7B
// target shape (bf16, hdim=128, non-causal decode). Auto-picked by
// the flash_fwd_*.cu glob in CMakeLists. Initially identical kernel
// content to flash_fwd_split_hdim128_bf16_sm80.cu — Phase 2.2+
// modifies the dispatch body in flash_fwd_launch_template.h.
#include "namespace_config.h"
#include "flash_fwd_launch_template.h"

namespace FLASH_NAMESPACE {

template void run_mha_fwd_splitkv_dispatch_int4kv<cutlass::bfloat16_t, 128, false>(Flash_fwd_params &params, cudaStream_t stream);

} // namespace FLASH_NAMESPACE
"""


def patch_new_cu(path: Path):
    if path.exists():
        print(f"  SKIP (already exists): {path}")
        return
    path.write_text(NEW_CU_CONTENT)
    print(f"  CREATED: {path}")


# ============================================================
# Main
# ============================================================

def main():
    if not DEV_ROOT.exists():
        print(f"ERROR: dev tree not at {DEV_ROOT}", file=sys.stderr)
        return 1

    targets = [
        (
            DEV_ROOT / "csrc/flash_attn/src/flash_fwd_launch_template.h",
            patch_launch_template_h,
        ),
        (
            DEV_ROOT / "csrc/flash_attn/src/flash_fwd_split_hdim128_bf16_int4kv_sm80.cu",
            patch_new_cu,
        ),
    ]

    print("Applying Phase 2.1 patches:")
    for path, fn in targets:
        try:
            fn(path)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR on {path}: {e}", file=sys.stderr)
            return 1

    print()
    print("Patches applied. Next steps:")
    print("  cd /workspace/dev/vllm-flash-attn-dev")
    print("  TORCH_CUDA_ARCH_LIST=8.0 MAX_JOBS=16 NVCC_THREADS=2 \\")
    print("      python setup.py bdist_wheel  # builds the new .cu instantiation")
    print("  bash /workspace/symbolu/CTM_plus/Bench/scripts/install_dev_vllm_flash_attn.sh")
    print("  python /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase1.py")
    print("    # ^ still bit-equality — new path is DEAD CODE in Phase 2.1.")
    print("    # Phase 2.2 will be the first time the new path runs at runtime.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
