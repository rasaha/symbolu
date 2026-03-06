"""
GovernanceDiagnostics: Training-time diagnostic tracker for conscious generation
governance signals.

Tracks per-step:
  - Kosha routing entropy and per-primitive weight distribution
  - Bliss coherence vs accuracy correlation
  - Primitive contribution analysis (which primitive most influences correct predictions)
  - Rank shift: position of correct token in base logits vs integrated scores

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 5 (D.7.2), Section 9.6
"""

import torch
from typing import Dict, Optional


class GovernanceDiagnostics:
    """
    Tracks governance diagnostics over a sliding window of training steps.

    Call `update()` each step with governance tensors. Call `get_summary()`
    periodically to retrieve aggregated diagnostics for logging.

    Args:
        window_size: Number of steps to keep in sliding window.
    """

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._alpha_entropies: list = []
        self._alpha_means: list = []
        self._bliss_means: list = []
        self._disagree_means: list = []
        self._shortlist_coverages: list = []
        self._rank_shifts: list = []
        self._primitive_contributions: list = []
        self._step_count = 0

    def update(
        self,
        alpha: Optional[torch.Tensor] = None,
        B: Optional[torch.Tensor] = None,
        D: Optional[torch.Tensor] = None,
        T: Optional[torch.Tensor] = None,
        Z_star: Optional[torch.Tensor] = None,
        target_ids: Optional[torch.Tensor] = None,
        candidate_ids: Optional[torch.Tensor] = None,
        base_logits: Optional[torch.Tensor] = None,
    ):
        """
        Update diagnostics with current step's governance tensors.

        All arguments are optional — only available tensors are tracked.
        """
        self._step_count += 1

        with torch.no_grad():
            # Kosha routing entropy
            if alpha is not None:
                entropy = -(alpha * (alpha + 1e-8).log()).sum(dim=-1).mean().item()
                self._alpha_entropies.append(entropy)
                self._alpha_means.append(alpha.mean(dim=tuple(range(alpha.dim() - 1))).tolist())

            # Bliss statistics
            if B is not None:
                self._bliss_means.append(B.mean().item())
            if D is not None:
                self._disagree_means.append(D.mean().item())

            # Shortlist coverage (fraction of targets in top-K)
            if target_ids is not None and candidate_ids is not None:
                in_shortlist = (candidate_ids == target_ids.unsqueeze(-1)).any(dim=-1)
                self._shortlist_coverages.append(in_shortlist.float().mean().item())

            # Rank shift: how much does re-ranking move the correct token?
            if (base_logits is not None and Z_star is not None
                    and target_ids is not None and candidate_ids is not None):
                self._compute_rank_shift(base_logits, Z_star, target_ids, candidate_ids)

            # Primitive contribution: which primitive most aligns with correct token?
            if T is not None and target_ids is not None and candidate_ids is not None:
                self._compute_primitive_contribution(T, target_ids, candidate_ids)

        # Trim windows
        for buf in [self._alpha_entropies, self._alpha_means, self._bliss_means,
                     self._disagree_means, self._shortlist_coverages,
                     self._rank_shifts, self._primitive_contributions]:
            if len(buf) > self.window_size:
                del buf[:-self.window_size]

    def _compute_rank_shift(
        self,
        base_logits: torch.Tensor,
        Z_star: torch.Tensor,
        target_ids: torch.Tensor,
        candidate_ids: torch.Tensor,
    ):
        """Compute how much re-ranking shifts the correct token's position."""
        # Base rank: position of target in base logit ordering (lower = better)
        base_ranks = (base_logits.unsqueeze(-1) >= base_logits.gather(
            -1, target_ids.unsqueeze(-1))).sum(dim=-1).float().mean().item()

        # Integrated rank: position of target in Z_star ordering
        target_mask = (candidate_ids == target_ids.unsqueeze(-1))  # (..., K)
        if target_mask.any():
            target_z = (Z_star * target_mask.float()).amax(dim=-1)
            integrated_ranks = (Z_star >= target_z.unsqueeze(-1)).sum(dim=-1).float().mean().item()
            shift = base_ranks - integrated_ranks
            self._rank_shifts.append(shift)

    def _compute_primitive_contribution(
        self,
        T: torch.Tensor,
        target_ids: torch.Tensor,
        candidate_ids: torch.Tensor,
    ):
        """Track which primitive scores highest for the correct token."""
        target_mask = (candidate_ids == target_ids.unsqueeze(-1))  # (..., K)
        has_target = target_mask.any(dim=-1)  # (...)
        if not has_target.any():
            return
        # For positions with target in shortlist, get the primitive scores
        # T: (..., K, 6), target_mask: (..., K) -> target primitive scores: (..., 6)
        target_scores = (T * target_mask.unsqueeze(-1).float()).sum(dim=-2)  # (..., 6)
        valid_scores = target_scores[has_target]  # (N, 6)
        # Which primitive has highest score for correct token?
        top_primitive = valid_scores.argmax(dim=-1)  # (N,)
        counts = torch.zeros(6, device=T.device)
        for p in range(6):
            counts[p] = (top_primitive == p).float().sum()
        total = counts.sum()
        if total > 0:
            self._primitive_contributions.append((counts / total).tolist())

    def get_summary(self) -> Dict[str, float]:
        """
        Get aggregated diagnostics over the sliding window.

        Returns:
            Dict of diagnostic metrics suitable for logging.
        """
        result = {}

        if self._alpha_entropies:
            result["cg_diag_alpha_entropy"] = (
                sum(self._alpha_entropies) / len(self._alpha_entropies)
            )

        if self._alpha_means:
            # Average per-primitive weights
            n = len(self._alpha_means)
            avg = [sum(a[i] for a in self._alpha_means) / n
                   for i in range(len(self._alpha_means[0]))]
            names = ["base", "ont", "jepa", "csr", "vritti", "guna"]
            for name, val in zip(names, avg):
                result[f"cg_diag_alpha_{name}"] = val

        if self._bliss_means:
            result["cg_diag_bliss_mean"] = (
                sum(self._bliss_means) / len(self._bliss_means)
            )

        if self._disagree_means:
            result["cg_diag_disagree_mean"] = (
                sum(self._disagree_means) / len(self._disagree_means)
            )

        if self._shortlist_coverages:
            result["cg_diag_shortlist_coverage"] = (
                sum(self._shortlist_coverages) / len(self._shortlist_coverages)
            )

        if self._rank_shifts:
            result["cg_diag_rank_shift"] = (
                sum(self._rank_shifts) / len(self._rank_shifts)
            )

        if self._primitive_contributions:
            n = len(self._primitive_contributions)
            avg = [sum(c[i] for c in self._primitive_contributions) / n
                   for i in range(6)]
            names = ["base", "ont", "jepa", "csr", "vritti", "guna"]
            for name, val in zip(names, avg):
                result[f"cg_diag_contrib_{name}"] = val

        return result
