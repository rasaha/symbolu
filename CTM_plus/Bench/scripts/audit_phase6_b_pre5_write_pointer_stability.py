"""Phase 6 v2 Option B pre-flight (B-pre-5 / Phase 6B.1) — write-path
pointer stability audit.

The write path's CAPTURED REGION scatters into many tensors:

  kv_cache                   (vLLM-owned paged uint8 store)
  k_scale_ext / k_xmin_ext   (sidecars; writer-owned)
  k_protect_ext              (sidecar; writer-owned)
  v_scale_ext / v_xmin_ext   (sidecars; writer-owned)
  _bf16_k_backing_pool       (B-pre-1 pool; writer-owned)
  _bf16_v_backing_pool       (B-pre-1 pool; writer-owned)
  _k_stage_pool              (B-pre-1 pool; writer-owned)
  _seq_pos_pool              (Phase 6B.1 counter; writer-owned)
  _k_stage_count_pool        (Phase 6B.1 counter; writer-owned)
  _k_stage_block_id_pool     (Phase 6B.1 counter; writer-owned)

For CUDA-graph capture (6B.3) every one of these must have a STABLE
data_ptr() across decode calls within a (B, n_blocks_max) shape
bucket. The captured graph records ADDRESSES at capture time; replay
reads from those exact addresses. Mirrors the read-path audit
`audit_phase6_b_pre4_pointer_stability.py`.

This audit instruments a CPU writer (no vLLM stack needed) by logging
`data_ptr()` of every scatter target across N decode calls and
reporting per-tensor stability (STABLE / CYCLE-N / CHURN). Because
ALL of these tensors are allocated ONCE (in `_lazy_alloc` or by vLLM
at engine init) and never re-allocated, expectation is uniformly
STABLE.

If any tensor reports CYCLE or CHURN, the captured graph would point
at stale memory on replay — diagnose before 6B.3.

CPU-runnable. Run from CTM_plus/Bench:
  PYTHONPATH=../KVPolicy python3 \\
      scripts/audit_phase6_b_pre5_write_pointer_stability.py

Exit 0 on all-STABLE, 1 on any unstable tensor.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import torch


_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_kvp_root = os.path.join(_repo_root, "KVPolicy")
if _kvp_root not in sys.path:
    sys.path.insert(0, _kvp_root)

from kv_policy.phase5b_4c_paged_writer import PagedKVWriter


# (B, n_blocks_max) -> tensor_name -> list of (call_idx, data_ptr).
_LOG: Dict[tuple, Dict[str, List[tuple]]] = defaultdict(
    lambda: defaultdict(list),
)
_CALL_COUNT = [0]


def _log_writer_state(B: int, writer: PagedKVWriter, kv_cache: torch.Tensor):
    """Record data_ptr() of every scatter target for this call."""
    n_blocks_max = kv_cache.shape[1]
    bucket = (B, n_blocks_max)
    call_idx = _CALL_COUNT[0]
    _CALL_COUNT[0] += 1

    def _rec(name: str, t: torch.Tensor):
        _LOG[bucket][name].append(
            (call_idx, t.data_ptr(), tuple(t.shape), str(t.dtype))
        )

    _rec("kv_cache",                 kv_cache)
    _rec("k_scale_ext",              writer.k_scale_ext)
    _rec("k_xmin_ext",               writer.k_xmin_ext)
    _rec("k_protect_ext",            writer.k_protect_ext)
    _rec("v_scale_ext",              writer.v_scale_ext)
    _rec("v_xmin_ext",               writer.v_xmin_ext)
    _rec("_bf16_k_backing_pool",     writer._bf16_k_backing_pool)
    _rec("_bf16_v_backing_pool",     writer._bf16_v_backing_pool)
    _rec("_k_stage_pool",            writer._k_stage_pool)
    _rec("_seq_pos_pool",            writer._seq_pos_pool)
    _rec("_k_stage_count_pool",      writer._k_stage_count_pool)
    _rec("_k_stage_block_id_pool",   writer._k_stage_block_id_pool)
    _rec("protect_mask",             writer.protect_mask)
    _rec("protect_slot",             writer.protect_slot)
    _rec("protected_d_per_head",     writer.protected_d_per_head)


def _classify(n_unique: int) -> str:
    if n_unique == 1:
        return "STABLE"
    if n_unique <= 4:
        return f"CYCLE-{n_unique}"
    return "CHURN"


def main() -> int:
    print("=" * 78)
    print("Phase 6 v2 Option B pre-flight (B-pre-5 / Phase 6B.1)")
    print("write-path pointer-stability audit")
    print("=" * 78)
    print(f"device=cpu (audit is CPU-only)  torch={torch.__version__}")
    print()

    # Build a CPU writer + prefill 2 seqs.
    NUM_LAYERS, H, D, BS, N_PROTECT = 28, 4, 128, 32, 5
    mask = torch.zeros((H, D), dtype=torch.int8)
    mask[:, :N_PROTECT] = 1
    full = mask.unsqueeze(0).expand(NUM_LAYERS, -1, -1).contiguous()
    fd, mask_path = tempfile.mkstemp(suffix=".pt")
    os.close(fd)
    torch.save(full, mask_path)
    os.environ["PROTECT_MASK_PATH"] = mask_path

    try:
        writer = PagedKVWriter(layer_idx=0, sidecar_dtype=torch.bfloat16)
        kv_cache = torch.zeros((2, 64, BS, H, D), dtype=torch.uint8)

        # Prefill via legacy single-seq path (not captured).
        seq_ids = [300, 301]
        for i, sid in enumerate(seq_ids):
            base_block = (i + 1) * 4
            slots = torch.arange(
                base_block * BS, base_block * BS + BS, dtype=torch.long,
            )
            k = torch.randn(BS, H, D, dtype=torch.bfloat16) * 0.5
            v = torch.randn(BS, H, D, dtype=torch.bfloat16) * 0.5
            writer.write(k, v, kv_cache, slots, seq_id=sid)

        slot_idx_t = torch.tensor(
            [writer._slot_map[s] for s in seq_ids], dtype=torch.long,
        )

        # Decode loop — log writer state BEFORE each call (the addresses
        # the captured graph would record).
        B = 2
        N_STEPS = 32
        for step in range(N_STEPS):
            _log_writer_state(B, writer, kv_cache)
            k_step = torch.randn(B, H, D, dtype=torch.bfloat16) * 0.5
            v_step = torch.randn(B, H, D, dtype=torch.bfloat16) * 0.5
            slot_mapping = torch.tensor(
                [(i + 1) * 4 * BS + BS + step for i in range(B)],
                dtype=torch.long,
            )
            writer.write_decode_batched(
                key=k_step, value=v_step, kv_cache=kv_cache,
                slot_mapping=slot_mapping, slot_idx_t=slot_idx_t,
            )

        # Report.
        print(f"Ran {N_STEPS} write_decode_batched calls at B={B}.")
        print()
        overall_ok = True
        for bucket, by_name in _LOG.items():
            print(f"Bucket {bucket}:")
            print(f"  {'tensor':<30s} {'n_unique':>9s}  {'status':<10s}  "
                  f"{'shape':<32s} {'dtype':<16s}")
            print(f"  {'-'*30} {'-'*9}  {'-'*10}  {'-'*32} {'-'*16}")
            for name, recs in sorted(by_name.items()):
                addrs = {ptr for (_, ptr, _, _) in recs}
                _, _, shape, dtype = recs[0]
                status = _classify(len(addrs))
                marker = "" if status == "STABLE" else " <-- INVESTIGATE"
                print(f"  {name:<30s} {len(addrs):>9d}  {status:<10s}  "
                      f"{str(shape):<32s} {dtype:<16s}{marker}")
                if status != "STABLE":
                    overall_ok = False
            print()

    except Exception:
        traceback.print_exc()
        overall_ok = False
    finally:
        try:
            os.unlink(mask_path)
        except OSError:
            pass

    if overall_ok:
        print("Phase 6B.1 write-path pointer stability: GREEN")
        print("  Every scatter target observed across the audit window has")
        print("  a STABLE data_ptr(). Captured CUDA graphs can record these")
        print("  addresses once and replay them safely.")
        return 0
    print("Phase 6B.1 write-path pointer stability: FAIL")
    print("  At least one scatter target reports CYCLE / CHURN. Diagnose")
    print("  before enabling capture (6B.3).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
