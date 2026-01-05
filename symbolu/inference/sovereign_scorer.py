"""
Sovereign Inference Scorer Module
=================================

Compute Sovereign-1 style signals during inference for quality scoring.

This module implements ontological alignment scoring using:
- The SOVEREIGN_R_MATRIX: 5 Vṛttis × 12 Layers target distribution
- Learned Vṛtti projectors: Map d_model hidden → 5D Vṛtti space
- Per-layer alignment scores against R-Matrix targets

The scorer provides interpretable quality metrics without backpropagation,
enabling:
1. Scoring generated sequences for ontological alignment
2. Detecting quality degradation during generation
3. Providing human-readable cognitive state interpretation

Vṛtti Categories:
- Pramāṇa (प्रमाण): Valid cognition, truth-bearing
- Vikalpa (विकल्प): Conceptual construction, imagination
- Viparyaya (विपर्यय): Misconception, error
- Nidrā (निद्रा): Sleep/dormancy, latent state
- Smṛti (स्मृति): Memory, recollection

Usage:
------
    from symbolu.inference import SovereignInferenceScorer

    scorer = SovereignInferenceScorer(dim=768)
    scorer.load_projectors(checkpoint)  # Load trained Vṛtti heads

    # Score a generation
    scores = scorer.score_sequence(
        hidden_states={0: h0, 5: h5, 11: h11},
        generated_tokens=token_ids,
        gunas=(sattva, rajas, tamas),
    )

    print(f"Ontological alignment: {scores['ontological_alignment']:.3f}")
    print(f"Coherence: {scores['coherence_score']:.3f}")
"""

import math
from typing import Dict, List, Tuple, Optional, Any

import torch
import torch.nn as nn
import torch.nn.functional as F


# =============================================================================
# SOVEREIGN R-MATRIX (From train_unified_llm.py:214-222)
# =============================================================================

# Target Vṛtti distribution per ontological layer
# Shape: [5 Vṛttis, 12 Layers]
SOVEREIGN_R_MATRIX = torch.tensor([
    # O1    O2    O3    O4    O5    O6    O7    O8    O9   O10   O11   O12
    # POT  IDEN  EXEC  STRC  COGN  AGEN  REAS  PURP  WITN  UNIF  INTG  ABSL
    [0.1, 0.5, 0.7, 0.7, 0.8, 0.6, 0.9, 0.8, 0.6, 0.7, 0.5, 0.9],  # Pramāṇa
    [0.1, 0.2, 0.2, 0.4, 0.4, 0.4, 0.1, 0.1, 0.2, 0.2, 0.2, 0.3],  # Vikalpa
    [0.1, 0.2, 0.4, 0.4, 0.2, 0.3, 0.1, 0.1, 0.1, 0.1, 0.1, 0.0],  # Viparyaya
    [0.7, 0.1, 0.1, 0.3, 0.1, 0.1, 0.0, 0.0, 0.3, 0.3, 0.4, 0.1],  # Nidrā
    [0.1, 0.1, 0.3, 0.3, 0.2, 0.2, 0.1, 0.0, 0.2, 0.2, 0.2, 0.8],  # Smṛti
], dtype=torch.float32)

# Vṛtti names for interpretation
VRTTI_NAMES = ["Pramāṇa", "Vikalpa", "Viparyaya", "Nidrā", "Smṛti"]

# Layer names for interpretation
LAYER_NAMES = [
    "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION", "O4_STRUCTURE",
    "O5_COGNITION", "O6_AGENCY", "O7_REASONING", "O8_PURPOSE",
    "O9_WITNESSES", "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING",
]


