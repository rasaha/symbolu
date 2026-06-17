"""CPU tests for `kv_policy.tier5b_snapshot` — the WarmTier snapshot/restore primitive.

Scope (read this before trusting a green run):
  * These tests validate the snapshot/restore **logic and plumbing** on CPU tensors with a
    faithful mock writer. They DO NOT exercise the live vLLM int4_protected writer + paged
    kv_cache — that path is pod-only and was MEASURED byte-clean on A100 (see
    docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md §Phase 0 and
    scripts/verify_kvpro_snapshot_roundtrip.py). This file is the CPU regression guard for the
    serialize/restore/guard code itself, so a logic regression is caught without a GPU.
  * The pure helpers (plan_restore / check_meta_compatible / summarize_snapshot / writer_meta)
    run with NO third-party deps. The tensor round-trip tests need torch and SKIP if it is absent.

Round-trip contract under test (mirrors phase5b_4c_paged_writer):
  * default protect format = bf16 passthrough: _protect_store and _protect_view_bf16 are identity,
    so the whole snapshot->zero->restore->re-snapshot cycle is strictly byte-equal.
  * prot-int8 format: snapshot dequants codes -> bf16, restore re-quantizes bf16 -> codes via
    _protect_store; byte-clean iff round((c*qscale+qmin-qmin)/qscale) == c on the uint8 code
    lattice. The CPU test pins that identity; cross-arbitrary-data byte-cleanliness was the A100
    measurement, not this unit test's claim.
"""
from __future__ import annotations

import os
import sys
import unittest
import warnings
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

from kv_policy import tier5b_snapshot as t5b  # noqa: E402

try:
    import torch  # noqa: E402
    _HAS_TORCH = True
except Exception:  # noqa: BLE001
    _HAS_TORCH = False


# --------------------------------------------------------------------------- #
# Pure helpers — no torch required.
# --------------------------------------------------------------------------- #
class _Numelish:
    """Stand-in tensor for summarize_snapshot (exposes numel()/element_size() only)."""

    def __init__(self, numel: int, esize: int):
        self._n, self._e = numel, esize

    def numel(self):
        return self._n

    def element_size(self):
        return self._e


class _MetaWriter:
    """Minimal object for writer_meta (no tensors)."""

    def __init__(self, D=8, BS=16, H=2, n_protect=2, prot_int8=False):
        self.D, self.BS, self.H, self.n_protect = D, BS, H, n_protect
        self._prot_int8_active = prot_int8


class TestPureHelpers(unittest.TestCase):
    def test_plan_restore_one_to_one(self):
        self.assertEqual(t5b.plan_restore(3, 3), [(0, 0), (1, 1), (2, 2)])

    def test_plan_restore_rejects_empty(self):
        with self.assertRaises(ValueError):
            t5b.plan_restore(0, 0)

    def test_plan_restore_rejects_count_mismatch(self):
        # A partial KV load is silent corruption; the planner must refuse, not truncate.
        with self.assertRaises(ValueError):
            t5b.plan_restore(8, 6)
        with self.assertRaises(ValueError):
            t5b.plan_restore(6, 8)

    def test_check_meta_compatible_match(self):
        meta = {"D": 8, "BS": 16, "n_protect": 2, "prot_format": t5b._PROT_BF16_FORMAT}
        self.assertTrue(t5b.check_meta_compatible(dict(meta), dict(meta)))

    def test_check_meta_compatible_geometry_mismatch_raises(self):
        snap = {"D": 8, "BS": 16, "n_protect": 2, "prot_format": t5b._PROT_BF16_FORMAT}
        for bad in ("D", "BS", "n_protect"):
            w = dict(snap)
            w[bad] = snap[bad] + 1
            with self.assertRaises(ValueError):
                t5b.check_meta_compatible(dict(snap), w)

    def test_check_meta_compatible_protect_format_diff_warns_but_passes(self):
        snap = {"D": 8, "BS": 16, "n_protect": 2, "prot_format": t5b._PROT_BF16_FORMAT}
        w = dict(snap)
        w["prot_format"] = t5b._PROT_INT8_FORMAT
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertTrue(t5b.check_meta_compatible(dict(snap), w))
        self.assertTrue(any("protect-format" in str(x.message) for x in caught))

    def test_summarize_snapshot_counts_bytes(self):
        snap = {
            "meta": {"prot_format": t5b._PROT_INT8_FORMAT},
            "events": [
                {"packed_k": _Numelish(10, 1), "k_scale": _Numelish(4, 2), "label": "ignored"},
                {"packed_v": _Numelish(10, 1)},
            ],
        }
        out = t5b.summarize_snapshot(snap)
        self.assertEqual(out["n_blocks"], 2)
        self.assertEqual(out["approx_bytes"], 10 * 1 + 4 * 2 + 10 * 1)  # non-tensor 'label' skipped
        self.assertEqual(out["prot_format"], t5b._PROT_INT8_FORMAT)

    def test_writer_meta_format_mapping(self):
        self.assertEqual(t5b.writer_meta(_MetaWriter(prot_int8=False))["prot_format"],
                         t5b._PROT_BF16_FORMAT)
        m = t5b.writer_meta(_MetaWriter(D=16, BS=8, H=4, n_protect=3, prot_int8=True))
        self.assertEqual(m, {"D": 16, "BS": 8, "H": 4, "n_protect": 3,
                             "prot_format": t5b._PROT_INT8_FORMAT})


