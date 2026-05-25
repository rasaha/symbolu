"""Phase 6 v2 Option D step 1 — vectorized splice bit-equivalence verify.

Asserts that `_splice_k_partial_tail_batched_vectorized` (the new
fused-across-B implementation) produces tensor-equal output to a loop
of `_splice_k_partial_tail_batched_row` calls (the prior per-seq path).

Setup:
  - Allocate a PagedKVWriter and feed it B=4 sequences of writes, each
    leaving a partial K tail (so each seq has a non-zero last-block
    splice to apply).
  - Call get_packed_view_batched ONCE and clone the K-side tensors
    (k_int4, k_scale, k_xmin) into two copies, view_a and view_b.
  - Run per-row splice on view_a (the reference path) and vectorized
    splice on view_b (the new path).
  - Assert torch.equal on each (i, last_block_i) slot of all three K
    tensors.

PASS criterion: every byte of the spliced slots matches between the
two paths. This is the gate for shipping the Option D step 1 change —
the wire-level cache state seen by the kernel must be bit-identical.

Run on the pod:
  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/verify_phase6_d_step1_splice_equiv.py
"""
from __future__ import annotations

import copy
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
    _splice_k_partial_tail_batched_row,
    _splice_k_partial_tail_batched_vectorized,
)


# Match Qwen2.5-7B kv geometry.
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


