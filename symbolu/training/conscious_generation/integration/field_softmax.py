"""
FieldIntegratedSoftmax: Replaces standard logit-based softmax with multi-field
consensus distribution for token generation.

P(w) = exp(Z*(w) / τ) / Σ_{u ∈ C_t} exp(Z*(u) / τ)

where Z*(w) = B(w) · Z(w) is the Bliss-gated integrated score from Phase 3,
and C_t is the top-K candidate shortlist from base logits.

Optional agreement-energy extension:
  A_t(w) = Σ_{f<g} β_{fg} S_f(w) S_g(w)     — pairwise primitive synergy
  Z̃*(w) = B(w) · (Z(w) + β · A_t(w))

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 4 (D.6)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional


class FieldIntegratedSoftmax(nn.Module):
    """
    Computes token probability distribution from field-integrated scores Z*(w).

    Takes the integrated scorer output (Z_star, candidate_ids) and produces a
    full-vocabulary log-probability tensor suitable for cross-entropy loss or
    sampling.

    Args:
        vocab_size: Full vocabulary size (for scatter into full-vocab tensor).
        temperature: Softmax temperature (τ). Default 1.0.
        use_agreement_energy: If True, add pairwise agreement term A_t(w).
        agreement_energy_weight: β coefficient for agreement energy.
        num_primitives: Number of primitives (for agreement energy pairs).
    """

    def __init__(
        self,
        vocab_size: int,
        temperature: float = 1.0,
        use_agreement_energy: bool = False,
        agreement_energy_weight: float = 0.1,
        num_primitives: int = 6,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.temperature = temperature
        self.use_agreement_energy = use_agreement_energy
        self.agreement_energy_weight = agreement_energy_weight

        if use_agreement_energy:
            # Learnable pairwise coupling β_{fg} for each pair of primitives
            num_pairs = num_primitives * (num_primitives - 1) // 2
            self.beta = nn.Parameter(torch.full((num_pairs,), agreement_energy_weight))

    def _compute_agreement_energy(self, T: torch.Tensor) -> torch.Tensor:
        """
        Compute pairwise agreement energy A_t(w) = Σ_{f<g} β_{fg} S_f(w) S_g(w).

        Args:
            T: Token Evaluation Tensor (..., K, P) where P = num_primitives.

        Returns:
            Agreement energy (..., K).
        """
        P = T.shape[-1]
        energy = torch.zeros(T.shape[:-1], device=T.device, dtype=T.dtype)
        idx = 0
        for f in range(P):
            for g in range(f + 1, P):
                energy = energy + self.beta[idx] * T[..., f] * T[..., g]
                idx += 1
        return energy

    def forward(
        self,
        Z_star: torch.Tensor,
        candidate_ids: torch.Tensor,
        T: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute field-integrated log-probabilities over the full vocabulary.

        Non-candidate tokens receive -inf (zero probability). This makes the
        distribution equivalent to softmax over the shortlist, scattered into
        full-vocabulary shape for compatibility with standard cross-entropy.

        Args:
            Z_star: Bliss-gated integrated scores (..., K).
            candidate_ids: Token indices in shortlist (..., K).
            T: Token Evaluation Tensor (..., K, 6). Required if
               use_agreement_energy is True.

        Returns:
            Dict with keys:
                'log_probs': Full-vocab log-probabilities (..., V).
                'probs': Full-vocab probabilities (..., V).
                'shortlist_log_probs': Log-probs over shortlist only (..., K).
        """
        scores = Z_star

        # Optional: add agreement energy
        if self.use_agreement_energy and T is not None:
            A = self._compute_agreement_energy(T)
            scores = scores + A

        # Temperature scaling
        scores = scores / self.temperature

        # Softmax over shortlist (numerically stable)
        shortlist_log_probs = F.log_softmax(scores, dim=-1)  # (..., K)

        # Scatter into full vocabulary: non-candidates get -inf
        batch_shape = Z_star.shape[:-1]
        full_log_probs = torch.full(
            (*batch_shape, self.vocab_size),
            float('-inf'),
            device=Z_star.device,
            dtype=Z_star.dtype,
        )
        full_log_probs.scatter_(-1, candidate_ids, shortlist_log_probs)

        return {
            "log_probs": full_log_probs,
            "probs": full_log_probs.exp(),
            "shortlist_log_probs": shortlist_log_probs,
        }
