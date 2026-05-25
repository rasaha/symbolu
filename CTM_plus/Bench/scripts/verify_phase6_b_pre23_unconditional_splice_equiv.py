"""Phase 6 v2 Option B pre-flight (B-pre-2 + B-pre-3 bundled) —
unconditional splice bit-equivalence verify.

Asserts that `_splice_k_partial_tail_batched_unconditional` produces
tensor-equal view mutations to the prior conditional path
(`_splice_k_partial_tail_batched_vectorized` preflight call) across
mixed active / inactive sequences.

Test fixture: B=4 sequences where SOME have a partial tail (active)
and OTHERS have a full last block (inactive). The unconditional path
must produce the same mutations on active slots AND must leave
inactive slots untouched (read-modify-write self-write under the
torch.where mask).

Setup:
  - 4 seqs with seqlens designed to mix active/inactive:
      seq A: 97  tokens (3*32 + 1)  → tail=1   → ACTIVE
      seq B: 64  tokens (2*32 + 0)  → tail=0   → INACTIVE (full block)
      seq C: 159 tokens (4*32 + 31) → tail=31  → ACTIVE
      seq D: 96  tokens (3*32 + 0)  → tail=0   → INACTIVE (full block)

Run:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase6_b_pre23_unconditional_splice_equiv.py
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
    _splice_k_partial_tail_batched_unconditional,
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

    # Mixed seqlens: 2 with tail (active), 2 without (inactive).
    full_blocks_per_seq = [3, 2, 4, 3]
    tails               = [1, 0, 31, 0]
    seqlens = [full_blocks_per_seq[i] * BS + tails[i] for i in range(4)]

    block_ids_per_seq = []
    next_bid = 1
    for sl in seqlens:
        n_blocks = (sl + BS - 1) // BS
        block_ids_per_seq.append(list(range(next_bid, next_bid + n_blocks)))
        next_bid += n_blocks

    seq_ids = list(range(200, 204))

    torch.manual_seed(0xC0FFEE)
    for i in range(4):
        sl = seqlens[i]
        bids = block_ids_per_seq[i]
        slots = []
        n_full = full_blocks_per_seq[i]
        for b_idx in range(n_full):
            base = bids[b_idx] * BS
            slots.extend(range(base, base + BS))
        # If tail > 0, write tail tokens to a partial block.
        if tails[i] > 0:
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
        print("Setup: writer + 4 seqs (mixed active/inactive)...")
        NB = 32
        writer, kv_cache, seq_ids, n_blocks_per_seq, seqlens, block_ids_per_seq = \
            _build_writer(NB)
        BS_w = writer.BS
        B = len(seq_ids)
        tails = [s % BS_w for s in seqlens]
        active_mask = [t != 0 for t in tails]
        print(f"  seqlens={seqlens}  tails={tails}  active_mask={active_mask}")
        print(f"  (expect: A True, B False, C True, D False)")

        # Build TWO independent batched views.
        view = _build_batched_view(writer, kv_cache, block_ids_per_seq, n_blocks_per_seq)
        view_legacy_k        = _clone_view_k(view)
        view_unconditional_k = _clone_view_k(view)
        view_legacy        = {**view, **view_legacy_k}
        view_unconditional = {**view, **view_unconditional_k}

        # Resolve slot indices.
        slot_idx_list = writer.slot_indices_for(seq_ids)
        slot_idx_t    = torch.tensor(slot_idx_list, dtype=torch.long, device=DEVICE)
        last_block_indices_t = torch.tensor(
            [n_blocks_per_seq[i] - 1 for i in range(B)],
            dtype=torch.long, device=DEVICE,
        )
        active_mask_t = torch.tensor(active_mask, dtype=torch.bool, device=DEVICE)
        batch_idx_t   = torch.arange(B, device=DEVICE, dtype=torch.long)

        # Snapshot the original last-block values for INACTIVE seqs so we
        # can later verify the unconditional path didn't corrupt them.
        inactive_idx = [i for i in range(B) if not active_mask[i]]
        orig_inactive_k_int4 = {}
        orig_inactive_k_scale = {}
        orig_inactive_k_xmin = {}
        n_blocks_max = max(n_blocks_per_seq)
        k_int4_blocked = view["k_int4"].view(-1, n_blocks_max, BS_w, H_KV, D // 2)
        for i in inactive_idx:
            lb = n_blocks_per_seq[i] - 1
            orig_inactive_k_int4[i]  = k_int4_blocked[i, lb].clone()
            orig_inactive_k_scale[i] = view["k_scale"][i, lb].clone()
            orig_inactive_k_xmin[i]  = view["k_xmin"][i, lb].clone()

        # ------------------------------------------------------------
        # Path A: legacy preflight splice (active-only, bool-indexing).
        # ------------------------------------------------------------
        print()
        print("Path A: preflight (active-only) splice...")
        active_pos_b = [i for i in range(B) if active_mask[i]]
        if active_pos_b:
            active_batch_idx_t_a = torch.tensor(active_pos_b, dtype=torch.long, device=DEVICE)
            active_last_block_t_a = torch.tensor(
                [n_blocks_per_seq[i] - 1 for i in active_pos_b],
                dtype=torch.long, device=DEVICE,
            )
            active_slot_idx_t_a = slot_idx_t[active_batch_idx_t_a]
            _splice_k_partial_tail_batched_vectorized(
                view_legacy, writer,
                active_slot_idx_t=active_slot_idx_t_a,
                active_batch_idx_t=active_batch_idx_t_a,
                active_last_block_t=active_last_block_t_a,
            )

        # ------------------------------------------------------------
        # Path B: unconditional splice (all B, mask-gated).
        # ------------------------------------------------------------
        print("Path B: unconditional splice...")
        _splice_k_partial_tail_batched_unconditional(
            view_unconditional, writer,
            slot_idx_t=slot_idx_t,
            batch_idx_t=batch_idx_t,
            last_block_indices_t=last_block_indices_t,
            active_mask_t=active_mask_t,
        )

        # ------------------------------------------------------------
        # Assertions
        # ------------------------------------------------------------
        print()
        print("Assert tensor-equal mutations across all view tensors...")
        ok = True
        for name in ("k_int4", "k_scale", "k_xmin"):
            a = view_legacy[name]
            b = view_unconditional[name]
            if not torch.equal(a, b):
                diff = (a.float() - b.float()).abs()
                # Show which (batch, block) positions differ.
                if name == "k_int4":
                    a_b = view_legacy[name].view(B, n_blocks_max, BS_w, H_KV, D // 2)
                    b_b = view_unconditional[name].view(B, n_blocks_max, BS_w, H_KV, D // 2)
                    for i in range(B):
                        for bk in range(n_blocks_max):
                            if not torch.equal(a_b[i, bk], b_b[i, bk]):
                                print(f"  {name}: differ at (seq{i}, block{bk})")
                print(f"  {name}: MISMATCH max_diff={diff.max().item():.6g}")
                ok = False
            else:
                print(f"  {name}: identical")

        # Spot-check: inactive seqs' last-block slots must match the
        # ORIGINAL pre-splice values (read-modify-write self-write).
        print()
        print("Assert inactive seqs' last-block slots are byte-preserved...")
        k_int4_blocked_b = view_unconditional["k_int4"].view(
            -1, n_blocks_max, BS_w, H_KV, D // 2,
        )
        for i in inactive_idx:
            lb = n_blocks_per_seq[i] - 1
            if not torch.equal(k_int4_blocked_b[i, lb], orig_inactive_k_int4[i]):
                print(f"  seq{i} INACTIVE: k_int4 was modified (unexpected!)")
                ok = False
            else:
                print(f"  seq{i} INACTIVE: k_int4 preserved OK")
            if not torch.equal(view_unconditional["k_scale"][i, lb],
                               orig_inactive_k_scale[i]):
                print(f"  seq{i} INACTIVE: k_scale was modified (unexpected!)")
                ok = False
            if not torch.equal(view_unconditional["k_xmin"][i, lb],
                               orig_inactive_k_xmin[i]):
                print(f"  seq{i} INACTIVE: k_xmin was modified (unexpected!)")
                ok = False

        print()
        if ok:
            print("PASS: unconditional splice is bit-equivalent to "
                  "active-only legacy splice across all 4 seqs (mixed "
                  "active/inactive), and inactive slots are preserved.")
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
