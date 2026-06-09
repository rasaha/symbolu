#!/usr/bin/env python3
# CPU regression for the learned-rotation rotatability probe
# (Bench/scripts/kv_qat_learned_rotation.py). numpy-only; no torch/GPU.
#
# Guards the science the probe relies on:
#   * the Cayley/Stiefel optimizer keeps R orthogonal and the 4th-moment loss descends;
#   * it correctly labels CHANNEL-axis anisotropy "rotatable" and ROW/spectral
#     anisotropy "not_rotatable" (failure-mode #1) -- the whole point of the probe;
#   * the rotated round-trip un-rotate is exact (orthogonality).

import sys
from pathlib import Path

import numpy as np

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import kv_qat_learned_rotation as LR  # noqa: E402


def test_selftest_gates_pass():
    assert LR.selftest() == 0


def test_channel_aniso_is_rotatable():
    rng = np.random.default_rng(1)
    cs = np.ones(16); cs[0] = 10.0; cs[1] = 6.0
    K = rng.standard_normal((2000, 16)) * cs
    s = LR.compare_schemes(K, seed=1)
    assert s["verdict"]["label"] in ("rotatable", "partial")
    assert s["learned_pt"] < s["random_pt"]          # learned beats data-oblivious random
    assert s["learned_pt"] < s["unrotated_pt"]        # and beats no rotation


def test_row_aniso_is_not_rotatable():
    rng = np.random.default_rng(1)
    K = rng.standard_normal((2000, 16)); K[:20] *= 15.0
    s = LR.compare_schemes(K, seed=1)
    assert s["verdict"]["label"] == "not_rotatable"   # rotation can't fix row/spectral peaks
    # learned ~ unrotated: rotation gives essentially no per-tensor improvement here
    assert abs(s["learned_pt"] - s["unrotated_pt"]) / s["unrotated_pt"] < 0.05


def test_optimizer_keeps_orthogonal_and_descends():
    rng = np.random.default_rng(0)
    K = rng.standard_normal((500, 8)) * np.array([5, 1, 1, 1, 1, 1, 1, 1.0])
    R, m0, m1 = LR.learn_rotation(K, seed=0)
    assert np.linalg.norm(R.T @ R - np.eye(8)) < 1e-6
    assert m1 < m0


def test_rotated_round_trip_unrotate_exact():
    rng = np.random.default_rng(0)
    K = rng.standard_normal((64, 16))
    R = np.linalg.qr(rng.standard_normal((16, 16)))[0]
    # at high bits the rotated per-tensor round-trip ~ identity (orthogonality holds)
    Kh = LR.rotated_per_tensor_round_trip(K, R, bits=12)
    assert LR.rel_err(K, Kh) < 0.03


if __name__ == "__main__":
    rc = LR.selftest()
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"  [PASS] {name}")
    print("\nstandalone: ALL PASS" if rc == 0 else "\nselftest FAIL")
    raise SystemExit(rc)
