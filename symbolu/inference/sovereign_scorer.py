#!/usr/bin/env python3
"""
Sovereign Inference Scorer
===========================

Compute Sovereign-1 style signals during inference for quality scoring.

Not used for loss/backprop, but for:
1. Scoring generated sequences
2. Detecting quality degradation
3. Providing interpretable quality metrics

Training Reference: Sovereign loss in symbolu/sovereign/loss.py and
train_unified_llm.py:6690-6703

Author: Sovereign-1 Training Initiative
Date: January 2026
"""

import torch
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import math


# Sovereign R-Matrix: Maps ontological layers to Vritti states
# Each column represents target Vritti weights for that layer
SOVEREIGN_R_MATRIX = torch.tensor([
    # O1    O2    O3    O4    O5    O6    O7    O8    O9    O10   O11   O12
    [1.0,  0.8,  0.5,  0.3,  0.2,  0.1,  0.1,  0.1,  0.1,  0.1,  0.1,  0.1],  # Pramana (Valid cognition)
    [0.1,  0.3,  0.8,  0.9,  0.7,  0.5,  0.3,  0.2,  0.1,  0.1,  0.1,  0.1],  # Viparyaya (Misconception)
    [0.1,  0.2,  0.3,  0.5,  0.7,  0.8,  0.7,  0.5,  0.3,  0.2,  0.1,  0.1],  # Vikalpa (Conceptualization)
    [0.1,  0.1,  0.1,  0.2,  0.3,  0.5,  0.7,  0.8,  0.9,  0.8,  0.5,  0.3],  # Nidra (Sleep/Rest)
    [0.1,  0.1,  0.1,  0.1,  0.2,  0.3,  0.5,  0.7,  0.8,  0.9,  0.9,  0.8],  # Smriti (Memory)
], dtype=torch.float32)


@dataclass
class SovereignScorerConfig:
    """Configuration for Sovereign scoring."""
    guna_weight: float = 0.3
    ontology_weight: float = 0.4
    coherence_weight: float = 0.3
    vritti_threshold: float = 0.5
    enable_r_matrix: bool = True


