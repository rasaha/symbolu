"""
KoshaRoutingLoss: Supervision for governance-plane routing.

Trains the KoshaDomainRouter to produce contextually meaningful
routing weights. Four signal sources:

1. Agreement-based targets: When a specific primitive's top-scoring token
   matches the ground truth, that primitive should receive higher weight.

2. Entropy regularization: Prevents routing collapse where a single
   primitive dominates. Encourages exploration of multi-field evaluation.

3. Policy magnitude regularization: Prevents the structured Kosha x Domain
   policy from exploding and overwhelming the residual learned path.

4. (Optional) Corpus-type supervision: If corpus labels are available
   (factual, narrative, poetic, etc.), encourages domain-appropriate routing.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Dict


class KoshaRoutingLoss(nn.Module):
    """
    Multi-signal governance-plane routing supervision.

    Args:
        num_primitives: Number of primitives (6)
        entropy_weight: Weight for entropy regularization term
        min_entropy: Target minimum entropy (nats) -- below this, penalty applies
        agreement_temperature: Temperature for soft agreement targets
        policy_mag_weight: Weight for policy magnitude regularization
    """

    def __init__(
        self,
        num_primitives: int = 6,
        entropy_weight: float = 0.1,
        min_entropy: float = 0.5,
        agreement_temperature: float = 1.0,
        policy_mag_weight: float = 0.01,
    ):
        super().__init__()
        self.num_primitives = num_primitives
        self.entropy_weight = entropy_weight
        self.min_entropy = min_entropy
        self.agreement_temperature = agreement_temperature
        self.policy_mag_weight = policy_mag_weight

    def forward(
        self,
        router_result: Dict[str, torch.Tensor],
        T: torch.Tensor,
        target_ids: torch.Tensor,
        candidate_ids: torch.Tensor,
        corpus_labels: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute governance-plane routing loss.

        Args:
            router_result: Dict from KoshaDomainRouter.forward() containing
                           'alpha', 'residual_logits', 'policy_logits'
            T: Token Evaluation Tensor (..., K, 6)
            target_ids: Ground truth token ids (...,)
            candidate_ids: Candidate token ids (..., K)
            corpus_labels: Optional corpus type labels (...,)

        Returns:
            Dict with 'loss', 'agreement_loss', 'entropy_loss',
            'policy_mag_loss', and diagnostics.
        """
        alpha = router_result["alpha"]
        policy_logits = router_result["policy_logits"]

        # 1. Agreement-based supervision
        agreement_loss = self._agreement_loss(alpha, T, target_ids, candidate_ids)

        # 2. Entropy regularization
        entropy_loss = self._entropy_loss(alpha)

        # 3. Policy magnitude regularization (prevent policy explosion)
        policy_mag_loss = policy_logits.pow(2).mean()

        loss = (
            agreement_loss
            + self.entropy_weight * entropy_loss
            + self.policy_mag_weight * policy_mag_loss
        )

        return {
            "loss": loss,
            "agreement_loss": agreement_loss,
            "entropy_loss": entropy_loss,
            "policy_mag_loss": policy_mag_loss,
        }

    def _agreement_loss(
        self,
        alpha: torch.Tensor,
        T: torch.Tensor,
        target_ids: torch.Tensor,
        candidate_ids: torch.Tensor,
    ) -> torch.Tensor:
        """
        Agreement-based routing targets.

        For each primitive f, check if its top-scoring candidate matches
        the ground truth. Primitives that are "correct" should get higher weight.
        Only computes over positions where the target is in the shortlist.
        """
        # Find which positions have the target in the candidate list
        target_expanded = target_ids.unsqueeze(-1)
        target_in_candidates = (candidate_ids == target_expanded)  # (..., K)
        has_target = target_in_candidates.any(dim=-1)  # (...)

        if not has_target.any():
            return torch.tensor(0.0, device=alpha.device, dtype=alpha.dtype)

        # Filter to only positions where target is in shortlist
        alpha_valid = alpha[has_target]                    # (N, 6)
        T_valid = T[has_target]                            # (N, K, 6)
        mask_valid = target_in_candidates[has_target].float()  # (N, K)

        # Score of correct token per primitive: (N, 6)
        target_scores = (T_valid * mask_valid.unsqueeze(-1)).sum(dim=-2)

        # Per-primitive max score: (N, 6)
        max_scores = T_valid.max(dim=-2).values

        # Soft agreement: how close is the correct token's score to the max?
        score_gap = max_scores - target_scores  # (N, 6)
        soft_accuracy = torch.exp(-score_gap / self.agreement_temperature)

        # Target routing: primitives with higher accuracy should get more weight
        target_alpha = torch.softmax(soft_accuracy / self.agreement_temperature, dim=-1)

        # KL divergence: encourage alpha to match the agreement-derived target
        loss = F.kl_div(
            (alpha_valid + 1e-8).log(),
            target_alpha.detach(),
            reduction="batchmean",
            log_target=False,
        )

        return loss

    def _entropy_loss(self, alpha: torch.Tensor) -> torch.Tensor:
        """
        Entropy regularization: penalize if routing entropy drops below threshold.
        """
        entropy = -(alpha * (alpha + 1e-8).log()).sum(dim=-1)  # (...)
        mean_entropy = entropy.mean()

        # Convert min_entropy from bits to nats for comparison
        min_entropy_nats = self.min_entropy * 0.693  # ln(2)

        # Penalty only when entropy is too low
        shortfall = torch.clamp(min_entropy_nats - mean_entropy, min=0.0)
        return shortfall
