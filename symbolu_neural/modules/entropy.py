"""EQ-C1..C5 — Entropy engine + resonance modulation.

- Q1 differentiable?  Yes (Shannon entropy is smooth in p; sigmoids smooth).
- Q2 grads flow?      Yes. Parameter-light: only rho, base weights, thresholds.
- Q3 reformulation:   H = -sum p log p with p clamped; lambda_res = learned
                      convex combo over Guna; modulation = base * sigmoid(kappa(H-tau)).
- Q4 role:            Augments — turns typed latents into control features (FiLM-style).
- Q5 joint?           Yes.
- Q7 aux loss:        entropy-calibration loss (correlate H with predictive error).
- Q8 failure mode:    entropy-as-control circularity — the net can game H as a
                      shortcut; permutation invariance gives no semantic gradient.
"""
from __future__ import annotations

from typing import Dict

import torch
import torch.nn as nn

from ..config import N_GUNA


def shannon_entropy(logp: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    """log-prob tensor [...,C] -> entropy [...]  (nats)."""
    p = logp.exp()
    return -(p * logp.clamp_min(torch.log(torch.tensor(eps)))).sum(dim=-1)


class EntropyEngine(nn.Module):
    def __init__(self, sharpness_init: float = 4.0, eps: float = 1e-8):
        super().__init__()
        self.eps = eps
        # EQ-C4 Guna resonance weights rho(g)
        self.rho = nn.Parameter(torch.zeros(N_GUNA))
        # EQ-C5 base recursion weights and thresholds (learnable)
        self.base = nn.Parameter(torch.ones(3))               # alpha,beta,gamma
        self.tau = nn.Parameter(torch.zeros(3))               # tau_D,tau_G,tau_K
        self.kappa = nn.Parameter(torch.tensor(float(sharpness_init)))

    def forward(
        self,
        log_p_w: torch.Tensor,   # [B,10]  (EQ-C1 -> H_D)
        log_p_g: torch.Tensor,   # [B,3]   (EQ-C2 -> H_G)
        log_p_k: torch.Tensor,   # [B,5]   (EQ-C3 -> H_K)
    ) -> Dict[str, torch.Tensor]:
        H_D = shannon_entropy(log_p_w, self.eps)              # [B]
        H_G = shannon_entropy(log_p_g, self.eps)
        H_K = shannon_entropy(log_p_k, self.eps)
        H_K_acc = H_K / torch.log(torch.tensor(float(log_p_k.shape[-1])))

        # EQ-C4 resonance modulation coefficient lambda_res
        p_g = log_p_g.exp()
        lam_res = (p_g * self.rho).sum(-1) / p_g.sum(-1).clamp_min(self.eps)

        # EQ-C5 entropy-modulated recursion weights alpha',beta',gamma'
        H = torch.stack([H_D, H_G, H_K], dim=-1)              # [B,3]
        gate = torch.sigmoid(self.kappa * (H - self.tau))     # [B,3]
        mod = self.base * gate                                # [B,3]

        return {
            "H_D": H_D, "H_G": H_G, "H_K": H_K, "H_K_acc": H_K_acc,
            "lambda_res": lam_res, "mod": mod,                # mod = (alpha',beta',gamma')
            "entropy_vec": H,
        }