class SovereignInferenceScorer:
    """
    Compute Sovereign-1 style signals during inference for quality scoring.

    Provides interpretable quality scores:
    - guna_balance: How well Sattva/Rajas/Tamas are balanced
    - ontological_alignment: How well hidden states align with R-Matrix targets
    - coherence_score: Cross-layer and sequence coherence

    Example:
        scorer = SovereignInferenceScorer()

        # Score a generation
        scores = scorer.score_sequence(hidden_states, generated_tokens)
        print(f"Ontological alignment: {scores['ontological_alignment']:.2f}")
        print(f"Quality grade: {scores['quality_grade']}")
    """

    def __init__(self, config: Optional[SovereignScorerConfig] = None):
        """
        Initialize Sovereign scorer.

        Args:
            config: Scoring configuration
        """
        self.config = config or SovereignScorerConfig()
        self.r_matrix = SOVEREIGN_R_MATRIX

        # Scoring history
        self.score_history: List[Dict[str, float]] = []

    def score_sequence(
        self,
        hidden_states: Optional[List[torch.Tensor]] = None,
        generated_tokens: Optional[torch.Tensor] = None,
        gunas: Optional[Tuple[float, float, float]] = None,
    ) -> Dict[str, float]:
        """
        Score a generated sequence using Sovereign-1 metrics.

        Args:
            hidden_states: List of [B, T, D] or [B, D] hidden states per layer
            generated_tokens: [T] or [B, T] generated token IDs
            gunas: Optional (sattva, rajas, tamas) tuple

        Returns:
            scores: Dict with interpretable quality scores
        """
        scores = {}

        # Compute Guna balance score
        if gunas is not None:
            scores['guna_balance'] = self._compute_guna_balance(*gunas)
        else:
            scores['guna_balance'] = 0.5  # Neutral if not provided

        # Compute ontological alignment from hidden states
        if hidden_states is not None and len(hidden_states) > 0:
            scores['ontological_alignment'] = self._compute_ontological_alignment(hidden_states)
            scores['layer_coherence'] = self._compute_layer_coherence(hidden_states)
        else:
            scores['ontological_alignment'] = 0.5
            scores['layer_coherence'] = 0.5

        # Compute token-level coherence
        if generated_tokens is not None and generated_tokens.numel() > 1:
            scores['token_coherence'] = self._compute_token_coherence(generated_tokens)
        else:
            scores['token_coherence'] = 0.5

        # Combined coherence
        scores['coherence_score'] = (
            scores.get('layer_coherence', 0.5) * 0.5 +
            scores.get('token_coherence', 0.5) * 0.5
        )

        # Overall quality score
        scores['overall_quality'] = (
            self.config.guna_weight * scores['guna_balance'] +
            self.config.ontology_weight * scores['ontological_alignment'] +
            self.config.coherence_weight * scores['coherence_score']
        )

        # Quality grade
        scores['quality_grade'] = self._get_quality_grade(scores['overall_quality'])

        # Store in history
        self.score_history.append(scores)

        return scores

    def _compute_guna_balance(
        self,
        sattva: float,
        rajas: float,
        tamas: float,
    ) -> float:
        """
        Compute Guna balance score.

        Ideal balance is high Sattva with moderate Rajas and low Tamas.
        Training target: S=0.5, R=0.3, T=0.2

        Args:
            sattva, rajas, tamas: Guna values (should sum to ~1.0)

        Returns:
            balance: [0, 1] balance score
        """
        # Target distribution
        target_s, target_r, target_t = 0.5, 0.3, 0.2

        # Compute distance from target
        distance = math.sqrt(
            (sattva - target_s) ** 2 +
            (rajas - target_r) ** 2 +
            (tamas - target_t) ** 2
        )

        # Max distance is sqrt(3) (all in one corner)
        max_distance = math.sqrt(3)

        # Invert to get balance score (closer = higher)
        balance = 1.0 - (distance / max_distance)

        return balance

    def _compute_ontological_alignment(
        self,
        hidden_states: List[torch.Tensor],
    ) -> float:
        """
        Compute alignment with Sovereign R-Matrix targets.

        Each layer should exhibit the Vritti pattern specified in R-Matrix.

        Args:
            hidden_states: List of hidden states per layer

        Returns:
            alignment: [0, 1] alignment score
        """
        if not self.config.enable_r_matrix:
            return 0.5

        num_layers = min(len(hidden_states), 12)
        alignments = []

        for layer_idx in range(num_layers):
            hs = hidden_states[layer_idx]

            # Get target Vritti weights for this layer
            target_vritti = self.r_matrix[:, layer_idx]

            # Compute alignment (simplified projection)
            alignment = self._compute_vritti_alignment(hs, target_vritti)
            alignments.append(alignment)

        return sum(alignments) / len(alignments) if alignments else 0.5

    def _compute_vritti_alignment(
        self,
        hidden_state: torch.Tensor,
        target_vritti: torch.Tensor,
    ) -> float:
        """
        Compute alignment between hidden state and target Vritti.

        Uses simplified projection assuming hidden state encodes Vritti-like
        patterns in its structure.

        Args:
            hidden_state: [B, T, D] or [B, D] hidden state
            target_vritti: [5] target Vritti weights

        Returns:
            alignment: [0, 1] alignment score
        """
        # Flatten hidden state
        if hidden_state.dim() == 3:
            hs = hidden_state.mean(dim=1)  # [B, D]
        else:
            hs = hidden_state

        # Use first 5 dimensions as proxy for Vritti (simplified)
        if hs.shape[-1] >= 5:
            vritti_proxy = hs[..., :5]  # [B, 5]
        else:
            # Pad if needed
            vritti_proxy = F.pad(hs, (0, 5 - hs.shape[-1]))

        # Normalize
        vritti_proxy = F.softmax(vritti_proxy, dim=-1)
        target_norm = target_vritti / target_vritti.sum()

        # Cosine similarity
        if vritti_proxy.dim() == 2:
            vritti_proxy = vritti_proxy.mean(dim=0)

        vritti_proxy = vritti_proxy.to(target_norm.device)
        similarity = F.cosine_similarity(
            vritti_proxy.unsqueeze(0),
            target_norm.unsqueeze(0),
        ).item()

        # Map from [-1, 1] to [0, 1]
        return (similarity + 1) / 2

    def _compute_layer_coherence(
        self,
        hidden_states: List[torch.Tensor],
    ) -> float:
        """
        Compute coherence across layers.

        Adjacent layers should have smooth transitions.

        Args:
            hidden_states: List of hidden states per layer

        Returns:
            coherence: [0, 1] coherence score
        """
        if len(hidden_states) < 2:
            return 1.0

        similarities = []
        for i in range(1, len(hidden_states)):
            prev = hidden_states[i - 1]
            curr = hidden_states[i]

            # Mean pool if needed
            if prev.dim() == 3:
                prev = prev.mean(dim=1)
            if curr.dim() == 3:
                curr = curr.mean(dim=1)

            # Flatten for similarity
            prev_flat = prev.view(prev.size(0), -1)
            curr_flat = curr.view(curr.size(0), -1)

            sim = F.cosine_similarity(prev_flat, curr_flat).mean().item()
            similarities.append(sim)

        # Average similarity (higher = more coherent)
        avg_sim = sum(similarities) / len(similarities)

        # Map from [-1, 1] to [0, 1]
        return (avg_sim + 1) / 2

    def _compute_token_coherence(
        self,
        generated_tokens: torch.Tensor,
    ) -> float:
        """
        Compute token-level coherence using n-gram diversity.

        Args:
            generated_tokens: [T] or [B, T] generated tokens

        Returns:
            coherence: [0, 1] coherence score
        """
        if generated_tokens.dim() == 2:
            tokens = generated_tokens[0].tolist()
        else:
            tokens = generated_tokens.tolist()

        if len(tokens) < 2:
            return 1.0

        # Bigram diversity
        bigrams = list(zip(tokens[:-1], tokens[1:]))
        unique_bigrams = len(set(bigrams))
        total_bigrams = len(bigrams)
        bigram_diversity = unique_bigrams / max(1, total_bigrams)

        # Trigram diversity (if enough tokens)
        if len(tokens) >= 3:
            trigrams = list(zip(tokens[:-2], tokens[1:-1], tokens[2:]))
            unique_trigrams = len(set(trigrams))
            total_trigrams = len(trigrams)
            trigram_diversity = unique_trigrams / max(1, total_trigrams)
        else:
            trigram_diversity = 1.0

        # Combined diversity as coherence proxy
        # High diversity = good coherence (not repetitive)
        return 0.6 * bigram_diversity + 0.4 * trigram_diversity

    def _get_quality_grade(self, score: float) -> str:
        """
        Get letter grade for quality score.

        Args:
            score: [0, 1] quality score

        Returns:
            grade: Letter grade A-F
        """
        if score >= 0.9:
            return "A"
        elif score >= 0.8:
            return "B"
        elif score >= 0.7:
            return "C"
        elif score >= 0.6:
            return "D"
        return "F"

    def score_step(
        self,
        hidden_state: torch.Tensor,
        token_id: int,
        token_prob: float,
    ) -> Dict[str, float]:
        """
        Score a single generation step.

        Args:
            hidden_state: Current hidden state
            token_id: Generated token
            token_prob: Token probability

        Returns:
            step_scores: Dict with step-level scores
        """
        return {
            "confidence": token_prob,
            "hidden_magnitude": hidden_state.norm().item() if isinstance(hidden_state, torch.Tensor) else 0,
        }

    def get_status_line(self) -> str:
        """
        Get status line for monitoring display.

        Returns:
            status: Human-readable status string
        """
        if not self.score_history:
            return "Sovereign: no data"

        recent = self.score_history[-1]
        return (
            f"Sovereign: Q:{recent['overall_quality']:.2f} "
            f"[{recent['quality_grade']}] | "
            f"G:{recent['guna_balance']:.2f} O:{recent['ontological_alignment']:.2f}"
        )

    def get_average_scores(self) -> Dict[str, float]:
        """Get average scores across all scored sequences."""
        if not self.score_history:
            return {}

        keys = self.score_history[0].keys()
        averages = {}

        for key in keys:
            if key == 'quality_grade':
                continue
            values = [s[key] for s in self.score_history if isinstance(s.get(key), (int, float))]
            if values:
                averages[key] = sum(values) / len(values)

        return averages

    def reset(self) -> None:
        """Reset scoring history."""
        self.score_history = []