def _build_writer(NB: int) -> tuple:
    """Build a writer + paged kv_cache + a few B sequences with partial tails.

    Returns (writer, kv_cache, seq_ids, n_blocks_per_seq, seqlens).
    """
    # n_protect is derived from the protect_mask at _lazy_alloc time
    # (loaded from $PROTECT_MASK_PATH which the test-fixture sets).
    writer = PagedKVWriter(
        layer_idx=0, v_group_size=V_GROUP, sidecar_dtype=DTYPE_BF,
    )
    kv_cache = torch.zeros((2, NB, BS, H_KV, D), dtype=torch.uint8, device=DEVICE)

    # B=4 seqs with different partial-tail lengths covering edge cases.
    # Each seq gets seqlen = full_blocks*BS + tail where tail in {1, 7, BS-1, BS//2}.
    full_blocks_per_seq = [3, 2, 4, 1]      # number of FULL blocks per seq
    tails = [1, 7, BS - 1, BS // 2]         # partial tail lengths
    seqlens = [full_blocks_per_seq[i] * BS + tails[i] for i in range(4)]

    # Allocate block ids — disjoint per seq for clarity.
    block_ids_per_seq = []
    next_bid = 1                            # leave block 0 as padding sentinel
    for i, sl in enumerate(seqlens):
        n_blocks = (sl + BS - 1) // BS
        block_ids_per_seq.append(list(range(next_bid, next_bid + n_blocks)))
        next_bid += n_blocks

    seq_ids = list(range(100, 104))         # arbitrary seq_ids

    torch.manual_seed(0xC0FFEE)
    for i in range(4):
        sl = seqlens[i]
        bids = block_ids_per_seq[i]
        # Build slot_mapping for this seq's writes: BS tokens into each
        # block in order, last block gets only `tail` tokens.
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
    """Mirror what _read_decode_packed_batched does: pad block_ids and
    call get_packed_view_batched. Returns the view dict."""
    B = len(block_ids_per_seq)
    n_blocks_max = max(n_blocks_per_seq)
    block_ids_batched = torch.zeros((B, n_blocks_max), dtype=torch.long, device=DEVICE)
    for i in range(B):
        n_i = n_blocks_per_seq[i]
        block_ids_batched[i, :n_i] = torch.tensor(
            block_ids_per_seq[i], dtype=torch.long, device=DEVICE,
        )
    return writer.get_packed_view_batched(block_ids_batched, kv_cache)


def _clone_view_k(view) -> dict:
    """Deep-clone the K-side tensors that splice mutates. Others can be
    shared (we don't touch them)."""
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
        print("Setup: building writer + 4 seqs with partial tails...")
        NB = 32                              # plenty of blocks for our 4 seqs
        writer, kv_cache, seq_ids, n_blocks_per_seq, seqlens, block_ids_per_seq = \
            _build_writer(NB)
        BS_w = writer.BS
        print(f"  seqlens={seqlens}  tails={[s % BS_w for s in seqlens]}  "
              f"n_blocks_per_seq={n_blocks_per_seq}")

        print("Build batched view via get_packed_view_batched...")
        view = _build_batched_view(writer, kv_cache, block_ids_per_seq, n_blocks_per_seq)

        # Snapshot the K-side tensors twice (independent copies).
        view_a_k = _clone_view_k(view)       # reference path
        view_b_k = _clone_view_k(view)       # vectorized path

        # Build per-path views that point at their own clones for K, and
        # share the rest (splice doesn't read other entries).
        view_a = {**view, **view_a_k}
        view_b = {**view, **view_b_k}

        B = len(seq_ids)
        last_block_indices = [n_blocks_per_seq[i] - 1 for i in range(B)]
        active_mask = [seqlens[i] % BS_w != 0 for i in range(B)]
        seq_states_list = [writer.get_seq_state(seq_ids[i]) for i in range(B)]

        print(f"  active_mask={active_mask} (all True expected — every "
              f"seq has a partial tail)")

        print("Reference path: per-row splice loop...")
        for i in range(B):
            if not active_mask[i]:
                continue
            _splice_k_partial_tail_batched_row(
                view_a, writer,
                batch_idx=i, last_block_idx=last_block_indices[i],
                state=seq_states_list[i],
            )

        print("Vectorized path: _splice_k_partial_tail_batched_vectorized...")
        _splice_k_partial_tail_batched_vectorized(
            view_b, writer,
            seq_states_list=seq_states_list,
            last_block_indices=last_block_indices,
            active_mask=active_mask,
        )

        print()
        print("Asserting bit-equivalence on the spliced slots...")
        ok = True
        for i in range(B):
            if not active_mask[i]:
                continue
            lb = last_block_indices[i]
            bstart, bend = lb * BS_w, (lb + 1) * BS_w

            # k_int4: (B, S, H, half_D). Compare slice [i, bstart:bend, ...].
            a_int4 = view_a["k_int4"][i, bstart:bend]
            b_int4 = view_b["k_int4"][i, bstart:bend]
            if not torch.equal(a_int4, b_int4):
                diff = (a_int4.int() - b_int4.int()).abs()
                print(f"  seq{i}: k_int4 MISMATCH "
                      f"(max_abs_diff={diff.max().item()}, "
                      f"n_diff={(diff != 0).sum().item()})")
                ok = False
            # k_scale: (B, n_blocks_max, H, D). Compare slice [i, lb, ...].
            a_sc = view_a["k_scale"][i, lb]
            b_sc = view_b["k_scale"][i, lb]
            if not torch.equal(a_sc, b_sc):
                diff = (a_sc.float() - b_sc.float()).abs()
                print(f"  seq{i}: k_scale MISMATCH "
                      f"(max_abs_diff={diff.max().item():.6g})")
                ok = False
            # k_xmin: same shape as k_scale.
            a_xm = view_a["k_xmin"][i, lb]
            b_xm = view_b["k_xmin"][i, lb]
            if not torch.equal(a_xm, b_xm):
                diff = (a_xm.float() - b_xm.float()).abs()
                print(f"  seq{i}: k_xmin MISMATCH "
                      f"(max_abs_diff={diff.max().item():.6g})")
                ok = False

        # Also check the UNSPLICED slots weren't accidentally touched.
        print("Asserting unspliced slots are untouched...")
        for i in range(B):
            n_b = n_blocks_per_seq[i]
            for b_idx in range(n_b):
                if active_mask[i] and b_idx == last_block_indices[i]:
                    continue            # this is the spliced slot
                bstart, bend = b_idx * BS_w, (b_idx + 1) * BS_w
                if not torch.equal(view_a["k_int4"][i, bstart:bend],
                                   view_b["k_int4"][i, bstart:bend]):
                    print(f"  seq{i} block{b_idx}: k_int4 leaked write")
                    ok = False

        print()
        if ok:
            print("PASS: vectorized splice is bit-equivalent to per-row splice "
                  "across all 4 seqs (all partial-tail edge cases).")
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
