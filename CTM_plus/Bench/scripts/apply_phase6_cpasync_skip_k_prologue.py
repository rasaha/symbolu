#!/usr/bin/env python3
"""apply_phase6_cpasync_skip_k_prologue.py — Phase 6 step 4 (Option A).

Conservative kernel patch: wrap ONLY the K prologue cp.async with
`if constexpr (!Is_int4kv_packed)` so it's skipped on the packed path.

This is the SAFEST single site to test the hypothesis that "the
packed K helper fully overrides sK without needing the cp.async'd
bf16 K to seed it". If this site can be skipped cleanly:
  - existing verifies (write, read, e2e, char-diff, needle) all
    continue to PASS,
  - bench_phase5c_v1.py decode_tps should rise modestly,
  - we then expand the patch to also skip the V prologue + loop-body
    K/V prefetch cp.asyncs.

If this site CAN'T be skipped cleanly (S=128 fails the existing verify
suite with zero backing), we know the packed helper doesn't fully
seed sK and the right fix is a different one (e.g., explicit zero-
init of sK before the packed helper).

Anchor: the K prologue cp.async lives in compute_attn_1rowblock_splitkv,
immediately after `int n_block = n_block_max - 1;`. This site was
originally introduced by FlashAttention and is augmented in
apply_phase2_3 (Phase 2.3 added the K transform scratchpad nearby).

OLD (post-2.3):
    int n_block = n_block_max - 1;
    FLASH_NAMESPACE::copy<Is_even_MN, Is_even_K>(gmem_tiled_copy_KV, tKgK, tKsK, tKVcKV, tKVpKV,
                                                 binfo.actual_seqlen_k - n_block * kBlockN);
    cute::cp_async_fence();

NEW:
    int n_block = n_block_max - 1;
    // 6c.3C Phase 6: skip the prologue K cp.async on the packed path.
    // int4_packed_load_K_block (Phase 2.4.1b) overwrites sK from packed
    // HBM, so the BF16 K cp.async is wasted bandwidth + the source of
    // the 224 MB bf16 K/V backing we currently keep as a small-S
    // workaround.
    if constexpr (!Is_int4kv_packed) {
        FLASH_NAMESPACE::copy<Is_even_MN, Is_even_K>(gmem_tiled_copy_KV, tKgK, tKsK, tKVcKV, tKVpKV,
                                                     binfo.actual_seqlen_k - n_block * kBlockN);
        cute::cp_async_fence();
    }

Idempotent (re-running detects already-patched via sentinel string).

USAGE on the pod:
  # 1. Apply (patches the dev tree).
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase6_cpasync_skip_k_prologue.py

  # 2. Rebuild vllm_flash_attn (~10-15 min):
  cd /workspace/dev/vllm-flash-attn-dev && pip install -e . --no-deps --force-reinstall

  # 3. Run verifies (correctness gate):
  /workspace/venv-vllm/bin/python3 /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase5b_4c_1_write.py
  /workspace/venv-vllm/bin/python3 /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase2_4_1b.py
  /workspace/venv-vllm/bin/python3 /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase2_6_2.py
  /workspace/venv-vllm/bin/python3 /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase5b_4c_3_e2e.py --no-stock-compare
  /workspace/venv-vllm/bin/python3 /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase5b_5_needle.py

  # 4. Re-bench:
  /workspace/venv-vllm/bin/python3 /workspace/symbolu/CTM_plus/Bench/scripts/bench_phase5c_v1.py

ROLLBACK if any verify fails:
  bash /workspace/symbolu/CTM_plus/Bench/scripts/restore_vendored_vllm_flash_attn.sh
  # ... then re-apply phases 1, 2.1-2.6.2 (NOT this script):
  bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase1.sh
  bash /workspace/symbolu/CTM_plus/Bench/scripts/apply_phase2_1.sh
  # ... through apply_phase2_6_2.sh
  # ... then rebuild.

Decision rule after applying + verifying:
  - All verifies PASS + bench shows >5% int4_proto decode_tps gain:
    => Proceed with V prologue + loop-body sites (write follow-up
       patch).
  - Verifies PASS, but bench shows no improvement:
    => Skipping cp.async didn't help (kernel time wasn't dominated
       by that load). Stop here; revisit if we ever profile other
       gains.
  - Any verify FAILS:
    => The packed helper does NOT fully seed sK at this site. Rollback,
       and the fix path becomes "explicit zero-init of sK before the
       packed helper runs" (different patch).
"""
from __future__ import annotations

