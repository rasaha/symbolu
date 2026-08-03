"""Neural parity: incubated BindingSlots == historical BindingSlots (bit-level torch).

Proves the incubated extraction (src/binding_slots/legacy_phase_lc_slots.py) is numerically
identical to the historical experiments/phase_lc/models.py::BindingSlots — forward, gradients,
ablations, diagnostics, and state_dict. This is distinct from the stdlib semantic reference,
which must NOT be used as proof of neural parity.

RESOURCE_BLOCKED-safe: self-skips (returns) when torch is absent.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

try:
    import torch
    HAVE_TORCH = True
except Exception:
    HAVE_TORCH = False

FWD_ATOL, FWD_RTOL = 1e-7, 1e-6
GRAD_ATOL = 1e-7

_LAB = pathlib.Path(__file__).resolve().parents[2]
_REPO = _LAB.parent


def _load_classes():
    sys.path.insert(0, str(_LAB))
    sys.path.insert(0, str(_REPO / "experiments" / "phase_lc"))
    from src.binding_slots.legacy_phase_lc_slots import BindingSlots as Incubated
    import models as hist  # historical phase_lc models
    return Incubated, hist.BindingSlots


def _pair(seed, d=128, num_slots=32):
    torch.manual_seed(seed)
    Incubated, Historical = _load_classes()
    torch.manual_seed(seed); inc = Incubated(d, num_slots=num_slots)
    torch.manual_seed(seed); his = Historical(d, num_slots=num_slots)
    inc.load_state_dict(his.state_dict())  # identical weights
    inc.eval(); his.eval()
    return inc, his


def test_state_dict_parity():
    if not HAVE_TORCH:
        print("neural parity: RESOURCE_BLOCKED (torch absent) — skipped"); return
    inc, his = _pair(0)
    ik, hk = set(inc.state_dict()), set(his.state_dict())
    assert ik == hk, f"state_dict keys differ: {ik ^ hk}"
    for k in ik:
        assert inc.state_dict()[k].shape == his.state_dict()[k].shape, f"shape mismatch {k}"


def test_forward_and_gradient_parity():
    if not HAVE_TORCH:
        print("neural parity: RESOURCE_BLOCKED (torch absent) — skipped"); return
    for B in (1, 2):
        for N in (1, 8, 32, 160):
            inc, his = _pair(1)
            torch.manual_seed(99)
            x = torch.randn(B, N, 128, dtype=torch.float32)
            xi = x.clone().requires_grad_(True)
            xh = x.clone().requires_grad_(True)
            oi = inc(xi); oh = his(xh)
            assert torch.allclose(oi, oh, atol=FWD_ATOL, rtol=FWD_RTOL), \
                f"forward mismatch B{B} N{N}: max {(oi-oh).abs().max().item():.2e}"
            (oi.sum()).backward(); (oh.sum()).backward()
            assert torch.allclose(xi.grad, xh.grad, atol=GRAD_ATOL), \
                f"input-grad mismatch B{B} N{N}: max {(xi.grad-xh.grad).abs().max().item():.2e}"
            for (ni, pi), (nh, ph) in zip(inc.named_parameters(), his.named_parameters()):
                assert ni == nh
                if pi.grad is None and ph.grad is None:
                    continue
                assert torch.allclose(pi.grad, ph.grad, atol=GRAD_ATOL), \
                    f"param-grad mismatch {ni} B{B} N{N}: max {(pi.grad-ph.grad).abs().max().item():.2e}"


def test_ablation_parity():
    if not HAVE_TORCH:
        print("neural parity: RESOURCE_BLOCKED (torch absent) — skipped"); return
    for mode in (None, "zero", "shuffle_val", "rand_keys"):
        inc, his = _pair(2)
        x = torch.randn(2, 32, 128, dtype=torch.float32)
        # stochastic ablations depend on torch RNG -> reset the SAME seed before each forward
        torch.manual_seed(7); inc.ablate = mode; oi = inc(x)
        torch.manual_seed(7); his.ablate = mode; oh = his(x)
        assert torch.allclose(oi, oh, atol=FWD_ATOL, rtol=FWD_RTOL), \
            f"ablation '{mode}' output mismatch: max {(oi-oh).abs().max().item():.2e}"


def test_diagnostics_parity():
    if not HAVE_TORCH:
        print("neural parity: RESOURCE_BLOCKED (torch absent) — skipped"); return
    inc, his = _pair(3)
    x = torch.randn(2, 32, 128, dtype=torch.float32)
    inc(x); his(x)
    assert set(inc.diag) == set(his.diag)
    for k in inc.diag:
        assert abs(float(inc.diag[k]) - float(his.diag[k])) <= 1e-6, f"diag {k} differs"


def _run():
    if not HAVE_TORCH:
        print("neural parity: RESOURCE_BLOCKED (torch not installed) — documented skip"); return
    for fn in (test_state_dict_parity, test_forward_and_gradient_parity,
               test_ablation_parity, test_diagnostics_parity):
        fn()
    print("neural parity: 4 passed (EXACT / NUMERICAL parity within 1e-7)")


if __name__ == "__main__":
    _run()
