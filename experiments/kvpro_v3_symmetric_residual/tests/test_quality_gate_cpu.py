"""CPU tests for the end-to-end quality result parsing + the updated (needle/hard-needle/MMLU) gate.

Covers: benchmark-output parsing, exact-answer comparison, per-seed aggregation, candidate-vs-affine
regression detection, verdict logic, missing-result / NOT_RUN handling. No torch, no model.
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import results as R          # noqa: E402
import gates as G            # noqa: E402

CELLS = ["fp", "affine", "S1", "S2", "S3", "S4"]


def bench(benchmark, model, corr):
    """corr: {cell: [bool per item]} -> a driver-shaped benchmark JSON."""
    n = len(next(iter(corr.values())))
    items = []
    for i in range(n):
        it = {"seed": i % 2, "cells": {}}
        if benchmark == "mmlu":
            it["gold"] = 0
        elif benchmark == "needle":
            it["context_len"] = [200, 600, 1200][i % 3]; it["needle"] = f"N{i}"
        elif benchmark == "hard_needle":
            it["mode"] = ["multi", "distractor", "conflict", "qa"][i % 4]
        for cell, flags in corr.items():
            ok = flags[i]
            if benchmark == "needle":
                it["cells"][cell] = {"hit": ok, "output": "x"}
            elif benchmark == "hard_needle":
                it["cells"][cell] = {"label": "HIT" if ok else "MISS_K", "output": "x"}
            else:
                it["cells"][cell] = {"pred": 0 if ok else 1}
        items.append(it)
    return {"model": model, "label": "MEASURED", "cells": list(corr), "items": items}


def attn_ok(passing=True):
    v = (0.99999, 1.0, 0.0) if passing else (0.90, 3.0, 0.5)
    s = {c: {"attn_out_cos_min": v[0], "attn_out_mse_vs_affine_max": v[1], "softmax_kl_max_max": v[2],
             "attn_out_mse_max": 0.0, "softmax_kl_mean_max": 0.0} for c in CELLS}
    return {"summary": s, "label": "MEASURED"}


ALL_T = {c: [True] * 8 for c in CELLS}


class TestResults(unittest.TestCase):
    def test_per_seed_aggregation(self):
        corr = {"fp": [True] * 4, "affine": [True] * 4, "S1": [True, False, True, True]}
        b = bench("needle", "m", corr)
        agg = R.aggregate(b["items"], ["S1"], "needle", group_keys=("seed",))
        self.assertEqual(agg["S1"]["overall"], {"correct": 3, "total": 4, "accuracy": 0.75})
        # items 0,2 are seed 0 (both True) -> 2/2; items 1,3 seed 1 (F,T) -> 1/2
        self.assertEqual(agg["S1"]["by_seed"]["0"]["accuracy"], 1.0)
        self.assertEqual(agg["S1"]["by_seed"]["1"]["accuracy"], 0.5)

    def test_regression_detection(self):
        corr = {"affine": [True, True, True, True], "S1": [True, True, False, True]}
        b = bench("hard_needle", "m", corr)
        regr = R.regressions(b["items"], "hard_needle", "affine", "S1")
        self.assertEqual(len(regr), 1)
        self.assertEqual(regr[0]["index"], 2)
        self.assertEqual(regr[0]["mode"], "conflict")   # item 2 mode

    def test_exact_answer_changes_mmlu(self):
        corr = {"fp": [True, True], "affine": [True, True], "S1": [True, False]}
        b = bench("mmlu", "m", corr)
        ch = R.answer_changes(b["items"], "mmlu", "affine", "S1")
        self.assertEqual(ch["changed"], 1)                 # item1 pred 0->1
        self.assertEqual(ch["regressions_introduced"], 1)  # affine right, S1 wrong

    def test_not_run_handling(self):
        self.assertEqual(R.summarize(None, "needle")["label"], "NOT_RUN")
        self.assertEqual(R.summarize({"label": "NOT_RUN"}, "mmlu")["label"], "NOT_RUN")
        self.assertEqual(R.summarize({"label": "MEASURED", "items": []}, "needle")["label"], "NOT_RUN")

    def test_marginal_flag(self):
        self.assertTrue(R.summarize(bench("needle", "Qwen/Qwen2.5-7B-Instruct", ALL_T), "needle")["marginal_model"])
        self.assertFalse(R.summarize(bench("needle", "meta-llama/Llama-3.1-8B", ALL_T), "needle")["marginal_model"])


class TestVerdict(unittest.TestCase):
    def _run(self, model="Qwen/Qwen2.5-7B-Instruct", ndl=None, hn=None, mm=None, attn=None):
        return G.verdict(attn if attn is not None else attn_ok(True),
                         ndl, hn, mm, geom=G.A.QWEN2_5_7B)

    def test_all_pass_go_kernel_prototype(self):
        v = self._run(ndl=bench("needle", "Qwen/Qwen2.5-7B-Instruct", ALL_T),
                      hn=bench("hard_needle", "Qwen/Qwen2.5-7B-Instruct", ALL_T),
                      mm=bench("mmlu", "Qwen/Qwen2.5-7B-Instruct", ALL_T))
        self.assertEqual(v["verdict"], "GO_KERNEL_PROTOTYPE")
        self.assertTrue(v["per_candidate"]["S1"]["full_quality"])

    def test_missing_benchmarks_inconclusive(self):
        # offline passes but end-to-end NOT RUN -> cannot GO
        v = self._run(ndl=None, hn=None, mm=None)
        self.assertEqual(v["verdict"], "INCONCLUSIVE")

    def test_hard_needle_fail_no_go(self):
        cand_fail = {**{c: [True] * 8 for c in ("fp", "affine", "S3", "S4")},
                     "S1": [False] * 8, "S2": [False] * 8}
        v = self._run(ndl=bench("needle", "Qwen/Qwen2.5-7B-Instruct", ALL_T),
                      hn=bench("hard_needle", "Qwen/Qwen2.5-7B-Instruct",
                               {c: [False] * 8 for c in CELLS} | {"fp": [True] * 8, "affine": [True] * 8}),
                      mm=bench("mmlu", "Qwen/Qwen2.5-7B-Instruct", ALL_T))
        self.assertEqual(v["verdict"], "NO_GO_QUALITY")

    def test_marginal_one_regression_kills_that_candidate(self):
        # S1 introduces exactly ONE hard-needle regression vs affine on the marginal model -> S1 fails,
        # but S2 is clean -> GO via S2.
        s1 = [True] * 8; s1[3] = False                    # affine True at 3, S1 False -> 1 regression
        hn = bench("hard_needle", "Qwen/Qwen2.5-7B-Instruct",
                   {"fp": [True] * 8, "affine": [True] * 8, "S1": s1,
                    "S2": [True] * 8, "S3": [True] * 8, "S4": [True] * 8})
        v = self._run(ndl=bench("needle", "Qwen/Qwen2.5-7B-Instruct", ALL_T), hn=hn,
                      mm=bench("mmlu", "Qwen/Qwen2.5-7B-Instruct", ALL_T))
        self.assertFalse(v["per_candidate"]["S1"]["hard_needle"])   # killed by the marginal 0-regression rule
        self.assertTrue(v["per_candidate"]["S2"]["hard_needle"])
        self.assertEqual(v["verdict"], "GO_KERNEL_PROTOTYPE")       # S2 carries it

    def test_only_v_symmetric_go_with_modification(self):
        # Only S3 (affine-K, symmetric-V) passes everywhere; S1/S2/S4 fail hard-needle.
        bad = [False] * 8
        def hn_corr():
            return {"fp": [True] * 8, "affine": [True] * 8, "S3": [True] * 8,
                    "S1": bad, "S2": bad, "S4": bad}
        v = self._run(ndl=bench("needle", "Qwen/Qwen2.5-7B-Instruct", ALL_T),
                      hn=bench("hard_needle", "Qwen/Qwen2.5-7B-Instruct", hn_corr()),
                      mm=bench("mmlu", "Qwen/Qwen2.5-7B-Instruct", ALL_T))
        self.assertEqual(v["verdict"], "GO_WITH_MODIFICATION")
        self.assertTrue(v["per_candidate"]["S3"]["full_quality"])

    def test_offline_fail_blocks_go_even_if_e2e_passes(self):
        # end-to-end all-pass but the offline attention proxy FAILS -> not full_quality -> not GO.
        v = G.verdict(attn_ok(False),
                      bench("needle", "Qwen/Qwen2.5-7B-Instruct", ALL_T),
                      bench("hard_needle", "Qwen/Qwen2.5-7B-Instruct", ALL_T),
                      bench("mmlu", "Qwen/Qwen2.5-7B-Instruct", ALL_T), geom=G.A.QWEN2_5_7B)
        self.assertFalse(v["per_candidate"]["S1"]["full_quality"])
        self.assertNotEqual(v["verdict"], "GO_KERNEL_PROTOTYPE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
