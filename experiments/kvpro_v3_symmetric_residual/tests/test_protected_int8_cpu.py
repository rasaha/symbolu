"""CPU tests for the P8 protected-INT8 fake-quant (Part F). Validates: INT8 error bounds; that P8 leaves
the INT4 residual + V byte-identical to the affine baseline and differs ONLY on protected channels; that
INT8 protection is far closer to exact than INT4 would be; and the protected-stream byte accounting."""
from __future__ import annotations

import os
import sys
import unittest

import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import quantizers as Q            # noqa: E402
import protected_int8 as P8       # noqa: E402


class TestProtectedInt8(unittest.TestCase):
    def _kv(self, S=64, H=2, D=8, seed=0):
        g = torch.Generator().manual_seed(seed)
        return torch.randn(S, H, D, generator=g), torch.randn(S, H, D, generator=g)

    def test_int8_symmetric_within_one_step(self):
        x, _ = self._kv()
        xh, s = P8.protected_int8_symmetric(x, red_dim=0)
        self.assertTrue(torch.all((x.float() - xh).abs() <= s.squeeze(0) + 1e-5))

    def test_int8_affine_within_one_step(self):
        x, _ = self._kv(seed=1)
        xh, s, _ = P8.protected_int8_affine(x, red_dim=0)
        self.assertTrue(torch.all((x.float() - xh).abs() <= s.squeeze(0) + 1e-5))

    def test_residual_and_v_identical_to_affine_baseline(self):
        K, V = self._kv(seed=2)
        mask = torch.zeros(2, 8, dtype=torch.int8); mask[0, 1] = 1; mask[1, 5] = 1
        Kh8, Vh8 = P8.reconstruct_p8(K, V, mask, "P8sym", BS=32, v_group_size=4)
        Khaf, Vhaf = Q.reconstruct(K, V, mask, "affine", BS=32, v_group_size=4)
        prot = mask.to(torch.bool).view(1, 2, 8).expand_as(Kh8)
        # non-protected K channels: byte-identical to the affine baseline
        self.assertTrue(torch.equal(Kh8[~prot], Khaf[~prot]))
        # V: identical (P8 does not touch V)
        self.assertTrue(torch.equal(Vh8, Vhaf))

    def test_p8_differs_only_on_protected_channels(self):
        K, V = self._kv(seed=3)
        mask = torch.zeros(2, 8, dtype=torch.int8); mask[0, 2] = 1
        Kh8, _ = P8.reconstruct_p8(K, V, mask, "P8aff", BS=32, v_group_size=4)
        Khaf, _ = Q.reconstruct(K, V, mask, "affine", BS=32, v_group_size=4)  # exact protected
        diff = (Kh8 - Khaf).abs() > 0
        prot = mask.to(torch.bool).view(1, 2, 8).expand_as(Kh8)
        # every differing element must be a protected channel
        self.assertTrue(torch.all(prot[diff]))
        # and the protected channel actually changed (int8 != exact)
        self.assertTrue(diff[:, 0, 2].any())

    def test_int8_protection_beats_int4_residual_on_protected_channel(self):
        # The whole point: INT8 on the outlier channel is far closer to fp than INT4 would be.
        K, V = self._kv(seed=4)
        # make channel (0,0) a large-dynamic-range outlier (why it is "protected")
        K[:, 0, 0] = K[:, 0, 0] * 20.0
        mask = torch.zeros(2, 8, dtype=torch.int8); mask[0, 0] = 1
        Kh8, _ = P8.reconstruct_p8(K, V, mask, "P8sym", BS=32, v_group_size=4)
        Khint4 = Q.quantize_k_sequence(K, 32, "affine")   # what int4 would do to that channel
        err8 = (Kh8[:, 0, 0] - K[:, 0, 0].float()).abs().mean()
        err4 = (Khint4[:, 0, 0] - K[:, 0, 0].float()).abs().mean()
        self.assertLess(err8, err4)                        # int8 protection << int4 on the outlier

    def test_protected_stream_accounting(self):
        acc = P8.protected_stream_bytes(n_protect=6, sidecar_B_bf16=2)
        self.assertEqual(acc["protected_bytes_per_tok_head_layer_bf16"], 12.0)
        self.assertEqual(acc["protected_bytes_per_tok_head_layer_int8"], 6.0)
        self.assertEqual(acc["protected_stream_reduction_pct"], 50.0)

    def test_unknown_candidate_raises(self):
        K, V = self._kv()
        with self.assertRaises(ValueError):
            P8.reconstruct_p8(K, V, torch.zeros(2, 8, dtype=torch.int8), "P8bogus")


if __name__ == "__main__":
    unittest.main(verbosity=2)
