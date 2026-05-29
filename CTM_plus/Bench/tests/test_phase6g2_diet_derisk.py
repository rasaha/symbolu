#!/usr/bin/env python3
# Phase 6G.2 — CPU regression for the sidecar-diet de-risk analyzer.
#
# Guards the pure-Python decision core (linear regression from sufficient
# statistics + the predicted-xmin / symmetric-V verdicts + the model rollup)
# against hand-computed cases, independent of the script's own --selftest
# synthetic data. Torch-free; runs anywhere (the GPU pod runs --capture).
#
# Run:  python CTM_plus/Bench/tests/test_phase6g2_diet_derisk.py
#       (also pytest-collectable)

import math
import sys
from pathlib import Path

_SCR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCR) not in sys.path:
    sys.path.insert(0, str(_SCR))

import phase6g2_sidecar_diet_derisk as m  # noqa: E402


def _sums(xs, ys):
    n = len(xs)
    return [n, sum(xs), sum(ys), sum(x * x for x in xs),
            sum(x * y for x, y in zip(xs, ys)), sum(y * y for y in ys)]


def test_linreg_matches_hand_computation():
    # y = 3x + 1 exactly.
    xs = [0.0, 1.0, 2.0, 3.0]
    ys = [3.0 * x + 1.0 for x in xs]
    a, b, r2, rr, mx = m.linreg_from_sums(*_sums(xs, ys))
    assert abs(a - 3.0) < 1e-9
    assert abs(b - 1.0) < 1e-9
    assert abs(r2 - 1.0) < 1e-9
    assert rr < 1e-9
    assert abs(mx - 1.5) < 1e-9


def test_linreg_known_r2():
    # A noisy set with a closed-form R² we can check independently.
    xs = [1.0, 2.0, 3.0, 4.0]
    ys = [1.0, 3.0, 2.0, 5.0]
    a, b, r2, rr, mx = m.linreg_from_sums(*_sums(xs, ys))
    # Hand: Var(x)=1.25, Cov=1.375, Var(y)=2.1875 -> r2 = cov²/(vx·vy)
    expect = (1.375 ** 2) / (1.25 * 2.1875)
    assert abs(r2 - expect) < 1e-9, (r2, expect)


def test_inflation_closed_form():
    # infl = 2·absmax/(max−min). Centered -> 1; offset by half-range -> 1.5.
    assert abs(2.0 * 2.0 / (2.0 - -2.0) - 1.0) < 1e-12
    assert abs(2.0 * 3.0 / (3.0 - -1.0) - 1.5) < 1e-12


def test_predicted_xmin_green_and_red():
    scales = [0.1 * i for i in range(1, 41)]
    tight = [-9.0 * s for s in scales]               # exact law -> GREEN
    assert m.predicted_xmin_unit(_sums(scales, tight))["verdict"] == "GREEN"
    noisy = [(-9.0 * s) + 3.0 * ((i * 7) % 11 - 5) for i, s in enumerate(scales)]
    assert m.predicted_xmin_unit(_sums(scales, noisy))["verdict"] == "RED"


def test_dead_channel_is_green():
    u = m.predicted_xmin_unit(_sums([0.0] * 8, [0.0] * 8))
    assert u["dead"] is True
    assert u["verdict"] == "GREEN"


def test_symmetric_v_thresholds():
    assert m.symmetric_v_unit(1.0 * 50, 1.0 * 50, 1.04, 50)["verdict"] == "GREEN"
    assert m.symmetric_v_unit(1.2 * 50, 1.5 * 50, 1.5, 50)["verdict"] == "YELLOW"
    assert m.symmetric_v_unit(1.9 * 50, 3.7 * 50, 2.0, 50)["verdict"] == "RED"


def test_rollup_one_red_blocks_green():
    greens = [{"verdict": "GREEN"}] * 99
    assert m._rollup(greens)["verdict"] == "GREEN"
    # A single RED in 100 units (1%) downgrades GREEN -> YELLOW (not GREEN).
    assert m._rollup(greens + [{"verdict": "RED"}])["verdict"] == "YELLOW"
    # 10% RED -> RED.
    mixed = [{"verdict": "GREEN"}] * 90 + [{"verdict": "RED"}] * 10
    assert m._rollup(mixed)["verdict"] == "RED"


def test_percentile_interpolation():
    s = [1.0, 2.0, 3.0, 4.0]
    assert abs(m._pct(s, 0.0) - 1.0) < 1e-12
    assert abs(m._pct(s, 1.0) - 4.0) < 1e-12
    assert abs(m._pct(s, 0.5) - 2.5) < 1e-12


def test_save_gb_constants():
    # Tie the recovered-GB claims to the Phase 6G inventory.
    assert m.SAVE_GB["predicted_xmin"] == 1.30   # k_xmin + v_xmin
    assert m.SAVE_GB["symmetric_v"] == 0.65      # v_xmin only


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
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'} "
          f"({len(tests) - failed}/{len(tests)})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
