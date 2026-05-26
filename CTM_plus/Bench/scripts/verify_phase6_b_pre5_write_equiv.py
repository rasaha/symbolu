"""Phase 6 v2 Option B pre-flight (B-pre-5 / Phase 6B.1) —
write_decode_batched bit-equivalence verify.

Asserts that the new graph-capture-friendly `PagedKVWriter.
write_decode_batched(...)` produces byte-identical KV cache state vs
the legacy per-seq `writer.write(seq_id=...)` Python loop, across:

  * Three "modes" of prefill→decode handoff:
      Mode A: aligned prefill (prefill_len % BS == 0); decode begins on
              a fresh block boundary.
      Mode B: prefill ends near block boundary (prefill_len == BS - 1);
              first decode token completes the prefill's partial block.
      Mode C: mid-block handoff (prefill_len == BS // 2); decode
              continues filling the same partial block first.

  * Four batch sizes (B in {1, 2, 4, 8}) — covers the ship target.

  * Three step-count regimes per mode: {1, 32, 64} decode steps. 32
    exercises one full FULL-block transition; 64 exercises two.

For each cell the verifier compares 9 state tensors bit-for-bit:
  - kv_cache (paged uint8 nibbles)
  - k_scale_ext / k_xmin_ext / k_protect_ext (K sidecars)
  - v_scale_ext / v_xmin_ext (V sidecars)
  - _bf16_k_backing_pool / _bf16_v_backing_pool (bf16 backings)
  - _k_stage_pool (staging buffer pool)

Math is bit-identical between paths because the unconditional re-
quantize in write_decode_batched reproduces the same packed-nibble +
scale + xmin chain the legacy splice / finalize paths run, just laid
out as one batched op chain instead of a per-seq Python loop.

CPU-runnable — no GPU, no full vLLM stack. Mirrors the structural
pattern of verify_phase5b_4c_1_write.py / verify_phase6_b_pre1_*.py.

Run from CTM_plus/Bench:
  PYTHONPATH=../KVPolicy python3 \\
      scripts/verify_phase6_b_pre5_write_equiv.py

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
NB         = 64       # generous block range; covers all test fixtures


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
    """Run one (B, prefill_len, n_decode_steps) cell through both paths
    and return list[(check_name, ok)] for the 9 state comparisons."""
    torch.manual_seed(seed)
    w_legacy = _make_writer()
    w_new    = _make_writer()
    kv_legacy = _make_kv_cache()
    kv_new    = kv_legacy.clone()

    seq_ids = [100 + i for i in range(B)]
    # Non-overlapping block ranges per seq (4 blocks apart so 64 decode
    # steps can't collide with a neighbor).
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
        for w, kv in ((w_legacy, kv_legacy), (w_new, kv_new)):
            w.write(k, v, kv, slots, seq_id=sid)

    # Resolve seq_id -> slot once (would-be pre-capture step).
    assert w_legacy._slot_map == w_new._slot_map, (
        "slot maps diverged during prefill — verifier setup bug"
    )
    slot_idx_t = torch.tensor(
        [w_new._slot_map[s] for s in seq_ids],
        dtype=torch.long, device=DEVICE,
    )

    # Decode loop.
    for step in range(n_decode_steps):
        k_step = torch.randn(B, H_KV, D, dtype=DTYPE_BF, device=DEVICE) * 0.5
        v_step = torch.randn(B, H_KV, D, dtype=DTYPE_BF, device=DEVICE) * 0.5
        slot_mapping = torch.tensor(
            [seq_base_blocks[i] * BS + prefill_len + step for i in range(B)],
            dtype=torch.long, device=DEVICE,
        )
        # Legacy: per-seq Python loop.
        for i, sid in enumerate(seq_ids):
            w_legacy.write(
                k_step[i:i+1], v_step[i:i+1], kv_legacy,
                slot_mapping[i:i+1], seq_id=sid,
            )
        # New: batched call.
        w_new.write_decode_batched(
            key=k_step, value=v_step, kv_cache=kv_new,
            slot_mapping=slot_mapping, slot_idx_t=slot_idx_t,
        )

    return [
        ("kv_cache",         torch.equal(kv_legacy, kv_new)),
        ("k_scale_ext",      torch.equal(w_legacy.k_scale_ext, w_new.k_scale_ext)),
        ("k_xmin_ext",       torch.equal(w_legacy.k_xmin_ext,  w_new.k_xmin_ext)),
        ("k_protect_ext",    torch.equal(w_legacy.k_protect_ext, w_new.k_protect_ext)),
        ("v_scale_ext",      torch.equal(w_legacy.v_scale_ext, w_new.v_scale_ext)),
        ("v_xmin_ext",       torch.equal(w_legacy.v_xmin_ext,  w_new.v_xmin_ext)),
        ("bf16_k_backing",   torch.equal(w_legacy._bf16_k_backing_pool, w_new._bf16_k_backing_pool)),
        ("bf16_v_backing",   torch.equal(w_legacy._bf16_v_backing_pool, w_new._bf16_v_backing_pool)),
        ("k_stage_pool",     torch.equal(w_legacy._k_stage_pool, w_new._k_stage_pool)),
    ]


def main() -> int:
    print("=" * 78)
    print("Phase 6 v2 Option B pre-flight (B-pre-5 / Phase 6B.1)")
    print("write_decode_batched bit-equivalence verify")
    print("=" * 78)
    print(f"device={DEVICE}  torch={torch.__version__}")
    print()

    mask_path = _make_protect_artifact()
    overall_ok = True
    try:
        cells: list[tuple[str, int, int, int]] = []
        # Mode A — aligned prefill (no handoff at decode start).
        for B in (1, 2, 4, 8):
            for steps in (1, 32, 64):
                cells.append((f"A_B{B}_steps{steps}", B, BS, steps))
        # Mode B — near-boundary prefill (first decode token closes partial block).
        for B in (1, 2, 4, 8):
            for steps in (1, 32, 64):
                cells.append((f"B_B{B}_steps{steps}", B, BS - 1, steps))
        # Mode C — mid-block prefill (decode continues partial block first).
        for B in (1, 2, 4, 8):
            for steps in (1, 32, 64):
                cells.append((f"C_B{B}_steps{steps}", B, BS // 2, steps))

        n_pass = 0
        for label, B, prefill_len, n_decode_steps in cells:
            results = _run_cell(B, prefill_len, n_decode_steps, seed=hash(label) & 0xFFFFFFFF)
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
        print("Phase 6B.1 write equivalence: GREEN")
        print("  write_decode_batched produces byte-identical KV state to the")
        print("  legacy per-seq writer.write loop across B in {1,2,4,8} and")
        print("  Modes A/B/C at decode step counts {1, 32, 64}.")
        return 0
    print("Phase 6B.1 write equivalence: FAIL")
    print("  At least one cell diverged. Diagnose the unconditional re-")
    print("  quantize or pool-counter update path before proceeding.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
