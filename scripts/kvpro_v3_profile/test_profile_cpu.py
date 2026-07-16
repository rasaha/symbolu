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
import route_a_builder as RB  # noqa: E402
CG = _load("06_correctness_gate.py", "correctness_gate")


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

    def test_summarize_route_a_events_ablation(self):
        # fused route-A cuda-events: protect% from the ablation; gather already inlined -> 0
        s = PP.summarize([], events={"attention": 10.0, "protect": 2.0})
        self.assertEqual(s["label"], "GPU-measured")
        self.assertEqual(s["stages"]["protect"]["pct_of_kernel_time"], 20.0)
        self.assertEqual(s["stages"]["gather"]["pct_of_kernel_time"], 0.0)
        self.assertEqual(s["stages"]["attention"]["pct_of_kernel_time"], 80.0)

    def test_summarize_events_unusable_is_not_run(self):
        s = PP.summarize([], events={"attention": "UNAVAILABLE", "protect": "UNAVAILABLE"})
        self.assertEqual(s["label"], "NOT_RUN")


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

    def test_decide_from_route_a_events(self):
        # route-A already fuses gather (0%); the measurable removable pole is protect (via ablation)
        s = PP.summarize([], events={"attention": 10.0, "protect": 3.0})   # protect 30%
        d = DM.decide(stages=s)
        self.assertEqual(d["recommendation"], "BUILD_PROTECT_STREAM_FIRST")

    def test_decide_route_a_small_protect_no_project(self):
        s = PP.summarize([], events={"attention": 100.0, "protect": 2.0})  # protect 2% < 8%
        d = DM.decide(stages=s)
        self.assertEqual(d["recommendation"], "NO_KERNEL_PROJECT_JUSTIFIED")


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

    def test_read_mask_accounting_from_real_artifact(self):
        # Part F: read n_protect from the ACTUAL mask, don't assume 5.
        import torch, tempfile, os
        L, H, D, k = 3, 4, 16, 5
        m = torch.zeros(L, H, D, dtype=torch.int8); m[:, :, :k] = 1     # exactly k protected/head (topk-like)
        p = os.path.join(tempfile.gettempdir(), "kvv3_mask_test.pt")
        torch.save({"mask": m, "protect_fraction": 0.3125, "minmax_margin": 1.1,
                    "k_min": torch.zeros(L, H, D), "k_max": torch.ones(L, H, D)}, p)
        acc = CA.read_mask_accounting(p)
        self.assertEqual(acc["n_protect"]["max"], k)
        self.assertTrue(acc["n_protect"]["uniform_by_construction"])
        self.assertTrue(acc["has_calibrated_minmax"])
        self.assertEqual(acc["protected_bytes_per_tok_head_layer_bf16"], k * 2)

    def test_build_adopts_mask_n_protect(self):
        import torch, tempfile, os
        m = torch.zeros(2, 4, 16, dtype=torch.int8); m[:, :, :7] = 1    # n_protect=7, not the default 5
        p = os.path.join(tempfile.gettempdir(), "kvv3_mask7_test.pt")
        torch.save({"mask": m}, p)
        b = CA.build(mask_path=p)
        self.assertEqual(b["n_protect_used"], 7)
        self.assertEqual(b["n_protect_source"], "mask-file")
        self.assertEqual(b["total_bytes_per_tok_head_layer"], 64 + 64 + 8 + 8 + 14 + 8 + 8)   # 174


class TestRouteABuilderAndGate(unittest.TestCase):
    """Parts A + B: the builder produces the writer's packed view faithfully, and the correctness gate
    round-trips it against the in-repo reference dequant (full + partial tails, bf16 + prod-int8)."""
    def _mask(self, H, D, k=2):
        import torch
        m = torch.zeros(H, D, dtype=torch.int8); m[:, :k] = 1
        return m

    def test_view_shapes_and_padding(self):
        import torch
        S, H, D = 70, 4, 16
        v = RB.build_packed_view(torch.randn(S, H, D), torch.randn(S, H, D), self._mask(H, D), BS=32, v_group_size=8)
        self.assertEqual(v["S_padded"], 96)                      # ceil(70/32)*32
        self.assertEqual(tuple(v["k_int4"].shape), (1, 96, H, D // 2))
        self.assertEqual(tuple(v["k_scale"].shape), (1, 3, H, D))   # per-block
        self.assertEqual(v["active_in_last_block"], 70 - 64)
        self.assertEqual(v["n_protect"], 2)

    def test_roundtrip_full_and_partial_tails(self):
        import torch
        H, D = 4, 16
        mask = self._mask(H, D)
        kmin, kmax = torch.full((H, D), -3.0), torch.full((H, D), 3.0)
        for S in (64, 64 + 1, 64 + 7, 64 + 31):
            ck, _ = CG.roundtrip_checks(torch.randn(S, H, D), torch.randn(S, H, D), mask, 32, 8, kmin, kmax, False)
            self.assertTrue(all(c["pass"] for c in ck.values()), f"S={S}: {ck}")

    def test_prot_int8_overlay_matches_p8prod(self):
        import torch
        H, D = 4, 16
        kmin, kmax = torch.full((H, D), -3.0), torch.full((H, D), 3.0)
        ck, _ = CG.roundtrip_checks(torch.randn(64, H, D), torch.randn(64, H, D), self._mask(H, D), 32, 8, kmin, kmax, True)
        self.assertTrue(ck["k_protect_overlay_exact"]["pass"])

    def test_full_cpu_gate_passes(self):
        r = CG.run_cpu(H=2, D=16, BS=32, v_group_size=8)
        self.assertTrue(r["all_pass"])
        self.assertGreaterEqual(r["n_cases"], 10)

    def test_kernel_input_adapter_matches_fp_oracle(self):
        # the Route-A kernel-input adapter, run through the sketch oracle, matches fp attention within
        # int4 error — proves the adapter feeds the kernel numerically-correct inputs (no GPU needed).
        for pint8 in (False, True):
            kw, meta = RB.make_kernel_inputs(context_len=128, H_kv=4, D=64, G=2, BS=32, seed=2, prot_int8=pint8)
            orc, ref = RB.oracle_attention(kw, meta).float().reshape(-1), RB.reference_fp_attention(meta).float().reshape(-1)
            cos = float((orc @ ref) / (orc.norm() * ref.norm()))
            self.assertGreater(cos, 0.98, f"prot_int8={pint8} cos={cos}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
