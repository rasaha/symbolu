#!/usr/bin/env python3
# Phase 6L — CPU regression for the capacity instrumentation analysis layer.
#
# Independently verifies the four core claims of the Phase 6L analysis (with
# different data from the --selftest).  No torch/vllm; runs anywhere.
#
# Run:  python CTM_plus/Bench/tests/test_phase6l_capacity_demo.py
#       (also pytest-collectable)

import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

import phase6l_capacity_demo as m


def _row(cell, B, completed=None, oom=False, preempts=0, slot_x=False,
         peak_live=None, peak_util_pct=None, total_blocks=1000,
         max_concurrency=None, hbm_gb=None, agg_tps=None):
    pu = (peak_util_pct / 100.0) if peak_util_pct is not None else None
    sat = bool((pu or 0) >= 0.90 or preempts > 0 or oom)
    return {
        "cell": cell, "batch": B,
        "completed": completed if completed is not None else B,
        "oom": oom, "preempts": preempts, "slot_exhausted": slot_x,
        "peak_live": peak_live, "peak_util": pu,
        "saturation_observed": sat, "total_blocks": total_blocks,
        "max_concurrency": max_concurrency, "hbm_gb": hbm_gb, "agg_tps": agg_tps,
        "error": None,
    }


def test_ceiling_not_reached_low_util():
    # A run where the largest B completed cleanly at 55% utilization.
    rows = [_row("bf16", 96, peak_live=96, peak_util_pct=55.0)]
    assert m._ceiling_not_reached(rows)
    assert m._demonstrated_live(rows) is None


def test_ceiling_reached_high_util():
    rows = [_row("bf16", 96, peak_live=54, peak_util_pct=94.0, preempts=2)]
    assert not m._ceiling_not_reached(rows)
    assert m._demonstrated_live(rows) == 54


def test_submitted_b_exceeds_demonstrated_live():
    # B=160 submitted, but only 58 ran resident simultaneously.
    rows = [_row("bf16", 160, completed=160, peak_live=58,
                 peak_util_pct=96.0, preempts=5)]
    dem = m._demonstrated_live(rows)
    assert dem == 58
    assert dem < 160


def test_demonstrated_density_ratio_uses_live_not_submitted_b():
    rows = [
        _row("bf16",      160, peak_live=55, peak_util_pct=95.0, preempts=3,
             total_blocks=1000),
        _row("protected", 160, peak_live=99, peak_util_pct=93.0, preempts=1,
             total_blocks=900),
    ]
    a = m._phase6l_analyze(rows)
    # bf16 seq_per_kblock = 55/1.0 = 55; prot = 99/0.9 = 110; ratio = 2.0x
    assert a["by_cell"]["bf16"]["demonstrated_live"] == 55
    assert a["by_cell"]["protected"]["demonstrated_live"] == 99
    assert a["demonstrated_density_ratio"] is not None
    assert abs(a["demonstrated_density_ratio"] - 2.0) < 0.01
    # Submitted B was equal (160/160=1.0x) — ratio must differ significantly.
    assert abs(a["demonstrated_density_ratio"] - 1.0) > 0.5


def test_claim_demonstrated_in_window():
    rows = [
        _row("bf16",      128, peak_live=55, peak_util_pct=95.0, preempts=2,
             total_blocks=1000),
        _row("protected", 192, peak_live=95, peak_util_pct=92.0, preempts=1,
             total_blocks=900),
    ]
    a = m._phase6l_analyze(rows)
    # ratio ≈ (95/0.9)/(55/1.0) ≈ 105.6/55 ≈ 1.92×  → in [1.5, 2.5] → DEMONSTRATED
    assert a["claim_demonstrated"]
    assert a["claim_status"] == "DEMONSTRATED"


def test_claim_not_demonstrated_outside_window():
    # protected has similar live seqs but far fewer blocks -> ratio < 1.5.
    rows = [
        _row("bf16",      64, peak_live=55, peak_util_pct=95.0, preempts=1,
             total_blocks=1000),
        _row("protected", 64, peak_live=52, peak_util_pct=97.0, preempts=2,
             total_blocks=800),
    ]
    # ratio = (52/0.8)/(55/1.0) = 65/55 ≈ 1.18× → outside [1.5, 2.5]
    a = m._phase6l_analyze(rows)
    assert not a["claim_demonstrated"]
    assert a["claim_status"] == "MEASURED_OUTSIDE_WINDOW"


def test_ceiling_not_reached_blocks_demonstration():
    # Both cells submitted large B but never pressured the pool.
    rows = [
        _row("bf16",      200, peak_live=200, peak_util_pct=60.0),
        _row("protected", 200, peak_live=200, peak_util_pct=58.0),
    ]
    a = m._phase6l_analyze(rows)
    assert "CEILING_NOT_REACHED" in a["claim_status"]
    assert a["demonstrated_density_ratio"] is None
    assert not a["claim_demonstrated"]


def test_invalid_slot_exhaustion():
    rows = [_row("protected", 64, slot_x=True, peak_live=40, peak_util_pct=70.0)]
    a = m._phase6l_analyze(rows)
    assert a["claim_status"] == "INVALID_SLOT_EXHAUSTION"
    assert not a["claim_demonstrated"]


def test_selftest_passes():
    assert m._selftest() == 0


def main():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'} "
          f"({len(tests) - failed}/{len(tests)})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
