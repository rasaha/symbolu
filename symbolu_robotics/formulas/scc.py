# Symbolu Robotics - SCC Formulas
"""
SCC: Semantic Coherence Controller for Robotics

Adapted from main Symbolu SCC for real-time robot control.

Core Formulas:

S1 - Per-Layer Coherence:
    Cᵢ = α·Sᵢ + β·Rᵢ + γ·(1-Eᵢ) + δ·Pᵢ

    For robotics:
    - Sᵢ: Sensor consistency (stable readings = coherent)
    - Rᵢ: Resonance with related layers (mirror pair alignment)
    - Eᵢ: Entropy (uncertainty - lower is better)
    - Pᵢ: Predictability (follows expected dynamics)

S2 - Global Coherence:
    C_global = Σᵢ wᵢ·Cᵢ + coupling_term

    Weighted sum with cross-layer coupling.

S3 - Coherence Threshold:
    action_valid = C_global > θ_coherence

    Actions only executed when coherence exceeds threshold.

S4 - Cosine Similarity:
    sim(a, b) = (a · b) / (||a|| × ||b||)

    Used for comparing 12D representations.

S5 - Semantic Entropy:
    H = -Σᵢ pᵢ log pᵢ

    Measures uncertainty in layer activations.

S6 - Entropy Rate:
    dH/dt = H(t) - H(t-1)

    Positive rate = increasing uncertainty (potential issue).

S7 - Coherence Momentum:
    M = β₁·M + (1-β₁)·(C - C_prev)

    Tracks coherence trend with momentum.

S8 - Layer Imbalance:
    I = max(Cᵢ) - min(Cᵢ)

    High imbalance = inconsistent layer activations.

S9 - Safety Coherence:
    C_safety = C₁₂ × C_global

    Special coherence for O12_ABSOLVING (safety layer).

Usage in Robotics:
    - Real-time coherence monitoring
    - Action validation before execution
    - Anomaly detection via entropy spikes
    - Safety layer enforcement
"""

import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from enum import IntEnum


class OntologicalLayerRobotics(IntEnum):
    """12 ontological layers for robotics."""
    O1_POTENTIAL = 0    # Sensor readiness
    O2_IDENTITY = 1     # Localization
    O3_EXECUTION = 2    # Motor commands
    O4_STRUCTURE = 3    # Scene structure
    O5_AGENCY = 4       # Force/effort
    O6_SYNTHESIS = 5    # Grasp/manipulation
    O7_REASONING = 6    # Path planning
    O8_PURPOSE = 7      # Goal hierarchy
    O9_WITNESSES = 8    # World model
    O10_UNIFYING = 9    # Multi-robot coordination
    O11_INFORMING = 10  # Human communication
    O12_ABSOLVING = 11  # Safety constraints


@dataclass
class SCCConfig:
    """Configuration for SCC monitoring."""
    # S1 component weights
    alpha: float = 0.3  # Sensor consistency
    beta: float = 0.3   # Resonance
    gamma: float = 0.2  # Entropy (inverted)
    delta: float = 0.2  # Predictability

    # Layer importance weights (higher for critical layers)
    layer_weights: Optional[List[float]] = None

    # Thresholds
    coherence_threshold: float = 0.5  # S3: Minimum for action
    entropy_spike_threshold: float = 0.3  # S6: Max entropy rate
    imbalance_threshold: float = 0.5  # S8: Max layer imbalance

    # Safety
    safety_layer_weight: float = 2.0  # Extra weight for O12

    def __post_init__(self):
        if self.layer_weights is None:
            # Default: higher weight for safety, planning, execution
            self.layer_weights = [
                0.06,  # O1_POTENTIAL
                0.10,  # O2_IDENTITY (localization important)
                0.12,  # O3_EXECUTION (motor commands critical)
                0.08,  # O4_STRUCTURE
                0.08,  # O5_AGENCY
                0.08,  # O6_SYNTHESIS
                0.10,  # O7_REASONING (planning important)
                0.08,  # O8_PURPOSE
                0.08,  # O9_WITNESSES
                0.06,  # O10_UNIFYING
                0.06,  # O11_INFORMING
                0.10,  # O12_ABSOLVING (safety critical)
            ]


@dataclass
class LayerCoherence:
    """Coherence result for a single layer."""
    layer_index: int
    coherence: float
    sensor_consistency: float  # S
    resonance: float           # R
    entropy: float             # E
    predictability: float      # P


