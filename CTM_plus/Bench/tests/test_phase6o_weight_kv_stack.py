#!/usr/bin/env python3
# Phase 6O — CPU regression for the weight×KV stacking analysis.
#
# Tests the pure accounting/verdict functions with fixtures distinct from the
# script's --selftest. No torch/vllm/GPU/AWQ-checkpoint.
#
# Run:  python CTM_plus/Bench/tests/test_phase6o_weight_kv_stack.py

import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

import bench_phase6o_weight_kv_stack as m


def _cells(awq_stack_weights=4.0):
    return {
        "bf16_bf16":     {"weights_gb": 14.25, "kv_budget_gb": 24.0, "total_gb": 14.25},
        "awq_bf16":      {"weights_gb": 4.0,   "kv_budget_gb": 24.0, "total_gb": 4.0},
        "bf16_int4prot": {"weights_gb": 14.25, "kv_budget_gb": 24.0, "total_gb": 14.25},
        "awq_int4prot":  {"weights_gb": awq_stack_weights, "kv_budget_gb": 24.0,
                          "total_gb": awq_stack_weights},
    }


def test_weight_saving_computed_vs_baseline():
    a = m.stacking_analysis(_cells())
    assert abs(a["weight_saving_awq_only_gb"] - 10.25) < 1e-6


def test_weight_saving_independent_of_kv_when_stack_clean():
    a = m.stacking_analysis(_cells(awq_stack_weights=4.0))
    assert a["weight_saving_independent_of_kv"] is True
    assert a["composes"] is True


def test_detects_broken_stack_weights_not_quantized():
    # stacked cell shows full weight size -> AWQ silently didn't apply with int4 KV.
    a = m.stacking_analysis(_cells(awq_stack_weights=14.25))
    assert a["weight_saving_independent_of_kv"] is False


def test_no_baseline_returns_note():
    a = m.stacking_analysis({"awq_bf16": {"weights_gb": 4.0, "kv_budget_gb": 24.0,
                                          "total_gb": 4.0}})
    assert "note" in a


def test_verdict_coexist_ok_and_stacks():
    a = m.stacking_analysis(_cells())
    v = m.verdict(a, list(m.CELLS))
    assert v["integration"].startswith("COEXIST_OK")
    assert v["composition"].startswith("STACKS")


def test_verdict_integration_failed_when_stack_cell_absent():
    a = m.stacking_analysis(_cells())
    v = m.verdict(a, ["bf16_bf16", "awq_bf16", "bf16_int4prot"])
    assert v["integration"].startswith("INTEGRATION_FAILED")


def test_verdict_does_not_stack_when_composes_false():
    a = m.stacking_analysis(_cells(awq_stack_weights=14.25))
    # composes will be False (saving < weight saving); but stack cell DID load.
    v = m.verdict(a, list(m.CELLS))
    assert v["composition"].startswith("DOES_NOT_STACK")


def test_cell_matrix_definitions():
    # The four corners must be exactly weights×kv.
    assert m.CELLS["awq_int4prot"] == {"weights": "awq", "kv": "int4_protected"}
    assert m.CELLS["bf16_bf16"] == {"weights": "bf16", "kv": "bf16"}


def test_dry_run_cells_load():
    for c in m.CELLS:
        r = m._run_cell_dry(c)
        assert r["loaded"] and "weights_gb" in r


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