import sys
from pathlib import Path

DEV_ROOT = Path("/workspace/dev/vllm-flash-attn-dev")
KERNEL_PATH = DEV_ROOT / "csrc/flash_attn/src/flash_fwd_kernel.h"

# Sentinel string used to detect "already patched".
SENTINEL = "// 6c.3C Phase 6: skip the prologue K cp.async on the packed path."

# Anchor: the K prologue cp.async, post-phase2_3 state.
# Must match EXACTLY the current source (including whitespace).
OLD = """    int n_block = n_block_max - 1;
    // We don't need to clear the sK smem tiles since we'll mask out the scores anyway.
    FLASH_NAMESPACE::copy<Is_even_MN, Is_even_K>(gmem_tiled_copy_KV, tKgK, tKsK, tKVcKV, tKVpKV,
                                                 binfo.actual_seqlen_k - n_block * kBlockN);
    cute::cp_async_fence();"""

NEW = """    int n_block = n_block_max - 1;
    // We don't need to clear the sK smem tiles since we'll mask out the scores anyway.
    // 6c.3C Phase 6: skip the prologue K cp.async on the packed path.
    // int4_packed_load_K_block (Phase 2.4.1b) overwrites sK from packed
    // HBM, so the BF16 K cp.async is wasted bandwidth + the source of
    // the 224 MB bf16 K/V backing we currently keep as a small-S
    // workaround. Stock and Phase 2.3 _int4kv paths keep the cp.async.
    if constexpr (!Is_int4kv_packed) {
        FLASH_NAMESPACE::copy<Is_even_MN, Is_even_K>(gmem_tiled_copy_KV, tKgK, tKsK, tKVcKV, tKVpKV,
                                                     binfo.actual_seqlen_k - n_block * kBlockN);
        cute::cp_async_fence();
    }"""


def _exactly_once(src: str, needle: str, label: str) -> None:
    count = src.count(needle)
    if count == 0:
        raise RuntimeError(
            f"anchor '{label}' NOT FOUND in {KERNEL_PATH}. "
            f"Has the file changed since apply_phase2_3? Check that all "
            f"prior phases applied cleanly first."
        )
    if count > 1:
        raise RuntimeError(
            f"anchor '{label}' matches {count} times — not unique. "
            f"Refine the anchor string."
        )


def patch_file(path: Path) -> None:
    src = path.read_text()
    if SENTINEL in src:
        print(f"  SKIP (already patched): {path}")
        return
    _exactly_once(src, OLD, "K prologue cp.async")
    src_new = src.replace(OLD, NEW, 1)
    path.write_text(src_new)
    print(f"  PATCHED: {path}")


def main() -> int:
    if not DEV_ROOT.exists():
        print(f"ERROR: dev tree not at {DEV_ROOT}", file=sys.stderr)
        print(f"This patcher must run on the pod where the vllm-flash-attn "
              f"dev tree exists.", file=sys.stderr)
        return 1
    if not KERNEL_PATH.exists():
        print(f"ERROR: kernel file not at {KERNEL_PATH}", file=sys.stderr)
        return 1

    print("6c.3C Phase 6 step 4 (Option A.1 — conservative single-site)")
    print(f"  Target: {KERNEL_PATH}")
    patch_file(KERNEL_PATH)
    print()
    print("Patched. Next steps:")
    print("  cd /workspace/dev/vllm-flash-attn-dev && pip install -e . --no-deps --force-reinstall")
    print("  # ... wait ~10-15 min for recompile ...")
    print("  /workspace/venv-vllm/bin/python3 /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase5b_4c_1_write.py")
    print("  /workspace/venv-vllm/bin/python3 /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase2_4_1b.py")
    print("  /workspace/venv-vllm/bin/python3 /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase5b_4c_3_e2e.py --no-stock-compare")
    print("  /workspace/venv-vllm/bin/python3 /workspace/symbolu/CTM_plus/Bench/scripts/bench_phase5c_v1.py")
    print()
    print("Rollback (if any verify fails): restore vendored + re-apply phases 1..2.6.2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
