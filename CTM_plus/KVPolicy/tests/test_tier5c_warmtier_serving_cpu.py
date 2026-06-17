"""CPU tests for Tier 5C — KVPro WarmTier serving orchestration (host-side logic).

Validates the host-side serving wiring on CPU: prefix keying, the snapshot store + manifest, the
reuse plan + computed-token accounting, the eviction policy, the scheduler-injection accounting's
loud-failure paths, and an end-to-end snapshot->store->plan->restore round-trip on a mock writer that
gates byte-clean through the tier5b primitive. The GPU/vLLM-bound serving (decode over restored KV)
is pod-only and not exercised here.
"""
from __future__ import annotations

import os
import sys
import tempfile
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

from kv_policy import tier5c_warmtier_serving as t5c  # noqa: E402

try:
    import torch  # noqa: E402
    _HAS_TORCH = True
except Exception:  # noqa: BLE001
    _HAS_TORCH = False


def _rec(key, n_blocks, block_hashes, n_tokens=None, bytes_on_disk=1000, path="/tmp/x.pt"):
    return t5c.WarmTierRecord(
        key=key, n_blocks=n_blocks, n_tokens=n_tokens or n_blocks * 4, path=path,
        bytes_on_disk=bytes_on_disk, prot_format="bf16",
        geometry={"D": 8, "BS": 4, "n_protect": 2}, block_hashes=list(block_hashes))


# --------------------------------------------------------------------------- #
# Pure host logic — no torch.
# --------------------------------------------------------------------------- #
class TestPrefixHashing(unittest.TestCase):
    def test_deterministic_and_block_aligned(self):
        toks = list(range(20))
        a = t5c.block_prefix_hashes(toks, 4)
        b = t5c.block_prefix_hashes(toks, 4)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 5)                      # 20 // 4, partial ignored

    def test_partial_block_ignored(self):
        self.assertEqual(len(t5c.block_prefix_hashes(list(range(22)), 4)), 5)
        self.assertEqual(t5c.block_prefix_hashes(list(range(3)), 4), [])

    def test_chain_sensitivity(self):
        base = list(range(20))
        changed = list(range(20)); changed[9] = 999      # alter block index 2 (tokens 8..11)
        hb, hc = t5c.block_prefix_hashes(base, 4), t5c.block_prefix_hashes(changed, 4)
        self.assertEqual(hb[:2], hc[:2])                 # blocks 0,1 unaffected
        self.assertNotEqual(hb[2], hc[2])                # block 2 onward diverges
        self.assertNotEqual(hb[4], hc[4])

    def test_rejects_bad_block_size(self):
        with self.assertRaises(ValueError):
            t5c.block_prefix_hashes([1, 2, 3], 0)


class TestStoreAndMatch(unittest.TestCase):
    def setUp(self):
        self.toks = list(range(20))
        self.hs = t5c.block_prefix_hashes(self.toks, 4)
        self.store = t5c.WarmTierStore()

    def test_longest_prefix_match_returns_deepest(self):
        self.store.put(_rec(self.hs[1], 2, self.hs[:2]))     # 2-block prefix
        self.store.put(_rec(self.hs[3], 4, self.hs[:4]))     # 4-block prefix (deeper)
        m = self.store.longest_prefix_match(self.toks, 4)
        self.assertIsNotNone(m)
        self.assertEqual(m.n_blocks, 4)

    def test_no_match_returns_none(self):
        self.assertIsNone(self.store.longest_prefix_match(self.toks, 4))

    def test_shorter_prefix_when_only_shallow_stored(self):
        self.store.put(_rec(self.hs[1], 2, self.hs[:2]))
        m = self.store.longest_prefix_match(self.toks, 4)
        self.assertEqual(m.n_blocks, 2)

    def test_collision_guard_rejects_wrong_block_count(self):
        # Record indexed at the depth-4 hash but claiming the wrong n_blocks must be skipped.
        self.store.put(_rec(self.hs[3], 99, self.hs[:4]))
        self.assertIsNone(self.store.longest_prefix_match(self.toks, 4))

    def test_has_prefix(self):
        self.store.put(_rec(self.hs[4], 5, self.hs[:5]))
        self.assertTrue(self.store.has_prefix(self.toks, 4))
        self.assertFalse(t5c.WarmTierStore().has_prefix(self.toks, 4))

    def test_manifest_roundtrip(self):
        self.store.put(_rec(self.hs[3], 4, self.hs[:4], bytes_on_disk=2222))
        with tempfile.TemporaryDirectory() as d:
            mp = os.path.join(d, "manifest.json")
            self.store.persist(mp)
            loaded = t5c.WarmTierStore.load(mp)
        self.assertEqual(len(loaded), 1)
        m = loaded.longest_prefix_match(self.toks, 4)
        self.assertEqual(m.n_blocks, 4)
        self.assertEqual(m.bytes_on_disk, 2222)


