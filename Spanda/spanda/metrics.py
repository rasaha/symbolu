"""
SpandaMetrics: Logging and diagnostic checks for Spanda-Softmax Hybrid.

Tracks:
    - Perplexity
    - Mean logit magnitude
    - Temperature tau
    - Mean/Max ||Psi||
    - Mean ||Delta||
    - Cosine(Psi_t, Psi_{t+1})  -- emission continuity
    - Cosine(h_t, h_{t+1})      -- backbone continuity
    - Anchor pairwise cosine histogram (sample 1000 pairs)
    - Anchor nearest-neighbor mean distance
    - Active anchor coverage

Diagnostic warnings:
    - Tau < 0.1 or > 100
    - Anchor mean cosine > 0.9
    - Psi norm always saturates at clamp
    - Emission continuity < backbone continuity
"""

import math
import logging
import torch
import torch.nn.functional as F
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SpandaMetrics:
    """
    Computes and logs all Spanda-specific metrics and diagnostics.

    Usage:
        metrics = SpandaMetrics()
        stats = metrics.compute(psi, delta, h, logits, tau, anchors)
        metrics.check_diagnostics(stats)
    """

    def __init__(self, num_anchor_pairs: int = 1000):
        self.num_anchor_pairs = num_anchor_pairs
        self._step_count = 0

    def compute(
        self,
        psi: torch.Tensor,
        delta: torch.Tensor,
        h: torch.Tensor,
        logits: torch.Tensor,
        tau: float,
        anchors: Optional[torch.Tensor] = None,
        norm_clamp_c: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Compute all Spanda metrics for a single batch.

        Args:
            psi: [B, T, psi_dim] -- Psi state trajectory.
            delta: [B, T, psi_dim] -- Delta sequence.
            h: [B, T, embed_dim] -- Backbone hidden states.
            logits: [B, T, V] -- Output logits.
            tau: float -- Current temperature value.
            anchors: [V, psi_dim] -- Unit-norm anchors (optional, for anchor diagnostics).
            norm_clamp_c: float -- Norm clamp ceiling (for saturation check).

        Returns:
            Dict of metric name -> value.
        """
        stats = {}
        self._step_count += 1

        with torch.no_grad():
            # Temperature
            stats["tau"] = tau

            # Logit magnitude
            stats["mean_logit_magnitude"] = logits.abs().mean().item()

            # Psi norms
            psi_norms = psi.norm(dim=-1)  # [B, T]
            stats["mean_psi_norm"] = psi_norms.mean().item()
            stats["max_psi_norm"] = psi_norms.max().item()

            # Delta norms
            delta_norms = delta.norm(dim=-1)  # [B, T]
            stats["mean_delta_norm"] = delta_norms.mean().item()

            # Emission continuity: cosine(Psi_t, Psi_{t+1})
            if psi.size(1) > 1:
                psi_cos = F.cosine_similarity(
                    psi[:, :-1, :], psi[:, 1:, :], dim=-1
                )  # [B, T-1]
                stats["psi_continuity"] = psi_cos.mean().item()
            else:
                stats["psi_continuity"] = 0.0

            # Backbone continuity: cosine(h_t, h_{t+1})
            if h.size(1) > 1:
                h_cos = F.cosine_similarity(
                    h[:, :-1, :], h[:, 1:, :], dim=-1
                )  # [B, T-1]
                stats["backbone_continuity"] = h_cos.mean().item()
            else:
                stats["backbone_continuity"] = 0.0

            # Psi norm saturation check
            if norm_clamp_c is not None:
                saturation_threshold = 0.99 * norm_clamp_c
                psi_saturated = (psi_norms > saturation_threshold).float().mean().item()
                stats["psi_norm_saturation_frac"] = psi_saturated

            # Anchor diagnostics (computed less frequently for cost)
            if anchors is not None:
                anchor_stats = self._compute_anchor_metrics(anchors)
                stats.update(anchor_stats)

        return stats

    def _compute_anchor_metrics(self, anchors: torch.Tensor) -> Dict[str, float]:
        """Compute anchor geometry metrics."""
        stats = {}
        V, D = anchors.shape

        # Sample pairs for pairwise cosine
        num_pairs = min(self.num_anchor_pairs, V * (V - 1) // 2)
        if num_pairs > 0 and V > 1:
            idx_i = torch.randint(0, V, (num_pairs,), device=anchors.device)
            idx_j = torch.randint(0, V, (num_pairs,), device=anchors.device)
            # Avoid self-pairs
            mask = idx_i != idx_j
            idx_i = idx_i[mask]
            idx_j = idx_j[mask]

            if len(idx_i) > 0:
                cos_sim = F.cosine_similarity(
                    anchors[idx_i], anchors[idx_j], dim=-1
                )
                stats["anchor_pairwise_cosine_mean"] = cos_sim.mean().item()
                stats["anchor_pairwise_cosine_std"] = cos_sim.std().item()
                stats["anchor_pairwise_cosine_max"] = cos_sim.max().item()

        # Nearest-neighbor mean distance
        if V > 1:
            # Subsample for cost control
            sample_size = min(512, V)
            idx = torch.randperm(V, device=anchors.device)[:sample_size]
            A_sample = anchors[idx]  # [S, D]

            # Pairwise distances within sample
            dists = torch.cdist(A_sample, A_sample, p=2)  # [S, S]
            # Set diagonal to large value to exclude self
            dists.fill_diagonal_(float("inf"))
            nn_dists = dists.min(dim=-1).values  # [S]
            stats["anchor_nn_mean_dist"] = nn_dists.mean().item()

        return stats

    def compute_active_coverage(
        self, psi: torch.Tensor, anchors: torch.Tensor, vocab_size: int
    ) -> float:
        """
        Compute active anchor coverage: fraction of vocab used as nearest anchor.

        Args:
            psi: [B, T, psi_dim] -- Psi states from validation pass.
            anchors: [V, psi_dim] -- Unit-norm anchors.
            vocab_size: Total vocabulary size.

        Returns:
            Fraction of vocabulary anchors that are nearest to at least one Psi.
        """
        with torch.no_grad():
            # Flatten psi to [N, psi_dim]
            psi_flat = psi.reshape(-1, psi.size(-1))

            # For memory efficiency, process in chunks
            chunk_size = 4096
            active_anchors = set()

            for i in range(0, psi_flat.size(0), chunk_size):
                chunk = psi_flat[i : i + chunk_size]
                # Distances: [chunk, V]
                dists = torch.cdist(chunk, anchors, p=2)
                nearest = dists.argmin(dim=-1)  # [chunk]
                active_anchors.update(nearest.cpu().tolist())

            return len(active_anchors) / vocab_size

    def check_diagnostics(self, stats: Dict[str, float]) -> list:
        """
        Check for diagnostic warning conditions.

        Returns:
            List of warning messages (empty if all OK).
        """
        warnings = []

        # Tau range
        tau = stats.get("tau", None)
        if tau is not None:
            if tau < 0.1:
                msg = f"WARNING: Temperature tau={tau:.4f} < 0.1 (too low, logits may explode)"
                warnings.append(msg)
                logger.warning(msg)
            elif tau > 100:
                msg = f"WARNING: Temperature tau={tau:.4f} > 100 (too high, logits near-uniform)"
                warnings.append(msg)
                logger.warning(msg)

        # Anchor mean cosine
        cos_mean = stats.get("anchor_pairwise_cosine_mean", None)
        if cos_mean is not None and cos_mean > 0.9:
            msg = f"WARNING: Anchor mean pairwise cosine={cos_mean:.4f} > 0.9 (anchor collapse risk)"
            warnings.append(msg)
            logger.warning(msg)

        # Psi norm saturation
        sat_frac = stats.get("psi_norm_saturation_frac", None)
        if sat_frac is not None and sat_frac > 0.95:
            msg = f"WARNING: Psi norm saturates at clamp {sat_frac:.1%} of the time"
            warnings.append(msg)
            logger.warning(msg)

        # Emission continuity vs backbone continuity
        psi_cont = stats.get("psi_continuity", None)
        h_cont = stats.get("backbone_continuity", None)
        if psi_cont is not None and h_cont is not None:
            if psi_cont < h_cont - 0.05:
                msg = (
                    f"WARNING: Emission continuity ({psi_cont:.4f}) < "
                    f"backbone continuity ({h_cont:.4f}). "
                    f"Spanda may be injecting noise."
                )
                warnings.append(msg)
                logger.warning(msg)

        return warnings
