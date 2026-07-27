"""
scan.py — stable, exact, O(N) selective linear scan for a time-varying first-order
recurrence:  S_t = A_t ⊙ S_{t-1} + u_t   (A_t input-dependent, complex or real).

Naive parallel forms compute a global cumulative product P_t = Π A_i and then divide
u_j / P_j; with γ_t ≤ 1 this underflows/overflows for long N and is unusable. Instead
we use a CHUNKED associative scan that never divides:

  * split the sequence into chunks of size C;
  * scan WITHIN each chunk (vectorized across all chunks at once — only C python steps),
    accumulating both the local state S_local and the local cumulative product cumA
    (bounded: |cumA| ≥ γ_min^C);
  * carry the chunk-end state across chunks (NC python steps);
  * S = S_local + cumA · carry_in.

Total python iterations = C + N/C (choose C≈√N); everything else is vectorized. Exact
to floating point (no division), numerically stable, and O(N) with constant state in N.
Works for complex64 (the phase state) and float32 (the amplitude accumulator) alike.
"""
from __future__ import annotations

from typing import Optional

import torch
from torch import Tensor


def selective_scan(A: Tensor, u: Tensor, prev: Optional[Tensor] = None,
                   chunk: int = 64) -> Tensor:
    """S_t = A_t * S_{t-1} + u_t over dim=1.

    A, u : [B, N, H, Dh] (A broadcast-compatible; same dtype as u — complex or real).
    prev : [B, H, Dh] initial state S_0, or None (zero).
    returns S : [B, N, H, Dh].
    """
    B, N, H, Dh = u.shape
    dev, out_dt = u.device, u.dtype
    # Accumulate in double precision so the chunked reordering matches a sequential scan
    # to ≤1e-6 (§9); the persisted state is cast back to the input dtype (complex64/float32).
    hi = torch.complex128 if u.is_complex() else torch.float64
    A = A.to(hi); u = u.to(hi)
    if prev is not None:
        prev = prev.to(hi)
    dt = hi
    A = A.expand(B, N, H, Dh) if A.shape != u.shape else A
    C = min(chunk, N) if N > 0 else 1
    pad = (C - N % C) % C
    if pad:
        A = torch.cat([A, torch.ones(B, pad, H, Dh, dtype=A.dtype, device=dev)], dim=1)
        u = torch.cat([u, torch.zeros(B, pad, H, Dh, dtype=dt, device=dev)], dim=1)
    NC = (N + pad) // C
    Ac = A.reshape(B, NC, C, H, Dh)
    uc = u.reshape(B, NC, C, H, Dh)

    # within-chunk scan, vectorized across (B, NC, H, Dh); C python steps.
    s = torch.zeros(B, NC, H, Dh, dtype=dt, device=dev)
    p = torch.ones(B, NC, H, Dh, dtype=A.dtype, device=dev)
    local_S = torch.empty(B, NC, C, H, Dh, dtype=dt, device=dev)
    cumA = torch.empty(B, NC, C, H, Dh, dtype=A.dtype, device=dev)
    for c in range(C):
        a_c = Ac[:, :, c]
        s = a_c * s + uc[:, :, c]
        p = a_c * p
        local_S[:, :, c] = s
        cumA[:, :, c] = p

    chunkA = cumA[:, :, -1]          # [B,NC,H,Dh] product of A over each chunk
    chunk_end = local_S[:, :, -1]    # [B,NC,H,Dh] chunk-end state (zero carry-in)

    # cross-chunk carry; NC python steps.
    e = prev if prev is not None else torch.zeros(B, H, Dh, dtype=dt, device=dev)
    carry_in = torch.empty(B, NC, H, Dh, dtype=dt, device=dev)
    for nc in range(NC):
        carry_in[:, nc] = e
        e = chunkA[:, nc] * e + chunk_end[:, nc]

    S = local_S + cumA * carry_in.unsqueeze(2)     # broadcast carry over the chunk
    return S.reshape(B, NC * C, H, Dh)[:, :N].to(out_dt)


def scan_last(A: Tensor, u: Tensor, prev: Optional[Tensor] = None,
              chunk: int = 64) -> Tensor:
    """Final state S_N only (for streaming carry). Convenience wrapper."""
    return selective_scan(A, u, prev, chunk)[:, -1]
