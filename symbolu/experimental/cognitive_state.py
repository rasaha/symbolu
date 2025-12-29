#!/usr/bin/env python3
"""
Cognitive State: Structured Meaning Representation
==================================================

This module defines the CognitiveState - a structured, interpretable
representation of "understanding" at any moment in processing.

Instead of opaque hidden vectors (768 dim), we use structured states (~150 dim)
that have explicit semantic meaning.

The Paradigm Shift:
------------------
Token LLM:     hidden[768] → LM_head → logits[50K] → loss
State-Delta:   hidden[768] → delta_pred → delta[768] → loss
Ontological:   hidden[768] → projector → CognitiveState[~150] → delta → loss

Memory Comparison at 10M context:
--------------------------------
Token:       2 TB (impossible)
State-Delta: 30 GB (fits on H200)
Ontological: 6 GB (fits on consumer GPU)
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F
from enum import Enum


# =============================================================================
# ONTOLOGICAL CATEGORIES (Bhava States)
# =============================================================================

class OntologyLayer(Enum):
    """
    Fundamental ontological categories (Bhava states).

    These represent WHERE in meaning-space the current understanding sits.
    Based on SymbolU's ontological model.
    """
    # Descriptive layers
    FACTUAL = 0          # Stating facts
    ANALYTICAL = 1       # Analyzing/explaining
    EVALUATIVE = 2       # Judging/assessing

    # Rhetorical layers
    NARRATIVE = 3        # Telling a story
    ARGUMENTATIVE = 4    # Making a case
    INSTRUCTIVE = 5      # Teaching/directing

    # Epistemic layers
    CERTAIN = 6          # High confidence claims
    SPECULATIVE = 7      # Possibilities/hypotheticals
    QUESTIONING = 8      # Seeking information

    # Emotional layers
    POSITIVE = 9         # Positive sentiment
    NEGATIVE = 10        # Negative sentiment
    NEUTRAL = 11         # Neutral/objective


class ConstraintType(Enum):
    """Types of constraints on next valid states."""
    PHONOTACTIC = 0      # What sounds can follow
    SYNTACTIC = 1        # What grammar allows
    SEMANTIC = 2         # What meaning allows
    PRAGMATIC = 3        # What context allows
    ONTOLOGICAL = 4      # What Bhava transitions are legal


# =============================================================================
# COGNITIVE STATE DATACLASS
# =============================================================================

@dataclass
class CognitiveState:
    """
    Structured representation of understanding at time t.

    This replaces opaque hidden states with interpretable components.
    Total dimensionality: ~150 (vs 768 for hidden, 50K for vocab)

    Components:
    -----------
    1. Phoneme Layer (~44 dims): Acoustic/phonemic energy distribution
    2. Topic Layer (~64 dims): Domain/subject embedding
    3. Ontology Layer (~12 dims): Bhava state probabilities
    4. Dynamics Layer (~4 dims): Coherence, entropy, confidence, momentum
    5. Constraint Mask: Sparse tensor of legal next tokens

    Example State after "The company reported strong revenue growth, but...":
    -------------------------------------------------------------------------
    phoneme_energy: [h:0.1, ʌ:0.2, t:0.3, ...]  # Recent acoustic pattern
    topic: [0.8, 0.1, ...]  # Business/finance domain
    ontology: [ANALYTICAL:0.6, EVALUATIVE:0.3, NEGATIVE:0.1]
    coherence: 0.85
    entropy: 0.6  # Uncertainty increased by "but"
    confidence: 0.5
    momentum: 0.3  # How fast meaning is changing
    """

    # Phonemic layer: energy distribution over phoneme inventory
    # Using IPA-based phoneme set (~44 for English, extensible)
    phoneme_energy: torch.Tensor  # [num_phonemes] default 44

    # Topic/domain embedding (learned, compressed)
    topic_embedding: torch.Tensor  # [topic_dim] default 64

    # Ontological position: probability over Bhava states
    ontology_probs: torch.Tensor  # [num_ontology_layers] default 12

    # Dynamic quantities
    coherence: float = 0.5      # Phase alignment (0-1)
    entropy: float = 0.5        # Uncertainty level (0-1)
    confidence: float = 0.5     # Belief strength (0-1)
    momentum: float = 0.0       # Rate of meaning change

    # Constraint mask (sparse): which tokens are legal next
    # None means all tokens legal, otherwise sparse indices
    constraint_mask: Optional[torch.Tensor] = None  # [num_legal_tokens]

    def to_tensor(self) -> torch.Tensor:
        """Flatten state to single tensor for neural processing."""
        dynamics = torch.tensor([
            self.coherence,
            self.entropy,
            self.confidence,
            self.momentum
        ], device=self.phoneme_energy.device)

        return torch.cat([
            self.phoneme_energy,      # 44
            self.topic_embedding,     # 64
            self.ontology_probs,      # 12
            dynamics,                 # 4
        ])  # Total: 124 dimensions

    @classmethod
    def from_tensor(
        cls,
        tensor: torch.Tensor,
        num_phonemes: int = 44,
        topic_dim: int = 64,
        num_ontology: int = 12,
    ) -> 'CognitiveState':
        """Reconstruct state from flattened tensor."""
        idx = 0

        phoneme_energy = tensor[idx:idx + num_phonemes]
        idx += num_phonemes

        topic_embedding = tensor[idx:idx + topic_dim]
        idx += topic_dim

        ontology_probs = tensor[idx:idx + num_ontology]
        idx += num_ontology

        dynamics = tensor[idx:idx + 4]

        return cls(
            phoneme_energy=phoneme_energy,
            topic_embedding=topic_embedding,
            ontology_probs=ontology_probs,
            coherence=dynamics[0].item(),
            entropy=dynamics[1].item(),
            confidence=dynamics[2].item(),
            momentum=dynamics[3].item(),
        )

    @classmethod
    def zeros(
        cls,
        device: torch.device = torch.device('cpu'),
        num_phonemes: int = 44,
        topic_dim: int = 64,
        num_ontology: int = 12,
    ) -> 'CognitiveState':
        """Create zero-initialized state."""
        return cls(
            phoneme_energy=torch.zeros(num_phonemes, device=device),
            topic_embedding=torch.zeros(topic_dim, device=device),
            ontology_probs=torch.ones(num_ontology, device=device) / num_ontology,
            coherence=0.5,
            entropy=0.5,
            confidence=0.5,
            momentum=0.0,
        )

    @property
    def dim(self) -> int:
        """Total state dimensionality."""
        return (
            len(self.phoneme_energy) +
            len(self.topic_embedding) +
            len(self.ontology_probs) +
            4  # dynamics
        )


@dataclass
class StateDelta:
    """
    Change in cognitive state: ΔS = S_{t+1} - S_t

    This is what the model learns to predict.

    Instead of predicting P(token_{t+1}), we predict how understanding changes.
    """

    # Changes in each component
    phoneme_delta: torch.Tensor       # Change in phoneme energy
    topic_delta: torch.Tensor         # Change in topic embedding
    ontology_delta: torch.Tensor      # Change in Bhava probabilities

    # Changes in dynamics
    coherence_delta: float = 0.0
    entropy_delta: float = 0.0
    confidence_delta: float = 0.0
    momentum_delta: float = 0.0

    def to_tensor(self) -> torch.Tensor:
        """Flatten delta to single tensor."""
        dynamics = torch.tensor([
            self.coherence_delta,
            self.entropy_delta,
            self.confidence_delta,
            self.momentum_delta,
        ], device=self.phoneme_delta.device)

        return torch.cat([
            self.phoneme_delta,
            self.topic_delta,
            self.ontology_delta,
            dynamics,
        ])

    @classmethod
    def from_states(cls, s_t: CognitiveState, s_next: CognitiveState) -> 'StateDelta':
        """Compute delta between two states."""
        return cls(
            phoneme_delta=s_next.phoneme_energy - s_t.phoneme_energy,
            topic_delta=s_next.topic_embedding - s_t.topic_embedding,
            ontology_delta=s_next.ontology_probs - s_t.ontology_probs,
            coherence_delta=s_next.coherence - s_t.coherence,
            entropy_delta=s_next.entropy - s_t.entropy,
            confidence_delta=s_next.confidence - s_t.confidence,
            momentum_delta=s_next.momentum - s_t.momentum,
        )

    def apply_to(self, state: CognitiveState) -> CognitiveState:
        """Apply this delta to a state to get next state."""
        return CognitiveState(
            phoneme_energy=state.phoneme_energy + self.phoneme_delta,
            topic_embedding=state.topic_embedding + self.topic_delta,
            ontology_probs=F.softmax(state.ontology_probs + self.ontology_delta, dim=-1),
            coherence=max(0, min(1, state.coherence + self.coherence_delta)),
            entropy=max(0, min(1, state.entropy + self.entropy_delta)),
            confidence=max(0, min(1, state.confidence + self.confidence_delta)),
            momentum=state.momentum + self.momentum_delta,
        )


# =============================================================================
# STATE PROJECTOR: Hidden → CognitiveState
# =============================================================================

class StateProjector(nn.Module):
    """
    Projects transformer hidden states to structured CognitiveState.

    This is the bridge between Tier 2 (opaque hidden) and Tier 3 (structured).

    Architecture:
        hidden[768] → linear layers → CognitiveState[~124]

    Each component is projected separately for interpretability.
    """

    def __init__(
        self,
        hidden_dim: int = 768,
        num_phonemes: int = 44,
        topic_dim: int = 64,
        num_ontology: int = 12,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_phonemes = num_phonemes
        self.topic_dim = topic_dim
        self.num_ontology = num_ontology

        # Separate projectors for each component (interpretability)
        self.phoneme_proj = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 4, num_phonemes),
            nn.Softmax(dim=-1),  # Energy distribution sums to 1
        )

        self.topic_proj = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, topic_dim),
        )

        self.ontology_proj = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 4, num_ontology),
            nn.Softmax(dim=-1),  # Probability over Bhava states
        )

        self.dynamics_proj = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 4, 4),
            nn.Sigmoid(),  # All dynamics in [0, 1]
        )

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        """
        Project hidden states to cognitive state tensor.

        Args:
            hidden: [B, T, hidden_dim] or [B, hidden_dim]

        Returns:
            state_tensor: [B, T, state_dim] or [B, state_dim]
        """
        phoneme = self.phoneme_proj(hidden)
        topic = self.topic_proj(hidden)
        ontology = self.ontology_proj(hidden)
        dynamics = self.dynamics_proj(hidden)

        return torch.cat([phoneme, topic, ontology, dynamics], dim=-1)

    def to_cognitive_state(self, hidden: torch.Tensor) -> CognitiveState:
        """
        Project single hidden state to CognitiveState object.

        Args:
            hidden: [hidden_dim] single position

        Returns:
            CognitiveState object
        """
        state_tensor = self.forward(hidden)
        return CognitiveState.from_tensor(
            state_tensor,
            num_phonemes=self.num_phonemes,
            topic_dim=self.topic_dim,
            num_ontology=self.num_ontology,
        )

    @property
    def state_dim(self) -> int:
        return self.num_phonemes + self.topic_dim + self.num_ontology + 4


# =============================================================================
# ONTOLOGICAL STATE DELTA PREDICTOR
# =============================================================================

class OntologicalDeltaPredictor(nn.Module):
    """
    Predicts state deltas in structured CognitiveState space.

    This is the Tier 3 equivalent of StateDeltaPredictor (Tier 2).

    Key difference:
    - Tier 2: Predicts delta in opaque 768-dim hidden space
    - Tier 3: Predicts delta in structured 124-dim meaning space

    Training signal:
        L = MSE(ΔS_pred, ΔS_actual)
          + ontology_violation_penalty
          + coherence_drift_penalty
          + entropy_mismatch_penalty
    """

    def __init__(
        self,
        state_dim: int = 124,
        hidden_dim: int = 256,
        num_layers: int = 2,
        dropout: float = 0.1,
        num_phonemes: int = 44,
        topic_dim: int = 64,
        num_ontology: int = 12,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.num_phonemes = num_phonemes
        self.topic_dim = topic_dim
        self.num_ontology = num_ontology

        # Delta predictor network
        layers = []
        in_dim = state_dim
        for i in range(num_layers - 1):
            layers.extend([
                nn.Linear(in_dim, hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout),
            ])
            in_dim = hidden_dim
        layers.append(nn.Linear(in_dim, state_dim))

        self.delta_net = nn.Sequential(*layers)
        self.norm = nn.LayerNorm(state_dim)

        # Ontology transition matrix (learnable Bhava transition priors)
        # Some transitions are more likely than others
        self.ontology_transition = nn.Parameter(
            torch.eye(num_ontology) * 0.5 + torch.ones(num_ontology, num_ontology) * 0.05
        )

    def forward(self, state_t: torch.Tensor) -> torch.Tensor:
        """
        Predict state delta from current state.

        Args:
            state_t: [B, T, state_dim] current cognitive states

        Returns:
            delta: [B, T-1, state_dim] predicted deltas
        """
        # Predict delta for each position
        delta = self.delta_net(state_t[:, :-1])
        return self.norm(delta)

    def compute_loss(
        self,
        state_sequence: torch.Tensor,
        lambda_ontology: float = 0.1,
        lambda_coherence: float = 0.1,
        lambda_entropy: float = 0.1,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Compute ontological state delta loss.

        This is richer than simple MSE - it includes ontological constraints.

        Args:
            state_sequence: [B, T, state_dim] sequence of states

        Returns:
            loss: Total loss
            metrics: Dict of component losses
        """
        B, T, D = state_sequence.shape

        # Actual deltas
        actual_delta = state_sequence[:, 1:] - state_sequence[:, :-1]  # [B, T-1, D]

        # Predicted deltas
        pred_delta = self.forward(state_sequence)  # [B, T-1, D]

        # 1. Base MSE loss on delta prediction
        delta_loss = F.mse_loss(pred_delta, actual_delta)

        # 2. Ontology transition loss
        # Extract ontology components
        onto_start = self.num_phonemes + self.topic_dim
        onto_end = onto_start + self.num_ontology

        onto_t = state_sequence[:, :-1, onto_start:onto_end]  # [B, T-1, num_onto]
        onto_next = state_sequence[:, 1:, onto_start:onto_end]  # [B, T-1, num_onto]

        # Predicted transition based on transition matrix
        expected_onto = torch.einsum('bti,ij->btj', onto_t, F.softmax(self.ontology_transition, dim=-1))
        ontology_loss = F.mse_loss(onto_next, expected_onto)

        # 3. Coherence drift penalty (coherence shouldn't change too fast)
        coherence_idx = -4  # 4th from end in dynamics
        coherence_delta = actual_delta[:, :, coherence_idx]
        coherence_loss = (coherence_delta ** 2).mean()  # Penalize large coherence changes

        # 4. Entropy alignment (entropy changes should be smooth)
        entropy_idx = -3
        entropy_delta = actual_delta[:, :, entropy_idx]
        entropy_loss = (entropy_delta ** 2).mean()

        # Combined loss
        total_loss = (
            delta_loss +
            lambda_ontology * ontology_loss +
            lambda_coherence * coherence_loss +
            lambda_entropy * entropy_loss
        )

        metrics = {
            'delta_loss': delta_loss.detach(),
            'ontology_loss': ontology_loss.detach(),
            'coherence_loss': coherence_loss.detach(),
            'entropy_loss': entropy_loss.detach(),
        }

        return total_loss, metrics


