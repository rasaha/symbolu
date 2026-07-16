#!/usr/bin/env python3
"""CPU tests for accounting + gate logic + verdict precedence (task Tests list:
metadata accounting, gate logic, missing-result handling, NOT_RUN behavior)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import accounting  # noqa: E402
import decide       # noqa: E402


def _scale_struct(ok=True):
    # ok=False fails BOTH the rank-1 (QF1/QF2) and the svd_R2 (QF3) decompositions, so
    # no candidate can pass structure -> NO_GO_STRUCTURE.
    v = (0.05, 0.97, 0.02) if ok else (0.30, 0.60, 0.20)
    r2 = (0.04, 0.98, 0.01) if ok else (0.28, 0.62, 0.18)
    return {"kind": "scale", "models": {
        "rank1_mult": {"rel_frob_worst": v[0], "var_explained_median": v[1],
                       "max_rel_channel_bias_worst": v[2]},
        "svd_R2": {"rel_frob_worst": r2[0], "var_explained_median": r2[1],
                   "max_rel_channel_bias_worst": r2[2]},
        "svd_R4": {"rel_frob_worst": 0.0, "var_explained_median": 1.0,
                   "max_rel_channel_bias_worst": 0.0}}}


def _xmin_struct(ok=True):
    v = (0.05, 0.97, 0.02) if ok else (0.40, 0.30, 0.30)
    return {"kind": "xmin", "models": {
        "additive": {"rel_frob_worst": v[0], "var_explained_median": v[1],
                     "max_rel_channel_bias_worst": v[2]},
        "svd_R2": {"rel_frob_worst": 0.03, "var_explained_median": 0.99,
                   "max_rel_channel_bias_worst": 0.01},
        "svd_R4": {"rel_frob_worst": 0.0, "var_explained_median": 1.0,
                   "max_rel_channel_bias_worst": 0.0}}}


def _attn(ok=True):
    r = ({"attn_out_cos_minus_affine": -0.002, "softmax_kl_ratio_to_affine": 1.2,
          "topk_overlap_minus_affine": -0.01} if ok else
         {"attn_out_cos_minus_affine": -0.05, "softmax_kl_ratio_to_affine": 3.0,
          "topk_overlap_minus_affine": -0.10})
    return {"relative_to_affine": {c: dict(r) for c in ("QF1", "QF2", "QF3")}}


def _quality(ok=True):
    q = {"needle_frac_of_affine": 1.0, "mmlu_drop_pts": 0.4} if ok else \
        {"needle_frac_of_affine": 0.7, "mmlu_drop_pts": 5.0}
    return {"per_candidate": {c: dict(q) for c in ("QF1", "QF2", "QF3")}}


def _write(d, tag, *, struct_ok=True, attn=None, qual=None):
    json.dump(_scale_struct(struct_ok), open(os.path.join(d, f"{tag}_scale_structure.json"), "w"))
    json.dump(_xmin_struct(struct_ok), open(os.path.join(d, f"{tag}_xmin_structure.json"), "w"))
    if attn is not None:
        json.dump(_attn(attn), open(os.path.join(d, f"{tag}_attention.json"), "w"))
    if qual is not None:
        json.dump(_quality(qual), open(os.path.join(d, f"{tag}_quality.json"), "w"))


class TestAccounting(unittest.TestCase):
    def test_affine_saves_nothing(self):
        sv = accounting.systems_value("affine")
        self.assertEqual(sv["metadata_bytes_saved_pct"], 0.0)
        self.assertFalse(sv["per_element_reconstruct_removed"])

    def test_qf_savings_ordered(self):
        q1 = accounting.systems_value("QF1")["metadata_bytes_saved_pct"]
        q2 = accounting.systems_value("QF2")["metadata_bytes_saved_pct"]
        self.assertGreater(q1, 25.0)                 # clears the systems byte gate
        self.assertGreater(q2, q1)                   # QF2 folds xmin too -> saves more
        self.assertTrue(accounting.systems_value("QF1")["replacement_cost"]["cancels_saving"] is False)


class TestVerdicts(unittest.TestCase):
    def _decide(self, **kw):
        require_q = kw.pop("require_q", True)
        with tempfile.TemporaryDirectory() as d:
            _write(d, "qwen", **kw); _write(d, "llama", **kw)
            return decide.decide(d, ["qwen", "llama"], require_quality=require_q)

    def test_no_files_inconclusive(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(decide.decide(d, ["qwen", "llama"])["verdict"], "INCONCLUSIVE")

    def test_structure_fail(self):
        r = self._decide(struct_ok=False, attn=True, qual=True)
        self.assertEqual(r["verdict"], "NO_GO_STRUCTURE")

    def test_structure_pass_attention_notrun(self):
        r = self._decide(struct_ok=True)                  # no attention/quality files
        self.assertEqual(r["verdict"], "INCONCLUSIVE")
        self.assertIn("attention", r["reason"].lower())

    def test_attention_fail(self):
        r = self._decide(struct_ok=True, attn=False, qual=True)
        self.assertEqual(r["verdict"], "NO_GO_ATTENTION_ERROR")

    def test_quality_pending_inconclusive(self):
        r = self._decide(struct_ok=True, attn=True)       # structure+attention pass, no quality
        self.assertEqual(r["verdict"], "INCONCLUSIVE")
        self.assertIn("quality", r["reason"].lower())
        self.assertTrue(r["survivors"])                   # survivors carried forward

    def test_quality_fail(self):
        r = self._decide(struct_ok=True, attn=True, qual=False)
        self.assertEqual(r["verdict"], "NO_GO_QUALITY")

    def test_full_go(self):
        r = self._decide(struct_ok=True, attn=True, qual=True)
        self.assertEqual(r["verdict"], "GO_QUERY_FOLD_KERNEL_PROTOTYPE")
        self.assertEqual(r["best_candidate"], "QF1")

    def test_structure_only_mode(self):
        r = self._decide(struct_ok=True, attn=True, require_q=False)
        self.assertEqual(r["verdict"], "INCONCLUSIVE")    # systems pass, quality not required
        self.assertTrue(r["survivors"])

    def test_notrun_contagious_across_models(self):
        # qwen fully passes; llama has NO structure files -> NOT_RUN contagious -> INCONCLUSIVE
        with tempfile.TemporaryDirectory() as d:
            _write(d, "qwen", struct_ok=True, attn=True, qual=True)
            r = decide.decide(d, ["qwen", "llama"])
            self.assertEqual(r["verdict"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
