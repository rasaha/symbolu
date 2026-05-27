"""Phase 6B.2 — hook-on vs hook-off bit-equivalence verify.

Mirrors verify_phase6_b_pre5_write_equiv.py's 36-cell shape, but
compares:

  cell HOOK-OFF : write_decode_batched(pre_synced=False)  — Phase 6B.1
                  semantics; writer does its own sync + writeback.
  cell HOOK-ON  : caller does _resolve_and_stash-style work outside
                  (one-time SeqState->pool sync), then calls
                  write_decode_batched(pre_synced=True).

The two paths MUST produce byte-identical kv_cache + sidecar +
backing pool + staging pool state. This is the load-bearing
correctness gate for Phase 6B.2: it proves the hook-driven path is
semantically equivalent to the self-resolve path on representative
batch sizes + modes.

CPU-runnable — no GPU, no full vLLM stack. Run from CTM_plus/Bench:
  PYTHONPATH=../KVPolicy python3 \\
      scripts/verify_phase6_b2_hook_equiv.py

Exit 0 on PASS, 1 on FAIL.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback

import torch


_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_kvp_root = os.path.join(_repo_root, "KVPolicy")
if _kvp_root not in sys.path:
    sys.path.insert(0, _kvp_root)

from kv_policy.phase5b_4c_paged_writer import PagedKVWriter


NUM_LAYERS = 28
H_KV       = 4
D          = 128
BS         = 32
V_GROUP    = 32
N_PROTECT  = 5
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE_BF   = torch.bfloat16
NB         = 64


def _make_protect_artifact() -> str:
    mask = torch.zeros((H_KV, D), dtype=torch.int8)
    mask[:, :N_PROTECT] = 1
    full = mask.unsqueeze(0).expand(NUM_LAYERS, -1, -1).contiguous()
    fd, path = tempfile.mkstemp(suffix=".pt")
    os.close(fd)
    torch.save(full, path)
    os.environ["PROTECT_MASK_PATH"] = path
    return path


def _make_writer() -> PagedKVWriter:
    return PagedKVWriter(layer_idx=0, sidecar_dtype=DTYPE_BF)


def _make_kv_cache() -> torch.Tensor:
    return torch.zeros((2, NB, BS, H_KV, D), dtype=torch.uint8, device=DEVICE)


def _run_cell(B: int, prefill_len: int, n_decode_steps: int, seed: int):
    """Run the same workload through:
      (off) write_decode_batched(pre_synced=False)  — 6B.1 baseline.
      (on)  caller _sync_pool_counters_from_states() pre-call;
            write_decode_batched(pre_synced=True). Mimics 6B.2 hook.
    Returns list[(check_name, ok)] for state comparisons."""
    torch.manual_seed(seed)
    w_off = _make_writer()
    w_on  = _make_writer()
    kv_off = _make_kv_cache()
    kv_on  = kv_off.clone()

    seq_ids = [400 + i for i in range(B)]
    seq_base_blocks = [(i + 1) * 4 for i in range(B)]

    # Prefill — same legacy single-seq path on both writers.
    for i, sid in enumerate(seq_ids):
        base_block = seq_base_blocks[i]
        slots = torch.arange(
            base_block * BS, base_block * BS + prefill_len,
            dtype=torch.long, device=DEVICE,
        )
        k = torch.randn(prefill_len, H_KV, D, dtype=DTYPE_BF, device=DEVICE) * 0.5
        v = torch.randn(prefill_len, H_KV, D, dtype=DTYPE_BF, device=DEVICE) * 0.5
        for w, kv in ((w_off, kv_off), (w_on, kv_on)):
            w.write(k, v, kv, slots, seq_id=sid)

    assert w_off._slot_map == w_on._slot_map, (
        "slot maps diverged during prefill — verifier setup bug"
    )
    slot_idx_t = torch.tensor(
        [w_on._slot_map[s] for s in seq_ids],
        dtype=torch.long, device=DEVICE,
    )
    slot_idx_list = slot_idx_t.cpu().tolist()

    # Decode loop.
    for step in range(n_decode_steps):
        k_step = torch.randn(B, H_KV, D, dtype=DTYPE_BF, device=DEVICE) * 0.5
        v_step = torch.randn(B, H_KV, D, dtype=DTYPE_BF, device=DEVICE) * 0.5
        slot_mapping = torch.tensor(
            [seq_base_blocks[i] * BS + prefill_len + step for i in range(B)],
            dtype=torch.long, device=DEVICE,
        )
        # HOOK-OFF cell.
        w_off.write_decode_batched(
            key=k_step, value=v_step, kv_cache=kv_off,
            slot_mapping=slot_mapping, slot_idx_t=slot_idx_t,
            pre_synced=False,
        )
        # HOOK-ON cell — mimics what install_int4_protected_precapture_
        # hook's wrap does on each step: sync ONCE pre-capture (only
        # fires on the first decode step due to sentinel gate; no-op
        # after), then call write_decode_batched with pre_synced=True.
        w_on._sync_pool_counters_from_states(slot_idx_list)
        w_on.write_decode_batched(
            key=k_step, value=v_step, kv_cache=kv_on,
            slot_mapping=slot_mapping, slot_idx_t=slot_idx_t,
            pre_synced=True,
        )

    return [
        ("kv_cache",         torch.equal(kv_off, kv_on)),
        ("k_scale_ext",      torch.equal(w_off.k_scale_ext, w_on.k_scale_ext)),
        ("k_xmin_ext",       torch.equal(w_off.k_xmin_ext, w_on.k_xmin_ext)),
        ("k_protect_ext",    torch.equal(w_off.k_protect_ext, w_on.k_protect_ext)),
        ("v_scale_ext",      torch.equal(w_off.v_scale_ext, w_on.v_scale_ext)),
        ("v_xmin_ext",       torch.equal(w_off.v_xmin_ext, w_on.v_xmin_ext)),
        ("bf16_k_backing",   torch.equal(w_off._bf16_k_backing_pool, w_on._bf16_k_backing_pool)),
        ("bf16_v_backing",   torch.equal(w_off._bf16_v_backing_pool, w_on._bf16_v_backing_pool)),
        ("k_stage_pool",     torch.equal(w_off._k_stage_pool, w_on._k_stage_pool)),
    ]


def main() -> int:
    print("=" * 78)
    print("Phase 6B.2 hook-on vs hook-off bit-equivalence verify")
    print("=" * 78)
    print(f"device={DEVICE}  torch={torch.__version__}")
    print()

    mask_path = _make_protect_artifact()
    overall_ok = True
    try:
        cells = []
        # Mode A — aligned prefill.
        for B in (1, 2, 4, 8):
            for steps in (1, 32, 64):
                cells.append((f"A_B{B}_steps{steps}", B, BS, steps))
        # Mode B — near-boundary prefill.
        for B in (1, 2, 4, 8):
            for steps in (1, 32, 64):
                cells.append((f"B_B{B}_steps{steps}", B, BS - 1, steps))
        # Mode C — mid-block prefill.
        for B in (1, 2, 4, 8):
            for steps in (1, 32, 64):
                cells.append((f"C_B{B}_steps{steps}", B, BS // 2, steps))

        n_pass = 0
        for label, B, prefill_len, n_decode_steps in cells:
            results = _run_cell(B, prefill_len, n_decode_steps,
                                seed=hash(label) & 0xFFFFFFFF)
            failed = [n for n, ok in results if not ok]
            verdict = "PASS" if not failed else "FAIL"
            if not failed:
                n_pass += 1
            else:
                overall_ok = False
            print(
                f"  [{verdict}] {label:<24s}  prefill={prefill_len:>3d} "
                f"decode_steps={n_decode_steps:>3d}  "
                f"{'all 9 tensors byte-equal' if not failed else 'diverged: ' + ','.join(failed)}"
            )

        print()
        print(f"Total cells: {len(cells)}   PASS: {n_pass}   FAIL: {len(cells) - n_pass}")
        print()
    except Exception:
        traceback.print_exc()
        overall_ok = False
    finally:
        os.unlink(mask_path)

    print()
    if overall_ok:
        print("Phase 6B.2 hook-on vs hook-off equivalence: GREEN")
        print("  Hook-driven path (sync once via _sync_pool_counters_from_states")
        print("  pre-call; write_decode_batched with pre_synced=True) produces")
        print("  byte-identical KV state to the self-resolve path (pre_synced=")
        print("  False) across B in {1,2,4,8} and Modes A/B/C at decode step")
        print("  counts {1, 32, 64}.")
        return 0
    print("Phase 6B.2 hook-on vs hook-off equivalence: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
