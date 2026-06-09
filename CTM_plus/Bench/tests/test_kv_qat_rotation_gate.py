#!/usr/bin/env python3
# CPU regression for the learned-rotation hard-tail GATE
# (Bench/scripts/kv_qat_rotation_gate.py). numpy-only; the 3-arm model run is pod-only.
#
# Guards the injection math + the gate decision logic:
#   * rotated Q & K (post-RoPE, same per-head R) preserve attention EXACTLY;
#   * the rotated + per-tensor-quant K path -> exact as bits grow;
#   * the gate compares arm3 to per-channel+PROTECT (the bar), with bf16 as the
#     1.0 reference, NOT the bar (the key correction vs the external "98% of bf16").

import sys
from pathlib import Path

import numpy as np

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import kv_qat_rotation_gate as G  # noqa: E402


def test_selftest_gates_pass():
    assert G.selftest() == 0


def test_rotation_preserves_attention_exactly():
    rng = np.random.default_rng(3)
    H, T, D = 4, 16, 64
    q, k = rng.standard_normal((H, T, D)), rng.standard_normal((H, T, D))
    R = np.stack([np.linalg.qr(rng.standard_normal((D, D)))[0] for _ in range(H)])
    base = G.attn_scores(q, k)
    rot = G.attn_scores(G.rotate_per_head(q, R), G.rotate_per_head(k, R))
    assert np.abs(rot - base).max() < 1e-9


def test_pertensor_quant_path_converges_with_bits():
    rng = np.random.default_rng(4)
    H, T, D = 2, 16, 64
    q, k = rng.standard_normal((H, T, D)), rng.standard_normal((H, T, D))
    R = np.stack([np.linalg.qr(rng.standard_normal((D, D)))[0] for _ in range(H)])
    qr = G.rotate_per_head(q, R)
    base = G.attn_scores(qr, G.rotate_per_head(k, R))
    e4 = np.abs(G.attn_scores(qr, G.arm3_k_path(k, R, 4)) - base).max()
    e12 = np.abs(G.attn_scores(qr, G.arm3_k_path(k, R, 12)) - base).max()
    assert e12 < e4


def test_gate_bar_is_protect_not_bf16():
    # learned 0.75 vs protect 0.74 -> PASS even though bf16 is 1.0
    assert G.gate_verdict(1.0, 0.74, 0.75)["verdict"] == "PASS"
    # learned 0.60 loses the hard tail vs protect 0.74 -> FAIL
    assert G.gate_verdict(1.0, 0.74, 0.60)["verdict"] == "FAIL"
    # noise within margin still passes
    assert G.gate_verdict(1.0, 0.74, 0.735)["verdict"] == "PASS"


if __name__ == "__main__":
    rc = G.selftest()
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"  [PASS] {name}")
    print("\nstandalone: ALL PASS" if rc == 0 else "\nselftest FAIL")
    raise SystemExit(rc)
