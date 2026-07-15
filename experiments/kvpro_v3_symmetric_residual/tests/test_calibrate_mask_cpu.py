"""CPU test: the HF mask calibrator's pure builder matches the production top-k-by-max-abs criterion."""
from __future__ import annotations

import os
import sys
import unittest

import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
import calibrate_mask_hf as C          # noqa: E402


class TestMaskBuilder(unittest.TestCase):
    def test_topk_by_maxabs(self):
        # H_kv=2, D=8, protect_fraction=0.25 -> n_protect=2. Put the two largest per head at known idx.
        ma = torch.zeros(2, 8)
        ma[0, 3] = 9.0; ma[0, 6] = 8.0          # head 0 outliers at 3,6
        ma[1, 0] = 5.0; ma[1, 7] = 4.0          # head 1 outliers at 0,7
        mask, n_protect = C.build_mask_from_maxabs({0: ma, 1: ma.clone()}, 0.25)
        self.assertEqual(n_protect, 2)
        self.assertEqual(tuple(mask.shape), (2, 2, 8))
        self.assertEqual(set(mask[0, 0].nonzero().flatten().tolist()), {3, 6})
        self.assertEqual(set(mask[0, 1].nonzero().flatten().tolist()), {0, 7})
        self.assertTrue(torch.all(mask.sum(-1) == n_protect))   # exactly n_protect per (layer,head)

    def test_n_protect_rounding_matches_production(self):
        # D=128, 0.04 -> round(5.12) = 5 (same as production n_protect)
        ma = {0: torch.randn(4, 128).abs()}
        _, n = C.build_mask_from_maxabs(ma, 0.04)
        self.assertEqual(n, 5)

    def test_inconsistent_shape_raises(self):
        with self.assertRaises(RuntimeError):
            C.build_mask_from_maxabs({0: torch.zeros(2, 8), 1: torch.zeros(2, 4)}, 0.25)


if __name__ == "__main__":
    unittest.main(verbosity=2)
