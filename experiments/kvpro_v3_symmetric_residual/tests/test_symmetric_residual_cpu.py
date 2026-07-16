"""CPU unit tests for the KVPro V3 Gate-1 symmetric-residual harness.

Validates: affine quantizer matches production math; symmetric drops xmin; protected channels are
reconstructed EXACT; the analytical accounting numbers; metric identities; and the pre-registered
gate decision tree. These test the HARNESS — they are not a quality verdict on symmetric INT4
(that needs real captured KV on a pod).
"""
from __future__ import annotations

import os
import sys
import unittest

import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import quantizers as Q          # noqa: E402
import metrics as M             # noqa: E402
import accounting as A          # noqa: E402
import gates as G               # noqa: E402


def _k_loop_reference(K, BS, scheme, bias=None):
    """The original per-block Python loop — the numerical ORACLE the vectorized path must match."""
    S, H, D = K.shape
    out = torch.empty_like(K, dtype=torch.float32)
    for s0 in range(0, S, BS):
        blk = K[s0:s0 + BS]                       # (T<=BS, H, D)
        if scheme == "affine":
            deq, _, _ = Q.affine_int4(blk, red_dim=0)
        elif scheme == "symmetric":
            deq, _ = Q.symmetric_int4(blk, red_dim=0, bias=bias)
        else:
            raise ValueError(scheme)
        out[s0:s0 + blk.shape[0]] = deq
    return out


class TestQuantizers(unittest.TestCase):
    def test_vectorized_k_matches_loop(self):
        # The vectorization must NOT change the pre-registered numerics: batched == per-block loop,
        # bit-for-bit (max/min reductions are order-invariant; the rest is elementwise). Covers
        # divisible, partial-tail, sub-block (S<BS), and full+partial sequence lengths.
        g = torch.Generator().manual_seed(7)
        for S in (32, 64, 96, 100, 17, 31, 33, 128):
            for H, D in ((2, 8), (4, 16)):
                K = torch.randn(S, H, D, generator=g)
                bias = torch.randn(H, D, generator=g)
                for scheme, b in (("affine", None), ("symmetric", None), ("symmetric", bias)):
                    ref = _k_loop_reference(K, 32, scheme, bias=b)
                    vec = Q.quantize_k_sequence(K, 32, scheme, bias=b)
                    self.assertTrue(torch.equal(ref, vec),
                                    f"vectorized K != loop for S={S} H={H} D={D} "
                                    f"scheme={scheme} bias={b is not None}")


    def test_affine_matches_production_formula(self):
        # production: scale=((amax-amin)/15).clamp(1e-8); q=round((x-xmin)/scale).clamp(0,15); x_hat=q*scale+xmin
        g = torch.Generator().manual_seed(0)
        blk = torch.randn(32, 2, 8, generator=g)              # (BS,H,D)
        x_hat, scale, xmin = Q.affine_int4(blk, red_dim=0)
        xmax = blk.float().amax(0, keepdim=True); xmn = blk.float().amin(0, keepdim=True)
        sc = ((xmax - xmn) / 15.0).clamp(min=1e-8)
        q = ((blk.float() - xmn) / sc).round().clamp(0, 15)
        self.assertTrue(torch.allclose(x_hat, q * sc + xmn, atol=1e-6))
        self.assertTrue(torch.allclose(scale, sc, atol=1e-6))

    def test_affine_error_bounded_by_step(self):
        g = torch.Generator().manual_seed(1)
        blk = torch.randn(32, 2, 8, generator=g)
        x_hat, scale, _ = Q.affine_int4(blk, red_dim=0)
        self.assertTrue(torch.all((blk.float() - x_hat).abs() <= scale.squeeze(0) + 1e-5))

    def test_symmetric_has_no_bias_term(self):
        # For zero-mean symmetric data, reconstruction is unbiased and within one step.
        g = torch.Generator().manual_seed(2)
        blk = torch.randn(32, 2, 8, generator=g)
        x_hat, scale = Q.symmetric_int4(blk, red_dim=0)
        self.assertTrue(torch.all((blk.float() - x_hat).abs() <= scale.squeeze(0) + 1e-5))

    def test_reconstruct_protected_exact_and_residual_quantized(self):
        g = torch.Generator().manual_seed(3)
        S, H, D = 64, 2, 8
        K = torch.randn(S, H, D, generator=g); V = torch.randn(S, H, D, generator=g)
        mask = torch.zeros(H, D, dtype=torch.int8); mask[0, 1] = 1; mask[1, 5] = 1
        Kh, Vh = Q.reconstruct(K, V, mask, "S1", BS=32, v_group_size=4)
        # protected channels: exact
        self.assertTrue(torch.allclose(Kh[:, 0, 1], K[:, 0, 1].float(), atol=1e-6))
        self.assertTrue(torch.allclose(Kh[:, 1, 5], K[:, 1, 5].float(), atol=1e-6))
        # an unprotected channel: quantized (not exact, but close)
        self.assertFalse(torch.allclose(Kh[:, 0, 0], K[:, 0, 0].float(), atol=1e-4))

    def test_s3_keeps_affine_k_symmetric_v(self):
        g = torch.Generator().manual_seed(4)
        K = torch.randn(64, 2, 8, generator=g); V = torch.randn(64, 2, 8, generator=g)
        mask = torch.zeros(2, 8, dtype=torch.int8)
        Kh_s3, _ = Q.reconstruct(K, V, mask, "S3", BS=32, v_group_size=4)
        Kh_aff, _ = Q.reconstruct(K, V, mask, "affine", BS=32, v_group_size=4)
        self.assertTrue(torch.allclose(Kh_s3, Kh_aff, atol=1e-6))   # S3 K == affine K


