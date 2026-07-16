"""CPU tests for the P8 verdict — P8prod (production-faithful) DECIDES; experimental variants are advisory.
Reuses the SAME thresholds as the S-study gate, affine as baseline."""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import p8_gate as P8G   # noqa: E402

M = "Qwen/Qwen2.5-7B-Instruct"


def bench(benchmark, corr, model=M):
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


def allT(cells):
    return {c: [True] * 8 for c in cells}


PROD = ["fp", "affine", "P8prod"]


class TestP8Verdict(unittest.TestCase):
    def test_p8prod_clean(self):
        v = P8G.verdict(bench("needle", allT(PROD)), bench("hard_needle", allT(PROD)), bench("mmlu", allT(PROD)))
        self.assertEqual(v["verdict"], "P8_CLEAN")
        self.assertTrue(v["p8_quality_clean"])
        self.assertEqual(v["recommended_variant"], "P8prod")

    def test_p8prod_regression_no_go(self):
        hn = {"fp": [True] * 8, "affine": [True] * 8, "P8prod": [True] * 7 + [False]}  # 1 flip vs affine (marginal)
        v = P8G.verdict(bench("needle", allT(PROD)), bench("hard_needle", hn), bench("mmlu", allT(PROD)))
        self.assertEqual(v["verdict"], "NO_GO_QUALITY")
        self.assertFalse(v["p8_quality_clean"])

    def test_experimental_only_is_inconclusive_for_production(self):
        # only P8aff run (no P8prod) -> cannot validate production -> INCONCLUSIVE
        cells = ["fp", "affine", "P8aff"]
        v = P8G.verdict(bench("needle", allT(cells)), bench("hard_needle", allT(cells)), bench("mmlu", allT(cells)))
        self.assertEqual(v["verdict"], "INCONCLUSIVE")
        self.assertFalse(v["p8_quality_clean"])

    def test_inconclusive_when_not_run(self):
        v = P8G.verdict(None, None, None)
        self.assertEqual(v["verdict"], "INCONCLUSIVE")

    def test_protected_stream_bytes_reported(self):
        v = P8G.verdict(bench("needle", allT(PROD)), bench("hard_needle", allT(PROD)), bench("mmlu", allT(PROD)))
        self.assertEqual(v["protected_stream"]["protected_bytes_per_tok_head_layer_bf16"], 10.0)
        self.assertEqual(v["protected_stream"]["protected_bytes_per_tok_head_layer_int8"], 5.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
