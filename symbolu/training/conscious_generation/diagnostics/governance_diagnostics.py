"""
GovernanceDiagnostics: Causality-aware diagnostic tracker for governance plane.

Tracks two categories of signals:

A. Summary statistics (existing):
   - Routing entropy, per-primitive weights, bliss, disagreement, rank shift

B. Causality signals (new — answers "is governance causal or decorative?"):
   - Policy vs residual influence (norm ratio)
   - Routing sensitivity probes (delta-alpha under Kosha/domain perturbation)
   - Interaction term contribution (isolated kd_logits magnitude)
   - Bliss governance (lambda_eff distribution, correlation with blissful Kosha)
   - Kosha statistics (per-dimension mean, entropy)

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 5 (D.7.2)
"""

import math
import torch
from typing import Dict, List, Optional


class GovernanceDiagnostics:
    """
    Tracks governance diagnostics over a sliding window of training steps.

    Call `update()` each step with governance tensors. Call `get_summary()`
    periodically to retrieve aggregated diagnostics for logging.

    Args:
        window_size: Number of steps to keep in sliding window.
        enable_sensitivity_probes: Whether to run perturbation probes
            (adds ~2 extra forward passes per step through the router).
    """

    PRIMITIVE_NAMES = ["base", "ont", "jepa", "csr", "vritti", "guna"]
    KOSHA_NAMES = ["material", "vital", "mental", "intellectual", "blissful"]

    def __init__(self, window_size: int = 100, enable_sensitivity_probes: bool = True):
        self.window_size = window_size
        self.enable_sensitivity_probes = enable_sensitivity_probes

        # --- A. Summary statistics buffers ---
        self._alpha_entropies: List[float] = []
        self._alpha_means: List[List[float]] = []
        self._alpha_top1_probs: List[float] = []
        self._bliss_means: List[float] = []
        self._disagree_means: List[float] = []
        self._shortlist_coverages: List[float] = []
        self._rank_shifts: List[float] = []
        self._primitive_contributions: List[List[float]] = []

        # --- B. Causality signal buffers ---
        self._policy_norms: List[float] = []
        self._residual_norms: List[float] = []
        self._policy_residual_ratios: List[float] = []
        self._interaction_norms: List[float] = []
        self._interaction_ratios: List[float] = []
        self._kosha_means: List[List[float]] = []
        self._kosha_entropies: List[float] = []
        self._lambda_effs: List[float] = []
        self._lambda_eff_stds: List[float] = []
        self._bliss_lambda_corrs: List[float] = []
        self._policy_scales: List[float] = []
        self._route_temps: List[float] = []

        # Sensitivity probes
        self._delta_alpha_kosha: List[float] = []
        self._delta_alpha_domain: List[float] = []
        self._delta_alpha_interaction: List[float] = []

        # Residual baseline divergence
        self._alpha_baseline: Optional[torch.Tensor] = None  # Cached from residual-only run
        self._alpha_divergences: List[float] = []

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
        # New: governance causality signals
        router_result: Optional[Dict[str, torch.Tensor]] = None,
        lambda_eff: Optional[torch.Tensor] = None,
        kosha: Optional[torch.Tensor] = None,
        # For sensitivity probes
        router: Optional[object] = None,
        hidden: Optional[torch.Tensor] = None,
        o_ctx: Optional[torch.Tensor] = None,
        domain: Optional[torch.Tensor] = None,
    ):
        """
        Update diagnostics with current step's governance tensors.

        All arguments are optional — only available tensors are tracked.

        New args for causality tracking:
            router_result: Full dict from KoshaDomainRouter.forward()
            lambda_eff: Effective bliss lambda from BlissTokenGate
            kosha: Kosha distribution (..., 5) from router
            router: KoshaDomainRouter instance (for sensitivity probes)
            hidden, o_ctx, domain: Inputs (for sensitivity probes)
        """
        self._step_count += 1

        with torch.no_grad():
            # === A. Summary statistics ===
            if alpha is not None:
                entropy = -(alpha * (alpha + 1e-8).log()).sum(dim=-1).mean().item()
                self._alpha_entropies.append(entropy)
                self._alpha_means.append(
                    alpha.mean(dim=tuple(range(alpha.dim() - 1))).tolist()
                )
                top1 = alpha.max(dim=-1).values.mean().item()
                self._alpha_top1_probs.append(top1)

            if B is not None:
                self._bliss_means.append(B.mean().item())
            if D is not None:
                self._disagree_means.append(D.mean().item())

            if target_ids is not None and candidate_ids is not None:
                in_shortlist = (candidate_ids == target_ids.unsqueeze(-1)).any(dim=-1)
                self._shortlist_coverages.append(in_shortlist.float().mean().item())

            if (base_logits is not None and Z_star is not None
                    and target_ids is not None and candidate_ids is not None):
                self._compute_rank_shift(base_logits, Z_star, target_ids, candidate_ids)

            if T is not None and target_ids is not None and candidate_ids is not None:
                self._compute_primitive_contribution(T, target_ids, candidate_ids)

            # === B. Causality signals ===

            # B1. Policy vs residual influence
            if router_result is not None:
                pol = router_result.get("policy_logits")
                res = router_result.get("residual_logits")
                if pol is not None and res is not None:
                    pol_norm = pol.norm(dim=-1).mean().item()
                    res_norm = res.norm(dim=-1).mean().item()
                    self._policy_norms.append(pol_norm)
                    self._residual_norms.append(res_norm)
                    self._policy_residual_ratios.append(
                        pol_norm / (res_norm + 1e-6)
                    )

            # B3. Kosha statistics
            k = kosha if kosha is not None else (
                router_result.get("kosha") if router_result else None
            )
            if k is not None:
                k_mean = k.mean(dim=tuple(range(k.dim() - 1))).tolist()
                self._kosha_means.append(k_mean)
                k_ent = -(k * (k + 1e-8).log()).sum(dim=-1).mean().item()
                self._kosha_entropies.append(k_ent)

            # B4. Interaction contribution (isolated kd_logits)
            if router_result is not None:
                kd = router_result.get("kd_logits")
                pol = router_result.get("policy_logits")
                if kd is not None:
                    kd_norm = kd.norm(dim=-1).mean().item()
                    self._interaction_norms.append(kd_norm)
                    if pol is not None:
                        pol_norm = pol.norm(dim=-1).mean().item()
                        self._interaction_ratios.append(
                            kd_norm / (pol_norm + 1e-6)
                        )

            # B5. Bliss governance
            if lambda_eff is not None:
                if lambda_eff.dim() > 0:
                    self._lambda_effs.append(lambda_eff.mean().item())
                    self._lambda_eff_stds.append(lambda_eff.std().item())

                    # Correlation: blissful Kosha vs lambda_eff
                    if k is not None:
                        blissful = k[..., 4]  # BLISSFUL index
                        # Flatten both to 1D for correlation
                        b_flat = blissful.reshape(-1)
                        l_flat = lambda_eff.reshape(-1)
                        if b_flat.numel() > 1:
                            corr = self._pearson_corr(b_flat, l_flat)
                            self._bliss_lambda_corrs.append(corr)
                else:
                    self._lambda_effs.append(lambda_eff.item())

            # B6. Router control parameters
            if router is not None:
                if hasattr(router, 'policy_scale'):
                    self._policy_scales.append(router.policy_scale.item())
                if hasattr(router, 'route_temp'):
                    self._route_temps.append(router.route_temp.item())

            # === C. Sensitivity probes ===
            if (self.enable_sensitivity_probes and router is not None
                    and hidden is not None and o_ctx is not None):
                self._run_sensitivity_probes(router, hidden, o_ctx, domain)

            # === D. Alpha divergence from residual baseline ===
            if alpha is not None and self._alpha_baseline is not None:
                # KL(alpha || alpha_baseline) — how much has governance changed routing?
                baseline = self._alpha_baseline.to(alpha.device)
                # Broadcast baseline to match batch dims
                kl = (alpha * ((alpha + 1e-8).log() - (baseline + 1e-8).log())).sum(dim=-1)
                self._alpha_divergences.append(kl.mean().item())

        # Trim all buffers
        self._trim_buffers()

    def cache_residual_baseline(
        self,
        router,
        hidden: torch.Tensor,
        o_ctx: torch.Tensor,
    ):
        """
        Cache the residual-only routing distribution as baseline.

        Run this ONCE before evaluation begins, with ablation switches
        set to use_kosha=False, use_domain=False, use_interaction=False.
        The cached baseline is used to compute alpha divergence: how much
        governance actually changes routing vs the original MLP-only system.

        Args:
            router: KoshaDomainRouter instance
            hidden: Sample hidden states [B, embed_dim]
            o_ctx: Sample ontological states [B, 32]
        """
        with torch.no_grad():
            # Save current ablation state
            orig_k = router.use_kosha
            orig_d = router.use_domain
            orig_i = router.use_interaction

            # Temporarily disable all structured policy
            router.use_kosha = False
            router.use_domain = False
            router.use_interaction = False

            result = router(hidden, o_ctx, domain=None)
            # Average over batch to get a single baseline distribution
            self._alpha_baseline = result["alpha"].mean(
                dim=tuple(range(result["alpha"].dim() - 1))
            ).detach().cpu()

            # Restore ablation state
            router.use_kosha = orig_k
            router.use_domain = orig_d
            router.use_interaction = orig_i

    def _run_sensitivity_probes(
        self,
        router,
        hidden: torch.Tensor,
        o_ctx: torch.Tensor,
        domain: Optional[torch.Tensor],
    ):
        """
        Measure routing sensitivity to Kosha, domain, and interaction perturbations.

        Runs 2-3 extra forward passes through the router with perturbed inputs.
        Uses a small batch slice (first 4 samples) to keep cost low.
        """
        # Use small slice to limit compute
        max_probe = min(4, hidden.shape[0])
        h = hidden[:max_probe].detach()
        o = o_ctx[:max_probe].detach()
        d = domain[:max_probe].detach() if domain is not None else None

        # Baseline routing
        base_result = router(h, o, domain=d)
        alpha_base = base_result["alpha"]

        # Probe 1: Perturb Kosha (shuffle dims 12:17 in o_ctx)
        o_perturbed = o.clone()
        k_slice = o_perturbed[..., 12:17]
        # Reverse the Kosha dimensions to create a meaningful perturbation
        o_perturbed[..., 12:17] = k_slice.flip(-1)
        perturbed_result = router(h, o_perturbed, domain=d)
        delta_k = (perturbed_result["alpha"] - alpha_base).abs().sum(dim=-1).mean().item()
        self._delta_alpha_kosha.append(delta_k)

        # Probe 2: Perturb domain (if available)
        if d is not None:
            d_perturbed = d.flip(-1)  # Reverse domain distribution
            perturbed_result = router(h, o, domain=d_perturbed)
            delta_d = (perturbed_result["alpha"] - alpha_base).abs().sum(dim=-1).mean().item()
            self._delta_alpha_domain.append(delta_d)

            # Probe 3: Isolate interaction — perturb both k and d together
            # vs perturbing each alone. Interaction effect = joint - sum of marginals
            both_result = router(h, o_perturbed, domain=d_perturbed)
            delta_both = (both_result["alpha"] - alpha_base).abs().sum(dim=-1).mean().item()
            interaction_effect = delta_both - (delta_k + delta_d)
            self._delta_alpha_interaction.append(abs(interaction_effect))

    @staticmethod
    def _pearson_corr(x: torch.Tensor, y: torch.Tensor) -> float:
        """Compute Pearson correlation between two 1D tensors."""
        x_centered = x - x.mean()
        y_centered = y - y.mean()
        num = (x_centered * y_centered).sum()
        den = (x_centered.pow(2).sum() * y_centered.pow(2).sum()).sqrt()
        if den.item() < 1e-8:
            return 0.0
        return (num / den).item()

    def _compute_rank_shift(
        self,
        base_logits: torch.Tensor,
        Z_star: torch.Tensor,
        target_ids: torch.Tensor,
        candidate_ids: torch.Tensor,
    ):
        """Compute how much re-ranking shifts the correct token's position."""
        base_ranks = (base_logits.unsqueeze(-1) >= base_logits.gather(
            -1, target_ids.unsqueeze(-1))).sum(dim=-1).float().mean().item()

        target_mask = (candidate_ids == target_ids.unsqueeze(-1))
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
        target_mask = (candidate_ids == target_ids.unsqueeze(-1))
        has_target = target_mask.any(dim=-1)
        if not has_target.any():
            return
        target_scores = (T * target_mask.unsqueeze(-1).float()).sum(dim=-2)
        valid_scores = target_scores[has_target]
        top_primitive = valid_scores.argmax(dim=-1)
        counts = torch.zeros(6, device=T.device)
        for p in range(6):
            counts[p] = (top_primitive == p).float().sum()
        total = counts.sum()
        if total > 0:
            self._primitive_contributions.append((counts / total).tolist())

    def _trim_buffers(self):
        """Trim all sliding window buffers."""
        buffers = [
            self._alpha_entropies, self._alpha_means, self._alpha_top1_probs,
            self._bliss_means, self._disagree_means, self._shortlist_coverages,
            self._rank_shifts, self._primitive_contributions,
            self._policy_norms, self._residual_norms, self._policy_residual_ratios,
            self._interaction_norms, self._interaction_ratios,
            self._kosha_means, self._kosha_entropies,
            self._lambda_effs, self._lambda_eff_stds, self._bliss_lambda_corrs,
            self._policy_scales, self._route_temps,
            self._delta_alpha_kosha, self._delta_alpha_domain,
            self._delta_alpha_interaction, self._alpha_divergences,
        ]
        for buf in buffers:
            if len(buf) > self.window_size:
                del buf[:-self.window_size]

    def get_summary(self) -> Dict[str, float]:
        """
        Get aggregated diagnostics over the sliding window.

        Returns:
            Dict of diagnostic metrics, organized by category:
            - cg_diag_alpha_*: Routing distribution stats
            - cg_gov_*: Governance causality signals
            - cg_probe_*: Sensitivity probe results
        """
        result: Dict[str, float] = {}

        # === A. Summary statistics ===
        self._avg_into(result, "cg_diag_alpha_entropy", self._alpha_entropies)
        self._avg_into(result, "cg_diag_alpha_top1", self._alpha_top1_probs)

        if self._alpha_means:
            n = len(self._alpha_means)
            for i, name in enumerate(self.PRIMITIVE_NAMES):
                result[f"cg_diag_alpha_{name}"] = (
                    sum(a[i] for a in self._alpha_means) / n
                )

        self._avg_into(result, "cg_diag_bliss_mean", self._bliss_means)
        self._avg_into(result, "cg_diag_disagree_mean", self._disagree_means)
        self._avg_into(result, "cg_diag_shortlist_coverage", self._shortlist_coverages)
        self._avg_into(result, "cg_diag_rank_shift", self._rank_shifts)

        if self._primitive_contributions:
            n = len(self._primitive_contributions)
            for i, name in enumerate(self.PRIMITIVE_NAMES):
                result[f"cg_diag_contrib_{name}"] = (
                    sum(c[i] for c in self._primitive_contributions) / n
                )

        # === B. Governance causality signals ===

        # B1. Policy vs residual influence
        self._avg_into(result, "cg_gov_policy_norm", self._policy_norms)
        self._avg_into(result, "cg_gov_residual_norm", self._residual_norms)
        self._avg_into(result, "cg_gov_policy_residual_ratio", self._policy_residual_ratios)

        # B3. Kosha statistics
        if self._kosha_means:
            n = len(self._kosha_means)
            for i, name in enumerate(self.KOSHA_NAMES):
                result[f"cg_gov_kosha_{name}"] = (
                    sum(k[i] for k in self._kosha_means) / n
                )
        self._avg_into(result, "cg_gov_kosha_entropy", self._kosha_entropies)

        # B4. Interaction contribution
        self._avg_into(result, "cg_gov_interaction_norm", self._interaction_norms)
        self._avg_into(result, "cg_gov_interaction_ratio", self._interaction_ratios)

        # B5. Bliss governance
        self._avg_into(result, "cg_gov_lambda_eff_mean", self._lambda_effs)
        self._avg_into(result, "cg_gov_lambda_eff_std", self._lambda_eff_stds)
        self._avg_into(result, "cg_gov_bliss_lambda_corr", self._bliss_lambda_corrs)

        # B6. Router control parameters
        self._avg_into(result, "cg_gov_policy_scale", self._policy_scales)
        self._avg_into(result, "cg_gov_route_temp", self._route_temps)

        # === C. Sensitivity probes ===
        self._avg_into(result, "cg_probe_delta_alpha_kosha", self._delta_alpha_kosha)
        self._avg_into(result, "cg_probe_delta_alpha_domain", self._delta_alpha_domain)
        self._avg_into(result, "cg_probe_delta_alpha_interaction", self._delta_alpha_interaction)

        # === D. Alpha divergence from residual baseline ===
        self._avg_into(result, "cg_gov_alpha_divergence", self._alpha_divergences)

        return result

    @staticmethod
    def _avg_into(result: dict, key: str, buf: list):
        """Average a buffer into the result dict if non-empty."""
        if buf:
            result[key] = sum(buf) / len(buf)
