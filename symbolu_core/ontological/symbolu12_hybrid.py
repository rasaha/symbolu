#!/usr/bin/env python3
"""
SymbolU12 Hybrid - Best of Both Worlds
=======================================

Combines:
- MiniLM pre-trained encoder (fast, transfer learning)
- SymbolU12 ontological layers (interpretable, cognitive hierarchy)

This gives you:
✓ Pre-trained language understanding from MiniLM
✓ 12 interpretable ontological layers
✓ Coherence matrix C'[i,j]
✓ Witness layer for confidence
✓ Faster training than full SymbolU12 LLM

Architecture:
-------------
    Text → MiniLM Encoder (384D) → SymbolU12 Layers (12)
                                          ↓
                              Layer 1-4: Low-level processing
                              Layer 5-8: Semantic/Reasoning
                              Layer 9-12: Meta-cognitive

Usage:
------
    from symbolu_core.ontological.symbolu12_hybrid import SymbolU12Hybrid

    model = SymbolU12Hybrid()
    result = model.analyze("What is consciousness?")

    print(result["dominant_layer"])
    print(result["coherence"])
    print(result["witness_confidence"])
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import math

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    raise ImportError("PyTorch required for hybrid model")

import numpy as np

from symbolu_core.ontological.types import LAYER_NAMES, LAYER_INDEX


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SymbolU12HybridConfig:
    """Configuration for hybrid model."""

    # MiniLM encoder
    encoder_dim: int = 384  # MiniLM output dimension
    encoder_name: str = "minilm"

    # SymbolU12 layers
    hidden_dim: int = 256
    num_heads: int = 8
    num_concepts: int = 500
    num_intents: int = 30

    # Thresholds
    coherence_threshold: float = 0.7

    # Harmonic ratios
    HARMONIC_RATIOS: Dict[int, int] = None

    def __post_init__(self):
        if self.HARMONIC_RATIOS is None:
            self.HARMONIC_RATIOS = {
                1: 100000, 2: 50000, 3: 20000, 4: 10000,
                5: 5000, 6: 2000, 7: 1000, 8: 400,
                9: 100, 10: 50, 11: 10, 12: 1
            }


# =============================================================================
# SIMPLIFIED ONTOLOGICAL LAYERS
# =============================================================================

class OntologicalBlock(nn.Module):
    """
    A single ontological layer block.

    Each block represents one of the 12 cognitive layers with:
    - Self-attention for intra-layer processing
    - FFN for transformation
    - Phase modulation
    """

    def __init__(
        self,
        dim: int,
        num_heads: int = 4,
        layer_idx: int = 1,
        layer_name: str = "Potential",
    ):
        super().__init__()
        self.layer_idx = layer_idx
        self.layer_name = layer_name

        self.attn = nn.MultiheadAttention(dim, num_heads, batch_first=True)
        self.norm1 = nn.LayerNorm(dim)
        self.ffn = nn.Sequential(
            nn.Linear(dim, dim * 2),
            nn.GELU(),
            nn.Linear(dim * 2, dim),
        )
        self.norm2 = nn.LayerNorm(dim)

        # Layer-specific projection
        self.layer_proj = nn.Linear(dim, dim)

    def forward(
        self,
        x: torch.Tensor,
        phase: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        # Self-attention
        attn_out, _ = self.attn(x, x, x)
        x = self.norm1(x + attn_out)

        # FFN
        ffn_out = self.ffn(x)
        x = self.norm2(x + ffn_out)

        # Layer-specific transformation
        x = self.layer_proj(x)

        # Phase modulation
        if phase is not None:
            modulation = (1 + torch.cos(phase)) / 2
            x = x * modulation

        return x


class WitnessBlock(nn.Module):
    """
    Layer 9: WITNESS - Meta-cognitive monitoring.

    Special block that estimates confidence.
    """

    def __init__(self, dim: int):
        super().__init__()
        self.state_encoder = nn.Linear(dim, dim)
        self.confidence_head = nn.Sequential(
            nn.Linear(dim, dim // 2),
            nn.ReLU(),
            nn.Linear(dim // 2, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        # Global state
        state = self.state_encoder(x.mean(dim=1))

        # Confidence estimation
        confidence = self.confidence_head(state)

        return x, confidence


class UnifyingBlock(nn.Module):
    """
    Layer 10: UNIFYING - Coherence matrix computation.

    Computes C'[i,j] = C[i,j] × S[i,j]
    """

    def __init__(self, dim: int, num_layers: int = 12):
        super().__init__()
        self.num_layers = num_layers
        self.phase_proj = nn.Linear(dim, num_layers)

    def forward(
        self,
        layer_embeds: List[torch.Tensor],
        x: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        # Stack layer embeddings [B, N, dim]
        stacked = torch.stack(layer_embeds, dim=1)
        B, N, dim = stacked.shape

        # Semantic similarity S[i,j]
        normalized = F.normalize(stacked, dim=-1)
        S = torch.einsum('bid,bjd->bij', normalized, normalized)

        # Phase correlations C[i,j]
        phase_repr = torch.tanh(self.phase_proj(stacked.mean(dim=1)))
        phase_diff = phase_repr.unsqueeze(2) - phase_repr.unsqueeze(1)
        C = torch.cos(phase_diff * math.pi)

        # C'[i,j] = C[i,j] × S[i,j]
        C_prime = C * S

        # Global coherence J
        mask = torch.triu(torch.ones(N, N, device=C.device), diagonal=1)
        J = (C_prime * mask).sum(dim=(1, 2)) / (mask.sum() + 1e-8)

        # Unified representation
        weights = F.softmax(C_prime.sum(dim=-1), dim=-1)
        unified = torch.einsum('bn,bnd->bd', weights, stacked)

        return x, unified, C_prime, J


# =============================================================================
# HYBRID MODEL
# =============================================================================

class SymbolU12Hybrid(nn.Module):
    """
    SymbolU12 Hybrid Model

    Combines MiniLM encoder with 12 ontological layers.

    Best of both:
    - Pre-trained language understanding (MiniLM)
    - Interpretable cognitive hierarchy (SymbolU12)
    - Coherence enforcement (C'[i,j])
    - Confidence estimation (Witness layer)
    """

    def __init__(self, config: Optional[SymbolU12HybridConfig] = None):
        super().__init__()
        self.config = config or SymbolU12HybridConfig()

        # MiniLM encoder (lazy loaded)
        self._encoder = None

        # Project MiniLM output to hidden dim
        self.input_proj = nn.Linear(self.config.encoder_dim, self.config.hidden_dim)

        # 12 Ontological layer blocks
        layer_names = [
            "Potential", "Identity", "Execution", "Structure",
            "Cognition", "Agency", "Reasoning", "Purpose",
            "Witness", "Unifying", "Integration", "Absolving"
        ]

        self.onto_layers = nn.ModuleList()
        for i in range(12):
            if i == 8:  # Witness layer
                self.onto_layers.append(WitnessBlock(self.config.hidden_dim))
            elif i == 9:  # Unifying layer
                self.onto_layers.append(UnifyingBlock(self.config.hidden_dim))
            else:
                self.onto_layers.append(OntologicalBlock(
                    self.config.hidden_dim,
                    self.config.num_heads,
                    layer_idx=i + 1,
                    layer_name=layer_names[i],
                ))

        # Classification head (12 ontological classes)
        self.classifier = nn.Linear(self.config.hidden_dim, 12)

        # Task heads
        self.reasoning_head = nn.Linear(self.config.hidden_dim, 1)
        self.creativity_head = nn.Linear(self.config.hidden_dim, 1)

        # Master phase
        self.master_phase = nn.Parameter(torch.zeros(1))

    @property
    def encoder(self):
        """Lazy load MiniLM encoder."""
        if self._encoder is None:
            from symbolu_core.ontological.encoder import get_encoder
            self._encoder = get_encoder(self.config.encoder_name)
        return self._encoder

    def get_layer_phase(self, layer_idx: int) -> torch.Tensor:
        return self.config.HARMONIC_RATIOS[layer_idx] * self.master_phase

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Forward pass.

        Args:
            x: [B, encoder_dim] MiniLM embeddings

        Returns:
            Dict with all outputs
        """
        B = x.shape[0]

        # Project to hidden dim
        x = self.input_proj(x).unsqueeze(1)  # [B, 1, hidden_dim]

        layer_embeddings = []
        confidence = None
        C_prime = None
        J = None
        unified = None

        # Process through 12 layers
        for i, layer in enumerate(self.onto_layers):
            phase = self.get_layer_phase(i + 1)

            if i == 8:  # Witness
                x, confidence = layer(x)
            elif i == 9:  # Unifying
                x, unified, C_prime, J = layer(layer_embeddings, x)
            else:
                x = layer(x, phase)

            layer_embeddings.append(x.mean(dim=1))

        # Final representation
        final = x.squeeze(1)  # [B, hidden_dim]

        # Classification
        logits = self.classifier(final)
        probs = F.softmax(logits, dim=-1)

        # Task scores
        reasoning = torch.sigmoid(self.reasoning_head(final))
        creativity = torch.sigmoid(self.creativity_head(final))

        return {
            'logits': logits,
            'probs': probs,
            'layer_embeddings': layer_embeddings,
            'coherence_matrix': C_prime,
            'global_coherence': J,
            'witness_confidence': confidence,
            'reasoning_score': reasoning,
            'creativity_score': creativity,
            'hidden': final,
        }

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyze text with hybrid model.

        Args:
            text: Input text

        Returns:
            Dict with ontological analysis
        """
        self.eval()

        # Encode with MiniLM
        embedding = self.encoder.encode(text)
        x = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0)

        device = next(self.parameters()).device
        x = x.to(device)

        with torch.no_grad():
            outputs = self.forward(x)

        # Extract results
        probs = outputs['probs'].squeeze(0).cpu().numpy()
        coherence = outputs['global_coherence'].item() if outputs['global_coherence'] is not None else 0.0
        confidence = outputs['witness_confidence'].item() if outputs['witness_confidence'] is not None else 0.5

        # Dominant layer
        dominant_idx = int(np.argmax(probs))
        dominant_layer = LAYER_NAMES[dominant_idx]
        layer_confidence = float(probs[dominant_idx])

        # Uncertainty from witness
        uncertainty = 1.0 - confidence

        # Certainty level
        if uncertainty > 0.7:
            certainty_level = "very_uncertain"
        elif uncertainty > 0.4:
            certainty_level = "uncertain"
        elif uncertainty > 0.2:
            certainty_level = "moderate"
        else:
            certainty_level = "confident"

        # Probabilities
        probabilities = {
            LAYER_NAMES[i]: float(probs[i])
            for i in range(12)
        }

        # Coherence matrix as bhava vector
        if outputs['coherence_matrix'] is not None:
            bhava_vector = outputs['coherence_matrix'].squeeze(0).flatten().cpu().numpy().tolist()
        else:
            bhava_vector = [0.0] * 144

        # Full vector
        full_vector = probs.tolist() + bhava_vector

        # Strongest relationships
        if outputs['coherence_matrix'] is not None:
            strongest = self._extract_relationships(
                outputs['coherence_matrix'].squeeze(0).cpu().numpy()
            )
        else:
            strongest = []

        return {
            "dominant_layer": dominant_layer,
            "confidence": layer_confidence,
            "probabilities": probabilities,
            "uncertainty": uncertainty,
            "certainty_level": certainty_level,
            "coherence": coherence,
            "witness_confidence": confidence,
            "reasoning_score": outputs['reasoning_score'].item(),
            "creativity_score": outputs['creativity_score'].item(),
            "ontological_vector": probs.tolist(),
            "bhava_vector": bhava_vector,
            "full_vector": full_vector,
            "strongest_relationships": strongest,
            "engine_type": "symbolu12_hybrid",
        }

    def _extract_relationships(
        self,
        C_prime: np.ndarray,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Extract strongest relationships."""
        relationships = []

        for i in range(12):
            for j in range(12):
                if i != j:
                    relationships.append({
                        "from_layer": LAYER_NAMES[i],
                        "to_layer": LAYER_NAMES[j],
                        "strength": float(C_prime[i, j]),
                    })

        relationships.sort(key=lambda x: x["strength"], reverse=True)
        return relationships[:top_k]


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_hybrid_engine() -> SymbolU12Hybrid:
    """Create a SymbolU12 Hybrid engine."""
    return SymbolU12Hybrid()


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("   SYMBOLU12 HYBRID - Best of Both Worlds")
    print("=" * 70)

    print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│                        HYBRID ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Text Input                                                                │
│       │                                                                     │
│       ▼                                                                     │
│   ┌─────────────────────────────┐                                          │
│   │   MiniLM Encoder (384D)     │  ← Pre-trained language understanding   │
│   │   (sentence-transformers)   │                                          │
│   └─────────────────────────────┘                                          │
│       │                                                                     │
│       ▼                                                                     │
│   ┌─────────────────────────────┐                                          │
│   │   SymbolU12 Layers (1-12)   │  ← Interpretable cognitive hierarchy    │
│   │   • Potential → Absolving   │                                          │
│   │   • Witness (confidence)    │                                          │
│   │   • Unifying (C'[i,j])      │                                          │
│   └─────────────────────────────┘                                          │
│       │                                                                     │
│       ▼                                                                     │
│   ┌─────────────────────────────┐                                          │
│   │   Outputs:                  │                                          │
│   │   • 12D classification      │                                          │
│   │   • 144D coherence matrix   │                                          │
│   │   • Witness confidence      │                                          │
│   │   • Reasoning/Creativity    │                                          │
│   └─────────────────────────────┘                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
    """)

    print("\nAdvantages of Hybrid:")
    print("  ✓ Pre-trained encoder = less training data needed")
    print("  ✓ 12 interpretable layers = understand what's happening")
    print("  ✓ Coherence matrix = consistency checking")
    print("  ✓ Witness layer = hallucination detection")
    print("  ✓ Compatible with RAG pipeline")