class TestReusePlanAndEviction(unittest.TestCase):
    def setUp(self):
        self.toks = list(range(20))
        self.hs = t5c.block_prefix_hashes(self.toks, 4)
        self.store = t5c.WarmTierStore()

    def test_plan_reuse_accounting(self):
        self.store.put(_rec(self.hs[3], 4, self.hs[:4]))
        plan = t5c.plan_reuse(self.toks, self.store, 4)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.n_blocks, 4)
        self.assertEqual(plan.num_computed_tokens, 4 * 4)        # n_blocks * block_size
        self.assertEqual(plan.target_block_count, 4)

    def test_plan_reuse_consistent_with_tier5b(self):
        from kv_policy import tier5b_snapshot as t5b
        self.store.put(_rec(self.hs[3], 4, self.hs[:4]))
        plan = t5c.plan_reuse(self.toks, self.store, 4)
        # restore is 1:1 in order over exactly target_block_count blocks.
        pairs = t5b.plan_restore(plan.n_blocks, plan.target_block_count)
        self.assertEqual(pairs, [(i, i) for i in range(plan.n_blocks)])

    def test_plan_reuse_miss_is_none(self):
        self.assertIsNone(t5c.plan_reuse(self.toks, self.store, 4))

    def test_should_snapshot_threshold_and_dedup(self):
        written = [10, 11, 12, 13, 14]
        plan = t5c.should_snapshot_on_evict(self.toks, written, 4, self.store, min_blocks=3)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.n_blocks, 5)
        self.assertEqual(plan.block_ids, written)
        self.assertEqual(plan.key, self.hs[4])
        # Below threshold -> None.
        self.assertIsNone(t5c.should_snapshot_on_evict(list(range(8)), [1, 2], 4, self.store,
                                                       min_blocks=3))
        # Dedup: once the key is in the store, re-eviction is skipped.
        self.store.put(_rec(plan.key, plan.n_blocks, plan.block_hashes))
        self.assertIsNone(t5c.should_snapshot_on_evict(self.toks, written, 4, self.store,
                                                       min_blocks=3))

    def test_reuse_economics(self):
        recs = [_rec(1, 2, [1, 2], n_tokens=8, bytes_on_disk=800),
                _rec(2, 3, [3, 4, 5], n_tokens=12, bytes_on_disk=1200)]
        e = t5c.reuse_economics(recs)
        self.assertEqual(e["n_records"], 2.0)
        self.assertEqual(e["total_bytes"], 2000.0)
        self.assertAlmostEqual(e["bytes_per_token"], 2000.0 / 20.0)
        self.assertAlmostEqual(e["bytes_per_block"], 2000.0 / 5.0)


class TestMarkPrefixComputed(unittest.TestCase):
    """The scheduler-injection accounting (host logic): iterate seqs, set num_computed_tokens.
    Real vLLM is pod-only; here we validate the loud-failure paths + the happy-path call."""

    def test_happy_path_calls_updater(self):
        calls = []

        class _Data:
            def update_num_computed_tokens(self, n):
                calls.append(n)

        class _Seq:
            data = _Data()

        class _Group:
            def get_seqs(self):
                return [_Seq(), _Seq()]

        t5c.mark_prefix_computed(_Group(), 64)
        self.assertEqual(calls, [64, 64])

    def test_loud_failure_no_get_seqs(self):
        with self.assertRaises(NotImplementedError):
            t5c.mark_prefix_computed(object(), 16)

    def test_loud_failure_no_updater(self):
        class _Seq:
            data = object()

        class _Group:
            def get_seqs(self):
                return [_Seq()]

        with self.assertRaises(NotImplementedError):
            t5c.mark_prefix_computed(_Group(), 16)

    def test_serve_is_pod_only(self):
        with self.assertRaises(NotImplementedError):
            t5c.serve_with_warmtier_reuse()


