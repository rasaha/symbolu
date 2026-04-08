"""
OntologyVrittiPrior: Soft directional regularizer (Ontology → Vritti).

Implements the cognitive axis of the directional model:
    Ontology is structurally primary → Vritti is an operative readout.

Given the 32D sovereign state, extracts the Bhava slice [0:12] as the
ontological layer activation, and uses the transpose of the R[v,a]
coupling matrix to derive an expected Vritti distribution. A KL
divergence term encourages the learned Vritti context profile (v_ctx)
to be consistent with this ontology-derived prior.

Math:
    bhava = softmax(state[..., 0:12])           # ontological layer activation
    prior_unnorm = bhava @ R^T                   # (12,) @ (12, 5) → (5,)
    prior = softmax(prior_unnorm / tau)          # normalized prior
    L_prior = alpha * KL(v_ctx || prior)         # regularization term

The prior is soft (alpha default 0.1), bounded, and fully ablatable
by setting alpha=0 or lambda_vritti_ontology_prior=0.

Reference: DIRECTIONAL_MODEL_ROADMAP.md Phase 1
Reference: MINIMUM_SAFE_ALIGNMENT_SPEC.md §4
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional


# R[v,a] coupling matrix from agentic/chitta_vritti/coupling.py
# 5 rows (vritti) × 12 columns (ontological layers)
# Row order: pramana, viparyaya, vikalpa, smrti, nidra
# Col order: POT, ID, EXEC, STR, COG, AGN, RSN, PUR, WIT, UNI, INT, ABS
_R_MATRIX = np.array([
    [0.40, 0.80, 0.70, 0.60, 0.70, 0.50, 0.95, 0.60, 0.80, 0.70, 0.75, 0.60],  # Pramana
    [0.30, 0.70, 0.50, 0.40, 0.60, 0.90, 0.40, 0.30, 0.50, 0.30, 0.35, 0.20],  # Viparyaya
    [0.50, 0.50, 0.60, 0.50, 0.85, 0.60, 0.70, 0.50, 0.60, 0.40, 0.55, 0.30],  # Vikalpa
    [0.70, 0.60, 0.80, 0.70, 0.70, 0.50, 0.60, 0.80, 0.50, 0.60, 0.70, 0.40],  # Smrti
    [0.85, 0.30, 0.30, 0.70, 0.40, 0.30, 0.20, 0.40, 0.60, 0.50, 0.55, 0.75],  # Nidra
], dtype=np.float64)


class OntologyVrittiPrior(nn.Module):
    """Compute a soft Vritti prior from ontological layer activations.

    Uses R^T (transpose of the 5×12 Vritti-Aspect coupling matrix) to
    map the 12D Bhava (ontological) activation into a 5D Vritti prior.
    Returns the KL divergence between the learned Vritti context profile
    and this ontology-derived prior.

    Args:
        alpha: Mixing/scaling weight for the KL term. Controls how
            strongly ontology biases Vritti. Default 0.1 (conservative).
            Hardcoded cap at 0.4 — values above this are clamped.
        tau: Temperature for the prior softmax. Lower = sharper prior.
            Default 1.0 (no sharpening).
    """

    # Hardcoded cap: alpha must not exceed this value.
    _ALPHA_CAP = 0.4

    def __init__(self, alpha: float = 0.1, tau: float = 1.0):
        super().__init__()
        self.alpha = min(alpha, self._ALPHA_CAP)
        self.tau = tau

        # R^T: (12, 5) — maps ontological activations to vritti tendencies
        # Registered as buffer (not a parameter — no gradients through R^T)
        R_T = torch.from_numpy(_R_MATRIX.T).float()  # (12, 5)
        self.register_buffer("R_T", R_T)

    def compute_prior(self, state: torch.Tensor) -> torch.Tensor:
        """Derive Vritti prior distribution from the 32D sovereign state.

        Args:
            state: Sovereign state tensor (..., 32). Bhava = [0:12].

        Returns:
            prior: Vritti prior distribution (..., 5), softmax-normalized.
        """
        bhava = state[..., 0:12]  # (..., 12)
        # Bhava is already softmax-normalized by SovereignStateProjector,
        # so it sums to 1 and all values are non-negative.
        prior_logits = bhava @ self.R_T  # (..., 5)
        prior = F.softmax(prior_logits / self.tau, dim=-1)
        return prior

    def forward(
        self,
        v_ctx: torch.Tensor,
        state: torch.Tensor,
    ) -> torch.Tensor:
        """Compute KL regularization loss: KL(v_ctx || prior).

        Args:
            v_ctx: Learned Vritti context profile (..., 5), softmax-normalized.
            state: Sovereign state tensor (..., 32).

        Returns:
            Scalar loss: alpha * mean(KL(v_ctx || prior)).
            Returns 0 if alpha is 0.
        """
        if self.alpha == 0:
            return torch.tensor(0.0, device=v_ctx.device, dtype=v_ctx.dtype)

        prior = self.compute_prior(state)  # (..., 5)

        # KL(v_ctx || prior) = sum(v_ctx * log(v_ctx / prior))
        # Use F.kl_div which expects log-probabilities as first arg:
        #   F.kl_div(log_prior, v_ctx, reduction='batchmean') = KL(v_ctx || prior)
        log_prior = torch.log(prior + 1e-8)
        kl = F.kl_div(log_prior, v_ctx, reduction="batchmean", log_target=False)

        return self.alpha * kl