@dataclass
class CoherenceResult:
    """Complete coherence analysis result."""
    global_coherence: float           # S2: Overall coherence
    layer_coherences: List[float]     # S1: Per-layer
    entropy: float                    # S5: Current entropy
    entropy_rate: float               # S6: Entropy change
    momentum: float                   # S7: Coherence momentum
    imbalance: float                  # S8: Layer imbalance
    safety_coherence: float           # S9: Safety-specific
    is_valid: bool                    # S3: Above threshold?


def compute_layer_coherence(
    layer_idx: int,
    activations: np.ndarray,
    previous_activations: Optional[np.ndarray] = None,
    config: Optional[SCCConfig] = None,
) -> LayerCoherence:
    """
    Compute S1: Per-layer coherence.

    Formula:
        Cᵢ = α·Sᵢ + β·Rᵢ + γ·(1-Eᵢ) + δ·Pᵢ

    Args:
        layer_idx: Index of layer (0-11)
        activations: Current 12D activation vector
        previous_activations: Previous activations for predictability
        config: SCC configuration

    Returns:
        LayerCoherence with component scores
    """
    config = config or SCCConfig()
    activation = activations[layer_idx]

    # S: Sensor consistency (stable = consistent)
    # High or low activations are more consistent than mid-range
    S = 0.5 + 0.5 * abs(activation - 0.5) * 2

    # R: Resonance with neighbors
    neighbors = []
    if layer_idx > 0:
        neighbors.append(activations[layer_idx - 1])
    if layer_idx < 11:
        neighbors.append(activations[layer_idx + 1])

    if neighbors:
        neighbor_avg = sum(neighbors) / len(neighbors)
        R = 1.0 - abs(activation - neighbor_avg)
    else:
        R = 0.5

    # E: Entropy (binary entropy of activation)
    p = np.clip(activation, 0.01, 0.99)
    E = -(p * np.log2(p) + (1 - p) * np.log2(1 - p))

    # P: Predictability (closeness to expected value)
    if previous_activations is not None:
        expected = previous_activations[layer_idx]
        P = 1.0 - abs(activation - expected)
    else:
        P = 0.5

    # S1 formula
    C = (
        config.alpha * S +
        config.beta * R +
        config.gamma * (1.0 - E) +
        config.delta * P
    )

    return LayerCoherence(
        layer_index=layer_idx,
        coherence=float(np.clip(C, 0.0, 1.0)),
        sensor_consistency=float(S),
        resonance=float(R),
        entropy=float(E),
        predictability=float(P),
    )


def compute_global_coherence(
    activations: np.ndarray,
    previous_activations: Optional[np.ndarray] = None,
    previous_entropy: Optional[float] = None,
    previous_coherence: Optional[float] = None,
    momentum: float = 0.0,
    config: Optional[SCCConfig] = None,
) -> CoherenceResult:
    """
    Compute complete coherence analysis (S1-S9).

    Args:
        activations: Current 12D activation vector
        previous_activations: Previous activations
        previous_entropy: Previous entropy for S6
        previous_coherence: Previous coherence for S7
        momentum: Current momentum value
        config: SCC configuration

    Returns:
        CoherenceResult with all metrics
    """
    config = config or SCCConfig()

    # S1: Per-layer coherences
    layer_results = [
        compute_layer_coherence(i, activations, previous_activations, config)
        for i in range(12)
    ]
    layer_coherences = [r.coherence for r in layer_results]

    # S2: Global coherence (weighted sum)
    weights = config.layer_weights
    C_global = sum(w * c for w, c in zip(weights, layer_coherences))
    C_global = float(np.clip(C_global, 0.0, 1.0))

    # S5: Semantic entropy
    p = np.abs(activations) + 1e-10
    p = p / p.sum()
    entropy = float(-np.sum(p * np.log(p)))

    # S6: Entropy rate
    if previous_entropy is not None:
        entropy_rate = entropy - previous_entropy
    else:
        entropy_rate = 0.0

    # S7: Coherence momentum
    if previous_coherence is not None:
        beta1 = 0.9
        new_momentum = beta1 * momentum + (1 - beta1) * (C_global - previous_coherence)
    else:
        new_momentum = 0.0

    # S8: Layer imbalance
    imbalance = max(layer_coherences) - min(layer_coherences)

    # S9: Safety coherence
    safety_layer_coherence = layer_coherences[OntologicalLayerRobotics.O12_ABSOLVING]
    safety_coherence = safety_layer_coherence * C_global * config.safety_layer_weight
    safety_coherence = float(np.clip(safety_coherence, 0.0, 1.0))

    # S3: Validity check
    is_valid = C_global >= config.coherence_threshold

    return CoherenceResult(
        global_coherence=C_global,
        layer_coherences=layer_coherences,
        entropy=entropy,
        entropy_rate=entropy_rate,
        momentum=new_momentum,
        imbalance=imbalance,
        safety_coherence=safety_coherence,
        is_valid=is_valid,
    )


