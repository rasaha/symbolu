"""KVPro V3 query-fold — core factorization math (CPU-pure, falsification-first).

Tests whether a per-block × per-channel metadata matrix ``M[b, d]`` (the production
K scale or xmin, for one (layer, head)) has structure that splits into

  * a STABLE per-channel term that can be folded into the query ONCE per decode
    token (α_d for scale, u_d for xmin), and
  * a CHEAP per-block residual applied once per block (β_b / v_b).

Two pre-registered model families:

  additive / rank-1-multiplicative
      xmin:  M[b,d] ≈ u_d + v_b                    (two-way additive)
      scale: log s[b,d] ≈ a_d + c_b  ⇔  s ≈ α_d·β_b (multiplicative — the QF1 fold)
      Folds as ONE query transform + ONE per-block scalar.

  linear low-rank R (truncated SVD, R ∈ {2, 4})
      M[b,d] ≈ Σ_{r≤R} p_{d,r} q_{b,r}
      Folds as R query transforms + R per-block scalars (QF3 = rank-2).

HONESTY: only rank-1-multiplicative *scale* and additive *xmin* fold into the clean
"one Q-transform + one scalar/block" form. A fit that needs the full per-(b,d)
residual to hit tolerance is a LOSSLESS REARRANGEMENT — it saves nothing and must
NOT be scored as a systems win. All functions return relative-Frobenius error so the
caller can see exactly how much the cheap form gives up.

No rank is chosen here from downstream results — the caller pre-registers the set.
"""
from __future__ import annotations

from typing import Dict

import torch

_EPS = 1e-12


def _rel_frob(M: torch.Tensor, fitted: torch.Tensor) -> float:
    """||M - fitted||_F / ||M||_F  — the reconstruction error that propagates to K."""
    num = torch.linalg.norm((M - fitted).reshape(-1)).item()
    den = torch.linalg.norm(M.reshape(-1)).item()
    return num / den if den > _EPS else (0.0 if num <= _EPS else float("inf"))


def _var_explained(M: torch.Tensor, fitted: torch.Tensor) -> float:
    """1 - SS_resid / SS_total, centered on the grand mean (fraction of the matrix's
    *variation* the model captures). Clipped to [<=1]; can go negative for a bad fit."""
    ss_res = ((M - fitted) ** 2).sum().item()
    ss_tot = ((M - M.mean()) ** 2).sum().item()
    if ss_tot <= _EPS:
        return 1.0 if ss_res <= _EPS else 0.0
    return 1.0 - ss_res / ss_tot


def two_way_additive(M: torch.Tensor) -> Dict[str, object]:
    """Fit M[b,d] ≈ mu + row_b + col_d (LS, the additive/rank-1 model).

    row_b (per block) and col_d (per channel) are the ANOVA main effects. For xmin
    this IS the candidate (u_d = mu + col_d foldable into Q; v_b = row_b per block).
    Returns fitted + the vectors + var_explained (centered) + rel_frob (uncentered)."""
    Mf = M.to(torch.float64)
    mu = Mf.mean()
    row = Mf.mean(dim=1) - mu           # (B,) per-block main effect
    col = Mf.mean(dim=0) - mu           # (D,) per-channel main effect
    fitted = mu + row[:, None] + col[None, :]
    return {
        "model": "two_way_additive",
        "fitted": fitted,
        "mu": float(mu),
        "row_b": row,                   # per-block residual term v_b
        "col_d": col,                   # per-channel foldable term (u_d = mu + col_d)
        "u_d": (mu + col),              # the foldable per-channel vector
        "var_explained": _var_explained(Mf, fitted),
        "rel_frob": _rel_frob(Mf, fitted),
    }


def rank1_log_multiplicative(S: torch.Tensor, floor: float = 1e-8) -> Dict[str, object]:
    """Scale-specific: fit s[b,d] ≈ α_d · β_b via the two-way additive model on log s.

    This is the QF1 form — α_d folds into Q once per decode token, β_b is one scalar
    per block. Reports var_explained on log s (how multiplicative it is) AND rel_frob
    on the LINEAR scale (the error that actually reaches K)."""
    Sf = S.to(torch.float64).clamp_min(floor)
    L = torch.log(Sf)
    add = two_way_additive(L)
    # α_d = exp(mu + col_d)  (per channel);  β_b = exp(row_b)  (per block)
    alpha_d = torch.exp(add["u_d"])                      # (D,)
    beta_b = torch.exp(add["row_b"])                     # (B,)
    fitted_lin = beta_b[:, None] * alpha_d[None, :]
    return {
        "model": "rank1_log_multiplicative",
        "alpha_d": alpha_d,
        "beta_b": beta_b,
        "fitted": fitted_lin,
        "var_explained_log": add["var_explained"],       # multiplicativity
        "rel_frob_log": add["rel_frob"],
        "var_explained": _var_explained(Sf, fitted_lin),  # on the linear scale
        "rel_frob": _rel_frob(Sf, fitted_lin),            # <-- the decode-relevant error
    }


def low_rank_svd(M: torch.Tensor, R: int) -> Dict[str, object]:
    """Truncated rank-R SVD of M[b,d] (uncentered — the fold reconstructs M directly).

    Returns fitted + the per-channel (p_{d,r}) and per-block (q_{b,r}) factors. Each
    rank-1 term folds as one query transform + one per-block scalar, so R controls the
    per-decode query-side cost (QF3 = R=2)."""
    Mf = M.to(torch.float64)
    B, D = Mf.shape
    R = int(min(R, B, D))
    U, Sv, Vh = torch.linalg.svd(Mf, full_matrices=False)   # U:(B,k) Sv:(k,) Vh:(k,D)
    Ur, Svr, Vr = U[:, :R], Sv[:R], Vh[:R, :]
    fitted = (Ur * Svr) @ Vr
    total = (Sv ** 2).sum().item()
    energy = (Svr ** 2).sum().item()
    return {
        "model": f"low_rank_svd_R{R}",
        "R": R,
        "fitted": fitted,
        "q_b_r": (Ur * Svr),            # (B, R) per-block factors
        "p_d_r": Vr.transpose(0, 1),    # (D, R) per-channel factors (foldable)
        "singular_values": Sv,
        "energy_fraction": energy / total if total > _EPS else 1.0,  # uncentered
        "var_explained": _var_explained(Mf, fitted),                  # centered
        "rel_frob": _rel_frob(Mf, fitted),
    }


def channel_bias(M: torch.Tensor, fitted: torch.Tensor) -> Dict[str, float]:
    """Does the approximation introduce a SYSTEMATIC per-channel bias (Phase D ask)?
    Reports the max |mean residual| over channels, relative to the matrix scale — a
    large value means some channel is consistently mis-reconstructed (dangerous even
    if the global Frobenius error looks small)."""
    resid = (M.to(torch.float64) - fitted)
    per_channel_mean = resid.mean(dim=0)                # (D,)
    scale = M.to(torch.float64).abs().mean().item()
    worst = per_channel_mean.abs().max().item()
    return {
        "max_abs_channel_bias": worst,
        "max_rel_channel_bias": (worst / scale) if scale > _EPS else 0.0,
        "worst_channel": int(per_channel_mean.abs().argmax().item()),
    }
