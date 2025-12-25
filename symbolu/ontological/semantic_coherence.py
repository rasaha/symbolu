#!/usr/bin/env python3
"""
SCC: Semantic Coherence Controller
==================================

Patent-pending framework for monitoring and optimizing semantic coherence
across the 12 ontological layers of SymbolU.

Core Formulas:

S1 - Per-Layer Coherence:
    Cᵢ(t) = α·Sᵢ + β·Rᵢ + γ·Eᵢ + δ·Pᵢ

    Where:
    - Sᵢ: Semantic consistency (embedding similarity within layer)
    - Rᵢ: Resonance (alignment with neighboring layers)
    - Eᵢ: Entropy (information disorder - lower is better)
    - Pᵢ: Predictability (how well layer follows from context)

S2 - Global Coherence:
    C_global(t) = Σᵢ wᵢ·Cᵢ(t) + Σᵢ<ⱼ Mᵢⱼ·Corr(Cᵢ, Cⱼ)

    Where:
    - wᵢ: Layer importance weights
    - Mᵢⱼ: Bhava relationship matrix (coupling strength)
    - Corr(Cᵢ, Cⱼ): Correlation between layer coherences

S3 - Coherence-Optimized Loss:
    L_coherence = L_task + λ·L_align + μ·L_consistency

    Multi-objective training that maintains semantic coherence.

This is THE game-changer for SymbolU because:
1. Directly monitors each of the 12 ontological layers
2. Uses the Bhava relationship matrix for cross-layer coupling
3. Provides real-time coherence signals during inference
4. Offers a training objective aligned with the architecture

Usage:
------
    from symbolu.ontological.semantic_coherence import (
        SemanticCoherenceController,
        LayerCoherence,
        GlobalCoherence,
        CoherenceLoss,
    )

    # Monitor coherence
    scc = SemanticCoherenceController()
    result = scc.compute(ontological_probs, bhava_matrix)

    print(f"Global coherence: {result.global_coherence:.3f}")
    for layer, score in result.layer_coherences.items():
        print(f"  {layer}: {score:.3f}")
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import math

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

import numpy as np

from symbolu.ontological.types import LAYER_NAMES, LAYER_INDEX, NUM_LAYERS


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SCCConfig:
    """
    Configuration for Semantic Coherence Controller.

    S1 Component Weights (must sum to 1.0):
        alpha: Weight for Semantic consistency (Sᵢ)
        beta: Weight for Resonance (Rᵢ)
        gamma: Weight for Entropy (Eᵢ) - note: we use 1-entropy
        delta: Weight for Predictability (Pᵢ)

    Layer Importance:
        layer_weights: Optional custom weights for each of 12 layers
                      Default gives higher weight to reasoning/integration layers

    Cross-Layer Coupling:
        use_bhava_coupling: Use Bhava relationship matrix for Mᵢⱼ
        coupling_strength: Overall strength of cross-layer coupling
    """
    # S1 component weights (α, β, γ, δ)
    alpha: float = 0.3  # Semantic consistency
    beta: float = 0.3   # Resonance
    gamma: float = 0.2  # Entropy (inverted)
    delta: float = 0.2  # Predictability

    # Layer importance weights (wᵢ)
    layer_weights: Optional[List[float]] = None

    # Cross-layer coupling
    use_bhava_coupling: bool = True
    coupling_strength: float = 0.5

    # Coherence thresholds
    high_coherence_threshold: float = 0.7
    low_coherence_threshold: float = 0.3

    def __post_init__(self):
        # Normalize component weights
        total = self.alpha + self.beta + self.gamma + self.delta
        if abs(total - 1.0) > 0.01:
            self.alpha /= total
            self.beta /= total
            self.gamma /= total
            self.delta /= total

        # Default layer weights (higher for reasoning/integration)
        if self.layer_weights is None:
            self.layer_weights = [
                0.06,  # O1_POTENTIAL
                0.07,  # O2_IDENTITY
                0.07,  # O3_EXECUTION
                0.08,  # O4_STRUCTURE
                0.10,  # O5_COGNITION
                0.10,  # O6_AGENCY
                0.12,  # O7_REASONING (higher weight)
                0.10,  # O8_PURPOSE
                0.10,  # O9_WITNESSES
                0.08,  # O10_UNIFYING
                0.07,  # O11_INTEGRATION
                0.05,  # O12_ABSOLVING
            ]


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class LayerCoherenceResult:
    """
    Coherence result for a single ontological layer.

    Formula S1: Cᵢ = α·Sᵢ + β·Rᵢ + γ·(1-Eᵢ) + δ·Pᵢ
    """
    layer_name: str
    layer_index: int
    coherence: float  # Cᵢ ∈ [0, 1]

    # S1 components
    semantic_consistency: float  # Sᵢ
    resonance: float             # Rᵢ
    entropy: float               # Eᵢ (raw, not inverted)
    predictability: float        # Pᵢ

    # Derived
    activation: float  # Layer activation strength

    @property
    def is_coherent(self) -> bool:
        return self.coherence >= 0.5

    @property
    def quality(self) -> str:
        if self.coherence >= 0.7:
            return "high"
        elif self.coherence >= 0.4:
            return "medium"
        else:
            return "low"


@dataclass
class GlobalCoherenceResult:
    """
    Global coherence result across all layers.

    Formula S2: C_global = Σᵢ wᵢ·Cᵢ + Σᵢ<ⱼ Mᵢⱼ·Corr(Cᵢ, Cⱼ)
    """
    global_coherence: float  # C_global ∈ [0, 1]
    layer_coherences: Dict[str, float]  # Cᵢ for each layer
    layer_results: List[LayerCoherenceResult]

    # S2 components
    weighted_layer_sum: float      # Σᵢ wᵢ·Cᵢ
    cross_layer_coupling: float    # Σᵢ<ⱼ Mᵢⱼ·Corr(Cᵢ, Cⱼ)

    # Statistics
    mean_coherence: float
    min_coherence: float
    max_coherence: float
    coherence_std: float

    # Weakest layers (for debugging/improvement)
    weakest_layers: List[str] = field(default_factory=list)

    @property
    def is_globally_coherent(self) -> bool:
        return self.global_coherence >= 0.5

    @property
    def quality(self) -> str:
        if self.global_coherence >= 0.7:
            return "high"
        elif self.global_coherence >= 0.4:
            return "medium"
        else:
            return "low"


# =============================================================================
# S1: PER-LAYER COHERENCE
# =============================================================================

class LayerCoherenceComputer:
    """
    Computes per-layer coherence using formula S1.

    Cᵢ(t) = α·Sᵢ + β·Rᵢ + γ·(1-Eᵢ) + δ·Pᵢ

    Components:
    - Sᵢ: Semantic consistency - how self-consistent is this layer's representation
    - Rᵢ: Resonance - alignment with neighboring layers (Bhava aspects)
    - Eᵢ: Entropy - information disorder (we use 1-E for coherence)
    - Pᵢ: Predictability - how expected is this layer given context
    """

    def __init__(self, config: Optional[SCCConfig] = None):
        self.config = config or SCCConfig()

    def compute_semantic_consistency(
        self,
        layer_activation: float,
        layer_embedding: Optional[np.ndarray] = None,
    ) -> float:
        """
        Compute semantic consistency Sᵢ for a layer.

        High consistency = stable, focused activation.
        Uses activation magnitude as proxy (stable layers have consistent activation).
        """
        # Base consistency from activation level
        # Very low or very high activations are more consistent
        # Mid-range activations suggest uncertainty
        if layer_activation < 0.1:
            return 0.3  # Low but consistent (not active)
        elif layer_activation > 0.7:
            return 0.9  # High and consistent (strongly active)
        else:
            # Mid-range: consistency decreases
            return 0.5 + 0.4 * (abs(layer_activation - 0.5) / 0.5)

    def compute_resonance(
        self,
        layer_idx: int,
        all_activations: List[float],
        bhava_matrix: Optional[np.ndarray] = None,
    ) -> float:
        """
        Compute resonance Rᵢ - alignment with related layers.

        Uses Bhava relationship strengths to weight neighbor contributions.
        High resonance = layer aligns well with its natural aspects.
        """
        if bhava_matrix is None:
            # Fallback: use adjacent layer correlation
            neighbors = []
            if layer_idx > 0:
                neighbors.append(all_activations[layer_idx - 1])
            if layer_idx < NUM_LAYERS - 1:
                neighbors.append(all_activations[layer_idx + 1])

            if not neighbors:
                return 0.5

            current = all_activations[layer_idx]
            # Resonance = similarity to neighbors
            neighbor_avg = sum(neighbors) / len(neighbors)
            diff = abs(current - neighbor_avg)
            return 1.0 - min(diff, 1.0)

        # Use Bhava matrix for weighted resonance
        current = all_activations[layer_idx]
        weighted_sum = 0.0
        weight_total = 0.0

        for j in range(NUM_LAYERS):
            if j != layer_idx:
                weight = bhava_matrix[layer_idx, j]
                weighted_sum += weight * (1.0 - abs(current - all_activations[j]))
                weight_total += weight

        if weight_total < 1e-6:
            return 0.5

        return float(weighted_sum / weight_total)

    def compute_entropy(
        self,
        layer_activation: float,
        context_activations: Optional[List[float]] = None,
    ) -> float:
        """
        Compute entropy Eᵢ - information disorder.

        Low entropy = more ordered/coherent.
        Uses activation uncertainty as entropy proxy.
        """
        # Entropy based on how "decisive" the activation is
        # Near 0 or 1 = low entropy (certain)
        # Near 0.5 = high entropy (uncertain)
        p = np.clip(layer_activation, 0.01, 0.99)
        binary_entropy = -(p * np.log2(p) + (1 - p) * np.log2(1 - p))

        return float(binary_entropy)

    def compute_predictability(
        self,
        layer_idx: int,
        activation: float,
        context_activations: Optional[List[float]] = None,
    ) -> float:
        """
        Compute predictability Pᵢ - how expected is this layer.

        High predictability = layer follows naturally from context.
        """
        if context_activations is None:
            return 0.5

        # Simple model: layer is predictable if it follows activation trend
        # from earlier layers
        if layer_idx == 0:
            return 0.7  # First layer is always somewhat predictable

        # Average of previous layers
        prev_avg = sum(context_activations[:layer_idx]) / layer_idx

        # Predictable if close to trend
        diff = abs(activation - prev_avg)
        return 1.0 - min(diff, 1.0)

    def compute_layer_coherence(
        self,
        layer_idx: int,
        all_activations: List[float],
        bhava_matrix: Optional[np.ndarray] = None,
        layer_embedding: Optional[np.ndarray] = None,
    ) -> LayerCoherenceResult:
        """
        Compute full coherence for a single layer.

        Formula S1: Cᵢ = α·Sᵢ + β·Rᵢ + γ·(1-Eᵢ) + δ·Pᵢ
        """
        activation = all_activations[layer_idx]

        # Compute S1 components
        S_i = self.compute_semantic_consistency(activation, layer_embedding)
        R_i = self.compute_resonance(layer_idx, all_activations, bhava_matrix)
        E_i = self.compute_entropy(activation)
        P_i = self.compute_predictability(layer_idx, activation, all_activations)

        # S1 formula (note: we use 1-E for coherence)
        C_i = (
            self.config.alpha * S_i +
            self.config.beta * R_i +
            self.config.gamma * (1.0 - E_i) +
            self.config.delta * P_i
        )

        return LayerCoherenceResult(
            layer_name=LAYER_NAMES[layer_idx],
            layer_index=layer_idx,
            coherence=float(np.clip(C_i, 0.0, 1.0)),
            semantic_consistency=S_i,
            resonance=R_i,
            entropy=E_i,
            predictability=P_i,
            activation=activation,
        )


# =============================================================================
# S2: GLOBAL COHERENCE
# =============================================================================

class GlobalCoherenceComputer:
    """
    Computes global coherence using formula S2.

    C_global(t) = Σᵢ wᵢ·Cᵢ(t) + Σᵢ<ⱼ Mᵢⱼ·Corr(Cᵢ, Cⱼ)

    Components:
    - Σᵢ wᵢ·Cᵢ: Weighted sum of layer coherences
    - Σᵢ<ⱼ Mᵢⱼ·Corr(Cᵢ, Cⱼ): Cross-layer coupling via Bhava matrix
    """

    def __init__(self, config: Optional[SCCConfig] = None):
        self.config = config or SCCConfig()
        self.layer_computer = LayerCoherenceComputer(config)

    def compute_cross_layer_coupling(
        self,
        layer_coherences: List[float],
        bhava_matrix: Optional[np.ndarray] = None,
    ) -> float:
        """
        Compute cross-layer coupling term.

        Formula: Σᵢ<ⱼ Mᵢⱼ·Corr(Cᵢ, Cⱼ)

        Where Corr(Cᵢ, Cⱼ) measures coherence correlation.
        """
        if bhava_matrix is None:
            # Fallback: uniform coupling
            coupling_matrix = np.ones((NUM_LAYERS, NUM_LAYERS)) * 0.5
            np.fill_diagonal(coupling_matrix, 0)
        else:
            coupling_matrix = bhava_matrix

        total_coupling = 0.0
        num_pairs = 0

        for i in range(NUM_LAYERS):
            for j in range(i + 1, NUM_LAYERS):
                M_ij = coupling_matrix[i, j]

                # Correlation: both high or both low = positive correlation
                C_i = layer_coherences[i]
                C_j = layer_coherences[j]

                # Simple correlation: 1 - |diff|
                corr = 1.0 - abs(C_i - C_j)

                total_coupling += M_ij * corr
                num_pairs += 1

        if num_pairs == 0:
            return 0.0

        # Normalize
        return float(total_coupling / num_pairs)

    def compute_global_coherence(
        self,
        ontological_probs: List[float],
        bhava_matrix: Optional[np.ndarray] = None,
        layer_embeddings: Optional[List[np.ndarray]] = None,
    ) -> GlobalCoherenceResult:
        """
        Compute global coherence across all layers.

        Formula S2: C_global = Σᵢ wᵢ·Cᵢ + Σᵢ<ⱼ Mᵢⱼ·Corr(Cᵢ, Cⱼ)
        """
        # Compute per-layer coherences
        layer_results = []
        for i in range(NUM_LAYERS):
            embedding = layer_embeddings[i] if layer_embeddings else None
            result = self.layer_computer.compute_layer_coherence(
                layer_idx=i,
                all_activations=ontological_probs,
                bhava_matrix=bhava_matrix,
                layer_embedding=embedding,
            )
            layer_results.append(result)

        layer_coherences = [r.coherence for r in layer_results]

        # Weighted sum: Σᵢ wᵢ·Cᵢ
        weights = self.config.layer_weights
        weighted_sum = sum(w * c for w, c in zip(weights, layer_coherences))

        # Cross-layer coupling
        if self.config.use_bhava_coupling:
            coupling = self.compute_cross_layer_coupling(layer_coherences, bhava_matrix)
        else:
            coupling = 0.0

        # Global coherence
        C_global = weighted_sum + self.config.coupling_strength * coupling
        C_global = float(np.clip(C_global, 0.0, 1.0))

        # Statistics
        mean_c = np.mean(layer_coherences)
        min_c = np.min(layer_coherences)
        max_c = np.max(layer_coherences)
        std_c = np.std(layer_coherences)

        # Find weakest layers
        sorted_layers = sorted(
            layer_results,
            key=lambda r: r.coherence
        )
        weakest = [r.layer_name for r in sorted_layers[:3]]

        return GlobalCoherenceResult(
            global_coherence=C_global,
            layer_coherences={r.layer_name: r.coherence for r in layer_results},
            layer_results=layer_results,
            weighted_layer_sum=weighted_sum,
            cross_layer_coupling=coupling,
            mean_coherence=float(mean_c),
            min_coherence=float(min_c),
            max_coherence=float(max_c),
            coherence_std=float(std_c),
            weakest_layers=weakest,
        )


# =============================================================================
# COMPLETE SEMANTIC COHERENCE CONTROLLER
# =============================================================================

class SemanticCoherenceController:
    """
    Complete Semantic Coherence Controller (SCC).

    Integrates:
    - S1: Per-layer coherence monitoring
    - S2: Global coherence with cross-layer coupling
    - Real-time coherence feedback

    This is specifically designed for SymbolU's 12-layer ontological architecture
    and integrates with the Bhava relationship matrix.

    Usage:
        scc = SemanticCoherenceController()

        # Compute coherence
        result = scc.compute(
            ontological_probs=[0.1, 0.2, ...],  # 12D
            bhava_matrix=bhava_output['relationship_matrix']  # 12x12
        )

        print(f"Global: {result.global_coherence:.3f}")
        print(f"Weakest: {result.weakest_layers}")
    """

    def __init__(self, config: Optional[SCCConfig] = None):
        self.config = config or SCCConfig()
        self.global_computer = GlobalCoherenceComputer(config)
        self.history: List[GlobalCoherenceResult] = []

    def compute(
        self,
        ontological_probs: List[float],
        bhava_matrix: Optional[np.ndarray] = None,
        layer_embeddings: Optional[List[np.ndarray]] = None,
    ) -> GlobalCoherenceResult:
        """
        Compute coherence for given ontological state.

        Args:
            ontological_probs: 12D layer probabilities
            bhava_matrix: 12x12 Bhava relationship matrix (optional)
            layer_embeddings: Per-layer embeddings (optional)

        Returns:
            GlobalCoherenceResult with full analysis
        """
        result = self.global_computer.compute_global_coherence(
            ontological_probs=ontological_probs,
            bhava_matrix=bhava_matrix,
            layer_embeddings=layer_embeddings,
        )

        self.history.append(result)
        return result

    def get_coherence_trend(self, window: int = 5) -> float:
        """
        Get coherence trend over recent history.

        Returns:
            Positive = improving, negative = degrading
        """
        if len(self.history) < 2:
            return 0.0

        recent = self.history[-window:]
        if len(recent) < 2:
            return 0.0

        # Linear trend
        values = [r.global_coherence for r in recent]
        trend = values[-1] - values[0]
        return float(trend)

    def is_coherent(
        self,
        ontological_probs: Optional[List[float]] = None,
        bhava_matrix: Optional[np.ndarray] = None,
    ) -> bool:
        """
        Quick check if current state is coherent.
        """
        if ontological_probs is not None:
            result = self.compute(ontological_probs, bhava_matrix)
        elif self.history:
            result = self.history[-1]
        else:
            return False

        return result.global_coherence >= self.config.high_coherence_threshold

    def get_improvement_suggestions(
        self,
        result: Optional[GlobalCoherenceResult] = None,
    ) -> List[str]:
        """
        Get suggestions for improving coherence.
        """
        if result is None:
            if not self.history:
                return ["No coherence data available"]
            result = self.history[-1]

        suggestions = []

        # Check weakest layers
        for layer_name in result.weakest_layers:
            layer_result = next(
                r for r in result.layer_results
                if r.layer_name == layer_name
            )

            if layer_result.resonance < 0.4:
                suggestions.append(
                    f"{layer_name}: Low resonance - consider strengthening "
                    f"connections to neighboring layers"
                )

            if layer_result.entropy > 0.7:
                suggestions.append(
                    f"{layer_name}: High entropy - activation is uncertain, "
                    f"consider stronger training signal"
                )

            if layer_result.predictability < 0.4:
                suggestions.append(
                    f"{layer_name}: Low predictability - layer doesn't follow "
                    f"context, check layer dependencies"
                )

        # Global suggestions
        if result.coherence_std > 0.3:
            suggestions.append(
                "High coherence variance across layers - consider "
                "regularization to balance layer contributions"
            )

        if result.cross_layer_coupling < 0.3:
            suggestions.append(
                "Low cross-layer coupling - Bhava relationships may be "
                "underutilized, consider increasing coupling_strength"
            )

        return suggestions or ["Coherence is within acceptable range"]

    def reset_history(self):
        """Clear coherence history."""
        self.history = []


# =============================================================================
# S3: COHERENCE-OPTIMIZED LOSS (PyTorch)
# =============================================================================

if PYTORCH_AVAILABLE:

    class CoherenceLoss(nn.Module):
        """
        Coherence-optimized loss for training.

        Formula S3:
            L_coherence = L_task + λ·L_align + μ·L_consistency

        Components:
        - L_task: Primary task loss (e.g., classification, embedding)
        - L_align: Layer alignment loss (encourage coherent representations)
        - L_consistency: Cross-layer consistency (via Bhava coupling)

        This loss helps train SymbolU to maintain semantic coherence
        across its 12 ontological layers.
        """

        def __init__(
            self,
            lambda_align: float = 0.1,
            mu_consistency: float = 0.05,
            target_coherence: float = 0.7,
        ):
            super().__init__()
            self.lambda_align = lambda_align
            self.mu_consistency = mu_consistency
            self.target_coherence = target_coherence

        def compute_alignment_loss(
            self,
            ontological_probs: torch.Tensor,
        ) -> torch.Tensor:
            """
            Compute alignment loss L_align.

            Encourages smooth transitions between adjacent layers.
            """
            if ontological_probs.dim() == 1:
                ontological_probs = ontological_probs.unsqueeze(0)

            # Difference between adjacent layers
            diffs = ontological_probs[:, 1:] - ontological_probs[:, :-1]

            # L2 penalty on large jumps
            alignment_loss = (diffs ** 2).mean()

            return alignment_loss

        def compute_consistency_loss(
            self,
            ontological_probs: torch.Tensor,
            bhava_matrix: Optional[torch.Tensor] = None,
        ) -> torch.Tensor:
            """
            Compute consistency loss L_consistency.

            Uses Bhava matrix to encourage consistent layer relationships.
            """
            if ontological_probs.dim() == 1:
                ontological_probs = ontological_probs.unsqueeze(0)

            batch_size = ontological_probs.shape[0]

            # Compute layer interaction matrix
            # layers_outer[i,j] = prob_i * prob_j (co-activation strength)
            layers_outer = torch.bmm(
                ontological_probs.unsqueeze(2),
                ontological_probs.unsqueeze(1)
            )  # (batch, 12, 12)

            if bhava_matrix is not None:
                # Weight by Bhava relationships
                # Strong Bhava relationships should have consistent activations
                if bhava_matrix.dim() == 2:
                    bhava_matrix = bhava_matrix.unsqueeze(0).expand(batch_size, -1, -1)

                # Penalize when Bhava expects relationship but activations don't match
                expected = bhava_matrix
                actual = layers_outer

                # Consistency = how well actual matches expected pattern
                consistency_diff = (expected - actual) ** 2
                consistency_loss = consistency_diff.mean()
            else:
                # Without Bhava matrix, just encourage diagonal dominance
                # (each layer should be self-consistent)
                eye = torch.eye(NUM_LAYERS, device=ontological_probs.device)
                consistency_loss = ((layers_outer - eye.unsqueeze(0)) ** 2).mean()

            return consistency_loss

        def compute_coherence_score(
            self,
            ontological_probs: torch.Tensor,
        ) -> torch.Tensor:
            """
            Compute differentiable coherence score.

            Higher is better (used for monitoring, not loss).
            """
            # Entropy-based coherence
            probs = ontological_probs + 1e-8
            probs = probs / probs.sum(dim=-1, keepdim=True)
            entropy = -(probs * torch.log(probs)).sum(dim=-1)
            max_entropy = torch.log(torch.tensor(NUM_LAYERS, dtype=torch.float32))

            # Coherence = 1 - normalized entropy (focused = coherent)
            coherence = 1.0 - (entropy / max_entropy)

            return coherence

        def forward(
            self,
            task_loss: torch.Tensor,
            ontological_probs: torch.Tensor,
            bhava_matrix: Optional[torch.Tensor] = None,
        ) -> Dict[str, torch.Tensor]:
            """
            Compute coherence-optimized loss.

            Formula S3: L = L_task + λ·L_align + μ·L_consistency

            Args:
                task_loss: Primary task loss
                ontological_probs: (batch, 12) layer probabilities
                bhava_matrix: (12, 12) or (batch, 12, 12) Bhava relationships

            Returns:
                Dict with total loss and components
            """
            # Alignment loss
            L_align = self.compute_alignment_loss(ontological_probs)

            # Consistency loss
            L_consistency = self.compute_consistency_loss(ontological_probs, bhava_matrix)

            # Total coherence loss
            L_coherence = (
                task_loss +
                self.lambda_align * L_align +
                self.mu_consistency * L_consistency
            )

            # Coherence score for monitoring
            coherence_score = self.compute_coherence_score(ontological_probs)

            return {
                'total_loss': L_coherence,
                'task_loss': task_loss,
                'alignment_loss': L_align,
                'consistency_loss': L_consistency,
                'coherence_score': coherence_score.mean(),
            }


    class LayerCoherenceModule(nn.Module):
        """
        Differentiable layer coherence computation.

        Implements S1 formula in PyTorch for training integration.
        """

        def __init__(
            self,
            alpha: float = 0.3,
            beta: float = 0.3,
            gamma: float = 0.2,
            delta: float = 0.2,
        ):
            super().__init__()
            self.alpha = nn.Parameter(torch.tensor(alpha), requires_grad=False)
            self.beta = nn.Parameter(torch.tensor(beta), requires_grad=False)
            self.gamma = nn.Parameter(torch.tensor(gamma), requires_grad=False)
            self.delta = nn.Parameter(torch.tensor(delta), requires_grad=False)

        def forward(
            self,
            ontological_probs: torch.Tensor,
            bhava_matrix: Optional[torch.Tensor] = None,
        ) -> Dict[str, torch.Tensor]:
            """
            Compute per-layer coherences.

            Args:
                ontological_probs: (batch, 12)
                bhava_matrix: (12, 12)

            Returns:
                Dict with layer_coherences, global_coherence
            """
            batch_size = ontological_probs.shape[0]

            # Semantic consistency (S): based on activation confidence
            # High/low activations are consistent, mid-range is uncertain
            S = 0.5 + 0.5 * torch.abs(ontological_probs - 0.5) * 2

            # Resonance (R): alignment with Bhava-weighted neighbors
            if bhava_matrix is not None:
                # Weighted neighbor coherence
                R = torch.matmul(ontological_probs, bhava_matrix)
                R = R / (R.sum(dim=-1, keepdim=True) + 1e-8)
            else:
                # Adjacent layer correlation
                R = torch.zeros_like(ontological_probs)
                R[:, 1:-1] = 0.5 * (ontological_probs[:, :-2] + ontological_probs[:, 2:])
                R[:, 0] = ontological_probs[:, 1]
                R[:, -1] = ontological_probs[:, -2]
                R = 1.0 - torch.abs(ontological_probs - R)

            # Entropy (E): activation uncertainty
            p = torch.clamp(ontological_probs, 0.01, 0.99)
            E = -(p * torch.log2(p) + (1 - p) * torch.log2(1 - p))

            # Predictability (P): how expected given context
            cumsum = torch.cumsum(ontological_probs, dim=-1)
            running_avg = cumsum / torch.arange(1, NUM_LAYERS + 1, device=ontological_probs.device)
            P = 1.0 - torch.abs(ontological_probs - running_avg)

            # S1 formula: Cᵢ = α·Sᵢ + β·Rᵢ + γ·(1-Eᵢ) + δ·Pᵢ
            C = (
                self.alpha * S +
                self.beta * R +
                self.gamma * (1.0 - E) +
                self.delta * P
            )

            # Global coherence (weighted average)
            layer_weights = torch.tensor(
                SCCConfig().layer_weights,
                device=ontological_probs.device
            )
            global_coherence = (C * layer_weights).sum(dim=-1)

            return {
                'layer_coherences': C,
                'global_coherence': global_coherence,
                'semantic_consistency': S,
                'resonance': R,
                'entropy': E,
                'predictability': P,
            }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def compute_coherence(
    ontological_probs: List[float],
    bhava_matrix: Optional[np.ndarray] = None,
    config: Optional[SCCConfig] = None,
) -> GlobalCoherenceResult:
    """
    Convenience function to compute coherence.

    Args:
        ontological_probs: 12D layer probabilities
        bhava_matrix: Optional 12x12 Bhava relationship matrix
        config: Optional SCC configuration

    Returns:
        GlobalCoherenceResult with full analysis

    Example:
        >>> probs = [0.1, 0.15, 0.1, 0.1, 0.2, 0.1, 0.08, 0.07, 0.05, 0.03, 0.01, 0.01]
        >>> result = compute_coherence(probs)
        >>> print(f"Global coherence: {result.global_coherence:.3f}")
    """
    scc = SemanticCoherenceController(config)
    return scc.compute(ontological_probs, bhava_matrix)


def is_coherent(
    ontological_probs: List[float],
    threshold: float = 0.5,
) -> bool:
    """
    Quick check if ontological state is coherent.

    Args:
        ontological_probs: 12D layer probabilities
        threshold: Coherence threshold (default 0.5)

    Returns:
        True if coherence >= threshold
    """
    result = compute_coherence(ontological_probs)
    return result.global_coherence >= threshold


def get_scc_summary() -> str:
    """Get summary of SCC module."""
    return """
