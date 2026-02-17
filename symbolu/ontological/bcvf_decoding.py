#!/usr/bin/env python3
"""
BCVF Controlled Decoding Pipeline
===================================

Token-level controlled decoding using the Bidirectional Consistency
Verification Framework (BCVF). Implements three independently togglable
strategies on top of standard autoregressive softmax:

    Option A – Logit Modulation:  Adjust the full logit distribution by
        subtracting β·L from top-M candidate logits before softmax.

    Option B – Calibration Layer:  Post-hoc confidence assessment that
        bins predictions into HIGH / MEDIUM / LOW tiers based on
        max-probability and margin-to-second heuristics.

    Option C – Reranking:  After standard softmax, re-score the top-M
        candidates with BCVF and pick the one with the best adjusted
        score (base_logit − β·L).

All three options are independently switchable via ``DecodingConfig``,
enabling a full 2³ ablation matrix.

Core BCVF formula (B1 – Consistency Lagrangian):

    L = λf·(1 − sf)² + λb·(1 − sb)² + λc·(sf − sb)²

Where:
    sf = σ(5 · cos_sim(hidden, candidate))   (forward feasibility)
    sb = σ(5 · cos_sim(candidate, goal))     (backward goal alignment)

Usage::

    from symbolu.ontological.bcvf_decoding import (
        BCVFDecoder,
        DecodingConfig,
        decode_step,
    )

    config = DecodingConfig(use_rerank=True, use_calibration=True)
    decoder = BCVFDecoder(config)

    best_idx, probs, log_data = decoder.decode_step(
        hidden_state, vocab_embeddings, goal_embedding, logits=logits
    )
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

import numpy as np


# =========================================================================
# Configuration
# =========================================================================


@dataclass
class DecodingConfig:
    """
    Configuration for the BCVF controlled decoding pipeline.

    Attributes:
        top_m: Number of candidates kept after initial logit ranking.
        lambda_f: Weight for forward-feasibility penalty.
        lambda_b: Weight for backward-goal penalty.
        lambda_c: Weight for forward-backward consistency penalty.
        beta: Scaling factor applied to the Lagrangian before subtracting
              from base logits.  Start small (0.1–0.3).
        conf_high: Max-probability threshold for HIGH confidence tier.
        conf_med: Max-probability threshold for MEDIUM confidence tier.
        margin_low: Minimum margin (p1 − p2) required for HIGH confidence.
        use_rerank: Enable Option C (BCVF reranking).
        use_logit_mod: Enable Option A (logit modulation).
        use_calibration: Enable Option B (calibration layer).
        use_bayesian_energy: Enable Bayesian Energy Softmax.
        energy_alpha: Scaling for uncertainty boost (α in z' = z + α·σ² − β·penalty).
        energy_beta: Scaling for penalty term (β, default 0 = no penalty).
        uncertainty_mode: Uncertainty estimator: prob_var, dropout_var, margin_inv, or entropy_temp.
    """

    top_m: int = 500
    lambda_f: float = 1.0
    lambda_b: float = 1.0
    lambda_c: float = 0.25
    beta: float = 0.2
    conf_high: float = 0.80
    conf_med: float = 0.55
    margin_low: float = 0.07
    use_rerank: bool = True
    use_logit_mod: bool = False
    use_calibration: bool = True
    # Bayesian Energy Softmax
    use_bayesian_energy: bool = False
    energy_alpha: float = 0.1
    energy_beta: float = 0.0
    uncertainty_mode: str = "prob_var"  # prob_var, dropout_var, margin_inv, entropy_temp
    # Softmax-Entmax Mix
    use_softmax_entmax_mix: bool = False
    entmax_alpha: float = 1.5
    gamma_low: float = 1.0
    gamma_high: float = 5.0


# =========================================================================
# BCVF Scoring Components
# =========================================================================

if PYTORCH_AVAILABLE:

    class BCVFScoringModule(nn.Module):
        """
        Computes forward / backward BCVF scores and the consistency
        Lagrangian over a batch of token candidates.

        All operations are pure tensor math — no learnable parameters
        (unless a bilinear_scorer is provided for the backward score).
        """

        def __init__(self, config: DecodingConfig, bilinear_scorer=None):
            super().__init__()
            self.lambda_f = config.lambda_f
            self.lambda_b = config.lambda_b
            self.lambda_c = config.lambda_c
            self.beta = config.beta
            self.bilinear_scorer = bilinear_scorer

        # ------------------------------------------------------------------
        def forward_score(
            self, hidden: torch.Tensor, candidates: torch.Tensor
        ) -> torch.Tensor:
            """
            Cosine-similarity based forward feasibility score.

            Args:
                hidden: [B, D]
                candidates: [B, M, D]

            Returns:
                sf: [B, M]  values in (0, 1) via sigmoid.
            """
            sim = F.cosine_similarity(
                hidden.unsqueeze(1), candidates, dim=-1
            )  # [B, M]
            return torch.sigmoid(sim * 5.0)

        # ------------------------------------------------------------------
        def backward_score(
            self, candidates: torch.Tensor, goal: torch.Tensor
        ) -> torch.Tensor:
            """
            Cosine-similarity based backward goal-alignment score.

            Args:
                candidates: [B, M, D]
                goal: [B, D]

            Returns:
                sb: [B, M]  values in (0, 1) via sigmoid.
            """
            sim = F.cosine_similarity(
                candidates, goal.unsqueeze(1), dim=-1
            )  # [B, M]
            return torch.sigmoid(sim * 5.0)

        # ------------------------------------------------------------------
        def backward_score_bilinear(
            self, hidden: torch.Tensor, candidates: torch.Tensor
        ) -> torch.Tensor:
            """
            Bilinear backward score using learned scorer.

            Replaces cosine goal-alignment with learned bilinear scoring.
            Only called when ``self.bilinear_scorer`` is not None.

            Args:
                hidden: [B, D] hidden state.
                candidates: [B, M, D] candidate embeddings.

            Returns:
                sb: [B, M] scores in [0, 1] (clamped).
            """
            sb = self.bilinear_scorer(hidden, candidates)  # [B, M]
            return sb.clamp(0.0, 1.0)

        # ------------------------------------------------------------------
        def lagrangian(
            self, sf: torch.Tensor, sb: torch.Tensor
        ) -> torch.Tensor:
            """
            Consistency Lagrangian  L = λf(1−sf)² + λb(1−sb)² + λc(sf−sb)²

            Args:
                sf, sb: [B, M]

            Returns:
                L: [B, M]
            """
            return (
                self.lambda_f * (1.0 - sf) ** 2
                + self.lambda_b * (1.0 - sb) ** 2
                + self.lambda_c * (sf - sb) ** 2
            )

        # ------------------------------------------------------------------
        def rerank(
            self,
            base_logits: torch.Tensor,
            topM_indices: torch.Tensor,
            vocab_embeddings: torch.Tensor,
            hidden: torch.Tensor,
            goal: torch.Tensor,
        ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
            """
            Re-score the top-M candidates with BCVF and return the best
            token index together with diagnostic tensors.

            Args:
                base_logits: [B, V]  raw model logits.
                topM_indices: [B, M] indices into vocab.
                vocab_embeddings: [V, D] embedding matrix.
                hidden: [B, D] last-layer hidden state.
                goal: [B, D] goal embedding.

            Returns:
                best_idx: [B]   chosen token id.
                sf:       [B, M]
                sb:       [B, M]
                L:        [B, M]
            """
            candidates = vocab_embeddings[topM_indices]  # [B, M, D]
            sf = self.forward_score(hidden, candidates)
            sb = self.backward_score(candidates, goal)
            L = self.lagrangian(sf, sb)

            # Adjusted score = base logit − β·L
            base_scores = base_logits.gather(1, topM_indices)  # [B, M]
            adjusted = base_scores - self.beta * L

            best_rel = torch.argmax(adjusted, dim=-1)  # [B]
            best_idx = topM_indices.gather(
                1, best_rel.unsqueeze(-1)
            ).squeeze(-1)  # [B]

            return best_idx, sf, sb, L

    # =====================================================================
    # Calibration Layer
    # =====================================================================

    class CalibrationLayer:
        """
        Post-hoc confidence tier assignment.

        Classifies each prediction into HIGH / MEDIUM / LOW based on
        max probability and margin to the runner-up.
        """

        def __init__(self, config: DecodingConfig):
            self.conf_high = config.conf_high
            self.conf_med = config.conf_med
            self.margin_low = config.margin_low

        def __call__(
            self, probs: torch.Tensor
        ) -> Dict[str, torch.Tensor]:
            """
            Args:
                probs: [B, V] probability distribution.

            Returns:
                dict with keys ``confidence``, ``margin``,
                ``confidence_level`` (str list per batch element).
            """
            max_prob, _ = probs.max(dim=-1)  # [B]
            sorted_probs, _ = probs.sort(dim=-1, descending=True)
            second_prob = sorted_probs[:, 1]  # [B]
            margin = max_prob - second_prob  # [B]

            levels: list[str] = []
            for mp, mg in zip(
                max_prob.tolist(), margin.tolist()
            ):
                if mp >= self.conf_high and mg >= self.margin_low:
                    levels.append("HIGH")
                elif mp >= self.conf_med:
                    levels.append("MEDIUM")
                else:
                    levels.append("LOW")

            return {
                "confidence": max_prob,
                "margin": margin,
                "confidence_level": levels,
            }

    # =====================================================================
    # Entmax (sparse softmax alternative)
    # =====================================================================

    def _entmax_bisect(
        z: torch.Tensor,
        alpha: float = 1.3,
        n_iter: int = 50,
    ) -> torch.Tensor:
        """
        Compute alpha-entmax via bisection on shifted logits.

        Entmax generalises softmax (alpha=1) and sparsemax (alpha=2).
        For 1 < alpha < 2, it produces a sparse probability distribution
        where low-probability tokens are driven exactly to zero.

        The solution satisfies:
            p_i = max(0, (alpha-1)*z_i - tau)^{1/(alpha-1)}
        where tau is the unique threshold such that sum(p_i) = 1.

        Args:
            z: [*, V] logits (last dim is the simplex dimension).
            alpha: Tsallis alpha parameter (> 1).  Default 1.3.
            n_iter: Number of bisection iterations (50 → ~1e-15 precision).

        Returns:
            p: [*, V] sparse probability distribution summing to 1.
        """
        am1 = alpha - 1.0
        power = 1.0 / am1  # 1/(alpha-1)

        # Shift for numerical stability: max becomes 0
        z_max = z.max(dim=-1, keepdim=True)[0]
        z_shift = z - z_max

        # Bisection: find tau such that
        #   sum_i [am1 * z_shift_i - tau]_+^power = 1
        # On shifted scale, tau ∈ (-inf, 0).  Use [-10, 0] as bracket.
        tau_lo = torch.full_like(z_max, -10.0)
        tau_hi = torch.zeros_like(z_max)

        for _ in range(n_iter):
            tau_mid = (tau_lo + tau_hi) * 0.5
            p = (am1 * z_shift - tau_mid).clamp(min=0.0).pow(power)
            s = p.sum(dim=-1, keepdim=True)

            tau_lo = torch.where(s > 1.0, tau_mid, tau_lo)
            tau_hi = torch.where(s <= 1.0, tau_mid, tau_hi)

        # Final computation with converged tau
        tau = (tau_lo + tau_hi) * 0.5
        p = (am1 * z_shift - tau).clamp(min=0.0).pow(power)
        p_sum = p.sum(dim=-1, keepdim=True)
        return p / (p_sum + 1e-10)

    # =====================================================================
    # Main Decoder
    # =====================================================================

    class BCVFDecoder(nn.Module):
        """
        Full BCVF Controlled Decoding Pipeline.

        Wraps BCVFScoringModule + CalibrationLayer and exposes a single
        ``decode_step`` method that performs one token prediction with
        optional reranking, logit modulation, and calibration.

        When ``bilinear_scorer`` is provided and ``goal_strategy`` is
        ``"bilinear"``, the backward score (sb) is computed via learned
        bilinear scoring instead of cosine similarity with a goal
        embedding.  This bypasses goal embedding entirely.
        """

        def __init__(
            self,
            config: Optional[DecodingConfig] = None,
            bilinear_scorer=None,
            goal_strategy: str = "default",
        ):
            super().__init__()
            self.config = config or DecodingConfig()
            self.goal_strategy = goal_strategy
            self.scorer = BCVFScoringModule(
                self.config, bilinear_scorer=bilinear_scorer
            )
            self.calibrator = CalibrationLayer(self.config)
            self._entmax_mix_step_count = 0

        # ------------------------------------------------------------------
        # Bayesian Energy Softmax — uncertainty estimators
        # ------------------------------------------------------------------

        def _uncertainty_prob_var(
            self, probs: torch.Tensor
        ) -> torch.Tensor:
            """
            Probability-variance uncertainty: σ²_y = p_y · (1 − p_y).

            Args:
                probs: [B, V] probability distribution.

            Returns:
                sigma2: [B, V] per-token variance.
            """
            return probs * (1.0 - probs)

        def _uncertainty_margin_inv(
            self, probs: torch.Tensor
        ) -> torch.Tensor:
            """
            Inverse-margin uncertainty: σ² = 1 / (margin + ε).

            The margin is (p_top1 − p_top2).  The scalar σ² is
            broadcast to all candidate tokens.

            Args:
                probs: [B, V] probability distribution.

            Returns:
                sigma2: [B, V] (constant across V for each batch element).
            """
            sorted_probs, _ = probs.sort(dim=-1, descending=True)
            margin = sorted_probs[:, 0] - sorted_probs[:, 1]  # [B]
            eps = 1e-8
            sigma2 = 1.0 / (margin + eps)  # [B]
            return sigma2.unsqueeze(-1).expand_as(probs)  # [B, V]

        def _uncertainty_dropout_var(
            self,
            hidden_state: torch.Tensor,
            vocab_embeddings: torch.Tensor,
            K: int = 3,
            drop_rate: float = 0.1,
        ) -> torch.Tensor:
            """
            MC-Dropout uncertainty: K stochastic forward passes.

            Applies dropout to the hidden state, recomputes logits,
            and returns the per-token variance across the K passes.

            Args:
                hidden_state: [B, D] hidden state.
                vocab_embeddings: [V, D] embedding matrix.
                K: Number of stochastic forward passes.
                drop_rate: Dropout probability.

            Returns:
                sigma2: [B, V] per-token logit variance.
            """
            logit_samples = []
            for _ in range(K):
                mask = torch.bernoulli(
                    torch.full_like(hidden_state, 1.0 - drop_rate)
                ) / (1.0 - drop_rate)
                h_drop = hidden_state * mask
                logits_k = h_drop @ vocab_embeddings.T  # [B, V]
                logit_samples.append(logits_k)
            stacked = torch.stack(logit_samples, dim=0)  # [K, B, V]
            return stacked.var(dim=0)  # [B, V]

        def _compute_uncertainty(
            self,
            probs: torch.Tensor,
            logits: torch.Tensor,
            hidden_state: torch.Tensor,
            vocab_embeddings: torch.Tensor,
        ) -> torch.Tensor:
            """
            Dispatch to the configured uncertainty estimator.

            Args:
                probs: [B, V] softmax probabilities (from original logits).
                logits: [B, V] raw logits (unused by prob_var/margin_inv).
                hidden_state: [B, D] (used by dropout_var).
                vocab_embeddings: [V, D] (used by dropout_var).

            Returns:
                sigma2: [B, V] uncertainty estimates.
            """
            mode = self.config.uncertainty_mode
            if mode == "prob_var":
                return self._uncertainty_prob_var(probs)
            elif mode == "margin_inv":
                return self._uncertainty_margin_inv(probs)
            elif mode == "dropout_var":
                return self._uncertainty_dropout_var(
                    hidden_state, vocab_embeddings
                )
            else:
                raise ValueError(f"Unknown uncertainty mode: {mode}")

        # ------------------------------------------------------------------
        @torch.no_grad()
        def decode_step(
            self,
            hidden_state: torch.Tensor,
            vocab_embeddings: torch.Tensor,
            goal_embedding: torch.Tensor,
            logits: Optional[torch.Tensor] = None,
        ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
            """
            Perform one controlled decoding step.

            Args:
                hidden_state: [B, D]  final hidden state from the model.
                vocab_embeddings: [V, D]  token embedding matrix.
                goal_embedding: [B, D]  goal / intent vector.
                logits: [B, V]  optional pre-computed logits.

            Returns:
                best_token_index: [B]
                probs: [B, V]
                log_data: dict of diagnostic tensors / values.
            """
            cfg = self.config
            log_data: Dict[str, Any] = {}

            # ---- Stage 1: Base logits -----------------------------------
            if logits is None:
                logits = hidden_state @ vocab_embeddings.T  # [B, V]
            log_data["base_logits"] = logits

            # ---- Bayesian Energy Softmax --------------------------------
            if cfg.use_bayesian_energy:
                if cfg.uncertainty_mode == "entropy_temp":
                    # Entropy-conditioned temperature scaling
                    eps = 1e-9
                    # 1) base probs from raw logits
                    p_base = F.softmax(logits, dim=-1)
                    # 2) entropy: H = -sum(p * log(p + eps))
                    H = -(p_base * torch.log(p_base + eps)).sum(dim=-1)  # [B]
                    # 3) normalised entropy: Hn = H / log(V)
                    V = logits.shape[-1]
                    Hn = H / math.log(V)  # [B]
                    # 4) temperature: T = 1 + alpha * (1 - Hn)
                    T = 1.0 + cfg.energy_alpha * (1.0 - Hn)  # [B]
                    # 5) scale logits and apply penalty
                    penalty = torch.zeros_like(logits)
                    logits = (
                        logits / T.unsqueeze(-1)
                        - cfg.energy_beta * penalty
                    )
                    log_data["energy_mode"] = "bayesian"
                    log_data["entropy_temp_T_mean"] = float(T.mean().item())
                    log_data["entropy_Hn_mean"] = float(Hn.mean().item())
                    log_data["energy_alpha"] = cfg.energy_alpha
                    log_data["energy_beta"] = cfg.energy_beta
                    log_data["uncertainty_mode"] = cfg.uncertainty_mode
                else:
                    temp_probs = F.softmax(logits, dim=-1)
                    sigma2 = self._compute_uncertainty(
                        temp_probs, logits, hidden_state, vocab_embeddings,
                    )
                    penalty = torch.zeros_like(logits)
                    logits = (
                        logits
                        + cfg.energy_alpha * sigma2
                        - cfg.energy_beta * penalty
                    )
                    log_data["energy_mode"] = "bayesian"
                    log_data["energy_sigma2_mean"] = float(sigma2.mean().item())
                    log_data["energy_alpha"] = cfg.energy_alpha
                    log_data["energy_beta"] = cfg.energy_beta
                    log_data["uncertainty_mode"] = cfg.uncertainty_mode
            else:
                log_data["energy_mode"] = "baseline"

            # ---- Stage 2: Top-M candidate selection ---------------------
            top_m = min(cfg.top_m, logits.shape[-1])
            topM_scores, topM_indices = torch.topk(logits, top_m, dim=-1)
            log_data["topM_indices"] = topM_indices

            # ---- Stage 3: BCVF scores -----------------------------------
            candidates = vocab_embeddings[topM_indices]  # [B, M, D]
            sf = self.scorer.forward_score(hidden_state, candidates)

            # Backward score: bilinear or cosine
            use_bilinear = (
                self.goal_strategy == "bilinear"
                and self.scorer.bilinear_scorer is not None
            )
            if use_bilinear:
                sb = self.scorer.backward_score_bilinear(
                    hidden_state, candidates
                )
                # Log bilinear-specific diagnostics
                log_data["goal_strategy"] = "bilinear"
                log_data["sb_mean"] = sb.mean().item()
                log_data["sb_std"] = sb.std().item()
                sb_sorted, _ = sb.sort(dim=-1, descending=True)
                log_data["sb_top1"] = sb_sorted[:, 0].mean().item()
                if sb_sorted.shape[1] > 1:
                    log_data["sb_gap"] = (
                        sb_sorted[:, 0] - sb_sorted[:, 1]
                    ).mean().item()
                else:
                    log_data["sb_gap"] = 0.0
            else:
                sb = self.scorer.backward_score(candidates, goal_embedding)

            L = self.scorer.lagrangian(sf, sb)

            log_data["sf"] = sf
            log_data["sb"] = sb
            log_data["L"] = L

            # ---- Baseline sf/sb for the original top-1 (Risk A diagnostic) --
            original_best = torch.argmax(logits, dim=-1)  # [B]
            # Find where original_best sits in topM_indices
            orig_in_topM = (
                topM_indices == original_best.unsqueeze(-1)
            )  # [B, M] bool
            # Extract sf/sb for the baseline token
            orig_sf = (sf * orig_in_topM.float()).sum(dim=-1)  # [B]
            orig_sb = (sb * orig_in_topM.float()).sum(dim=-1)  # [B]
            log_data["baseline_sf"] = orig_sf
            log_data["baseline_sb"] = orig_sb

            # ---- Option C: Reranking ------------------------------------
            if cfg.use_rerank:
                adjusted_scores = topM_scores - cfg.beta * L
                best_rel = torch.argmax(adjusted_scores, dim=-1)
                best_token_index = topM_indices.gather(
                    1, best_rel.unsqueeze(-1)
                ).squeeze(-1)

                log_data["rerank_adjusted_scores"] = adjusted_scores
                log_data["rerank_selected"] = best_token_index
                log_data["rerank_changed"] = (
                    best_token_index != original_best
                )
                log_data["original_top_token"] = original_best

                # sf/sb delta diagnostics (Risk A: is the goal embedding
                # actually doing work?)
                sel_in_topM = (
                    topM_indices == best_token_index.unsqueeze(-1)
                )
                sel_sf = (sf * sel_in_topM.float()).sum(dim=-1)
                sel_sb = (sb * sel_in_topM.float()).sum(dim=-1)
                log_data["selected_sf"] = sel_sf
                log_data["selected_sb"] = sel_sb
                log_data["delta_sf"] = sel_sf - orig_sf
                log_data["delta_sb"] = sel_sb - orig_sb
            else:
                best_token_index = original_best

            # ---- Base probs (always computed for KL reference) ----------
            base_probs = F.softmax(logits, dim=-1)
            log_data["base_probs"] = base_probs

            # ---- Option A: Logit modulation -----------------------------
            # Track which logits produced the softmax distribution
            # (needed by softmax-entmax mix to apply entmax to the same
            # edited logits).
            effective_logits = logits
            if cfg.use_logit_mod:
                # Build full adjusted logit tensor (fill with -inf)
                adjusted_logits = torch.full_like(logits, float("-inf"))
                adjusted_logits.scatter_(
                    1, topM_indices, topM_scores - cfg.beta * L
                )
                probs = F.softmax(adjusted_logits, dim=-1)
                effective_logits = adjusted_logits

                # KL divergence and entropy delta (logit mod sanity)
                eps = 1e-10
                kl_base_mod = (
                    base_probs
                    * (torch.log(base_probs + eps) - torch.log(probs + eps))
                ).sum(dim=-1)  # [B]
                entropy_base = -(
                    base_probs * torch.log(base_probs + eps)
                ).sum(dim=-1)
                entropy_mod = -(
                    probs * torch.log(probs + eps)
                ).sum(dim=-1)
                log_data["kl_base_mod"] = kl_base_mod
                log_data["entropy_base"] = entropy_base
                log_data["entropy_mod"] = entropy_mod
                log_data["entropy_delta"] = entropy_mod - entropy_base
            else:
                probs = base_probs

            # ---- Softmax-Entmax(α) Mix ----------------------------------
            # Entropy-gated mixture: in high-entropy (uncertain) regimes,
            # entmax sparsifies the distribution, concentrating mass on
            # fewer tokens.  In low-entropy (confident) regimes, standard
            # softmax is preserved unchanged.
            if cfg.use_softmax_entmax_mix:
                p_soft = probs  # softmax on effective_logits

                # Entmax on the *same* edited logits
                p_ent = _entmax_bisect(
                    effective_logits, alpha=cfg.entmax_alpha,
                )

                # Entropy of softmax distribution: H = -Σ p log p
                _eps = 1e-10
                H = -(p_soft * torch.log(p_soft + _eps)).sum(
                    dim=-1, keepdim=True
                )  # [B, 1]

                # Dynamic gamma: 0 at low entropy, 1 at high entropy
                gamma = (
                    (H - cfg.gamma_low) / (cfg.gamma_high - cfg.gamma_low)
                ).clamp(0.0, 1.0)  # [B, 1]

                # Mix: p = (1 - γ) · softmax + γ · entmax
                probs = (1.0 - gamma) * p_soft + gamma * p_ent

                # Update token selection to reflect mixed distribution
                # (reranking selects its own token via BCVF scores,
                #  so only override when reranking is off)
                if not cfg.use_rerank:
                    best_token_index = torch.argmax(probs, dim=-1)

                # Diagnostics
                log_data["entropy_soft"] = H.squeeze(-1)
                log_data["gamma_entmax"] = gamma.squeeze(-1)
                log_data["p_soft_top1"] = p_soft.max(dim=-1)[0]
                log_data["p_ent_top1"] = p_ent.max(dim=-1)[0]
                log_data["p_mixed_top1"] = probs.max(dim=-1)[0]

                # Diagnostic prints for the first 10 decode steps
                self._entmax_mix_step_count += 1
                if self._entmax_mix_step_count <= 10:
                    for b in range(H.shape[0]):
                        print(
                            f"  [entmax-mix step "
                            f"{self._entmax_mix_step_count}] "
                            f"H={H[b, 0].item():.3f} "
                            f"γ={gamma[b, 0].item():.3f} "
                            f"top1_soft={p_soft[b].max().item():.4f} "
                            f"top1_ent={p_ent[b].max().item():.4f} "
                            f"top1_mixed={probs[b].max().item():.4f}"
                        )

            log_data["probs"] = probs

            # ---- Always compute confidence from the active distribution --
            # This ensures ECE/Brier are computed from actual max_prob
            # regardless of whether the calibration layer is enabled.
            max_prob, _ = probs.max(dim=-1)  # [B]
            sorted_probs, _ = probs.sort(dim=-1, descending=True)
            second_prob = sorted_probs[:, 1]  # [B]
            margin = max_prob - second_prob  # [B]
            log_data["confidence"] = max_prob
            log_data["margin"] = margin

            # ---- Option B: Calibration tier assignment -------------------
            if cfg.use_calibration:
                cal_info = self.calibrator(probs)
                # Calibrator also sets confidence/margin — let it override
                # so tier thresholds stay consistent with its own values
                log_data.update(cal_info)

            return best_token_index, probs, log_data

    # =====================================================================
    # Convenience wrapper
    # =====================================================================

    def decode_step(
        hidden_state: torch.Tensor,
        vocab_embeddings: torch.Tensor,
        goal_embedding: torch.Tensor,
        logits: Optional[torch.Tensor] = None,
        config: Optional[DecodingConfig] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
        """
        Stateless convenience wrapper around :class:`BCVFDecoder`.

        Creates a temporary decoder with the given config and runs a
        single decode step.  Prefer instantiating ``BCVFDecoder``
        directly for repeated use.
        """
        decoder = BCVFDecoder(config)
        return decoder.decode_step(
            hidden_state, vocab_embeddings, goal_embedding, logits
        )

else:
    # Stubs when PyTorch is not available
    class BCVFScoringModule:  # type: ignore[no-redef]
        pass

    class CalibrationLayer:  # type: ignore[no-redef]
        pass

    class BCVFDecoder:  # type: ignore[no-redef]
        pass

    def decode_step(*args, **kwargs):  # type: ignore[no-redef]
        raise ImportError("PyTorch is required for BCVF decoding")
