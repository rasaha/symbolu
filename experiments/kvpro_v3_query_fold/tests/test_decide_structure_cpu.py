#!/usr/bin/env python3
"""CPU tests for Phase F/G: method reduces_work flags, verdict precedence, stop rules,
NOT_RUN handling. No GPU."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import compare_structure_methods as CM  # noqa: E402
import decide_structure as DS            # noqa: E402
import synthetic                         # noqa: E402


def _m(rf, rw, by):
    return {"rel_frob_median": round(rf * 0.5, 4), "rel_frob_worst": rf, "worst_block_rel_err": rf,
            "block_meta_values": 1, "channel_meta_values": 128, "metadata_bytes_saved_pct": by,
            "reduces_per_element_work": rw, "classification": "x"}


def _methods(rank=True, template=False, comp=True):
    return {"methods": {
        "rank1_multiplicative": _m(0.02 if rank else 0.4, True, 99.0),
        "svd_R2": _m(0.03 if rank else 0.4, True, 98.0),
        "per_head_template": _m(0.02 if template else 0.4, True, 99.0),
        "codebook": _m(0.03 if comp else 0.5, False, 75.0),
        "delta_prev": _m(0.03 if comp else 0.5, False, 41.0),
    }}


def _var(calib):
    return {"label": "MEASURED", "offline_calibratable_hint": calib}


def _write(d, tag, methods, variance):
    json.dump(methods, open(os.path.join(d, f"{tag}_scale_methods.json"), "w"))
    if variance is not None:
        json.dump(variance, open(os.path.join(d, f"{tag}_scale_variance.json"), "w"))


class TestMethodFlags(unittest.TestCase):
    def test_rank_reduces_work_compression_does_not(self):
        rep = CM.run(synthetic.explore_manifest_synthetic("low_rank"), "scale")["methods"]
        self.assertTrue(rep["rank1_multiplicative"]["reduces_per_element_work"])
        self.assertFalse(rep["codebook"]["reduces_per_element_work"])
        self.assertFalse(rep["piecewise_const"]["reduces_per_element_work"])
        self.assertTrue(rep["per_layer_template"]["reduces_per_element_work"])


class TestDecide(unittest.TestCase):
    def _run(self, q, l):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "qwen", q[0], q[1]); _write(d, "llama", l[0], l[1])
            return DS.decide(d, ["qwen", "llama"])

    def test_low_rank_calibratable_advances(self):
        r = self._run((_methods(rank=True), _var(True)), (_methods(rank=True), _var(True)))
        self.assertEqual(r["natural_structure"], "STRUCTURE_LOW_RANK")
        self.assertEqual(r["recommendation"], "ADVANCE_EXISTING_QUERY_FOLD")

    def test_work_but_prompt_dependent_closes(self):
        r = self._run((_methods(rank=True), _var(False)), (_methods(rank=True), _var(False)))
        self.assertEqual(r["natural_structure"], "STRUCTURE_WEAK")
        self.assertEqual(r["recommendation"], "CLOSE_QUERY_FOLD_NO_STRUCTURE")

    def test_template_advances_non_rank(self):
        r = self._run((_methods(rank=False, template=True), _var(True)),
                      (_methods(rank=False, template=True), _var(True)))
        self.assertEqual(r["natural_structure"], "STRUCTURE_CLUSTERED")
        self.assertEqual(r["recommendation"], "ADVANCE_NON_RANK_STRUCTURE")

    def test_only_compression_closes(self):
        r = self._run((_methods(rank=False, template=False, comp=True), _var(True)),
                      (_methods(rank=False, template=False, comp=True), _var(True)))
        self.assertEqual(r["recommendation"], "CLOSE_QUERY_FOLD_NO_STRUCTURE")

    def test_nothing_passes_weak(self):
        r = self._run((_methods(rank=False, template=False, comp=False), _var(True)),
                      (_methods(rank=False, template=False, comp=False), _var(True)))
        self.assertEqual(r["natural_structure"], "STRUCTURE_WEAK")

    def test_mixed_across_models_revises(self):
        # qwen rank, llama template -> mixed -> revise
        r = self._run((_methods(rank=True, template=False), _var(True)),
                      (_methods(rank=False, template=True), _var(True)))
        self.assertEqual(r["natural_structure"], "STRUCTURE_MIXED")
        self.assertEqual(r["recommendation"], "REVISE_QUERY_FOLD_CANDIDATES")

    def test_missing_methods_inconclusive(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "qwen", _methods(), _var(True))     # llama missing entirely
            self.assertEqual(DS.decide(d, ["qwen", "llama"])["recommendation"], "INCONCLUSIVE")

    def test_variance_notrun_advances_with_caveat(self):
        # work passes on both, variance NOT_RUN -> advances but flags calibratability
        r = self._run((_methods(rank=True), None), (_methods(rank=True), None))
        self.assertEqual(r["recommendation"], "ADVANCE_EXISTING_QUERY_FOLD")
        self.assertIn("NOT_RUN", r["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