class VrttiProjector(nn.Module):
    """
    Learned projector from hidden state to 5D Vṛtti space.

    Maps d_model → 5 dimensions corresponding to the five Vṛttis.
    Each output dimension represents activation of that Vṛtti.

    Args:
        dim: Input hidden dimension (d_model)
        num_vrttis: Number of Vṛtti categories (default 5)
    """

    def __init__(self, dim: int, num_vrttis: int = 5):
        super().__init__()
        self.dim = dim
        self.num_vrttis = num_vrttis

        # Two-layer projection for expressiveness
        self.proj = nn.Sequential(
            nn.Linear(dim, dim // 4),
            nn.GELU(),
            nn.Linear(dim // 4, num_vrttis),
        )

    def forward(self, hidden_state: torch.Tensor) -> torch.Tensor:
        """
        Project hidden state to Vṛtti activations.

        Args:
            hidden_state: [B, D] or [B, N, D]

        Returns:
            vrtti_activations: [B, 5] or [B, N, 5] (softmax normalized)
        """
        logits = self.proj(hidden_state)
        return F.softmax(logits, dim=-1)


class SovereignInferenceScorer:
    """
    Compute Sovereign-1 signals during inference for quality scoring.

    This provides interpretable quality metrics based on:
    - Vṛtti alignment with R-Matrix targets per layer
    - Guna balance (Sattva/Rajas/Tamas)
    - Token-level coherence (bigram uniqueness)

    Addresses gap 2.4 from INFERENCE_HYBRID_TRANSFORMER_GAPS.md.

    Args:
        dim: Model hidden dimension
        num_vrttis: Number of Vṛtti categories (default 5)
        num_layers: Number of ontological layers (default 12)
        device: Torch device

    Attributes:
        r_matrix: Sovereign R-Matrix [5, 12]
        vrtti_projectors: Per-layer Vṛtti projection heads
    """

    def __init__(
        self,
        dim: int,
        num_vrttis: int = 5,
        num_layers: int = 12,
        device: Optional[torch.device] = None,
    ):
        self.dim = dim
        self.num_vrttis = num_vrttis
        self.num_layers = num_layers
        self.device = device or torch.device('cpu')

        # R-Matrix on device
        self.r_matrix = SOVEREIGN_R_MATRIX.to(self.device)

        # Per-layer Vṛtti projectors
        # In a full implementation, each layer could have its own projector
        # For simplicity, we use a shared projector with layer embedding
        self.vrtti_projector = VrttiProjector(dim, num_vrttis).to(self.device)

        # Layer embedding to condition the projector
        self.layer_embedding = nn.Embedding(num_layers, dim // 4).to(self.device)

        # Statistics
        self.scored_sequences = 0

    def to(self, device: torch.device) -> 'SovereignInferenceScorer':
        """Move scorer to device."""
        self.device = device
        self.r_matrix = self.r_matrix.to(device)
        self.vrtti_projector = self.vrtti_projector.to(device)
        self.layer_embedding = self.layer_embedding.to(device)
        return self

    def load_projectors(self, checkpoint: Dict[str, Any], prefix: str = "sovereign_"):
        """
        Load trained Vṛtti projector weights from checkpoint.

        Args:
            checkpoint: Training checkpoint dict
            prefix: Key prefix for sovereign weights
        """
        # Try to find projector weights
        proj_keys = [k for k in checkpoint.keys() if "vrtti_proj" in k.lower()]
        if proj_keys:
            proj_state = {
                k.replace(f"{prefix}vrtti_projector.", ""): v
                for k, v in checkpoint.items()
                if k.startswith(f"{prefix}vrtti_projector.")
            }
            if proj_state:
                self.vrtti_projector.load_state_dict(proj_state, strict=False)

    def compute_vrtti_distribution(
        self,
        hidden_state: torch.Tensor,
        layer_idx: int,
    ) -> torch.Tensor:
        """
        Compute Vṛtti distribution for a hidden state at given layer.

        Args:
            hidden_state: Hidden state [B, D] or [B, N, D]
            layer_idx: Ontological layer index (0-11)

        Returns:
            vrtti_dist: Vṛtti distribution [B, 5] or [B, N, 5]
        """
        # Get layer embedding
        layer_emb = self.layer_embedding(
            torch.tensor([layer_idx], device=self.device)
        )  # [1, dim//4]

        # For now, we don't condition on layer (would need architectural changes)
        # Just use the base projector
        vrtti_dist = self.vrtti_projector(hidden_state)

        return vrtti_dist

    def compute_layer_alignment(
        self,
        hidden_state: torch.Tensor,
        layer_idx: int,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute alignment between hidden state and R-Matrix target for layer.

        Args:
            hidden_state: Hidden state [B, D] or [B, N, D]
            layer_idx: Ontological layer index (0-11)

        Returns:
            alignment: Overall alignment score [0, 1]
            vrtti_scores: Per-Vṛtti alignment scores
        """
        # Get predicted Vṛtti distribution
        vrtti_pred = self.compute_vrtti_distribution(hidden_state, layer_idx)

        # Average over batch and sequence if needed
        if vrtti_pred.dim() == 3:
            vrtti_pred = vrtti_pred.mean(dim=(0, 1))  # [5]
        elif vrtti_pred.dim() == 2:
            vrtti_pred = vrtti_pred.mean(dim=0)  # [5]

        # Get target distribution from R-Matrix
        vrtti_target = self.r_matrix[:, layer_idx]  # [5]

        # Normalize target to probability distribution
        vrtti_target = vrtti_target / vrtti_target.sum()

        # Compute cosine similarity as alignment
        alignment = F.cosine_similarity(
            vrtti_pred.unsqueeze(0),
            vrtti_target.unsqueeze(0),
            dim=1,
        ).item()

        # Map from [-1, 1] to [0, 1]
        alignment = (alignment + 1) / 2

        # Per-Vṛtti scores
        vrtti_scores = {}
        for i, name in enumerate(VRTTI_NAMES):
            # How close is predicted to target for this Vṛtti
            diff = abs(vrtti_pred[i].item() - vrtti_target[i].item())
            vrtti_scores[name] = 1.0 - min(1.0, diff * 2)

        return alignment, vrtti_scores

    def score_step(
        self,
        layer_states: Dict[int, torch.Tensor],
        gunas: Tuple[float, float, float],
    ) -> Dict[str, float]:
        """
        Score a single generation step using layer states and Gunas.

        Args:
            layer_states: Dict mapping layer_idx -> hidden state
            gunas: (sattva, rajas, tamas) tuple

        Returns:
            scores: Dict with guna_balance, ontological_alignment, etc.
        """
        scores = {}
        s, r, t = gunas

        # Guna balance: higher Sattva relative to Rajas+Tamas is better
        scores['guna_balance'] = s / (r + t + 1e-6)
        scores['sattva'] = s
        scores['rajas'] = r
        scores['tamas'] = t

        # Ontological alignment across available layers
        if layer_states:
            alignments = []
            vrtti_details = {}

            for layer_idx, state in layer_states.items():
                if layer_idx < self.num_layers:
                    alignment, vrtti_scores = self.compute_layer_alignment(
                        state, layer_idx
                    )
                    alignments.append(alignment)
                    vrtti_details[LAYER_NAMES[layer_idx]] = vrtti_scores

            if alignments:
                scores['ontological_alignment'] = sum(alignments) / len(alignments)
                scores['layer_alignments'] = {
                    LAYER_NAMES[idx]: alignments[i]
                    for i, idx in enumerate(sorted(layer_states.keys()))
                    if idx < self.num_layers
                }

        # Coherence from Tamas (low Tamas = high coherence)
        scores['coherence_proxy'] = 1.0 - t

        return scores

    def score_sequence(
        self,
        hidden_states: Dict[int, torch.Tensor],
        generated_tokens: torch.Tensor,
        gunas: Optional[Tuple[float, float, float]] = None,
    ) -> Dict[str, Any]:
        """
        Score a complete generated sequence.

        Args:
            hidden_states: Dict mapping layer_idx -> hidden state
            generated_tokens: Generated token IDs [N] or [B, N]
            gunas: Optional final Guna state

        Returns:
            scores: Comprehensive quality scores
        """
        self.scored_sequences += 1

        scores = {
            'sequence_id': self.scored_sequences,
        }

        # Token-level coherence: unique bigram ratio
        if generated_tokens.numel() > 1:
            tokens = generated_tokens.flatten().tolist()

            # Unigram uniqueness
            unique_unigrams = len(set(tokens))
            scores['unigram_ratio'] = unique_unigrams / len(tokens)

            # Bigram uniqueness
            if len(tokens) >= 2:
                bigrams = list(zip(tokens[:-1], tokens[1:]))
                unique_bigrams = len(set(bigrams))
                scores['bigram_ratio'] = unique_bigrams / len(bigrams)
                scores['coherence_score'] = scores['bigram_ratio']
            else:
                scores['coherence_score'] = 1.0

        # Ontological alignment
        if hidden_states:
            alignments = []
            for layer_idx, state in hidden_states.items():
                if layer_idx < self.num_layers:
                    alignment, _ = self.compute_layer_alignment(state, layer_idx)
                    alignments.append(alignment)

            if alignments:
                scores['ontological_alignment'] = sum(alignments) / len(alignments)

        # Guna-weighted quality
        if gunas is not None:
            s, r, t = gunas
            scores['guna_sattva'] = s
            scores['guna_rajas'] = r
            scores['guna_tamas'] = t
            scores['guna_balance'] = s / (r + t + 1e-6)

            # Combined quality: alignment weighted by Guna balance
            if 'ontological_alignment' in scores:
                scores['sovereign_quality'] = (
                    scores['ontological_alignment'] *
                    (1.0 + scores['guna_balance']) / 2
                )

        # Overall quality score
        component_scores = [
            scores.get('coherence_score', 0.5),
            scores.get('ontological_alignment', 0.5),
        ]
        scores['overall_quality'] = sum(component_scores) / len(component_scores)

        return scores

    def interpret_scores(self, scores: Dict[str, Any]) -> str:
        """
        Generate human-readable interpretation of scores.

        Args:
            scores: Dict from score_sequence()

        Returns:
            interpretation: Human-readable string
        """
        lines = ["=== Sovereign Quality Report ==="]

        # Overall quality
        quality = scores.get('overall_quality', 0.5)
        if quality >= 0.8:
            quality_label = "Excellent"
        elif quality >= 0.6:
            quality_label = "Good"
        elif quality >= 0.4:
            quality_label = "Moderate"
        else:
            quality_label = "Poor"
        lines.append(f"Overall Quality: {quality:.3f} ({quality_label})")

        # Coherence
        if 'coherence_score' in scores:
            coh = scores['coherence_score']
            lines.append(f"Coherence: {coh:.3f} (bigram uniqueness)")

        # Ontological alignment
        if 'ontological_alignment' in scores:
            align = scores['ontological_alignment']
            lines.append(f"Ontological Alignment: {align:.3f}")

        # Guna state
        if 'guna_sattva' in scores:
            s, r, t = scores['guna_sattva'], scores['guna_rajas'], scores['guna_tamas']
            dominant = "Sattva" if s >= r and s >= t else ("Rajas" if r >= t else "Tamas")
            lines.append(f"Guna State: {dominant} (S={s:.2f}, R={r:.2f}, T={t:.2f})")

        return "\n".join(lines)

    def get_vrtti_interpretation(
        self,
        hidden_state: torch.Tensor,
        layer_idx: int,
    ) -> Dict[str, Any]:
        """
        Get detailed Vṛtti interpretation for a hidden state.

        Args:
            hidden_state: Hidden state tensor
            layer_idx: Ontological layer index

        Returns:
            interpretation: Dict with Vṛtti breakdown and meaning
        """
        vrtti_dist = self.compute_vrtti_distribution(hidden_state, layer_idx)

        if vrtti_dist.dim() > 1:
            vrtti_dist = vrtti_dist.mean(dim=tuple(range(vrtti_dist.dim() - 1)))

        vrtti_values = vrtti_dist.tolist()

        # Find dominant Vṛtti
        dominant_idx = vrtti_values.index(max(vrtti_values))
        dominant = VRTTI_NAMES[dominant_idx]

        # Meanings
        meanings = {
            "Pramāṇa": "Valid cognition - truthful, well-grounded output",
            "Vikalpa": "Conceptual construction - creative but potentially unfounded",
            "Viparyaya": "Misconception - likely erroneous or confused",
            "Nidrā": "Dormant state - underactivated, low engagement",
            "Smṛti": "Memory recall - drawing from learned patterns",
        }

        return {
            "layer": LAYER_NAMES[layer_idx],
            "dominant_vrtti": dominant,
            "meaning": meanings[dominant],
            "distribution": {name: val for name, val in zip(VRTTI_NAMES, vrtti_values)},
        }
