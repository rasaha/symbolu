#!/usr/bin/env python3
"""
Penalty Score Provider for Logit Modulation
=============================================

Computes token-level penalty scores C_y for the logit modulation
decoding rule:

    modified_logits = base_logits + α·R_y − β·C_y

Supported penalty sources (independently togglable):

1. **repetition** — Penalizes tokens that have already appeared in the
   generated sequence.
2. **blacklist** — Penalizes tokens from a domain-specific blacklist.
3. **safety** — Applies safety classifier output as a penalty.
4. **constraint** — Rule-engine or ontology constraint violations.

All penalties are combined additively. Each source returns a tensor of
shape [B, V] (matching base_logits).

Author: Sovereign-1 Training Initiative
Date: February 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

try:
    import torch

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

if PYTORCH_AVAILABLE:

    @dataclass
    class PenaltyScorerConfig:
        """Configuration for penalty scoring.

        Attributes:
            enable_repetition: Whether to apply repetition penalty.
            repetition_penalty_value: Flat penalty for repeated tokens.
            repetition_decay: Exponential decay factor — more recent
                occurrences are penalized more. 1.0 means no decay.
            enable_blacklist: Whether to apply blacklist penalty.
            blacklist_token_ids: Set of token IDs to penalize.
            blacklist_penalty_value: Flat penalty for blacklisted tokens.
            enable_safety: Whether to apply safety penalty.
            enable_constraint: Whether to apply constraint penalty.
        """

        enable_repetition: bool = True
        repetition_penalty_value: float = 2.0
        repetition_decay: float = 0.95

        enable_blacklist: bool = False
        blacklist_token_ids: Set[int] = field(default_factory=set)
        blacklist_penalty_value: float = 10.0

        enable_safety: bool = False
        enable_constraint: bool = False

    class PenaltyScorer:
        """Computes combined token-level penalty scores.

        Multiple penalty sources are computed independently and summed.
        The result has shape [B, V] matching the model logits.
        """

        def __init__(self, config: Optional[PenaltyScorerConfig] = None):
            self.config = config or PenaltyScorerConfig()

        def score(
            self,
            base_logits: torch.Tensor,
            generated_ids: Optional[torch.Tensor] = None,
            safety_scores: Optional[torch.Tensor] = None,
            constraint_scores: Optional[torch.Tensor] = None,
        ) -> torch.Tensor:
            """Compute combined penalty scores.

            Args:
                base_logits: [B, V] raw model logits (used for shape).
                generated_ids: [B, T] token IDs generated so far.
                    Required for repetition penalty.
                safety_scores: [B, V] external safety classifier output.
                    Higher = more unsafe. Required when enable_safety=True.
                constraint_scores: [B, V] external constraint/rule engine
                    output. Required when enable_constraint=True.

            Returns:
                penalties: [B, V] combined penalty scores (all >= 0).
            """
            B, V = base_logits.shape
            device = base_logits.device

            penalties = torch.zeros(B, V, device=device, dtype=base_logits.dtype)

            if self.config.enable_repetition and generated_ids is not None:
                penalties = penalties + self._repetition_penalty(
                    B, V, device, base_logits.dtype, generated_ids
                )

            if self.config.enable_blacklist and self.config.blacklist_token_ids:
                penalties = penalties + self._blacklist_penalty(
                    B, V, device, base_logits.dtype
                )

            if self.config.enable_safety and safety_scores is not None:
                penalties = penalties + safety_scores.clamp(min=0.0)

            if self.config.enable_constraint and constraint_scores is not None:
                penalties = penalties + constraint_scores.clamp(min=0.0)

            return penalties

        def _repetition_penalty(
            self,
            B: int,
            V: int,
            device: torch.device,
            dtype: torch.dtype,
            generated_ids: torch.Tensor,
        ) -> torch.Tensor:
            """Compute repetition penalty based on generated history.

            Tokens that appear in the generated sequence get a penalty
            proportional to how recently they appeared (with decay).

            Args:
                B: Batch size.
                V: Vocabulary size.
                device: Target device.
                dtype: Target dtype.
                generated_ids: [B, T] token IDs generated so far.

            Returns:
                penalty: [B, V] repetition penalty tensor.
            """
            penalty = torch.zeros(B, V, device=device, dtype=dtype)
            T = generated_ids.size(1)

            if T == 0:
                return penalty

            base_val = self.config.repetition_penalty_value
            decay = self.config.repetition_decay

            # Apply decayed penalty: more recent tokens get higher penalty
            for t_offset in range(T):
                # t_offset=0 is the oldest token, T-1 is the most recent
                weight = base_val * (decay ** (T - 1 - t_offset))
                token_ids = generated_ids[:, t_offset]  # [B]
                # Scatter-add the penalty
                penalty.scatter_add_(
                    1,
                    token_ids.unsqueeze(1).clamp(0, V - 1),
                    torch.full((B, 1), weight, device=device, dtype=dtype),
                )

            return penalty

        def _blacklist_penalty(
            self,
            B: int,
            V: int,
            device: torch.device,
            dtype: torch.dtype,
        ) -> torch.Tensor:
            """Compute blacklist penalty.

            Args:
                B: Batch size.
                V: Vocabulary size.
                device: Target device.
                dtype: Target dtype.

            Returns:
                penalty: [B, V] blacklist penalty tensor.
            """
            penalty = torch.zeros(B, V, device=device, dtype=dtype)

            for token_id in self.config.blacklist_token_ids:
                if 0 <= token_id < V:
                    penalty[:, token_id] = self.config.blacklist_penalty_value

            return penalty

else:
    class PenaltyScorerConfig:  # type: ignore[no-redef]
        pass

    class PenaltyScorer:  # type: ignore[no-redef]
        pass
