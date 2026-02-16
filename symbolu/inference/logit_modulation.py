#!/usr/bin/env python3
"""
Logit Modulation Decoding
==========================

Inference-time logit shaping that replaces pure softmax decoding with
a modified decision rule:

    P(y | x) = softmax(z_y + α·R_y − β·C_y)

where:
    z_y = base model logits
    R_y = retrieval score for token y
    C_y = penalty score for token y
    α   = retrieval weight (float hyperparameter)
    β   = penalty weight (float hyperparameter)

This is pure inference-time logit modification — no model weights are
changed, no retraining occurs, and standard softmax is preserved.

Author: Sovereign-1 Training Initiative
Date: February 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import torch
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

if PYTORCH_AVAILABLE:

    @dataclass
    class LogitModulationConfig:
        """Configuration for logit modulation decoding.

        Attributes:
            alpha: Weight for retrieval scores. 0.0 disables retrieval.
            beta: Weight for penalty scores. 0.0 disables penalties.
            clamp_min: Minimum value for clamped modified logits.
            clamp_max: Maximum value for clamped modified logits.
            enable_retrieval: Whether to apply retrieval score modulation.
            enable_penalty: Whether to apply penalty score modulation.
        """

        alpha: float = 1.0
        beta: float = 1.0
        clamp_min: float = -50.0
        clamp_max: float = 50.0
        enable_retrieval: bool = True
        enable_penalty: bool = True

    class LogitModulator:
        """Applies inference-time logit shaping.

        Computes: modified_logits = base_logits + α·R − β·C
        then clamps to [clamp_min, clamp_max] and applies softmax.

        This is a stateless, functional component. It does not modify
        model weights or replace softmax — it only reshapes the logit
        distribution before the standard softmax+sampling step.
        """

        def __init__(self, config: Optional[LogitModulationConfig] = None):
            self.config = config or LogitModulationConfig()

        def modulate(
            self,
            base_logits: torch.Tensor,
            retrieval_scores: Optional[torch.Tensor] = None,
            penalty_scores: Optional[torch.Tensor] = None,
        ) -> torch.Tensor:
            """Apply logit modulation.

            Args:
                base_logits: [B, V] raw model logits.
                retrieval_scores: [B, V] retrieval relevance scores, or None.
                penalty_scores: [B, V] penalty scores, or None.

            Returns:
                modified_logits: [B, V] clamped modified logits.
            """
            modified = base_logits.clone()

            if self.config.enable_retrieval and retrieval_scores is not None:
                if retrieval_scores.shape != base_logits.shape:
                    raise ValueError(
                        f"retrieval_scores shape {retrieval_scores.shape} must "
                        f"match base_logits shape {base_logits.shape}"
                    )
                modified = modified + self.config.alpha * retrieval_scores

            if self.config.enable_penalty and penalty_scores is not None:
                if penalty_scores.shape != base_logits.shape:
                    raise ValueError(
                        f"penalty_scores shape {penalty_scores.shape} must "
                        f"match base_logits shape {base_logits.shape}"
                    )
                modified = modified - self.config.beta * penalty_scores

            # Clamp to prevent numeric instability
            modified = torch.clamp(
                modified, min=self.config.clamp_min, max=self.config.clamp_max
            )

            return modified

        def modulate_and_sample(
            self,
            base_logits: torch.Tensor,
            retrieval_scores: Optional[torch.Tensor] = None,
            penalty_scores: Optional[torch.Tensor] = None,
            temperature: float = 1.0,
            top_k: int = 0,
            top_p: float = 1.0,
        ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, Any]]:
            """Apply logit modulation, then sample a token.

            Args:
                base_logits: [B, V] raw model logits.
                retrieval_scores: [B, V] retrieval relevance scores, or None.
                penalty_scores: [B, V] penalty scores, or None.
                temperature: Sampling temperature.
                top_k: Top-k filtering (0 = disabled).
                top_p: Nucleus sampling threshold (1.0 = disabled).

            Returns:
                next_token: [B, 1] sampled token id.
                probs: [B, V] probability distribution after softmax.
                meta: Dict with diagnostic info.
            """
            modified_logits = self.modulate(
                base_logits, retrieval_scores, penalty_scores
            )

            # Apply temperature
            scaled_logits = modified_logits / max(temperature, 1e-8)

            # Top-k filtering
            if top_k > 0:
                top_k_vals = torch.topk(scaled_logits, min(top_k, scaled_logits.size(-1)))[0]
                threshold = top_k_vals[:, -1].unsqueeze(-1)
                scaled_logits = torch.where(
                    scaled_logits < threshold,
                    torch.full_like(scaled_logits, float("-inf")),
                    scaled_logits,
                )

            # Top-p (nucleus) filtering
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(scaled_logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                remove_mask = cumulative_probs > top_p
                remove_mask[:, 1:] = remove_mask[:, :-1].clone()
                remove_mask[:, 0] = False
                indices_to_remove = remove_mask.scatter(-1, sorted_indices, remove_mask)
                scaled_logits[indices_to_remove] = float("-inf")

            # Softmax and sample
            probs = F.softmax(scaled_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Diagnostics
            max_prob_per_batch = probs.max(dim=-1)[0]
            meta = {
                "alpha": self.config.alpha,
                "beta": self.config.beta,
                "logit_shift_mean": (modified_logits - base_logits).mean().item(),
                "logit_shift_std": (modified_logits - base_logits).std().item(),
                "modified_logits_mean": modified_logits.mean().item(),
                "modified_logits_std": modified_logits.std().item(),
                "max_prob": max_prob_per_batch.mean().item(),
                "max_prob_per_batch": max_prob_per_batch.tolist(),
            }

            return next_token, probs, meta

    # Convenience enum for experiment conditions
    class ModulationMode:
        """Named experiment conditions for ablation."""

        BASELINE = "baseline"
        RETRIEVAL_ONLY = "retrieval_only"
        PENALTY_ONLY = "penalty_only"
        RETRIEVAL_PENALTY = "retrieval_penalty"

        @staticmethod
        def get_config(mode: str, alpha: float = 1.0, beta: float = 1.0) -> LogitModulationConfig:
            """Get a LogitModulationConfig for a named condition.

            Args:
                mode: One of BASELINE, RETRIEVAL_ONLY, PENALTY_ONLY, RETRIEVAL_PENALTY.
                alpha: Retrieval weight.
                beta: Penalty weight.

            Returns:
                config: Configured LogitModulationConfig.
            """
            if mode == ModulationMode.BASELINE:
                return LogitModulationConfig(
                    alpha=0.0, beta=0.0,
                    enable_retrieval=False, enable_penalty=False,
                )
            elif mode == ModulationMode.RETRIEVAL_ONLY:
                return LogitModulationConfig(
                    alpha=alpha, beta=0.0,
                    enable_retrieval=True, enable_penalty=False,
                )
            elif mode == ModulationMode.PENALTY_ONLY:
                return LogitModulationConfig(
                    alpha=0.0, beta=beta,
                    enable_retrieval=False, enable_penalty=True,
                )
            elif mode == ModulationMode.RETRIEVAL_PENALTY:
                return LogitModulationConfig(
                    alpha=alpha, beta=beta,
                    enable_retrieval=True, enable_penalty=True,
                )
            else:
                raise ValueError(f"Unknown modulation mode: {mode}")

        @staticmethod
        def all_modes() -> List[str]:
            return [
                ModulationMode.BASELINE,
                ModulationMode.RETRIEVAL_ONLY,
                ModulationMode.PENALTY_ONLY,
                ModulationMode.RETRIEVAL_PENALTY,
            ]

else:
    # Stubs when PyTorch is unavailable
    class LogitModulationConfig:  # type: ignore[no-redef]
        pass

    class LogitModulator:  # type: ignore[no-redef]
        pass

    class ModulationMode:  # type: ignore[no-redef]
        pass
