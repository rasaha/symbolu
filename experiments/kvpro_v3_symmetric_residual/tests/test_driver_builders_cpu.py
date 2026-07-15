"""CPU tests: the pod drivers REUSE the repo's needle / hard-needle / MMLU protocols.

Validates the prompt-set builders (which import the real repo functions) produce the expected
structure — i.e. we did not invent a new incompatible protocol. Generation itself is pod-only and
not exercised here.
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))


class TestBuildersReuseRepoProtocols(unittest.TestCase):
    def test_needle_builder_reuses_repo(self):
        import needle_driver as ND
        self.assertTrue(hasattr(ND.vn, "_make_needle") and hasattr(ND.vn, "_build_prompt"))
        s = ND.build_prompt_set(seeds=(0, 1), num_needles=3)
        self.assertEqual(len(s), 2 * len(ND.CONTEXT_LENS) * 3)
        self.assertEqual(sorted(s[0]), ["context_len", "needle", "prompt", "seed"])
        self.assertIn(s[0]["needle"], s[0]["prompt"])         # needle actually planted
        self.assertEqual({it["context_len"] for it in s}, set(ND.CONTEXT_LENS))

    def test_needle_builder_deterministic(self):
        import needle_driver as ND
        self.assertEqual([i["needle"] for i in ND.build_prompt_set(seeds=(0,), num_needles=2)],
                         [i["needle"] for i in ND.build_prompt_set(seeds=(0,), num_needles=2)])

    def test_hard_needle_builder_reuses_repo(self):
        import hard_needle_driver as HD
        self.assertTrue(hasattr(HD.hn, "build_item") and hasattr(HD.hn, "classify"))
        s = HD.build_item_set(seeds=(0,), items_per_mode=2, target_tokens=600)
        self.assertEqual(len(s), len(HD.hn.MODES) * 2)
        self.assertEqual({it["mode"] for it in s}, set(HD.hn.MODES))
        self.assertTrue(all(it["expected"] and isinstance(it["distractors"], list) for it in s))

    def test_hard_needle_classify_is_repo_function(self):
        import hard_needle_driver as HD
        # sanity: repo classify labels a clean hit as HIT
        self.assertEqual(HD.hn.classify("The code is ABC12", "ABC12", ["ZZZ99"], "multi"), "HIT")

    def test_mmlu_builder_reuses_repo(self):
        import mmlu_driver as MD
        self.assertTrue(hasattr(MD.mm, "build_prompt") and hasattr(MD.mm, "parse_answer"))
        qs = MD.build_question_set(num_questions=6, real=False)
        self.assertEqual(len(qs), 6)
        self.assertEqual(sorted(qs[0]), ["answer", "choices", "q"])
        # repo prompt+parse round-trip
        p = MD.mm.build_prompt(qs[0]["q"], qs[0]["choices"])
        self.assertIn("Answer", p)
        self.assertEqual(MD.mm.parse_answer("The answer is B."), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
