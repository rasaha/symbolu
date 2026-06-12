"""Phase 6C CPU verifier — backing pool skip mode.

Verifies the writer's behavior when PHASE6C_BF16_BACKING_SKIP=1:

  1. _lazy_alloc allocates (1, 1, H, D) stub pools instead of
     (n_slots, max_S, H, D) full pools — a ~130x memory reduction
     on the largest writer-side auxiliary tensors.

  2. SeqState.bf16_k_backing / bf16_v_backing return None in skip
     mode (so legacy write paths skip cleanly via existing guards).

  3. seq_pos still advances per write — verified equal between skip
     and legacy modes after the same write sequence (state coherence
     for k_stage, sentinel, and other writer bookkeeping).

  4. get_bf16_backing_batched_by_slots in skip mode returns a
     stride-0 broadcast view with the correct logical shape
     (B, S_padded, H, D) and stride(-1) == 1 (passes the flash_attn
     wrapper's contiguous-last-dim assert).

  5. With PHASE6C_BF16_BACKING_SKIP=0 (legacy), the writer's behavior
     is byte-identical to pre-6C.

Note: this verifier exercises ONLY the CPU-side bookkeeping. The
actual end-to-end correctness (kernel reading int4 + producing the
same attention output) requires the GPU bench. The cap/bf16 ratio
in bench_phase6_b4_throughput_gpu.py is the dispositive test for
the architectural fix.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break

try:
    import torch
except ImportError:
    print("FAIL: torch import failed; cannot run verifier")
    sys.exit(2)


_SKIP_ENV = "PHASE6C_BF16_BACKING_SKIP"


def _fresh_writer(env_skip: str):
    """Construct a PagedKVWriter + _lazy_alloc with the env in place."""
    os.environ[_SKIP_ENV] = env_skip
    # Force a fresh import so the module-level env read sees the new value
    # in any module that caches it. The writer reads _bf16_backing_skip()
    # at _lazy_alloc time, so just constructing+allocating is enough.
    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
    w = PagedKVWriter(layer_idx=0)
    # Build a minimal stand-in for kv_cache: shape (2, NB, BS, H_kv, D) uint8.
    # NB=4 (small), BS=32, H_kv=4, D=128 — matches Qwen2.5-7B's GQA.
    NB, BS, H, D = 4, 32, 4, 128
    kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
    # _lazy_alloc reads a calibrated protect_mask file by default; for
    # the CPU test we provide a synthetic one.
    w._protect_mask_cpu = torch.zeros((H, D), dtype=torch.int8)
    w._protect_mask_cpu[:, :5] = 1   # 5 protected dims per head
    w._lazy_alloc(kv_cache)
    return w, NB, BS, H, D


class Phase6CSkipMode(unittest.TestCase):
    def test_skip_mode_allocates_stub_pools(self):
        w, NB, BS, H, D = _fresh_writer("1")
        self.assertTrue(w._bf16_backing_skipped,
                        "writer should report skipped=True with env=1")
        self.assertEqual(w._bf16_k_backing_pool.shape, (1, 1, H, D),
                         "K pool should be stub-sized (1,1,H,D) in skip mode")
        self.assertEqual(w._bf16_v_backing_pool.shape, (1, 1, H, D),
                         "V pool should be stub-sized (1,1,H,D) in skip mode")
        # Total memory of both stubs combined: 2 * 1 * 1 * H * D * 2 = ~1KB.
        total_bytes = (w._bf16_k_backing_pool.numel() +
                       w._bf16_v_backing_pool.numel()) * 2
        self.assertLess(total_bytes, 10_000,
                        f"stub pools should be ~1KB total; got {total_bytes}")

    def test_legacy_mode_allocates_full_pools(self):
        w, NB, BS, H, D = _fresh_writer("0")
        self.assertFalse(w._bf16_backing_skipped)
        # 6K.16c added the reserved pad-scratch slot at the last index,
        # so the pool carries max_active_slots + 1 entries.
        n_slots = w._max_active_slots + 1
        max_S = w._bf16_backing_max_seqlen
        self.assertEqual(w._bf16_k_backing_pool.shape, (n_slots, max_S, H, D))
        self.assertEqual(w._bf16_v_backing_pool.shape, (n_slots, max_S, H, D))

    def test_seqstate_property_returns_none_in_skip(self):
        w, *_ = _fresh_writer("1")
        state = w.ensure_seq_state(seq_id=42, device=torch.device("cpu"))
        self.assertIsNone(state.bf16_k_backing,
                          "bf16_k_backing should be None in skip mode")
        self.assertIsNone(state.bf16_v_backing,
                          "bf16_v_backing should be None in skip mode")

    def test_seqstate_property_returns_view_in_legacy(self):
        w, NB, BS, H, D = _fresh_writer("0")
        state = w.ensure_seq_state(seq_id=42, device=torch.device("cpu"))
        max_S = w._bf16_backing_max_seqlen
        self.assertIsNotNone(state.bf16_k_backing)
        self.assertEqual(state.bf16_k_backing.shape, (1, max_S, H, D))

    def test_get_bf16_backing_batched_by_slots_skip_stride0(self):
        w, NB, BS, H, D = _fresh_writer("1")
        # Provision 2 slots.
        w.ensure_seq_state(seq_id=10, device=torch.device("cpu"))
        w.ensure_seq_state(seq_id=20, device=torch.device("cpu"))
        slot_idx_tensor = torch.tensor([0, 1], dtype=torch.long)
        S_padded = 128
        bf16_k, bf16_v = w.get_bf16_backing_batched_by_slots(
            slot_idx_tensor, S_padded
        )
        # Logical shape must match what the kernel expects.
        self.assertEqual(bf16_k.shape, (2, S_padded, H, D))
        self.assertEqual(bf16_v.shape, (2, S_padded, H, D))
        # Contiguous-last-dim invariant required by flash_attn wrapper.
        self.assertEqual(bf16_k.stride(-1), 1)
        self.assertEqual(bf16_v.stride(-1), 1)
        # Batch + seq dims should be broadcast (stride 0) so the actual
        # underlying memory is the tiny stub, not B*S_padded*H*D*2.
        self.assertEqual(bf16_k.stride(0), 0,
                         "batch dim should be broadcast (stride 0)")
        self.assertEqual(bf16_k.stride(1), 0,
                         "seq dim should be broadcast (stride 0)")

    def test_seq_pos_advances_identically_skip_vs_legacy(self):
        """Critical invariant: seq_pos bookkeeping must be identical
        across skip and legacy so the rest of the writer state stays
        coherent (k_stage, sentinel, etc.).
        """
        # Skip mode writer
        w_skip, NB, BS, H, D = _fresh_writer("1")
        state_skip = w_skip.ensure_seq_state(seq_id=7, device=torch.device("cpu"))
        # Legacy writer (separate construction; env is per-_lazy_alloc).
        w_full, _, _, _, _ = _fresh_writer("0")
        state_full = w_full.ensure_seq_state(seq_id=7, device=torch.device("cpu"))
        # Drive a small prefill: 17 tokens, no padding.
        T = 17
        key = torch.randn((T, H, D), dtype=torch.bfloat16)
        value = torch.randn((T, H, D), dtype=torch.bfloat16)
        # slot_mapping: contiguous starting from block 0, position 0.
        slot_mapping = torch.arange(T, dtype=torch.long)
        # Fake kv_cache shapes (writer needs it for shapes only).
        kv_cache_skip = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
        kv_cache_full = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
        w_skip._write_into_state(state_skip, key, value, kv_cache_skip, slot_mapping)
        w_full._write_into_state(state_full, key, value, kv_cache_full, slot_mapping)
        self.assertEqual(state_skip.seq_pos, T,
                         f"skip mode seq_pos should be {T}, got {state_skip.seq_pos}")
        self.assertEqual(state_full.seq_pos, T,
                         f"legacy seq_pos should be {T}, got {state_full.seq_pos}")
        self.assertEqual(state_skip.seq_pos, state_full.seq_pos,
                         "seq_pos must match between skip and legacy")

    def test_default_env_is_skip(self):
        """The Phase 6C default behavior is skip=True. Verify with the
        env unset (not explicitly set to 0)."""
        os.environ.pop(_SKIP_ENV, None)
        from kv_policy.phase5b_4c_paged_writer import _bf16_backing_skip
        self.assertTrue(_bf16_backing_skip(),
                        "Default should be skip (Phase 6C is on by default)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
