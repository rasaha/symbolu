"""Assemble the USE-native signal vector S_USE per query.

For a completed inference batch, for a chosen (channel set, phase mapping, window W):
  1. build channels -> per-position phase per channel  (Phi_full [B, C, N])
  2. for each query position q, take the window [q-W+1 .. q]           (Phi_win [Q, C, W])
  3. U1/U2 windowed pairwise coherence  -> C_windowed
  4. U4/U5 detached relaxation on the instantaneous phases at q -> convergence diagnostics

Signals (the falsifiable USE proposition: correct answers begin closer to a coherent peer state,
need less correction, and converge more cleanly):
  C_windowed   temporal phase-locking of the completed inference (U1/U2)
  R_initial    instantaneous global coherence at the answer position
  R_final      achievable coherence after detached relaxation
  delta_R      coherence improvement available
  E_correction total counterfactual correction energy
  D_max        largest per-channel correction demand
  D_mean       mean per-channel correction demand
  T_conv       iterations to converge
  R_unresolved unresolved incoherence after bounded iterations
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import torch

from . import _qgr_path  # noqa: F401
from .channels import build_channels
from .phases import PhaseExtractor
from .kuramoto import windowed_pairwise_coherence, relax

SIGNAL_NAMES = ["C_windowed", "R_initial", "R_final", "delta_R", "E_correction",
                "D_max", "D_mean", "T_conv", "R_unresolved"]


@torch.no_grad()
def channel_phases(rec: Dict, model, channel_set: str, mapping: str,
                   extractor: PhaseExtractor) -> torch.Tensor:
    """Return Phi_full [B, C, N]: per-channel phase at every position."""
    chans = build_channels(rec, model, channel_set)
    phis = []
    for name, v in chans.items():                 # v: [B,N,dim]
        phis.append(extractor.extract(v, mapping))  # [B,N]
    return torch.stack(phis, dim=1)                 # [B,C,N]


@torch.no_grad()
def use_signals_for_batch(rec: Dict, model, query_bq: Tuple[torch.Tensor, torch.Tensor],
                          channel_set: str, mapping: str, extractor: PhaseExtractor,
                          W: int = 6, alpha: float = 0.1, max_iter: int = 200,
                          chunk: int = 4096) -> Dict[str, torch.Tensor]:
    """Compute S_USE for the given query positions. query_bq = (b_idx[Q], q_idx[Q])."""
    b_idx, q_idx = query_bq
    Phi_full = channel_phases(rec, model, channel_set, mapping, extractor)   # [B,C,N]
    B, C, N = Phi_full.shape
    Q = b_idx.shape[0]
    out = {k: [] for k in SIGNAL_NAMES}
    offs = torch.arange(W - 1, -1, -1)                       # W-1 .. 0
    for s in range(0, Q, chunk):
        bi = b_idx[s:s + chunk]
        qi = q_idx[s:s + chunk]
        idx = (qi[:, None] - offs[None, :]).clamp(min=0, max=N - 1)   # [q,W] positions q-W+1..q
        sel = Phi_full[bi]                                   # [q,C,N]
        Phi_win = sel.gather(2, idx[:, None, :].expand(-1, C, -1))    # [q,C,W]
        inst = Phi_win[:, :, -1]                             # [q,C] instantaneous phases at q
        cw = windowed_pairwise_coherence(Phi_win)            # [q]
        dyn = relax(inst, alpha=alpha, max_iter=max_iter)
        out["C_windowed"].append(cw)
        for k in ("R_initial", "R_final", "delta_R", "E_correction",
                  "D_max", "D_mean", "T_conv", "R_unresolved"):
            out[k].append(dyn[k])
    return {k: torch.cat(v) for k, v in out.items()}