# --------------------------------------------------------------------------- #
# Tensor round-trip — faithful CPU mock of the int4_protected paged writer.
# --------------------------------------------------------------------------- #
if _HAS_TORCH:

    def _prot_int8_quantize(x, qmin, qscale):
        q = ((x.to(torch.float32) - qmin) / qscale).round().clamp_(0.0, 255.0)
        return q.to(torch.uint8)

    def _prot_int8_dequantize(q, qmin, qscale, out_dtype):
        return (q.to(torch.float32) * qscale + qmin).to(out_dtype)

    class MockWriter:
        """CPU mirror of the paged writer's snapshot-relevant surface.

        Faithful to phase5b_4c_paged_writer: the same sidecar shapes/dtypes and the same
        _protect_store / _protect_view_bf16 semantics (bf16 passthrough by default; uint8
        code lattice under prot-int8). Geometry is small so the test is fast.
        """

        sidecar_dtype = torch.bfloat16

        def __init__(self, NB=4, BS=16, H=2, D=8, n_protect=2, v_groups=2, prot_int8=False,
                     qmin=-4.0, qscale=0.5, seed=0):
            self.NB, self.BS, self.H, self.D = NB, BS, H, D
            self.n_protect, self.v_groups = n_protect, v_groups
            self._prot_int8_active = prot_int8
            self._prot_qmin = torch.tensor(qmin, dtype=torch.float32)
            self._prot_qscale = torch.tensor(qscale, dtype=torch.float32)
            g = torch.Generator().manual_seed(seed)

            # kv_cache [2, NB, BS, H, D]; packed nibbles live in [..., :D//2] (uint8, byte-exact).
            self.kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8)
            self.kv_cache[..., : D // 2] = torch.randint(0, 256, (2, NB, BS, H, D // 2),
                                                          generator=g, dtype=torch.int32).to(torch.uint8)

            self.k_scale_ext = torch.randn((NB, H, D), generator=g).to(self.sidecar_dtype)
            self.k_xmin_ext = torch.randn((NB, H, D), generator=g).to(self.sidecar_dtype)
            self.v_scale_ext = torch.randn((NB, BS, H, v_groups), generator=g).to(self.sidecar_dtype)
            self.v_xmin_ext = torch.randn((NB, BS, H, v_groups), generator=g).to(self.sidecar_dtype)
            if prot_int8:
                self.k_protect_ext = torch.randint(0, 256, (NB, BS, H, n_protect),
                                                   generator=g, dtype=torch.int32).to(torch.uint8)
            else:
                self.k_protect_ext = torch.randn((NB, BS, H, n_protect), generator=g).to(self.sidecar_dtype)

        def _protect_store(self, k_protect):
            if not self._prot_int8_active:
                return k_protect
            return _prot_int8_quantize(k_protect, self._prot_qmin, self._prot_qscale)

        def _protect_view_bf16(self, raw):
            if not self._prot_int8_active:
                return raw
            return _prot_int8_dequantize(raw, self._prot_qmin, self._prot_qscale, self.sidecar_dtype)

    @unittest.skipUnless(_HAS_TORCH, "torch required for tensor round-trip")
    class TestSnapshotRoundtripCPU(unittest.TestCase):
        def _all_blocks(self, w):
            return list(range(w.NB))

        def test_default_format_verify_roundtrip_clean(self):
            w = MockWriter(prot_int8=False)
            res = t5b.verify_roundtrip(w, w.kv_cache, self._all_blocks(w))
            self.assertTrue(res["clean"], res["report"])
            self.assertTrue(all(res["report"].values()))
            self.assertEqual(res["n_blocks"], w.NB)

        def test_prot_int8_verify_roundtrip_clean(self):
            # Code-lattice identity: dequant->bf16->requant recovers the uint8 codes exactly
            # for this (qmin,qscale) regime, so the bf16-view byte-compare is clean.
            w = MockWriter(prot_int8=True, qmin=-4.0, qscale=0.5)
            res = t5b.verify_roundtrip(w, w.kv_cache, self._all_blocks(w))
            self.assertTrue(res["clean"], res["report"])

        def test_disk_roundtrip_byte_clean(self):
            import tempfile
            w = MockWriter(prot_int8=False)
            blocks = self._all_blocks(w)
            ref = [t5b.snapshot_block(w, w.kv_cache, b) for b in blocks]
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "prefix.pt")
                saved = t5b.save_prefix_snapshot(w, w.kv_cache, blocks, path)
                self.assertEqual(saved["n_blocks"], w.NB)
                self.assertGreater(saved["approx_bytes"], 0)
                t5b._zero_blocks(w, w.kv_cache, blocks)
                snap = t5b.load_prefix_snapshot(path)
                t5b.restore_prefix(w, w.kv_cache, snap, blocks)
            after = [t5b.snapshot_block(w, w.kv_cache, b) for b in blocks]
            for a, c in zip(ref, after):
                for k in t5b._TENSOR_KEYS:
                    self.assertTrue(torch.equal(a[k], c[k]), f"mismatch on {k}")

        def test_restore_prefix_refuses_count_mismatch(self):
            # Guards must fire BEFORE any tensor is touched (no partial / silently-corrupt load).
            w = MockWriter(prot_int8=False)
            snap = {"meta": t5b.writer_meta(w),
                    "events": [t5b.snapshot_block(w, w.kv_cache, b) for b in range(w.NB)]}
            with self.assertRaises(ValueError):
                t5b.restore_prefix(w, w.kv_cache, snap, list(range(w.NB - 1)))

        def test_restore_prefix_refuses_geometry_mismatch(self):
            w = MockWriter(prot_int8=False)
            snap = {"meta": t5b.writer_meta(w),
                    "events": [t5b.snapshot_block(w, w.kv_cache, b) for b in range(w.NB)]}
            snap["meta"] = dict(snap["meta"])
            snap["meta"]["D"] = w.D + 2  # geometry now incompatible
            with self.assertRaises(ValueError):
                t5b.restore_prefix(w, w.kv_cache, snap, list(range(w.NB)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
