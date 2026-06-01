#!/usr/bin/env python3
# Phase 6M.6 — CPU regression for the hardware (newer-silicon) analyzer.
#
# Independently exercises the compute-vs-bandwidth axis attribution and the
# report.json ingestion. No torch/vllm/GPU; runs anywhere — the CPU-side half
# of Test 2 of the throughput-recovery plan.
#
# Run:  python CTM_plus/Bench/tests/test_phase6m6_hardware.py
#       (also pytest-collectable)

import json
import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

import analyze_phase6m6_hardware as m

_TH = dict(material_abs=0.03, material_rel=0.10)


def _g(agg, per_seq=0.11, density=1.83, prot=117.0):
    return {"agg_ratio": agg, "per_seq_ratio": per_seq, "density_ratio": density,
            "protected_agg_tps": prot, "bf16_agg_tps": 530.0,
            "per_seq_slowdown_x": 9.0, "mml": 8192}


def test_compute_axis_when_h100_improves_and_compute_bound():
    pg = {"A100": _g(0.22), "H100": _g(0.41), "H200": _g(0.47)}
    head, _ = m.attribute_axis(pg, "A100", m.V_COMPUTE, **_TH)
    assert head.startswith("COMPUTE axis")


def test_bandwidth_axis_when_only_h200_improves():
    pg = {"A100": _g(0.22), "H100": _g(0.225), "H200": _g(0.40)}
    head, _ = m.attribute_axis(pg, "A100", m.V_COMPUTE, **_TH)
    assert head.startswith("BANDWIDTH axis")
    assert "NOT H100" in head


def test_structural_when_no_improvement():
    pg = {"A100": _g(0.22), "H100": _g(0.225), "H200": _g(0.23)}
    head, _ = m.attribute_axis(pg, "A100", m.V_COMPUTE, **_TH)
    assert head.startswith("STRUCTURAL") and "STOP" in head


def test_bandwidth_caution_when_h100_improves_but_bw_verdict():
    pg = {"A100": _g(0.22), "H100": _g(0.45)}
    head, _ = m.attribute_axis(pg, "A100", m.V_BW_UNCOALESCED, **_TH)
    assert head.startswith("BANDWIDTH axis (caution)")


def test_confounded_without_verdict():
    pg = {"A100": _g(0.22), "H100": _g(0.40)}
    head, _ = m.attribute_axis(pg, "A100", m.V_UNKNOWN, **_TH)
    assert head.startswith("CONFOUNDED")


def test_relative_threshold_gates_tiny_gain():
    # +0.02 absolute on a 0.22 base = 9% relative < 10% -> not material.
    pg = {"A100": _g(0.22), "H100": _g(0.24)}
    head, _ = m.attribute_axis(pg, "A100", m.V_COMPUTE, **_TH)
    assert head.startswith("STRUCTURAL")


def test_load_report_extracts_headline(tmp_path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({
        "mml": 8192,
        "throughput": {"aggregate_tps_ratio": 0.22, "protected_agg_tps": 117.0,
                       "bf16_agg_tps": 530.0, "per_seq_tps_ratio": 0.11,
                       "per_seq_slowdown_x": 9.0},
        "density": {"demonstrated_density_ratio": 1.83},
    }))
    r = m.load_report(p)
    assert abs(r["agg_ratio"] - 0.22) < 1e-9
    assert abs(r["density_ratio"] - 1.83) < 1e-9
    assert abs(r["protected_agg_tps"] - 117.0) < 1e-9


def test_load_report_density_fallback_to_analysis(tmp_path):
    # Older report.json may carry density ratio only under analysis.
    p = tmp_path / "r.json"
    p.write_text(json.dumps({
        "mml": 8192,
        "throughput": {"aggregate_tps_ratio": 0.22},
        "analysis": {"demonstrated_density_ratio": 1.9},
    }))
    r = m.load_report(p)
    assert abs(r["density_ratio"] - 1.9) < 1e-9


def test_norm_gpu_family_match():
    assert m._norm_gpu("h200-141gb") == "H200"
    assert m._norm_gpu("NVIDIA H100 80GB HBM3") == "H100"
    assert m._norm_gpu("A100-80GB") == "A100-80GB"


def test_missing_baseline_ratio_is_inconclusive():
    pg = {"A100": _g(None), "H100": _g(0.40)}
    head, _ = m.attribute_axis(pg, "A100", m.V_COMPUTE, **_TH)
    assert head.startswith("INCONCLUSIVE")


def test_full_report_renders(tmp_path):
    pg = {"A100": _g(0.22), "H100": _g(0.41), "H200": _g(0.47)}
    order = ["A100", "H100", "H200"]
    head, detail = m.attribute_axis(pg, "A100", m.V_COMPUTE, **_TH)
    txt = m.build_report(pg, order, "A100", m.V_COMPUTE, head, detail)
    assert "Phase 6M.6" in txt and "AXIS ATTRIBUTION" in txt
    assert "H200" in txt


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
