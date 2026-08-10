#!/usr/bin/env python3
"""
Semantic Coherence Integration — Appendix F Stage 7A
=====================================================

Bridges the existing SemanticCoherenceController (semantic_coherence.py)
with the UnifiedCoherenceController (Stage 4) by extracting S1, S2, S3
coherence signals and feeding them into the unified aggregation.

S1 (per-layer): C_i = α·S_i + β·R_i + γ·(1-E_i) + δ·P_i
S2 (global):    C_global = Σ_i w_i·C_i + coupling
S3 (loss):      L_coherence = L_task + λ·L_align + μ·L_consistency

Integration pattern::

    PhaseAttentionBlock.forward()
        → LayerCoherenceModule.compute_layer_coherence()
        → SemanticCoherenceIntegration.record_layer(s1_score)
        → ...after all layers...
        → SemanticCoherenceIntegration.compute_signals()
        → feed s1, s2, s3 into UnifiedCoherenceController.update()

Bounded introduction: S-score weights in UnifiedCoherenceConfig
initialized to 0.0, ramped during training with max bound 0.15.

Reference: Project_documentation/repository/docs/design/CONSCIOUS_GENERATION_DESIGN.md, Appendix F §F.10.6.1

Author: Sovereign-1 Training Initiative
Date: March 2026
Phase: Appendix F Stage 7A — SemanticCoherenceController Integration
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

import math


@dataclass
class SemanticCoherenceConfig:
    """Configuration for semantic coherence integration.

    Attributes:
        enable: Master switch for Stage 7A. When False, compute_signals()
            returns neutral defaults.
        num_layers: Number of transformer layers to track.
        coupling_threshold: Minimum correlation for cross-layer coupling
            contribution (S3 signal).
        s1_aggregation: How to aggregate per-layer S1 scores.
            'mean' or 'weighted' (by position).
    """
    enable: bool = True
    num_layers: int = 12
    coupling_threshold: float = 0.1
    s1_aggregation: str = "mean"


class SemanticCoherenceIntegration:
    """Collects per-layer coherence signals and computes S1/S2/S3.

    This module does NOT compute coherence from scratch — it receives
    pre-computed per-layer coherence scores from LayerCoherenceModule
    (semantic_coherence.py) and aggregates them for the unified controller.

    Usage::

        integration = SemanticCoherenceIntegration()

        # During forward pass, after each transformer layer:
        for layer_idx, layer in enumerate(model.layers):
            hidden = layer(hidden)
            s1_score = layer_coherence_module.compute_layer_coherence(hidden)
            integration.record_layer(layer_idx, s1_score)

        # After all layers:
        signals = integration.compute_signals()
        # signals = {"s1": 0.75, "s2": 0.80, "s3": 0.65}

        # Feed into UnifiedCoherenceController
        result = controller.update(s1=signals["s1"], s2=signals["s2"], s3=signals["s3"])

    Attributes:
        config: SemanticCoherenceConfig.
        layer_scores: Per-layer S1 coherence scores for current token.
    """

    def __init__(self, config: SemanticCoherenceConfig = None):
        self.config = config or SemanticCoherenceConfig()
        self.layer_scores: List[Optional[float]] = [None] * self.config.num_layers
        self._history: List[List[float]] = []  # Recent complete layer score vectors

    def record_layer(self, layer_idx: int, s1_score: float) -> None:
        """Record a per-layer S1 coherence score.

        Args:
            layer_idx: Layer index (0-based).
            s1_score: S1 coherence for this layer, typically in [0, 1].
        """
        if 0 <= layer_idx < len(self.layer_scores):
            self.layer_scores[layer_idx] = s1_score

    def compute_signals(self) -> Dict[str, float]:
        """Compute aggregated S1, S2, S3 from collected layer scores.

        Returns:
            Dict with:
                - s1: Aggregated per-layer coherence (mean or weighted).
                - s2: Global coherence (weighted sum + coupling).
                - s3: Cross-layer coupling strength.
        """
        if not self.config.enable:
            return {"s1": 0.5, "s2": 0.5, "s3": 0.5}

        # Collect valid scores
        valid_scores = [s for s in self.layer_scores if s is not None]
        if not valid_scores:
            return {"s1": 0.5, "s2": 0.5, "s3": 0.5}

        # S1: Aggregated per-layer coherence
        if self.config.s1_aggregation == "weighted":
            # Weight later layers more (they're closer to output)
            weights = [i + 1 for i in range(len(valid_scores))]
            w_sum = sum(weights)
            s1 = sum(w * s for w, s in zip(weights, valid_scores)) / w_sum
        else:
            s1 = sum(valid_scores) / len(valid_scores)

        # S2: Global coherence (weighted sum of per-layer)
        # Uniform weights for simplicity; can be learned later
        n = len(valid_scores)
        s2 = s1  # Base: same as mean S1

        # Add cross-layer coupling bonus (adjacent layer agreement)
        coupling = 0.0
        coupling_count = 0
        for i in range(len(valid_scores) - 1):
            agreement = 1.0 - abs(valid_scores[i] - valid_scores[i + 1])
            if agreement > self.config.coupling_threshold:
                coupling += agreement
                coupling_count += 1

        if coupling_count > 0:
            coupling_bonus = coupling / coupling_count
            s2 = 0.7 * s1 + 0.3 * coupling_bonus

        # S3: Cross-layer coupling strength (how aligned are adjacent layers)
        if len(valid_scores) > 1:
            diffs = [abs(valid_scores[i] - valid_scores[i + 1])
                     for i in range(len(valid_scores) - 1)]
            mean_diff = sum(diffs) / len(diffs)
            s3 = 1.0 - mean_diff  # Higher = more consistent across layers
        else:
            s3 = 0.5

        # Store for history tracking
        self._history.append(list(valid_scores))
        if len(self._history) > 20:
            self._history = self._history[-20:]

        return {"s1": s1, "s2": s2, "s3": s3}

    def reset(self) -> None:
        """Reset per-token layer scores for the next token."""
        self.layer_scores = [None] * self.config.num_layers

    def full_reset(self) -> None:
        """Reset all state for a new generation session."""
        self.reset()
        self._history.clear()
