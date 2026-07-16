#!/usr/bin/env python3
"""CPU tests for the metadata-exploration analyzers (Phase B–E). No GPU, no model.

Covers: entropy calculations, temporal correlations, clustering reconstruction,
variance decomposition, and detection of synthetic low-rank / clustered / piecewise /
random ground truth. Stop-rule + NOT_RUN tests live in test_decide_structure_cpu.py.
"""
import os
import sys
import unittest

import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analyze_clustering as AC        # noqa: E402
import analyze_entropy as AE           # noqa: E402
import analyze_temporal_stability as AT  # noqa: E402
import analyze_variance_sources as AV  # noqa: E402
import synthetic                       # noqa: E402


def _man(structure):
    return synthetic.explore_manifest_synthetic(structure=structure, n_captures=3, n_layers=3)


class TestEntropy(unittest.TestCase):
    def test_entropy_bits_constant_and_binary(self):
        self.assertAlmostEqual(AE.entropy_bits(torch.ones(100)), 0.0, places=6)
        self.assertAlmostEqual(AE.entropy_bits(torch.tensor([1.0, 2.0] * 64)), 1.0, places=5)

    def test_runs_and_reports_finite(self):
        rep = AE.run(_man("random"), "scale")
        self.assertGreater(rep["global"]["entropy_bits"], 0)
        self.assertIn("head_entropy_bits", rep)
        self.assertGreater(rep["global"]["n_unique_bf16"], 1)

    def test_piecewise_lower_unique_than_random(self):
        # piecewise metadata repeats values across blocks -> fewer unique per channel series
        pe = AE.run(_man("piecewise"), "scale")["channel_series_entropy_bits"]["median"]
        ra = AE.run(_man("random"), "scale")["channel_series_entropy_bits"]["median"]
        self.assertLess(pe, ra)


class TestTemporal(unittest.TestCase):
    def test_autocorr_perfectly_correlated(self):
        s = torch.arange(20.0)
        self.assertGreater(AT._autocorr(s, 1), 0.99)

    def test_piecewise_vs_random_classification(self):
        self.assertEqual(AT.run(_man("piecewise"), "scale")["classification"], "piecewise_constant_or_slow")
        self.assertEqual(AT.run(_man("random"), "scale")["classification"], "abrupt_noisy")

    def test_piecewise_lag1_beats_random(self):
        self.assertGreater(AT.run(_man("piecewise"), "scale")["lag1"]["median"],
                           AT.run(_man("random"), "scale")["lag1"]["median"])


class TestClustering(unittest.TestCase):
    def test_kmeans_recovers_two_clusters(self):
        X = torch.cat([torch.zeros(10, 8), torch.ones(10, 8) * 5])
        a, C = AC._kmeans(X, 2)
        self.assertEqual(len(set(a[:10].tolist())), 1)          # first 10 same cluster
        self.assertEqual(len(set(a[10:].tolist())), 1)

    def test_clustered_reconstructs_random_does_not(self):
        cl = AC.run(_man("clustered"), "scale")["template_clustering"]["k2"]["rel_frob_template_plus_scalar"]
        ra = AC.run(_man("random"), "scale")["template_clustering"]["k2"]["rel_frob_template_plus_scalar"]
        self.assertLess(cl, 0.1)
        self.assertGreater(ra, 0.3)


class TestVariance(unittest.TestCase):
    def test_stable_is_calibratable_random_is_not(self):
        st = AV.run(_man("stable"), "scale")
        ra = AV.run(_man("random"), "scale")
        self.assertTrue(st["offline_calibratable_hint"])
        self.assertFalse(ra["offline_calibratable_hint"])
        self.assertGreater(st["cross_prompt_profile_corr"]["median"],
                           ra["cross_prompt_profile_corr"]["median"])

    def test_not_enough_captures(self):
        one = synthetic.explore_manifest_synthetic(structure="stable", n_captures=1)
        self.assertEqual(AV.run(one, "scale")["label"], "NOT_ENOUGH_CAPTURES")


if __name__ == "__main__":
    unittest.main(verbosity=2)
