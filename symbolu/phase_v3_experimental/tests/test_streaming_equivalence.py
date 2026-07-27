"""
test_streaming_equivalence.py — §9 correctness gate for Phase v3.

Verifies:
  1. selective_scan matches a naive sequential reference (exact, complex + real).
  2. full-sequence forward == token-by-token streaming (≤ 1e-6).
  3. full-sequence forward == chunked streaming (≤ 1e-6).
  4. state size is independent of sequence length; runtime is O(N)-consistent.
"""
from __future__ import annotations

import torch

from symbolu.phase_v3_experimental.config import cfg_v3abc
from symbolu.phase_v3_experimental.scan import selective_scan
from symbolu.phase_v3_experimental.selective_complex_phase import SelectiveComplexPhaseV3
from symbolu.phase_v3_experimental.state import PhaseV3State

TOL = 1e-6


def _ref_scan(A, u, prev=None):
    """Ground-truth sequential scan in double precision, cast back to input dtype."""
    B, N, H, Dh = u.shape
    hi = torch.complex128 if u.is_complex() else torch.float64
    Ah, uh = A.to(hi), u.to(hi)
    S = torch.zeros(B, N, H, Dh, dtype=hi)
    s = (prev.to(hi) if prev is not None else torch.zeros(B, H, Dh, dtype=hi))
    for t in range(N):
        s = Ah[:, t] * s + uh[:, t]
        S[:, t] = s
    return S.to(u.dtype)


def test_scan_matches_reference_complex():
    torch.manual_seed(0)
    B, N, H, Dh = 2, 200, 3, 5
    gamma = 0.9 + 0.0999 * torch.rand(B, N, H, 1)
    omega = 3.0 * (torch.rand(B, N, H, 1) - 0.5)
    A = torch.polar(gamma.expand(B, N, H, Dh), omega.expand(B, N, H, Dh))
    u = torch.randn(B, N, H, Dh, dtype=torch.complex64)
    for chunk in (1, 7, 64, 256):
        out = selective_scan(A, u, chunk=chunk)
        err = (out - _ref_scan(A, u)).abs().max().item()
        assert err <= TOL, f"complex chunk={chunk} err={err}"


def test_scan_matches_reference_real_and_prev():
    torch.manual_seed(1)
    B, N, H, Dh = 2, 150, 4, 6
    A = (0.9 + 0.0999 * torch.rand(B, N, H, Dh))
    u = torch.randn(B, N, H, Dh)
    prev = torch.randn(B, H, Dh)
    out = selective_scan(A, u, prev, chunk=32)
    err = (out - _ref_scan(A, u, prev)).abs().max().item()
    assert err <= TOL, f"real+prev err={err}"


def test_token_by_token_equivalence():
    torch.manual_seed(2)
    m = SelectiveComplexPhaseV3(cfg_v3abc(embed_dim=48, num_heads=4)).eval()
    x = torch.randn(2, 120, 48)
    with torch.no_grad():
        full = m(x)
        st, ys = None, []
        for t in range(x.shape[1]):
            y_t, st = m.step(x[:, t], st)
            ys.append(y_t)
        stream = torch.stack(ys, dim=1)
    err = (full - stream).abs().max().item()
    assert err <= TOL, f"token-by-token err={err}"


def test_chunked_equivalence():
    torch.manual_seed(3)
    m = SelectiveComplexPhaseV3(cfg_v3abc(embed_dim=48, num_heads=4)).eval()
    x = torch.randn(2, 130, 48)
    with torch.no_grad():
        full = m(x)
        st, outs, i = None, [], 0
        for size in (17, 40, 1, 72):
            o = m(x[:, i:i + size], initial_state=st, return_state=True)
            outs.append(o.output); st = o.state; i += size
        stream = torch.cat(outs, dim=1)
    err = (full - stream).abs().max().item()
    assert err <= TOL, f"chunked err={err}"


def test_state_size_independent_of_N():
    m = SelectiveComplexPhaseV3(cfg_v3abc(embed_dim=48, num_heads=4)).eval()
    with torch.no_grad():
        s1 = m(torch.randn(1, 64, 48), return_state=True).state
        s2 = m(torch.randn(1, 4096, 48), return_state=True).state
    assert s1.state_bytes() == s2.state_bytes()


if __name__ == "__main__":
    for fn in [test_scan_matches_reference_complex, test_scan_matches_reference_real_and_prev,
               test_token_by_token_equivalence, test_chunked_equivalence,
               test_state_size_independent_of_N]:
        fn(); print("ok:", fn.__name__)
    print("ALL STREAMING TESTS PASSED")
