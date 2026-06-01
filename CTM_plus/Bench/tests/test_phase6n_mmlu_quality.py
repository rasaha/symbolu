#!/usr/bin/env python3
# Phase 6N — CPU regression for the MMLU quality-bench scoring core.
#
# Independently exercises the pure functions (prompt build, answer parse, score,
# acceptance gate) with different fixtures than the script's --selftest. No
# torch/vllm/GPU/dataset; runs anywhere.
#
# Run:  python CTM_plus/Bench/tests/test_phase6n_mmlu_quality.py
#       (also pytest-collectable)

import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

import bench_phase6n_mmlu_quality as m


def test_build_prompt_has_all_choices_and_answer_tag():
    p = m.build_prompt("Q?", ["w", "x", "y", "z"])
    for letter, ch in zip("ABCD", ["w", "x", "y", "z"]):
        assert f"{letter}. {ch}" in p
    assert p.rstrip().endswith("Answer:")


def test_parse_answer_standalone_letters():
    assert m.parse_answer("A") == 0
    assert m.parse_answer("B") == 1
    assert m.parse_answer("C") == 2
    assert m.parse_answer("D") == 3


def test_parse_answer_in_context():
    assert m.parse_answer("The answer is C.") == 2
    assert m.parse_answer("(D)") == 3
    assert m.parse_answer("Answer: B") == 1
    assert m.parse_answer("A. Paris") == 0


def test_parse_answer_rejects_prose_letters():
    # The whole reason the parser is conservative: these must NOT parse.
    assert m.parse_answer("I don't know") is None      # 'D' inside Don't
    assert m.parse_answer("ACID") is None              # A,C,D glued
    assert m.parse_answer("bead") is None              # contains B,A,D
    assert m.parse_answer("") is None
    assert m.parse_answer("none of these") is None


def test_parse_answer_takes_first_valid():
    assert m.parse_answer("B then maybe C") == 1


def test_score_counts():
    s = m.score([0, 1, 2, 3], [0, 1, 2, 3])
    assert s["correct"] == 4 and s["accuracy_pct"] == 100.0
    s = m.score([0, 0, 0, 0], [0, 1, 2, 3])
    assert s["correct"] == 1 and s["accuracy_pct"] == 25.0
    s = m.score([None, None], [0, 1])
    assert s["unparsed"] == 2 and s["accuracy_pct"] == 0.0


def test_score_empty():
    s = m.score([], [])
    assert s["n"] == 0 and s["accuracy_pct"] == 0.0


def test_acceptance_pass_within_tol():
    a = m.acceptance(67.0, 66.2, 1.0)
    assert a["status"] == "PASS" and a["within_tolerance"]


def test_acceptance_fail_real_regression():
    a = m.acceptance(67.0, 63.0, 1.0)
    assert a["status"] == "FAIL" and not a["collapse_suspected"]


def test_acceptance_collapse_flagged():
    # int4 near chance while bf16 high -> mask-collapse signature.
    a = m.acceptance(70.0, 25.0, 1.0)
    assert a["status"] == "COLLAPSE_SUSPECTED" and a["collapse_suspected"]


def test_acceptance_improvement_within_tol_passes():
    # int4 slightly ABOVE bf16 (noise) is still within tolerance -> PASS.
    a = m.acceptance(66.0, 66.5, 1.0)
    assert a["status"] == "PASS"


def test_dry_run_cells_schema():
    bf = m._run_cell_dry("bf16", m._BUILTIN_QA)
    pr = m._run_cell_dry("protected", m._BUILTIN_QA)
    for s in (bf, pr):
        assert {"n", "correct", "unparsed", "accuracy_pct", "cell"} <= set(s)
    assert bf["accuracy_pct"] == 100.0


def test_script_selftest_runs():
    assert m._selftest() == 0


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  {name}: PASS")
        except AssertionError as e:
            failed += 1
            print(f"  {name}: FAIL — {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
