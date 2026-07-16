"""CPU tests for the KVPro V3 Step-0 profiling logic: kernel->stage classification, nsys parsing,
stage summarization (with UNAVAILABLE discipline), the decision matrix, and the cost ceilings.
No GPU, no Nsight — pure logic on synthetic fixtures."""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)


def _load(fname, mod):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(_HERE, fname))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


PP = _load("04_parse_profile.py", "parse_profile")
DM = _load("05_decision_matrix.py", "decision_matrix")
import cost_accounting as CA  # noqa: E402  (valid module name)


class TestParse(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(PP.classify_kernel("paged_gather_copy_kernel"), "gather")
        self.assertEqual(PP.classify_kernel("elementwise_copy_contiguous"), "staging")
        self.assertEqual(PP.classify_kernel("_splice_k_partial_tail"), "splice")
        self.assertEqual(PP.classify_kernel("int4_unpack_nibble"), "dequant")
        self.assertEqual(PP.classify_kernel("protect_overlay_where"), "protect")
        self.assertEqual(PP.classify_kernel("_fused_protected_k_decode_attn_splitk"), "attention")
        self.assertEqual(PP.classify_kernel("some_random_kernel"), "other")

    def test_nsys_parse_tolerant(self):
        rows = [{"Name": "paged_gather", "Total Time (ns)": "1,000", "Instances": "10"},
                {"Name": "flash_attn", "Total Time (ns)": "3000", "Instances": "10"}]
        k = PP.parse_nsys_kernsum(rows)
        self.assertEqual(len(k), 2)
        self.assertEqual(k[0]["total_ns"], 1000.0)

    def test_summarize_pct_and_unavailable(self):
        kernels = [{"name": "paged_gather", "total_ns": 1000, "instances": 1},
                   {"name": "flash_attn_decode", "total_ns": 3000, "instances": 1}]
        s = PP.summarize(kernels)
        self.assertEqual(s["stages"]["gather"]["pct_of_kernel_time"], 25.0)
        self.assertEqual(s["stages"]["attention"]["pct_of_kernel_time"], 75.0)
        self.assertEqual(s["counters"]["dram__bytes_read.sum"], "UNAVAILABLE")  # no ncu
        self.assertEqual(s["label"], "GPU-measured")

    def test_summarize_no_data_is_not_run(self):
        s = PP.summarize([])
        self.assertEqual(s["label"], "NOT_RUN")
        self.assertEqual(s["stages"]["gather"]["pct_of_kernel_time"], "UNAVAILABLE")


def _stages(g=0, st=0, sp=0, de=0, pr=0, at=0, ot=0):
    tot = g + st + sp + de + pr + at + ot
    mk = lambda v: {"pct_of_kernel_time": v, "time_ns": v, "n_kernels": 1, "event_wall_ms": "UNAVAILABLE"}
    return {"label": "GPU-measured", "stages": {"gather": mk(g), "staging": mk(st), "splice": mk(sp),
            "dequant": mk(de), "protect": mk(pr), "attention": mk(at), "other": mk(ot)},
            "kernel_time_total_ns": tot}


class TestDecision(unittest.TestCase):
    def test_no_profile_blocked(self):
        env = {"can_profile_production_kernel": False, "can_profile_triton_route_a": False}
        d = DM.decide(env=env, stages=None)
        self.assertEqual(d["recommendation"], "FIX_PREREQUISITES_FIRST")

    def test_no_profile_but_profilable_inconclusive(self):
        env = {"can_profile_production_kernel": False, "can_profile_triton_route_a": True}
        d = DM.decide(env=env, stages=None)
        self.assertEqual(d["recommendation"], "INCONCLUSIVE")

    def test_gather_dominant(self):
        d = DM.decide(stages=_stages(g=30, st=10, pr=5, de=5, at=40, ot=5))
        self.assertEqual(d["recommendation"], "BUILD_GATHER_FIRST")

    def test_protect_dominant_p8_clean_int8(self):
        d = DM.decide(stages=_stages(g=3, st=2, pr=30, de=5, at=55, ot=5),
                      p8={"verdict": "P8_CLEAN"})
        self.assertEqual(d["recommendation"], "BUILD_PROTECT_STREAM_FIRST")
        self.assertIn("int8", d["rationale"])

    def test_both_big_combined(self):
        d = DM.decide(stages=_stages(g=15, st=10, pr=20, de=5, at=25, ot=5))
        self.assertEqual(d["recommendation"], "BUILD_COMBINED_KERNEL")

    def test_attention_dominant_no_project(self):
        d = DM.decide(stages=_stages(g=2, st=1, pr=2, de=3, at=90, ot=2))
        self.assertEqual(d["recommendation"], "NO_KERNEL_PROJECT_JUSTIFIED")

    def test_ranked_sorts_measured_first(self):
        d = DM.decide(stages=_stages(g=30, st=10, pr=5, at=40, ot=5))
        vals = [r["measured_removable_pct"] for r in d["ranked"]
                if isinstance(r["measured_removable_pct"], (int, float))]
        self.assertEqual(vals, sorted(vals, reverse=True))


class TestCost(unittest.TestCase):
    def test_layout_total(self):
        self.assertEqual(CA.TOTAL, 170)

    def test_format_change_ceiling(self):
        fc = CA.format_change_ceiling()
        self.assertAlmostEqual(fc["drop_both_xmin_pct"], 9.41, places=2)
        self.assertAlmostEqual(fc["protected_bf16_to_int8_pct"], 2.94, places=2)
        self.assertAlmostEqual(fc["xmin_plus_prot_int8_pct"], 12.35, places=2)

    def test_impl_removal_unavailable_without_profile(self):
        ir = CA.implementation_removal_ceiling(None)
        self.assertEqual(ir["max_time_gain_pct"], "UNAVAILABLE")

    def test_impl_removal_measured_with_profile(self):
        ir = CA.implementation_removal_ceiling(_stages(g=20, st=8, sp=2, at=70))
        self.assertAlmostEqual(ir["max_time_gain_pct"], 30.0, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