# =============================================================================
# CONSTRAINT MASK GENERATOR
# =============================================================================

class ConstraintMaskGenerator(nn.Module):
    """
    Generates sparse constraint masks from CognitiveState.

    Given a state, determines which tokens are LEGAL to generate.
    This replaces full 50K softmax with sparse masked selection.

    Constraints come from:
    1. Phonotactic: What sounds can follow (acoustic model)
    2. Syntactic: What grammar allows (not implemented here)
    3. Semantic: What meaning allows (ontology)
    4. Pragmatic: What context allows (topic)
    """

    def __init__(
        self,
        state_dim: int = 124,
        vocab_size: int = 50257,
        max_legal_tokens: int = 1000,  # Cap on legal tokens
        hidden_dim: int = 256,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.max_legal_tokens = max_legal_tokens

        # Score each token's legality given state
        self.scorer = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, vocab_size),
        )

    def forward(
        self,
        state: torch.Tensor,
        temperature: float = 1.0,
        top_k: Optional[int] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Generate constraint mask for given state.

        Args:
            state: [B, state_dim] current cognitive state
            temperature: Softmax temperature
            top_k: If set, only return top-k tokens

        Returns:
            mask: [B, num_legal] indices of legal tokens
            probs: [B, num_legal] probabilities for legal tokens
        """
        scores = self.scorer(state) / temperature  # [B, vocab_size]

        k = top_k or self.max_legal_tokens
        top_probs, top_indices = torch.topk(scores, k, dim=-1)

        probs = F.softmax(top_probs, dim=-1)

        return top_indices, probs


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

def example_usage():
    """Demonstrate the ontological state-delta system."""

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # 1. Create state projector (hidden → cognitive state)
    projector = StateProjector(hidden_dim=768).to(device)

    # 2. Create ontological delta predictor
    predictor = OntologicalDeltaPredictor(
        state_dim=projector.state_dim
    ).to(device)

    # 3. Simulate hidden states from transformer
    B, T = 2, 100
    hidden_states = torch.randn(B, T, 768, device=device)

    # 4. Project to cognitive states
    cognitive_states = projector(hidden_states)  # [B, T, 124]

    print(f"Hidden states: {hidden_states.shape}")  # [2, 100, 768]
    print(f"Cognitive states: {cognitive_states.shape}")  # [2, 100, 124]
    print(f"Compression: {768 / projector.state_dim:.1f}x")

    # 5. Compute ontological loss
    loss, metrics = predictor.compute_loss(cognitive_states)

    print(f"\nLoss: {loss.item():.4f}")
    for k, v in metrics.items():
        print(f"  {k}: {v.item():.4f}")

    # 6. Memory comparison
    vocab_size = 50257
    print(f"\nMemory at T={T} positions:")
    print(f"  Token logits: {B * T * vocab_size * 4 / 1e6:.1f} MB")
    print(f"  Hidden delta: {B * T * 768 * 4 / 1e6:.1f} MB")
    print(f"  Cognitive delta: {B * T * projector.state_dim * 4 / 1e6:.1f} MB")

    # Scale to 10M context
    T_10m = 10_000_000
    print(f"\nMemory at T={T_10m:,} (10M context):")
    print(f"  Token logits: {B * T_10m * vocab_size * 4 / 1e12:.1f} TB")
    print(f"  Hidden delta: {B * T_10m * 768 * 4 / 1e9:.1f} GB")
    print(f"  Cognitive delta: {B * T_10m * projector.state_dim * 4 / 1e9:.1f} GB")


if __name__ == "__main__":
    example_usage()