================================================================================
SCC: Semantic Coherence Controller
================================================================================

S1 - PER-LAYER COHERENCE:
    Cᵢ(t) = α·Sᵢ + β·Rᵢ + γ·(1-Eᵢ) + δ·Pᵢ

    Components:
    - Sᵢ: Semantic consistency (stable activation = coherent)
    - Rᵢ: Resonance (alignment with Bhava-related layers)
    - Eᵢ: Entropy (uncertainty - lower is better)
    - Pᵢ: Predictability (follows context)

    Default weights: α=0.3, β=0.3, γ=0.2, δ=0.2

S2 - GLOBAL COHERENCE:
    C_global = Σᵢ wᵢ·Cᵢ + Σᵢ<ⱼ Mᵢⱼ·Corr(Cᵢ, Cⱼ)

    Components:
    - Σᵢ wᵢ·Cᵢ: Weighted sum of layer coherences
    - Σᵢ<ⱼ Mᵢⱼ·Corr(Cᵢ, Cⱼ): Cross-layer coupling via Bhava matrix

S3 - COHERENCE LOSS (for training):
    L_coherence = L_task + λ·L_align + μ·L_consistency

    Multi-objective loss that maintains coherence during training.

WHY THIS IS PERFECT FOR SYMBOLU:
    1. Monitors each of the 12 ontological layers individually
    2. Uses Bhava relationship matrix for cross-layer coupling
    3. Provides actionable feedback (weakest layers, suggestions)
    4. Integrates as training objective

