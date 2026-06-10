"""Phase 6K.16b — CPU tests for block-local sequence identity.

Pinned acceptance criteria (the APC root-cause fix):

  1. DECODE COLLISION FIXED: rows sharing block_tables[:, 0] (a cached
     prefix) resolve to DISTINCT ids in block-local mode (the block of
     the token being written), where legacy mode collides.

  2. PREFILL/DECODE MATCH: a hit-sequence's prefill id (LAST written
     slot's block) equals what its first decode step derives
     (block_tables[i, (seq_len-1)//BS]) — the orphaned-staging bug.

  3. LEGACY PRESERVED: with block_local=False (bf16-backing mode) the
     derivations are byte-identical to the pre-6K.16b behavior
     (first slot / block_tables[:,0]).

  4. _derive_write_partitions wires the rule for both prefill segments
     and decode rows, gated on the writer's backing-skip flag.

  5. Padding (-1 slots) handled in both directions.
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
        block_local_seq_ids_enabled,
        decode_seq_ids_from_meta,
        prefill_seq_id_for_segment,
    )
    from kv_policy.phase5b_backend_install import _derive_write_partitions

BS = 32


@unittest.skipUnless(_HAVE_TORCH, "torch required")
class TestDecodeIds(unittest.TestCase):

    def setUp(self):
        # 3 sequences sharing a 2-block cached prefix (blocks 7, 8) —
        # the APC scenario. Private suffix blocks differ per seq.
        self.bt = torch.tensor([
            [7, 8, 100, 0],
            [7, 8, 101, 0],
            [7, 8, 102, 103],
        ], dtype=torch.int32)
        # seq_lens INCLUDE the token being written this step.
        self.sl = torch.tensor([70, 90, 97], dtype=torch.int32)
        # (70-1)//32=2 -> 100; (90-1)//32=2 -> 101; (97-1)//32=3 -> 103

    def test_legacy_collides_on_shared_prefix(self):
        ids = decode_seq_ids_from_meta(self.bt, self.sl, BS, block_local=False)
        self.assertEqual(ids, [7, 7, 7])          # the bug, preserved as legacy

    def test_block_local_unique_under_apc(self):
        ids = decode_seq_ids_from_meta(self.bt, self.sl, BS, block_local=True)
        self.assertEqual(ids, [100, 101, 103])
        self.assertEqual(len(set(ids)), 3)

    def test_block_local_missing_seqlens_falls_back(self):
        ids = decode_seq_ids_from_meta(self.bt, None, BS, block_local=True)
        self.assertEqual(ids, [7, 7, 7])

    def test_first_token_edge(self):
        ids = decode_seq_ids_from_meta(
            self.bt[:1], torch.tensor([1]), BS, block_local=True)
        self.assertEqual(ids, [7])                # (1-1)//32 = 0 -> first block


@unittest.skipUnless(_HAVE_TORCH, "torch required")
class TestPrefillIds(unittest.TestCase):

    def test_last_vs_first_block(self):
        # A hit-seq suffix crossing a block boundary: slots in block 100
        # then block 103.
        sm = torch.tensor([100 * BS + 30, 100 * BS + 31, 103 * BS + 0,
                           103 * BS + 1], dtype=torch.long)
        self.assertEqual(
            prefill_seq_id_for_segment(sm, 0, 4, BS, block_local=False), 100)
        self.assertEqual(
            prefill_seq_id_for_segment(sm, 0, 4, BS, block_local=True), 103)

    def test_prefill_matches_first_decode(self):
        # Criterion 2: prefill(last block) == decode(block of next token's
        # step) for a suffix ending mid-block at absolute position 96..98
        # (block 103 via table below).
        sm = torch.tensor([103 * BS, 103 * BS + 1, 103 * BS + 2])
        pid = prefill_seq_id_for_segment(sm, 0, 3, BS, block_local=True)
        bt = torch.tensor([[7, 8, 9, 103]], dtype=torch.int32)
        # next decode writes position 99+1?? seq_len after prefill of
        # ctx(96)+3 new = 99; decode step writes token at seq_len=100:
        did = decode_seq_ids_from_meta(
            bt, torch.tensor([100]), BS, block_local=True)[0]
        self.assertEqual(pid, did)                 # both -> block 103

    def test_padding_handling(self):
        sm = torch.tensor([-1, 50 * BS + 3, 51 * BS + 1, -1], dtype=torch.long)
        self.assertEqual(
            prefill_seq_id_for_segment(sm, 0, 4, BS, block_local=True), 51)
        self.assertEqual(
            prefill_seq_id_for_segment(sm, 0, 4, BS, block_local=False), 50)
        all_pad = torch.tensor([-1, -1], dtype=torch.long)
        self.assertEqual(
            prefill_seq_id_for_segment(all_pad, 0, 2, BS, block_local=True), -1)


@unittest.skipUnless(_HAVE_TORCH, "torch required")
class TestPartitionsWiring(unittest.TestCase):

    def _writer(self, skipped):
        return SimpleNamespace(_bf16_backing_skipped=skipped)

    def _decode_meta(self):
        return SimpleNamespace(
            block_tables=torch.tensor([[7, 8, 100], [7, 8, 101]],
                                      dtype=torch.int32),
            seq_lens_tensor=torch.tensor([70, 90], dtype=torch.int32),
        )

    def test_decode_partitions_block_local(self):
        md = SimpleNamespace(decode_metadata=self._decode_meta(),
                             prefill_metadata=None)
        sm = torch.tensor([70 - 1 + 100 * 0, 0], dtype=torch.long)  # unused in decode branch
        parts = _derive_write_partitions(md, sm, BS, writer=self._writer(True))
        self.assertEqual([p[0] for p in parts], [100, 101])

    def test_decode_partitions_legacy(self):
        md = SimpleNamespace(decode_metadata=self._decode_meta(),
                             prefill_metadata=None)
        sm = torch.tensor([0, 0], dtype=torch.long)
        parts = _derive_write_partitions(md, sm, BS, writer=self._writer(False))
        self.assertEqual([p[0] for p in parts], [7, 7])
        # and writer=None (legacy callers) behaves the same:
        parts2 = _derive_write_partitions(md, sm, BS)
        self.assertEqual([p[0] for p in parts2], [7, 7])

    def test_prefill_partitions_block_local(self):
        qsl = torch.tensor([0, 2, 5], dtype=torch.int32)
        md = SimpleNamespace(
            decode_metadata=None,
            prefill_metadata=SimpleNamespace(query_start_loc=qsl),
        )
        # seq0 slots in blocks [100,100]; seq1 crosses 101 -> 102.
        sm = torch.tensor([100 * BS, 100 * BS + 1,
                           101 * BS + 31, 102 * BS, 102 * BS + 1],
                          dtype=torch.long)
        parts = _derive_write_partitions(md, sm, BS, writer=self._writer(True))
        self.assertEqual([p[0] for p in parts], [100, 102])
        self.assertEqual([p[1] for p in parts],
                         [slice(0, 2), slice(2, 5)])
        legacy = _derive_write_partitions(md, sm, BS, writer=self._writer(False))
        self.assertEqual([p[0] for p in legacy], [100, 101])


if __name__ == "__main__":
    unittest.main(verbosity=2)
