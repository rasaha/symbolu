"""Phase 6K.16c — CPU tests for STABLE real-sequence identity.

The robust APC fix: real vLLM seq ids (stable, unique, never recycled
mid-flight) stashed by the 6B.2 hook, consumed with a count-checked
fallback to block-local.

  1. extract_real_seq_ids: pulls ids in attention-row order from
     sampling_metadata.seq_groups (primary) and request_ids_to_seq_ids
     (fallback); None when neither usable.

  2. stashed_real_seq_ids: returns the stash ONLY when its count matches
     the attention rows; mismatch -> None (safe fallback, no corruption).

  3. resolve_decode_seq_ids: stash wins when valid; else block-local /
     legacy.

  4. _derive_write_partitions consumes the prefill + decode stash.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

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
    _HAVE_TORCH = True
except ImportError:
    _HAVE_TORCH = False

if _HAVE_TORCH:
    from kv_policy.phase5b_4c_paged_writer import (
        stashed_real_seq_ids,
        resolve_decode_seq_ids,
        _REAL_SEQ_IDS_ATTR,
        _REAL_SEQ_IDS_PREFILL_ATTR,
    )
    from kv_policy.phase6b2_precapture_hook import extract_real_seq_ids
    from kv_policy.phase5b_backend_install import _derive_write_partitions

BS = 32


@unittest.skipUnless(_HAVE_TORCH, "torch required")
class TestExtract(unittest.TestCase):

    def test_sampling_metadata_seq_groups(self):
        mi = SimpleNamespace(sampling_metadata=SimpleNamespace(seq_groups=[
            SimpleNamespace(seq_ids=[42]),
            SimpleNamespace(seq_ids=[7]),
            SimpleNamespace(seq_ids=[100]),
        ]))
        self.assertEqual(extract_real_seq_ids(mi), [42, 7, 100])

    def test_parallel_sampling_flattened(self):
        # n>1 group contributes multiple seq_ids in order.
        mi = SimpleNamespace(sampling_metadata=SimpleNamespace(seq_groups=[
            SimpleNamespace(seq_ids=[5, 6]),
            SimpleNamespace(seq_ids=[9]),
        ]))
        self.assertEqual(extract_real_seq_ids(mi), [5, 6, 9])

    def test_request_ids_fallback(self):
        mi = SimpleNamespace(sampling_metadata=None,
                             request_ids_to_seq_ids={"r0": [3], "r1": [8, 9]})
        self.assertEqual(extract_real_seq_ids(mi), [3, 8, 9])

    def test_none_when_unavailable(self):
        self.assertIsNone(extract_real_seq_ids(SimpleNamespace()))
        self.assertIsNone(extract_real_seq_ids(
            SimpleNamespace(sampling_metadata=SimpleNamespace(seq_groups=[]))))


@unittest.skipUnless(_HAVE_TORCH, "torch required")
class TestStashFallback(unittest.TestCase):

    def test_count_match_returns_stash(self):
        md = SimpleNamespace()
        setattr(md, _REAL_SEQ_IDS_ATTR, [11, 22, 33])
        self.assertEqual(stashed_real_seq_ids(md, 3), [11, 22, 33])

    def test_count_mismatch_falls_back(self):
        md = SimpleNamespace()
        setattr(md, _REAL_SEQ_IDS_ATTR, [11, 22])
        self.assertIsNone(stashed_real_seq_ids(md, 3))   # 2 != 3 -> None

    def test_absent_stash_none(self):
        self.assertIsNone(stashed_real_seq_ids(SimpleNamespace(), 2))
        self.assertIsNone(stashed_real_seq_ids(None, 2))

    def test_prefill_attr_separate(self):
        md = SimpleNamespace()
        setattr(md, _REAL_SEQ_IDS_PREFILL_ATTR, [77])
        self.assertEqual(stashed_real_seq_ids(md, 1, prefill=True), [77])
        self.assertIsNone(stashed_real_seq_ids(md, 1, prefill=False))

    def test_resolve_decode_prefers_stash(self):
        bt = torch.tensor([[7, 8, 100], [7, 8, 101]], dtype=torch.int32)
        sl = torch.tensor([70, 90], dtype=torch.int32)
        md = SimpleNamespace()
        setattr(md, _REAL_SEQ_IDS_ATTR, [555, 666])     # real ids win
        self.assertEqual(
            resolve_decode_seq_ids(md, bt, sl, BS, block_local=True),
            [555, 666])

    def test_resolve_decode_falls_back_to_block_local(self):
        bt = torch.tensor([[7, 8, 100], [7, 8, 101]], dtype=torch.int32)
        sl = torch.tensor([70, 90], dtype=torch.int32)
        # No stash -> block-local: (70-1)//32=2 -> 100; (90-1)//32=2 -> 101.
        self.assertEqual(
            resolve_decode_seq_ids(SimpleNamespace(), bt, sl, BS, block_local=True),
            [100, 101])

    def test_cudagraph_padding_real_first_sentinel_tail(self):
        # 2 real seqs, decode batch padded to 4 rows (graph capture size).
        # Rows 0-1 real (stash); rows 2-3 padding -> PAD SENTINELS from a
        # negative namespace (contract B2: can never collide with a rid).
        from kv_policy.phase5b_4c_paged_writer import (
            is_pad_seq_id, _PAD_SEQ_ID_BASE,
        )
        bt = torch.tensor([[7, 8, 100], [7, 8, 101],
                          [0, 0, 0], [0, 0, 0]], dtype=torch.int32)
        sl = torch.tensor([70, 90, 1, 1], dtype=torch.int32)
        md = SimpleNamespace()
        setattr(md, _REAL_SEQ_IDS_ATTR, [555, 666])
        ids = resolve_decode_seq_ids(md, bt, sl, BS, block_local=True)
        self.assertEqual(ids[:2], [555, 666])
        self.assertTrue(all(is_pad_seq_id(s) for s in ids[2:]))
        self.assertEqual(len(set(ids)), 4)    # I3 incl. pads

    def test_apc_refusal_when_stash_absent(self):
        # Contract C-ID: under APC, no stash -> loud refusal.
        from kv_policy.phase5b_4c_paged_writer import set_apc_active
        bt = torch.tensor([[7, 8, 100]], dtype=torch.int32)
        sl = torch.tensor([70], dtype=torch.int32)
        set_apc_active(True)
        try:
            with self.assertRaises(RuntimeError) as cm:
                resolve_decode_seq_ids(SimpleNamespace(), bt, sl, BS,
                                       block_local=True)
            self.assertIn("refusing", str(cm.exception))
        finally:
            set_apc_active(False)
        # APC off: block-local fallback intact (legacy unchanged).
        self.assertEqual(
            resolve_decode_seq_ids(SimpleNamespace(), bt, sl, BS,
                                   block_local=True),
            [100])

    def test_pad_never_creates_seqstate(self):
        from kv_policy.phase5b_4c_paged_writer import (
            PagedKVWriter, _PAD_SEQ_ID_BASE,
        )
        w = PagedKVWriter.__new__(PagedKVWriter)   # no alloc needed
        with self.assertRaises(RuntimeError):
            PagedKVWriter.ensure_seq_state(w, _PAD_SEQ_ID_BASE - 1, None)

    def test_stash_longer_than_rows_full_fallback(self):
        bt = torch.tensor([[7, 8, 100], [7, 8, 101]], dtype=torch.int32)
        sl = torch.tensor([70, 90], dtype=torch.int32)
        md = SimpleNamespace()
        setattr(md, _REAL_SEQ_IDS_ATTR, [1, 2, 3])    # 3 > 2 rows -> fallback
        self.assertEqual(
            resolve_decode_seq_ids(md, bt, sl, BS, block_local=True),
            [100, 101])


@unittest.skipUnless(_HAVE_TORCH, "torch required")
class TestPartitionsConsumeStash(unittest.TestCase):

    def _writer(self):
        return SimpleNamespace(_bf16_backing_skipped=True)

    def test_decode_partitions_use_real_stash(self):
        md = SimpleNamespace(
            decode_metadata=SimpleNamespace(
                block_tables=torch.tensor([[7, 8, 100], [7, 8, 101]],
                                          dtype=torch.int32),
                seq_lens_tensor=torch.tensor([70, 90], dtype=torch.int32)),
            prefill_metadata=None)
        setattr(md, _REAL_SEQ_IDS_ATTR, [555, 666])
        parts = _derive_write_partitions(md, torch.tensor([0, 0]), BS,
                                         writer=self._writer())
        self.assertEqual([p[0] for p in parts], [555, 666])

    def test_prefill_partitions_use_real_stash(self):
        qsl = torch.tensor([0, 2, 5], dtype=torch.int32)
        md = SimpleNamespace(
            decode_metadata=None,
            prefill_metadata=SimpleNamespace(query_start_loc=qsl))
        setattr(md, _REAL_SEQ_IDS_PREFILL_ATTR, [555, 666])
        sm = torch.tensor([100 * BS, 100 * BS + 1,
                          102 * BS, 102 * BS + 1, 102 * BS + 2], dtype=torch.long)
        parts = _derive_write_partitions(md, sm, BS, writer=self._writer())
        self.assertEqual([p[0] for p in parts], [555, 666])
        self.assertEqual([p[1] for p in parts], [slice(0, 2), slice(2, 5)])

    def test_prefill_count_mismatch_falls_back(self):
        qsl = torch.tensor([0, 2, 5], dtype=torch.int32)
        md = SimpleNamespace(
            decode_metadata=None,
            prefill_metadata=SimpleNamespace(query_start_loc=qsl))
        setattr(md, _REAL_SEQ_IDS_PREFILL_ATTR, [555])    # 1 != 2 segments
        sm = torch.tensor([100 * BS, 100 * BS + 1,
                          102 * BS, 102 * BS + 1, 102 * BS + 2], dtype=torch.long)
        parts = _derive_write_partitions(md, sm, BS, writer=self._writer())
        # falls back to block-local last-slot: blocks 100 and 102.
        self.assertEqual([p[0] for p in parts], [100, 102])


if __name__ == "__main__":
    unittest.main(verbosity=2)