USAGE:
    from symbolu.ontological.semantic_coherence import (
        SemanticCoherenceController,
        compute_coherence,
    )

    # Quick check
    result = compute_coherence(ontological_probs)
    print(f"Coherence: {result.global_coherence:.3f}")

    # With controller (maintains history)
    scc = SemanticCoherenceController()
    result = scc.compute(probs, bhava_matrix)
    print(scc.get_improvement_suggestions())

================================================================================
"""


if __name__ == "__main__":
    print(get_scc_summary())

    # Example usage
    print("\nExample Usage:")
    print("-" * 60)

    # Sample ontological distribution (focused on reasoning layers)
    sample_probs = [
        0.05,  # O1_POTENTIAL
        0.08,  # O2_IDENTITY
        0.10,  # O3_EXECUTION
        0.10,  # O4_STRUCTURE
        0.18,  # O5_COGNITION (high)
        0.12,  # O6_AGENCY
        0.15,  # O7_REASONING (high)
        0.08,  # O8_PURPOSE
        0.06,  # O9_WITNESSES
        0.04,  # O10_UNIFYING
        0.03,  # O11_INTEGRATION
        0.01,  # O12_ABSOLVING
    ]

    scc = SemanticCoherenceController()
    result = scc.compute(sample_probs)

    print(f"Global Coherence: {result.global_coherence:.3f} ({result.quality})")
    print(f"Weighted Layer Sum: {result.weighted_layer_sum:.3f}")
    print(f"Cross-Layer Coupling: {result.cross_layer_coupling:.3f}")
    print(f"Mean Layer Coherence: {result.mean_coherence:.3f}")
    print(f"Coherence Std: {result.coherence_std:.3f}")

    print("\nPer-Layer Coherences:")
    for name, coh in result.layer_coherences.items():
        bar = "█" * int(coh * 20)
        print(f"  {name:20s}: {coh:.3f} {bar}")

    print(f"\nWeakest Layers: {result.weakest_layers}")

    print("\nImprovement Suggestions:")
    for suggestion in scc.get_improvement_suggestions():
        print(f"  • {suggestion}")
