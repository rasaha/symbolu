"""EQ-I1..I8 — Hard safety / provenance boundary.

By design this module is NOT fully differentiable. It trains soft *scorers*
(risk, compliance, learned resonance) with supervision, but applies the gates as
HARD thresholds at inference. Provenance (EQ-I7) is non-learned set membership.
Softening a harm gate so it admits harmful content with probability epsilon is
unacceptable; that is the intentional non-differentiable boundary of the system.

- Q1 differentiable?  Scorers yes; gates no (by design).
- Q2 grads flow?      Through scorer logits only (gate uses a detached hard mask).
- Q3 reformulation:   train sigmoid scorers; keep threshold gates hard; expose a
                      soft mask for training and a hard mask for inference (STE-like).
- Q4 role:            Alignment / constraint layer.
- Q5 joint?           Partial (scorers co-trained; gate is a constraint, not learned).
- Q7 aux loss:        supervised harm/compliance/provenance classification (REQUIRED).
- Q8 failure mode:    miscalibrated scorers -> over-suppression or unsafe admission;
                      constrained-optimization boundary complicates end-to-end training.
"""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn


class HardSafetyBoundary(nn.Module):
    def __init__(self, d_model: int, n_scorers: int = 3, threshold: float = 0.5):
        super().__init__()
        self.threshold = threshold
        # learned scorers: e.g. [risk, compliance, resonance]
        self.scorers = nn.Linear(d_model, n_scorers)

    def forward(
        self, pooled: torch.Tensor,
        approved_provenance: Optional[torch.Tensor] = None,  # [B] bool, EQ-I7
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """pooled:[B,d] -> (admit_mask:[B] in {0,1}, info).

        admit_mask is a HARD, detached gate for inference/constraint use.
        soft_scores (with grad) are returned for supervised scorer training.
        """
        logits = self.scorers(pooled)                 # [B, n_scorers] (grad path)
        soft = torch.sigmoid(logits)                  # [B, n_scorers]
        # convention: scorer[0]=risk (admit if low), others=admit if high
        risk_ok = soft[:, 0] <= self.threshold
        others_ok = (soft[:, 1:] >= self.threshold).all(dim=-1) if soft.shape[1] > 1 \
            else torch.ones_like(risk_ok)
        admit = risk_ok & others_ok
        if approved_provenance is not None:
            admit = admit & approved_provenance.bool()
        admit_mask = admit.float().detach()           # HARD gate, no grad
        return admit_mask, {"soft_scores": soft, "logits": logits}
