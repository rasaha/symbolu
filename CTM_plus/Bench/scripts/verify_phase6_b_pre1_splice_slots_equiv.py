"""Phase 6 v2 Option B pre-flight (B-pre-1) — slot-based splice and
bf16_backing bit-equivalence verify.

Two assertions:

  1. `_splice_k_partial_tail_batched_vectorized` called via the
     preflight (slot-tensor) convention produces tensor-equal view
     mutations vs the legacy (seq_states_list / active_mask) convention.

  2. `writer.get_bf16_backing_batched_by_slots(slot_idx_t, S)` produces
     tensor-equal (bf16_k, bf16_v) vs the legacy
     `writer.get_bf16_backing_batched(seq_ids, S)`.

Both call paths read from the SAME pool tensors so they should be
trivially bit-identical — this verify just confirms there's no slot/
seq_id mismatch + that the pool indexing math matches what the legacy
torch.stack path produced.

Run:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase6_b_pre1_splice_slots_equiv.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback

import torch

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_kvp_root  = os.path.join(_repo_root, "KVPolicy")
if _kvp_root not in sys.path:
    sys.path.insert(0, _kvp_root)

from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
from kv_policy.phase5b_backend_install import (
    _splice_k_partial_tail_batched_vectorized,
)


NUM_LAYERS = 28
H_KV       = 4
D          = 128
BS         = 32
V_GROUP    = 32
N_PROTECT  = 5
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE_BF   = torch.bfloat16


def _make_protect_artifact() -> str:
    mask = torch.zeros((H_KV, D), dtype=torch.int8)
    mask[:, :N_PROTECT] = 1
    full = mask.unsqueeze(0).expand(NUM_LAYERS, -1, -1).contiguous()
    fd, path = tempfile.mkstemp(suffix=".pt")
    os.close(fd)
    torch.save(full, path)
    os.environ["PROTECT_MASK_PATH"] = path
    return path


def _build_writer(NB: int):
    writer = PagedKVWriter(
        layer_idx=0, v_group_size=V_GROUP, sidecar_dtype=DTYPE_BF,
    )
    kv_cache = torch.zeros((2, NB, BS, H_KV, D), dtype=torch.uint8, device=DEVICE)

    full_blocks_per_seq = [3, 2, 4, 1]
    tails = [1, 7, BS - 1, BS // 2]
    seqlens = [full_blocks_per_seq[i] * BS + tails[i] for i in range(4)]

    block_ids_per_seq = []
    next_bid = 1
    for i, sl in enumerate(seqlens):
        n_blocks = (sl + BS - 1) // BS
        block_ids_per_seq.append(list(range(next_bid, next_bid + n_blocks)))
        next_bid += n_blocks

    seq_ids = list(range(100, 104))

    torch.manual_seed(0xC0FFEE)
    for i in range(4):
        sl = seqlens[i]
        bids = block_ids_per_seq[i]
        slots = []
        n_full = full_blocks_per_seq[i]
        for b_idx in range(n_full):
            base = bids[b_idx] * BS
            slots.extend(range(base, base + BS))
        base = bids[-1] * BS
        slots.extend(range(base, base + tails[i]))
        slot_mapping = torch.tensor(slots, dtype=torch.long, device=DEVICE)

        key   = torch.randn((sl, H_KV, D), dtype=DTYPE_BF, device=DEVICE) * 0.5
        value = torch.randn((sl, H_KV, D), dtype=DTYPE_BF, device=DEVICE) * 0.5
        writer.write(key, value, kv_cache, slot_mapping, seq_id=seq_ids[i])

    n_blocks_per_seq = [(s + BS - 1) // BS for s in seqlens]
    return writer, kv_cache, seq_ids, n_blocks_per_seq, seqlens, block_ids_per_seq


def _build_batched_view(writer, kv_cache, block_ids_per_seq, n_blocks_per_seq):
    B = len(block_ids_per_seq)
    n_blocks_max = max(n_blocks_per_seq)
    block_ids_batched = torch.zeros((B, n_blocks_max), dtype=torch.long, device=DEVICE)
    for i in range(B):
        n_i = n_blocks_per_seq[i]
        block_ids_batched[i, :n_i] = torch.tensor(
            block_ids_per_seq[i], dtype=torch.long, device=DEVICE,
        )
    return writer.get_packed_view_batched(block_ids_batched, kv_cache)


def _clone_view_k(view):
    return {
        "k_int4":  view["k_int4"].clone(),
        "k_scale": view["k_scale"].clone(),
        "k_xmin":  view["k_xmin"].clone(),
    }


def main() -> int:
    if DEVICE != "cuda":
        print("FAIL: cuda required."); return 1
    mask_path = _make_protect_artifact()
    try:
        print("Setup: writer + 4 seqs (with partial tails)...")
        NB = 32
        writer, kv_cache, seq_ids, n_blocks_per_seq, seqlens, block_ids_per_seq = \
            _build_writer(NB)
        BS_w = writer.BS
        B = len(seq_ids)
        print(f"  seqlens={seqlens} tails={[s%BS_w for s in seqlens]} "
              f"n_blocks={n_blocks_per_seq}")
        print(f"  slot_map (B-pre-1): {writer._slot_map}")
        print(f"  free_slots remaining: {writer._free_slots}")

        # Build TWO independent batched views (legacy vs preflight).
        view = _build_batched_view(writer, kv_cache, block_ids_per_seq, n_blocks_per_seq)
        view_legacy_k   = _clone_view_k(view)
        view_preflight_k = _clone_view_k(view)
        view_legacy   = {**view, **view_legacy_k}
        view_preflight = {**view, **view_preflight_k}

        last_block_indices = [n_blocks_per_seq[i] - 1 for i in range(B)]
        active_mask = [seqlens[i] % BS_w != 0 for i in range(B)]
        seq_states_list = [writer.get_seq_state(seq_ids[i]) for i in range(B)]

        print()
        print("Path A: legacy splice (seq_states_list + active_mask)...")
        _splice_k_partial_tail_batched_vectorized(
            view_legacy, writer,
            seq_states_list=seq_states_list,
            last_block_indices=last_block_indices,
            active_mask=active_mask,
        )

        print("Path B: preflight splice (slot tensors)...")
        active_pos_b = [i for i in range(B) if active_mask[i]]
        active_batch_idx_t = torch.tensor(active_pos_b, dtype=torch.long, device=DEVICE)
        active_last_block_t = torch.tensor(
            [last_block_indices[i] for i in active_pos_b],
            dtype=torch.long, device=DEVICE,
        )
        slot_idx_list = writer.slot_indices_for(seq_ids)
        slot_idx_t = torch.tensor(slot_idx_list, dtype=torch.long, device=DEVICE)
        active_slot_idx_t = slot_idx_t[active_batch_idx_t]
        _splice_k_partial_tail_batched_vectorized(
            view_preflight, writer,
            active_slot_idx_t=active_slot_idx_t,
            active_batch_idx_t=active_batch_idx_t,
            active_last_block_t=active_last_block_t,
        )

        print()
        print("Assert splice paths produce bit-identical mutations...")
        ok = True
        for name in ("k_int4", "k_scale", "k_xmin"):
            a = view_legacy[name]
            b = view_preflight[name]
            if not torch.equal(a, b):
                diff = (a.float() - b.float()).abs()
                print(f"  {name}: MISMATCH "
                      f"(max_abs_diff={diff.max().item():.6g}, "
                      f"n_diff={(diff != 0).sum().item()})")
                ok = False
            else:
                print(f"  {name}: identical")

        print()
        print("Assert bf16_backing slot-gather matches legacy seq_id gather...")
        S_padded = max(n_blocks_per_seq) * BS_w
        bf16_k_legacy, bf16_v_legacy = writer.get_bf16_backing_batched(
            seq_ids, S_padded,
        )
        bf16_k_preflight, bf16_v_preflight = \
            writer.get_bf16_backing_batched_by_slots(slot_idx_t, S_padded)

        if not torch.equal(bf16_k_legacy, bf16_k_preflight):
            print(f"  bf16_k: MISMATCH"); ok = False
        else:
            print(f"  bf16_k: identical")
        if not torch.equal(bf16_v_legacy, bf16_v_preflight):
            print(f"  bf16_v: MISMATCH"); ok = False
        else:
            print(f"  bf16_v: identical")

        # Smoke: evict + re-allocate exercises the slot recycling path.
        print()
        print("Smoke: evict seq, free slot should return to pool...")
        evicted_slot = writer._slot_map[seq_ids[0]]
        writer.evict_sequence(seq_ids[0])
        if evicted_slot not in writer._free_slots:
            print(f"  FAIL: evicted slot {evicted_slot} not in free_slots "
                  f"{writer._free_slots}"); ok = False
        else:
            print(f"  evicted slot {evicted_slot} back in free_slots OK")

        print()
        if ok:
            print("PASS: slot-based splice + bf16_backing bit-equivalent to "
                  "legacy dict-based paths; slot recycling works.")
            return 0
        else:
            print("FAIL: see mismatches above.")
            return 1
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        try:
            os.remove(mask_path)
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
