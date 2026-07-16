"""CPU tests for the P8 protected-INT8 verdict — reuses the SAME thresholds as the S-study gate, with
affine as the baseline and P8sym/P8aff as candidates. No torch/model."""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import p8_gate as P8G   # noqa: E402

CELLS = ["fp", "affine", "P8sym", "P8aff"]


def bench(benchmark, model, corr):
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


ALL_T = {c: [True] * 8 for c in CELLS}
M = "Qwen/Qwen2.5-7B-Instruct"


class TestP8Verdict(unittest.TestCase):
    def test_p8_clean_when_matches_affine(self):
        v = P8G.verdict(bench("needle", M, ALL_T), bench("hard_needle", M, ALL_T), bench("mmlu", M, ALL_T))
        self.assertEqual(v["verdict"], "P8_CLEAN")
        self.assertTrue(v["p8_quality_clean"])
        self.assertIn(v["recommended_variant"], ("P8sym", "P8aff"))

    def test_p8_no_go_on_hard_needle_regression(self):
        # both P8 variants flip a hard-needle item vs affine on the marginal model -> NO_GO
        hn = {"fp": [True] * 8, "affine": [True] * 8,
              "P8sym": [True] * 7 + [False], "P8aff": [True] * 7 + [False]}
        v = P8G.verdict(bench("needle", M, ALL_T), bench("hard_needle", M, hn), bench("mmlu", M, ALL_T))
        self.assertEqual(v["verdict"], "NO_GO_QUALITY")
        self.assertFalse(v["p8_quality_clean"])

    def test_p8_clean_if_one_variant_passes(self):
        # P8sym regresses but P8aff is clean -> P8_CLEAN via P8aff
        hn = {"fp": [True] * 8, "affine": [True] * 8,
              "P8sym": [True] * 7 + [False], "P8aff": [True] * 8}
        v = P8G.verdict(bench("needle", M, ALL_T), bench("hard_needle", M, hn), bench("mmlu", M, ALL_T))
        self.assertEqual(v["verdict"], "P8_CLEAN")
        self.assertEqual(v["recommended_variant"], "P8aff")

    def test_inconclusive_when_not_run(self):
        v = P8G.verdict(None, None, None)
        self.assertEqual(v["verdict"], "INCONCLUSIVE")
        self.assertFalse(v["p8_quality_clean"])

    def test_protected_stream_bytes_reported(self):
        v = P8G.verdict(bench("needle", M, ALL_T), bench("hard_needle", M, ALL_T), bench("mmlu", M, ALL_T))
        self.assertEqual(v["protected_stream"]["protected_bytes_per_tok_head_layer_bf16"], 10.0)
        self.assertEqual(v["protected_stream"]["protected_bytes_per_tok_head_layer_int8"], 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
