"""Phase 6K.16 Tier 1 — CPU tests for the dequant-context prefill module.

The load-bearing verification is the module's own selftest (13 checks:
nibble round-trip exact, K within the principled quant bound, protect
channels bit-exact, V in-bound, varlen interleave layout, alignment +
legacy-backing rails) — run here as a single gate, plus a few direct
edge-case asserts the selftest doesn't cover.

Requires torch (CPU is fine). Skips cleanly when torch is absent.
"""
from __future__ import annotations

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
    _HAVE_TORCH = True
except ImportError:
    _HAVE_TORCH = False

if _HAVE_TORCH:
    from kv_policy import phase6k16_prefix_prefill as pp


@unittest.skipUnless(_HAVE_TORCH, "torch required")
class TestPrefixPrefillModule(unittest.TestCase):

    def test_module_selftest_all_pass(self):
        self.assertEqual(pp.selftest(), 0)

    def test_unpack_nibbles_convention(self):
        # byte 0xBA -> even d=0 low nibble 0xA, odd d=1 high nibble 0xB.
        packed = torch.tensor([[0xBA]], dtype=torch.uint8)
        out = pp.unpack_nibbles(packed)
        self.assertEqual(out.tolist(), [[0x0A, 0x0B]])

    def test_varlen_batch_mismatch_raises(self):
        new = torch.zeros((4, 2, 8), dtype=torch.bfloat16)
        qsl = torch.tensor([0, 2, 4], dtype=torch.int32)   # B=2
        with self.assertRaises(ValueError):
            pp.build_prefix_varlen_inputs(new, new, [(None, None)], qsl)

    def test_all_miss_batch_passthrough(self):
        # No seq has context -> k_full is exactly new_k, cu = qsl.
        H, D = 2, 8
        new = torch.arange(4 * H * D, dtype=torch.float32) \
            .view(4, H, D).to(torch.bfloat16)
        qsl = torch.tensor([0, 1, 4], dtype=torch.int32)
        k_full, v_full, cu, mx = pp.build_prefix_varlen_inputs(
            new, new, [(None, None), (None, None)], qsl)
        self.assertTrue(bool((k_full == new).all()))
        self.assertEqual(cu.tolist(), [0, 1, 4])
        self.assertEqual(mx, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
