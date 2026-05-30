#!/usr/bin/env python3
# Phase 6M.5 — CPU regression for the roofline (ncu SpeedOfLight) analyzer.
#
# Independently exercises the bound-classifier on synthesized ncu CSVs (the
# script's own --selftest uses different fixtures). No torch/vllm/ncu; runs
# anywhere — this is the CPU-side half of Test 1 of the throughput-recovery plan.
#
# Run:  python CTM_plus/Bench/tests/test_phase6m5_roofline.py
#       (also pytest-collectable)

import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

import analyze_phase6m5_roofline as m


def _csv(tmp_path, name, *, sm, dram, mem=None, occ=50, sectors=30,
         kernel="flash_fwd_kvcache_int4"):
    """Write a minimal ncu-style CSV with one kernel and the SoL metrics."""
    mem = mem if mem is not None else max(sm, dram)
    p = tmp_path / name
    lines = ['"Kernel Name","Section Name","Metric Name","Metric Unit","Metric Value"']
    rows = [
        ("GPU Speed Of Light Throughput", "Compute (SM) Throughput", "%", sm),
        ("GPU Speed Of Light Throughput", "DRAM Throughput", "%", dram),
        ("GPU Speed Of Light Throughput", "Memory Throughput", "%", mem),
        ("Occupancy", "Achieved Occupancy", "%", occ),
        ("Memory Workload Analysis", "L2 Sectors/Req", "", sectors),
    ]
    for sec, mname, unit, val in rows:
        lines.append(f'"{kernel}","{sec}","{mname}","{unit}","{val}"')
    p.write_text("\n".join(lines) + "\n")
    return p


def _verdict(tmp_path, **kw):
    p = _csv(tmp_path, "k.csv", **kw)
    parsed = m.parse_ncu_csv(p)
    kname = m.pick_kernel(parsed, "int4")
    return m.classify(m.resolve_fields(parsed[kname]), dict(m.DEFAULTS))[0]


def test_compute_bound(tmp_path):
    assert _verdict(tmp_path, sm=85, dram=25, sectors=30) == m.V_COMPUTE


def test_bandwidth_uncoalesced(tmp_path):
    # DRAM leads, but scattered gather drives sectors/req low.
    assert _verdict(tmp_path, sm=38, dram=70, sectors=3) == m.V_BW_UNCOALESCED


def test_bandwidth_coalesced_saturated(tmp_path):
    assert _verdict(tmp_path, sm=40, dram=97, sectors=31) == m.V_BW_COALESCED


def test_occupancy_bound(tmp_path):
    assert _verdict(tmp_path, sm=20, dram=15, occ=12, sectors=30) == m.V_OCCUPANCY


def test_mixed_when_no_clean_winner(tmp_path):
    # SM 55 < compute floor 60; DRAM 55 < bandwidth floor 60 -> neither clean,
    # but both above the idle ceiling (50) -> MIXED.
    assert _verdict(tmp_path, sm=55, dram=55, sectors=30) == m.V_MIXED


def test_missing_sol_section_is_mixed(tmp_path):
    p = tmp_path / "noSoL.csv"
    p.write_text('"Kernel Name","Metric Name","Metric Unit","Metric Value"\n'
                 '"k","L2 Hit Rate","%","50"\n')
    parsed = m.parse_ncu_csv(p)
    v = m.classify(m.resolve_fields(parsed["k"]), dict(m.DEFAULTS))[0]
    assert v == m.V_MIXED


def test_parser_handles_prof_banner(tmp_path):
    # ncu prepends ==PROF== banner lines before the CSV header.
    p = tmp_path / "banner.csv"
    p.write_text(
        "==PROF== Connected to process 999\n"
        "==PROF== Profiling \"kernel\" - 0: 0%\n"
        '"Kernel Name","Metric Name","Metric Unit","Metric Value"\n'
        '"flash_fwd_int4","Compute (SM) Throughput","%","82"\n'
        '"flash_fwd_int4","DRAM Throughput","%","30"\n')
    parsed = m.parse_ncu_csv(p)
    assert "flash_fwd_int4" in parsed
    f = m.resolve_fields(parsed["flash_fwd_int4"])
    assert abs(f["sm_pct"] - 82) < 1e-6
    assert abs(f["dram_pct"] - 30) < 1e-6


def test_median_over_invocations(tmp_path):
    p = tmp_path / "multi.csv"
    p.write_text(
        '"Kernel Name","Metric Name","Metric Unit","Metric Value"\n'
        '"k","Compute (SM) Throughput","%","90"\n'
        '"k","Compute (SM) Throughput","%","50"\n'
        '"k","Compute (SM) Throughput","%","70"\n')
    f = m.resolve_fields(m.parse_ncu_csv(p)["k"])
    assert abs(f["sm_pct"] - 70.0) < 1e-6


def test_pick_kernel_by_substr(tmp_path):
    p = tmp_path / "two.csv"
    p.write_text(
        '"Kernel Name","Metric Name","Metric Unit","Metric Value"\n'
        '"elementwise_kernel","Compute (SM) Throughput","%","10"\n'
        '"elementwise_kernel","Duration","ns","100"\n'
        '"flash_fwd_kvcache_int4","Compute (SM) Throughput","%","80"\n'
        '"flash_fwd_kvcache_int4","Duration","ns","9000"\n')
    parsed = m.parse_ncu_csv(p)
    assert m.pick_kernel(parsed, "kvcache") == "flash_fwd_kvcache_int4"
    # No substr -> longest-duration kernel.
    assert m.pick_kernel(parsed, None) == "flash_fwd_kvcache_int4"


def test_script_selftest_runs():
    # The script's bundled --selftest must stay green.
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
