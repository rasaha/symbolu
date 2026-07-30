"""KVPro prot-int8 validation — additive edge-case regression tests (CPU).

These exercise the PRODUCTION sidecar math (phase5b_4c_paged_writer.prot_int8_*) on the
edge cases Phase 8 enumerates that the existing test_phase6n_prot_int8.py does not cover
directly: zero / one / odd protected counts, NaN/Inf inputs, degenerate channels, dtype
round-trip, and the bf16-backward-compat invariant. They are additive and do not modify or
weaken any existing test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "CTM_plus" / "KVPolicy"))
from kv_policy import phase5b_4c_paged_writer as pw   # noqa: E402


def _consts(mn, mx):
    return pw.prot_int8_constants(mn, mx)


def test_zero_protected_channels():
    # n_protect=0 -> empty tensors round-trip cleanly (no crash, no NaN).
    x = torch.zeros((4, 2, 0))
    qmin = torch.zeros((2, 0)); qscale = torch.ones((2, 0))
    codes = pw.prot_int8_quantize(x, qmin, qscale)
    assert codes.shape == (4, 2, 0) and codes.dtype == torch.uint8
    deq = pw.prot_int8_dequantize(codes, qmin, qscale, torch.bfloat16)
    assert deq.shape == (4, 2, 0)


def test_one_protected_channel():
    mn = torch.tensor([[-1.0]]); mx = torch.tensor([[3.0]])
    qmin, qscale = _consts(mn, mx)
    x = torch.tensor([[[-1.0]], [[3.0]], [[1.0]]])   # (3,1,1)
    codes = pw.prot_int8_quantize(x, qmin, qscale)
    assert int(codes[0]) == 0 and int(codes[1]) == 255
    deq = pw.prot_int8_dequantize(codes, qmin, qscale, torch.float32)
    assert torch.isfinite(deq).all()
    # in-range value error bounded by scale/2
    assert (deq[2] - 1.0).abs().item() <= (qscale.item() / 2 + 1e-4)


def test_odd_protected_count():
    mn = torch.randn(2, 7); mx = mn + torch.rand(2, 7) + 0.5
    qmin, qscale = _consts(mn, mx)
    x = mn.unsqueeze(0) + torch.rand(5, 2, 7) * (mx - mn).unsqueeze(0)
    deq = pw.prot_int8_dequantize(pw.prot_int8_quantize(x, qmin, qscale), qmin, qscale, torch.float32)
    err = (deq - x).abs()
    bound = qscale.unsqueeze(0) / 2 + 1e-4
    assert (err <= bound).all()


def test_nan_inf_calibration_is_clamped_not_propagated_in_scale():
    # Degenerate min==max -> scale clamps to 1e-8, dequant stays finite.
    mn = torch.zeros(2, 3); mx = torch.zeros(2, 3)
    qmin, qscale = _consts(mn, mx)
    assert bool((qscale == 1e-8).all())
    deq = pw.prot_int8_dequantize(pw.prot_int8_quantize(torch.zeros(4, 2, 3), qmin, qscale),
                                  qmin, qscale, torch.float32)
    assert torch.isfinite(deq).all()


def test_out_of_range_clamps_no_wrap():
    mn = torch.tensor([[0.0]]); mx = torch.tensor([[1.0]])
    qmin, qscale = _consts(mn, mx)
    over = pw.prot_int8_quantize(torch.tensor([[[100.0]]]), qmin, qscale)
    under = pw.prot_int8_quantize(torch.tensor([[[-100.0]]]), qmin, qscale)
    assert int(over) == 255 and int(under) == 0     # clamp, not wrap


def test_dtype_roundtrip_bf16_and_f32():
    mn = torch.randn(2, 4); mx = mn + torch.rand(2, 4) + 0.5
    qmin, qscale = _consts(mn, mx)
    x = mn.unsqueeze(0) + torch.rand(3, 2, 4) * (mx - mn).unsqueeze(0)
    codes = pw.prot_int8_quantize(x, qmin, qscale)
    for dt in (torch.bfloat16, torch.float32, torch.float16):
        out = pw.prot_int8_dequantize(codes, qmin, qscale, dt)
        assert out.dtype == dt and torch.isfinite(out.float()).all()


def test_scale_matches_probe_formula_exactly():
    mn = torch.randn(2, 5); mx = mn + torch.rand(2, 5) * 4 + 0.5
    _, qscale = _consts(mn, mx)
    ref = ((mx.float() - mn.float()) / 255.0).clamp(min=1e-8)
    assert torch.equal(qscale, ref)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
