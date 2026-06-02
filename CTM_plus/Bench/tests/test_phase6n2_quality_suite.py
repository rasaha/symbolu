#!/usr/bin/env python3
# Phase 6N.2 — CPU regression for the extended quality suite scorers.
#
# Tests the pure scoring/diagnostic functions (MMLU agreement, HumanEval
# completion extraction, LongBench token-F1, acceptance gate) with fixtures
# distinct from the script's --selftest. No torch/vllm/GPU/dataset/execution.
#
# Run:  python CTM_plus/Bench/tests/test_phase6n2_quality_suite.py

import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

import bench_phase6n2_quality_suite as m


def test_agreement_identical():
    ag = m.mmlu_agreement([0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3])
    assert ag["agreement_pct"] == 100.0 and ag["net_flips"] == 0


def test_agreement_catches_compensating_flips():
    # Same AGGREGATE accuracy (both 2/4) but different answers -> agreement < 100.
    # bf16: right on q0,q1; int4: right on q2,q3 -> agg equal, agreement 0%.
    bf = [0, 1, 9, 9]   # right, right, wrong, wrong  (ans 0,1,2,3)
    it = [9, 9, 2, 3]   # wrong, wrong, right, right
    ag = m.mmlu_agreement(bf, it, [0, 1, 2, 3])
    assert ag["agreement_pct"] == 0.0
    assert ag["bf16_right_int4_wrong"] == 2 and ag["bf16_wrong_int4_right"] == 2
    assert ag["net_flips"] == 0   # aggregate identical, but fidelity is NOT


def test_humaneval_extract_stops_at_next_def():
    prompt = "def f(x):\n    \"\"\"d\"\"\"\n"
    raw = prompt + "    return x*2\n\ndef g():\n    pass\n"
    full = m.extract_completion(prompt, raw)
    assert "return x*2" in full and "def g" not in full


def test_humaneval_extract_handles_echoed_prompt():
    prompt = "def f(x):\n"
    raw = "def f(x):\n    return 1\n"   # model echoed prompt
    full = m.extract_completion(prompt, raw)
    assert full.count("def f(x):") == 1   # not duplicated


def test_token_f1_strips_articles():
    assert abs(m.token_f1("the cat", "cat") - 1.0) < 1e-9


def test_token_f1_no_overlap():
    assert m.token_f1("dog", "cat") == 0.0


def test_token_f1_partial():
    f = m.token_f1("paris is in france", "paris france")
    assert 0.0 < f < 1.0


def test_longbench_max_over_answers():
    # exact match to one acceptable answer -> 1.0
    assert abs(m.longbench_score("Paris", ["London", "Paris"]) - 1.0) < 1e-9


def test_acceptance_pass_requires_both_tol_and_agreement():
    a = m.acceptance("mmlu", 63.5, 63.5, 99.0, 1.0, 95.0)
    assert a["status"] == "PASS"


def test_acceptance_parity_but_low_agreement_fails():
    # The whole point of the diagnostic: identical aggregate, low agreement -> FAIL.
    a = m.acceptance("mmlu", 63.5, 63.5, 80.0, 1.0, 95.0)
    assert a["status"] == "FAIL" and not a["agreement_ok"]


def test_acceptance_regression_fails():
    a = m.acceptance("humaneval", 60.0, 55.0, None, 1.0, 95.0)
    assert a["status"] == "FAIL"


def test_acceptance_collapse_flagged():
    a = m.acceptance("mmlu", 65.0, 25.0, 28.0, 1.0, 95.0)
    assert a["status"] == "COLLAPSE_SUSPECTED"


def test_acceptance_no_agreement_data_uses_tol_only():
    # humaneval generate-only may have None agreement on score; tol still applies.
    a = m.acceptance("longbench", 50.0, 49.5, None, 1.0, 95.0)
    assert a["status"] == "PASS"


def test_dry_run_all_evals_schema():
    for ev in ("mmlu", "humaneval", "longbench"):
        r = m._run_eval_dry(ev, 8)
        assert r["eval"] == ev and "cells" in r and "bf16" in r["cells"]


def test_score_eval_empty_items_no_zerodivision():
    # Regression: an empty dataset load must NOT ZeroDivisionError (it did on a
    # live LongBench run where the loader returned 0 items). Should return a
    # clean error dict instead.
    r = m._score_eval("longbench", [], {"bf16": [], "protected": []}, False)
    assert r["n"] == 0 and "error" in r


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
