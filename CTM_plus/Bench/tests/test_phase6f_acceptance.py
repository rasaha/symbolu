#!/usr/bin/env python3
# Phase 6F — CPU regression for the read-path-fusion acceptance analyzer.
#
# Exercises the gather/copy name-matched A/B + acceptance verdict on synthesized
# profiler CSVs. No torch/vllm/GPU; runs anywhere — the CPU-testable half of the
# Test 3 prep (the CUDA kernel itself is NOT implemented and is gated on Test 1).
#
# Run:  python CTM_plus/Bench/tests/test_phase6f_acceptance.py
#       (also pytest-collectable)

import csv
import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

import analyze_phase6f_acceptance as m

_INC, _EXC = m.DEFAULT_GATHER_COPY, m.DEFAULT_EXCLUDE
_AF, _RT = m.DEFAULT_ACCEPT_FRACTION, m.DEFAULT_REGRESS_TOL


def _csv(path, rows):
    """rows = [(name, total_us, instances)] -> profiler CSV (Total Time in ns)."""
    total_us = sum(r[1] for r in rows) or 1.0
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "Time(%)", "Total Time", "Instances", "Avg", "Min", "Max",
            "StdDev", "Name"])
        w.writeheader()
        for name, us, inst in rows:
            w.writerow({"Time(%)": f"{us/total_us*100:.2f}",
                        "Total Time": str(int(us * 1000)), "Instances": str(inst),
                        "Avg": "0", "Min": "0", "Max": "0", "StdDev": "0",
                        "Name": name})


# Baseline: gather/copy = (index 200 + copy 100) / 1000 = 30%.
_BEFORE = [("ampere_gemm", 600.0, 100),
           ("at::native::index_elementwise", 200.0, 5000),
           ("aten::copy_", 100.0, 4000),
           ("flash::fwd_kernel_int4", 100.0, 28)]


def _an(before_rows, after_rows, tmp_path):
    b, a = tmp_path / "b.csv", tmp_path / "a.csv"
    _csv(b, before_rows)
    _csv(a, after_rows)
    return m.analyze(b, a, _INC, _EXC, _AF, _RT)


def test_accepted_when_share_collapses(tmp_path):
    r = _an(_BEFORE, [("ampere_gemm", 600.0, 100),
                      ("at::native::index_elementwise", 10.0, 200),
                      ("aten::copy_", 5.0, 100),
                      ("flash::fwd_kernel_int4", 180.0, 28)], tmp_path)
    assert r["accepted"] and r["share_ok"] and r["time_ok"]


def test_not_accepted_when_share_unchanged(tmp_path):
    r = _an(_BEFORE, [("ampere_gemm", 600.0, 100),
                      ("at::native::index_elementwise", 180.0, 4800),
                      ("aten::copy_", 90.0, 3800),
                      ("flash::fwd_kernel_int4", 110.0, 28)], tmp_path)
    assert not r["share_ok"] and not r["accepted"]


def test_not_accepted_when_time_regresses(tmp_path):
    r = _an(_BEFORE, [("ampere_gemm", 600.0, 100),
                      ("at::native::index_elementwise", 10.0, 200),
                      ("aten::copy_", 5.0, 100),
                      ("flash::fwd_kernel_int4", 900.0, 28)], tmp_path)
    assert r["share_ok"] and not r["time_ok"] and not r["accepted"]


def test_share_math(tmp_path):
    r = _an(_BEFORE, _BEFORE, tmp_path)
    assert abs(r["gather_copy_share_before"] - 0.30) < 1e-6
    assert abs(r["gather_copy_share_after"] - 0.30) < 1e-6
    assert not r["accepted"]   # identical -> no drop


def test_exclude_blocks_flash_copy_false_positive():
    # A 'copy' substring inside the attention kernel must NOT count as gather/copy.
    assert not m._is_gather_copy("flash_fwd_splitkv_copy_kernel", _INC, _EXC)
    assert m._is_gather_copy("aten::index_put_", _INC, _EXC)
    assert m._is_gather_copy("at::native::index_elementwise", _INC, _EXC)
    assert not m._is_gather_copy("ampere_sgemm_128x64", _INC, _EXC)


def test_missing_input_errors_no_crash(tmp_path):
    a = tmp_path / "a.csv"
    _csv(a, _BEFORE)
    r = m.analyze(tmp_path / "nope.csv", a, _INC, _EXC, _AF, _RT)
    assert "error" in r


def test_report_renders(tmp_path):
    r = _an(_BEFORE, [("ampere_gemm", 600.0, 100),
                      ("at::native::index_elementwise", 10.0, 200),
                      ("aten::copy_", 5.0, 100),
                      ("flash::fwd_kernel_int4", 180.0, 28)], tmp_path)
    txt = m.build_report(r)
    assert "ACCEPTANCE" in txt and "VERDICT: ACCEPTED" in txt
    # The correctness reminder must always be present (it's non-negotiable).
    assert "byte-eq" in txt and "COLLAPSE=0" in txt


def test_custom_match_substring(tmp_path):
    # Targeting only 'scatter' (not present) -> share 0 -> share_ok False.
    b, a = tmp_path / "b.csv", tmp_path / "a.csv"
    _csv(b, _BEFORE)
    _csv(a, _BEFORE)
    r = m.analyze(b, a, ("scatter",), _EXC, _AF, _RT)
    assert r["gather_copy_share_before"] == 0.0
    assert not r["share_ok"]


def test_script_selftest_runs():
    assert m._selftest() == 0


if __name__ == "__main__":
    import tempfile

    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            if fn.__code__.co_argcount:
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            print(f"  {name}: PASS")
        except AssertionError as e:
            failed += 1
            print(f"  {name}: FAIL — {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