class TestAccounting(unittest.TestCase):
    def test_reduction_percentages(self):
        acc = A.account(A.QWEN2_5_7B, 8192)
        self.assertAlmostEqual(acc["affine"]["pct_reduction_vs_affine"], 0.0, places=2)
        self.assertAlmostEqual(acc["S1"]["pct_reduction_vs_affine"], 9.30, places=1)
        self.assertAlmostEqual(acc["S3"]["pct_reduction_vs_affine"], 4.65, places=1)
        self.assertAlmostEqual(acc["S4"]["pct_reduction_vs_affine"], 4.65, places=1)

    def test_xmin_removal_flags(self):
        acc = A.account(A.QWEN2_5_7B, 8192)
        self.assertEqual(acc["S1"]["xmin_fully_removed"], {"K": True, "V": True})
        self.assertEqual(acc["S3"]["xmin_fully_removed"], {"K": False, "V": True})
        self.assertEqual(acc["S4"]["xmin_fully_removed"], {"K": True, "V": False})

    def test_single_xmin_below_5pct_floor(self):
        # The crux: dropping ONE xmin (~4.65%) is below the 5% systems floor.
        acc = A.account(A.QWEN2_5_7B, 8192)
        self.assertLess(acc["S3"]["pct_reduction_vs_affine"], G.TH_SYSTEMS_PCT)
        self.assertGreater(acc["S1"]["pct_reduction_vs_affine"], G.TH_SYSTEMS_PCT)


class TestMetrics(unittest.TestCase):
    def test_identity(self):
        x = torch.randn(16, 2, 8)
        m = M.recon_metrics(x, x.clone())
        self.assertAlmostEqual(m["cos"], 1.0, places=5)
        self.assertAlmostEqual(m["mse"], 0.0, places=6)

    def test_attention_identity(self):
        g = torch.Generator().manual_seed(5)
        K = torch.randn(20, 2, 8, generator=g); V = torch.randn(20, 2, 8, generator=g)
        Qq = torch.randn(3, 2, 8, generator=g)
        am = M.attention_metrics(Qq, K, V, K.clone(), V.clone())
        self.assertGreater(am["attn_out_cos"], 0.9999)
        self.assertLess(am["softmax_kl_max"], 1e-6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