# --------------------------------------------------------------------------- #
# End-to-end host round-trip on a mock writer (gates byte-clean via tier5b).
# --------------------------------------------------------------------------- #
if _HAS_TORCH:

    class _MockWriter:
        sidecar_dtype = torch.bfloat16

        def __init__(self, NB=8, BS=4, H=2, D=8, n_protect=2, v_groups=2, seed=0):
            self.NB, self.BS, self.H, self.D = NB, BS, H, D
            self.n_protect, self.v_groups = n_protect, v_groups
            self._prot_int8_active = False
            g = torch.Generator().manual_seed(seed)
            self.kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
            self.kv_cache[..., : D // 2] = torch.randint(0, 256, (2, NB, BS, H, D // 2),
                                                          generator=g, dtype=torch.int32).to(torch.uint8)
            self.k_scale_ext = torch.randn((NB, H, D), generator=g).to(self.sidecar_dtype)
            self.k_xmin_ext = torch.randn((NB, H, D), generator=g).to(self.sidecar_dtype)
            self.v_scale_ext = torch.randn((NB, BS, H, v_groups), generator=g).to(self.sidecar_dtype)
            self.v_xmin_ext = torch.randn((NB, BS, H, v_groups), generator=g).to(self.sidecar_dtype)
            self.k_protect_ext = torch.randn((NB, BS, H, n_protect), generator=g).to(self.sidecar_dtype)

        def _protect_store(self, k):
            return k

        def _protect_view_bf16(self, raw):
            return raw

    @unittest.skipUnless(_HAS_TORCH, "torch required")
    class TestEndToEndHostRoundtrip(unittest.TestCase):
        def test_snapshot_store_plan_restore_byte_clean(self):
            from kv_policy import tier5b_snapshot as t5b
            w = _MockWriter()
            toks = list(range(5 * w.BS))                      # 5 complete blocks
            written = [0, 1, 2, 3, 4]
            store = t5c.WarmTierStore()
            with tempfile.TemporaryDirectory() as d:
                ev = t5c.should_snapshot_on_evict(toks, written, w.BS, store, min_blocks=2)
                self.assertIsNotNone(ev)
                ref = [t5b.snapshot_block(w, w.kv_cache, b) for b in ev.block_ids]
                rec = t5c.snapshot_prefix_on_evict(w, w.kv_cache, ev, d, store)
                self.assertEqual(rec.n_blocks, 5)
                self.assertTrue(store.has_prefix(toks, w.BS))

                plan = t5c.plan_reuse(toks, store, w.BS)
                self.assertEqual(plan.n_blocks, 5)

                # Simulate "fresh blocks" by zeroing the same block ids, then restore into them.
                with torch.inference_mode():
                    t5b._zero_blocks(w, w.kv_cache, ev.block_ids)
                    t5c.restore_prefix_into_blocks(w, w.kv_cache, plan, ev.block_ids)
                    after = [t5b.snapshot_block(w, w.kv_cache, b) for b in ev.block_ids]
                for a, c in zip(ref, after):
                    for k in t5b._TENSOR_KEYS:
                        self.assertTrue(torch.equal(a[k], c[k]), f"warm-tier reuse not byte-clean: {k}")

        def test_restore_wrong_block_count_refused(self):
            w = _MockWriter()
            rec = _rec(123, 3, [1, 2, 3])
            plan = t5c.RestorePlan(record=rec, snapshot_path="/tmp/none.pt", n_blocks=3,
                                   block_size=w.BS, num_computed_tokens=12, target_block_count=3)
            with self.assertRaises(ValueError):
                t5c.restore_prefix_into_blocks(w, w.kv_cache, plan, [0, 1])   # 2 != 3


if __name__ == "__main__":
    unittest.main(verbosity=2)
