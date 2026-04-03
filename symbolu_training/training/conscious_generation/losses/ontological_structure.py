"""
OntologicalStructureLoss: Contrastive loss for 32D manifold clustering.

Encourages semantically similar tokens to cluster in the 32D ontological
manifold while pushing dissimilar tokens apart. This gives the TokenOntologyProjector
meaningful gradients beyond what the downstream scoring losses provide.

Supports two formulations:
  1. "contrastive" (InfoNCE): Standard contrastive learning with in-batch negatives.
     Positive pairs: tokens within the same semantic group.
     Negatives: all other tokens in the batch.

  2. "prototype": Learnable prototypes per semantic class.
     Each token is attracted to its class prototype and repelled from others.
     More memory-efficient for large batch sizes.

Semantic groups are derived from token co-occurrence patterns:
  - Same-position tokens across batch elements form natural positive pairs
    (they fill the same syntactic/semantic role)
  - Tokens at different positions form negatives

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 1
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Dict


class OntologicalStructureLoss(nn.Module):
    """
    Contrastive or prototype-based loss for ontological manifold structure.

    During training, takes the cached O_tok codes and target token ids to
    compute a loss that encourages meaningful clustering in the 32D space.

    Args:
        state_dim: Ontological code dimension (32)
        loss_type: "contrastive" (InfoNCE) or "prototype"
        temperature: Softmax temperature for InfoNCE (lower = sharper)
        num_prototypes: Number of learnable prototypes (prototype mode only)
    """

    def __init__(
        self,
        state_dim: int = 32,
        loss_type: str = "contrastive",
        temperature: float = 0.1,
        num_prototypes: int = 64,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.loss_type = loss_type
        self.temperature = temperature

        if loss_type == "prototype":
            self.prototypes = nn.Parameter(torch.randn(num_prototypes, state_dim))
            nn.init.xavier_normal_(self.prototypes, gain=0.5)
        elif loss_type != "contrastive":
            raise ValueError(f"Unknown loss_type: {loss_type}. Use 'contrastive' or 'prototype'.")

    def forward(
        self,
        o_tokens: torch.Tensor,
        target_ids: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute ontological structure loss.

        Uses in-batch contrastive learning: tokens at the same sequence
        position across batch elements are treated as positive pairs
        (they occupy the same syntactic slot). Tokens at different positions
        are negatives.

        Args:
            o_tokens: Ontological codes for target tokens (B, T, 32)
            target_ids: Target token ids (B, T) — used for same-token positive mining

        Returns:
            Dict with:
              - "loss": Scalar loss value
              - "avg_pos_sim": Average positive pair similarity (diagnostic)
              - "avg_neg_sim": Average negative pair similarity (diagnostic)
        """
        if self.loss_type == "contrastive":
            return self._contrastive_loss(o_tokens, target_ids)
        else:
            return self._prototype_loss(o_tokens, target_ids)

    def _contrastive_loss(
        self,
        o_tokens: torch.Tensor,
        target_ids: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        InfoNCE contrastive loss with same-token positive mining.

        Tokens that share the same token_id within the batch form positive pairs.
        All other tokens in the batch are negatives.
        """
        B, T, D = o_tokens.shape
        # Flatten to (B*T, D)
        codes = o_tokens.reshape(-1, D)
        ids = target_ids.reshape(-1)
        N = codes.shape[0]

        # Subsample if batch is very large to keep memory bounded
        max_samples = 1024
        if N > max_samples:
            perm = torch.randperm(N, device=codes.device)[:max_samples]
            codes = codes[perm]
            ids = ids[perm]
            N = max_samples

        # L2-normalize for cosine similarity
        codes_norm = F.normalize(codes, dim=-1)

        # Similarity matrix: (N, N)
        sim = codes_norm @ codes_norm.t() / self.temperature

        # Positive mask: same token_id
        pos_mask = ids.unsqueeze(0) == ids.unsqueeze(1)  # (N, N)
        # Remove self-pairs from positive mask
        pos_mask.fill_diagonal_(False)

        # If no positive pairs exist, return zero loss with diagnostics
        if not pos_mask.any():
            zero = torch.tensor(0.0, device=codes.device, requires_grad=True)
            return {
                "loss": zero,
                "avg_pos_sim": torch.tensor(0.0, device=codes.device),
                "avg_neg_sim": torch.tensor(0.0, device=codes.device),
            }

        # InfoNCE: for each anchor, average over its positive pairs
        # log(exp(sim_pos) / sum(exp(sim_all_except_self)))
        # Mask out self from denominator
        self_mask = torch.eye(N, dtype=torch.bool, device=codes.device)
        neg_mask = ~self_mask  # Everything except self

        # Log-sum-exp over all non-self entries (denominator)
        log_denom = torch.logsumexp(sim.masked_fill(self_mask, float("-inf")), dim=-1)

        # For each pair (i, j) where pos_mask[i,j] = True: sim[i,j] - log_denom[i]
        pos_log_probs = sim - log_denom.unsqueeze(-1)  # (N, N)

        # Average over positive pairs per anchor, then average over anchors
        # Only consider anchors that have at least one positive
        has_pos = pos_mask.any(dim=-1)
        if has_pos.sum() == 0:
            zero = torch.tensor(0.0, device=codes.device, requires_grad=True)
            return {
                "loss": zero,
                "avg_pos_sim": torch.tensor(0.0, device=codes.device),
                "avg_neg_sim": torch.tensor(0.0, device=codes.device),
            }

        # Sum positive log-probs per anchor, divide by number of positives
        pos_log_probs_masked = pos_log_probs * pos_mask.float()
        num_pos_per_anchor = pos_mask.float().sum(dim=-1).clamp(min=1)
        anchor_losses = -pos_log_probs_masked.sum(dim=-1) / num_pos_per_anchor
        loss = anchor_losses[has_pos].mean()

        # Diagnostics (detached)
        with torch.no_grad():
            raw_sim = codes_norm @ codes_norm.t()
            avg_pos = raw_sim[pos_mask].mean() if pos_mask.any() else torch.tensor(0.0)
            neg_only = ~pos_mask & neg_mask
            avg_neg = raw_sim[neg_only].mean() if neg_only.any() else torch.tensor(0.0)

        return {
            "loss": loss,
            "avg_pos_sim": avg_pos,
            "avg_neg_sim": avg_neg,
        }

    def _prototype_loss(
        self,
        o_tokens: torch.Tensor,
        target_ids: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Prototype-based loss: each token is assigned to nearest prototype,
        then pulled toward it and pushed from others.
        """
        B, T, D = o_tokens.shape
        codes = o_tokens.reshape(-1, D)
        N = codes.shape[0]

        # Normalize
        codes_norm = F.normalize(codes, dim=-1)
        proto_norm = F.normalize(self.prototypes, dim=-1)

        # Assign each token to nearest prototype
        sim_to_proto = codes_norm @ proto_norm.t()  # (N, num_prototypes)

        # Cross-entropy style: each token's assignment is the "label"
        assignments = sim_to_proto.argmax(dim=-1).detach()  # (N,)

        # Pull toward assigned prototype (positive)
        pos_sim = sim_to_proto[torch.arange(N, device=codes.device), assignments]

        # Push from all other prototypes (contrastive)
        log_denom = torch.logsumexp(sim_to_proto / self.temperature, dim=-1)
        loss = -(pos_sim / self.temperature - log_denom).mean()

        with torch.no_grad():
            avg_pos = pos_sim.mean()
            # Negative = average similarity to non-assigned prototypes
            neg_mask = torch.ones_like(sim_to_proto, dtype=torch.bool)
            neg_mask[torch.arange(N, device=codes.device), assignments] = False
            avg_neg = sim_to_proto[neg_mask].mean()

        return {
            "loss": loss,
            "avg_pos_sim": avg_pos,
            "avg_neg_sim": avg_neg,
        }