def compute_cosine_similarity(
    a: np.ndarray,
    b: np.ndarray,
) -> float:
    """
    Compute S4: Cosine similarity.

    Formula:
        sim(a, b) = (a · b) / (||a|| × ||b||)

    Args:
        a, b: Vectors to compare

    Returns:
        Similarity ∈ [-1, 1]
    """
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def compute_semantic_entropy(
    activations: np.ndarray,
    normalize: bool = True,
) -> float:
    """
    Compute S5: Semantic entropy.

    Formula:
        H = -Σᵢ pᵢ log pᵢ

    Args:
        activations: 12D activation vector
        normalize: Whether to normalize to probability distribution

    Returns:
        Entropy value (0 = focused, log(12) = uniform)
    """
    if normalize:
        p = np.abs(activations) + 1e-10
        p = p / p.sum()
    else:
        p = activations

    entropy = -np.sum(p * np.log(p + 1e-10))
    return float(entropy)


class SCCMonitor:
    """
    Real-time SCC monitor for robotics.

    Tracks coherence over time and detects anomalies.

    Usage:
        monitor = SCCMonitor()

        # In control loop
        while running:
            activations = encoder.encode(sensors)
            result = monitor.update(activations)

            if not result.is_valid:
                # Reduce speed or stop
                safety_override()

            if result.entropy_rate > threshold:
                # Potential anomaly
                alert("Entropy spike detected")
    """

    def __init__(self, config: Optional[SCCConfig] = None):
        self.config = config or SCCConfig()
        self.previous_activations: Optional[np.ndarray] = None
        self.previous_entropy: Optional[float] = None
        self.previous_coherence: Optional[float] = None
        self.momentum: float = 0.0
        self.history: List[CoherenceResult] = []

    def update(self, activations: np.ndarray) -> CoherenceResult:
        """
        Update with new activations and return coherence result.
        """
        result = compute_global_coherence(
            activations,
            self.previous_activations,
            self.previous_entropy,
            self.previous_coherence,
            self.momentum,
            self.config,
        )

        # Update state
        self.previous_activations = activations.copy()
        self.previous_entropy = result.entropy
        self.previous_coherence = result.global_coherence
        self.momentum = result.momentum

        # Store history
        self.history.append(result)
        if len(self.history) > 100:
            self.history = self.history[-100:]

        return result

    def is_coherent(self) -> bool:
        """Check if current state is coherent."""
        if not self.history:
            return False
        return self.history[-1].is_valid

    def detect_entropy_spike(self) -> bool:
        """Detect entropy spike (S6)."""
        if not self.history:
            return False
        return self.history[-1].entropy_rate > self.config.entropy_spike_threshold

    def detect_imbalance(self) -> bool:
        """Detect layer imbalance (S8)."""
        if not self.history:
            return False
        return self.history[-1].imbalance > self.config.imbalance_threshold

    def get_safety_level(self) -> float:
        """Get safety coherence level (S9)."""
        if not self.history:
            return 0.0
        return self.history[-1].safety_coherence

    def get_trend(self, window: int = 10) -> float:
        """
        Get coherence trend over recent history.

        Positive = improving, negative = degrading.
        """
        if len(self.history) < 2:
            return 0.0

        recent = self.history[-window:]
        if len(recent) < 2:
            return 0.0

        values = [r.global_coherence for r in recent]
        return values[-1] - values[0]

    def get_weakest_layers(self, n: int = 3) -> List[int]:
        """Get indices of n weakest layers."""
        if not self.history:
            return []

        coherences = self.history[-1].layer_coherences
        indices = list(range(12))
        indices.sort(key=lambda i: coherences[i])
        return indices[:n]

    def reset(self) -> None:
        """Reset monitor state."""
        self.previous_activations = None
        self.previous_entropy = None
        self.previous_coherence = None
        self.momentum = 0.0
        self.history.clear()
