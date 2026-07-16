#!/usr/bin/env python3
"""CPU tests for the KVPro V3 query-fold structural gate. No GPU, no model.

Covers (task Tests list):
  * exact production-affine reconstruction
  * factorization math (rank-1 mult / additive / low-rank detect structure)
  * query-fold equivalence in the LOSSLESS case (factored grid == production grid)
  * candidate isolation (V untouched, protected channels exact for every candidate)
  * structural detector (factorable passes, random fails)
Accounting / gate-logic / missing-result / NOT_RUN tests live in test_gates_cpu.py.
"""
import os
import sys
import unittest

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import candidates  # noqa: E402
import factorize   # noqa: E402
import quant_ref   # noqa: E402
import structure   # noqa: E402
import synthetic   # noqa: E402


class TestFactorize(unittest.TestCase):
    def test_rank1_mult_exact(self):
        s = synthetic.factorable_scale(12, 64, seed=0)              # exact α_d·β_b
        f = factorize.rank1_log_multiplicative(s)
        self.assertLess(f["rel_frob"], 1e-5)
        self.assertGreater(f["var_explained"], 0.999)

    def test_additive_exact(self):
        x = synthetic.factorable_xmin(12, 64, seed=1)               # exact u_d+v_b
        f = factorize.two_way_additive(x)
        self.assertLess(f["rel_frob"], 1e-6)

    def test_random_not_rank1(self):
        s = synthetic.random_scale(12, 64, seed=2)
        self.assertGreater(factorize.rank1_log_multiplicative(s)["rel_frob"], 0.2)

    def test_svd_rank_monotone(self):
        m = torch.randn(16, 64, dtype=torch.float64)
        e2 = factorize.low_rank_svd(m, 2)["rel_frob"]
        e4 = factorize.low_rank_svd(m, 4)["rel_frob"]
        self.assertLessEqual(e4, e2 + 1e-9)                         # more rank -> no worse

    def test_channel_bias_flags_shift(self):
        m = torch.randn(20, 32, dtype=torch.float64)
        biased = m.clone(); biased[:, 5] += 3.0                     # channel 5 offset
        cb = factorize.channel_bias(biased, m)
        self.assertEqual(cb["worst_channel"], 5)
        self.assertGreater(cb["max_abs_channel_bias"], 2.5)


class TestProductionAffine(unittest.TestCase):
    def test_codes_in_range_and_roundtrip(self):
        K = torch.randn(70, 4, 128)
        s, x, codes = quant_ref.production_k_metadata(K, BS=32)
        self.assertTrue((codes <= 15).all() and (codes >= 0).all())
        self.assertEqual(s.shape, (3, 4, 128))                      # ceil(70/32)=3 blocks
        K_hat = quant_ref.dequant_k(codes, s, x, BS=32)
        # affine int4 error is bounded by scale/2 per element
        self.assertLess((K_hat - K).abs().max().item(),
                        float(s.max()) * 0.5 + 1e-3)

    def test_matches_affine_grid(self):
        K = torch.randn(64, 2, 128)
        s, x, codes = quant_ref.production_k_metadata(K, BS=32)
        # dequant == codes*scale+xmin, exactly
        man = quant_ref.dequant_k(codes, s, x, BS=32)
        blk0 = codes[:32, 0, :].float() * s[0, 0] + x[0, 0]
        self.assertTrue(torch.allclose(man[:32, 0, :], blk0, atol=1e-5))


class TestCandidates(unittest.TestCase):
    def _cap(self, factorable=True):
        return synthetic.synthetic_capture(n_layers=1, S=96, H=4, D=128,
                                            n_protect=5, factorable=factorable)

    def test_affine_candidate_is_production(self):
        cap = self._cap()
        lyr = cap["layers"][0]
        K = lyr["K"].float()
        khat = candidates.reconstruct_k(K, lyr["s_prod"], lyr["xmin_prod"],
                                        lyr["protect_mask"], "affine", BS=32)
        prod = quant_ref.dequant_k(lyr["codes"], lyr["s_prod"], lyr["xmin_prod"], BS=32)
        prot = lyr["protect_mask"].bool().view(1, 4, 128).expand(96, 4, 128)
        prod = torch.where(prot, K, prod)
        self.assertTrue(torch.allclose(khat, prod, atol=1e-4))

    def test_lossless_equivalence(self):
        """If production scale IS exactly rank-1 and xmin exactly additive, QF1/QF2's
        factored grid == production grid -> reconstruction is IDENTICAL to affine."""
        B, H, D, S = 8, 4, 128, 8 * 32
        s_prod = torch.stack([synthetic.factorable_scale(B, D, seed=h) for h in range(H)], 1)
        x_prod = torch.stack([synthetic.factorable_xmin(B, D, seed=10 + h) for h in range(H)], 1)
        K = torch.randn(S, H, D)
        mask = torch.zeros(H, D, dtype=torch.int8); mask[:, :5] = 1
        aff = candidates.reconstruct_k(K, s_prod, x_prod, mask, "affine", BS=32)
        for cand in ("QF1", "QF2"):
            got = candidates.reconstruct_k(K, s_prod, x_prod, mask, cand, BS=32)
            self.assertLess((got - aff).abs().max().item(), 1e-3,
                            f"{cand} not lossless on exactly-factorable metadata")

    def test_candidate_isolation_protected_exact(self):
        cap = self._cap()
        lyr = cap["layers"][0]; K = lyr["K"].float()
        mask = lyr["protect_mask"].bool()
        for cand in candidates.candidate_names():
            khat = candidates.reconstruct_k(K, lyr["s_prod"], lyr["xmin_prod"],
                                            lyr["protect_mask"], cand, BS=32)
            protected = khat[:, mask]                              # (S, n_prot_total)
            exact = K[:, mask]
            self.assertTrue(torch.allclose(protected, exact, atol=1e-4),
                            f"{cand}: protected channels not exact")

    def test_meta_accounting_shapes(self):
        s_prod = synthetic.factorable_scale(8, 128).unsqueeze(1)   # (B,1,D)
        x_prod = synthetic.factorable_xmin(8, 128).unsqueeze(1)
        m1 = candidates.build_metadata(s_prod[:, 0], x_prod[:, 0], "QF1")
        m3 = candidates.build_metadata(s_prod[:, 0], x_prod[:, 0], "QF3")
        self.assertEqual(m1["block_meta_values"], 1 + 128)         # β_b + production xmin(D)
        self.assertEqual(m3["block_meta_values"], 2 + 128)         # rank-2 scale + production xmin


class TestStructureDetector(unittest.TestCase):
    def test_factorable_passes_random_fails(self):
        fac = synthetic.synthetic_metadata_manifest(factorable=True)
        ran = synthetic.synthetic_metadata_manifest(factorable=False)
        for kind, good_model in (("scale", "rank1_mult"), ("xmin", "additive")):
            rf_fac = structure.audit_manifest(fac, kind)["models"][good_model]["rel_frob_worst"]
            rf_ran = structure.audit_manifest(ran, kind)["models"][good_model]["rel_frob_worst"]
            self.assertLess(rf_fac, 1e-3, f"{kind}: factorable should fit")
            self.assertGreater(rf_ran, 0.2, f"{kind}: random should NOT fit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
