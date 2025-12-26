# Symbolu Robotics - USE Formulas
"""
USE: Unified Sensor Encoding for Robotics

Multi-modal sensor fusion using coherence-based weighting.

Core Formulas:

U1 - Cross-Modal Correlation Matrix:
    R = [rᵢⱼ] where rᵢⱼ = corr(vᵢ, vⱼ)

    Measures coherence between sensor modalities (vision, proprioception,
    tactile, audio). High correlation indicates consistent world state.

U2 - Coherence-Weighted Fusion:
    z = Σᵢ wᵢ · vᵢ   where wᵢ = f(coherenceᵢ)

    Fuses modality vectors with weights based on coherence with other
    modalities. Consistent sensors get higher weight.

U3 - Temporal Alignment:
    vₜ' = α · vₜ + (1 - α) · vₜ₋₁

    Aligns temporally offset sensor readings using EMA smoothing.

U4 - Confidence Estimation:
    conf = 1 - H(p) / log(N)

    Estimates confidence from entropy of the fused representation.
    Low entropy = high confidence.

Usage in Robotics:
    - Multi-sensor fusion in reactive tier
    - Cross-modal consistency checking
    - Sensor failure detection
    - Confidence-weighted control
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class USEConfig:
    """Configuration for USE fusion."""
    temporal_alpha: float = 0.3       # EMA smoothing for U3
    coherence_threshold: float = 0.3   # Minimum coherence to include modality
    min_confidence: float = 0.1        # Minimum output confidence
    normalize_output: bool = True      # Normalize fused vector


@dataclass
class FusionResult:
    """Result of USE fusion."""
    fused_vector: np.ndarray           # Fused 12D representation
    correlation_matrix: np.ndarray     # U1: Cross-modal correlations
    modality_weights: Dict[str, float] # U2: Per-modality weights
    coherence_score: float             # Overall coherence
    confidence: float                  # U4: Fusion confidence


def compute_correlation_matrix(
    modality_vectors: Dict[str, np.ndarray],
) -> np.ndarray:
    """
    Compute U1: Cross-modal correlation matrix.

    Formula:
        R = [rᵢⱼ] where rᵢⱼ = corr(vᵢ, vⱼ)

    Measures agreement between different sensor modalities.

    Args:
        modality_vectors: Dict mapping modality name to 12D vector

    Returns:
        Correlation matrix R (n_modalities x n_modalities)

    Example:
        >>> vectors = {
        ...     'vision': np.array([0.1, 0.2, ...]),
        ...     'proprioception': np.array([0.15, 0.18, ...]),
        ... }
        >>> R = compute_correlation_matrix(vectors)
    """
    names = list(modality_vectors.keys())
    n = len(names)

    if n == 0:
        return np.array([[]])

    if n == 1:
        return np.array([[1.0]])

    # Stack vectors into matrix
    vectors = np.array([modality_vectors[name] for name in names])

    # Compute correlation matrix
    # Normalize vectors first
    norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-10
    normalized = vectors / norms

    # Correlation = normalized dot product
    R = np.dot(normalized, normalized.T)

    # Clip to valid correlation range
    R = np.clip(R, -1.0, 1.0)

    return R


def compute_coherence_fusion(
    modality_vectors: Dict[str, np.ndarray],
    correlation_matrix: Optional[np.ndarray] = None,
    config: Optional[USEConfig] = None,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Compute U2: Coherence-weighted fusion.

    Formula:
        z = Σᵢ wᵢ · vᵢ   where wᵢ = mean(rᵢⱼ for j ≠ i)

    Weights modalities by their coherence with other modalities.

    Args:
        modality_vectors: Dict mapping modality name to 12D vector
        correlation_matrix: Pre-computed R (optional)
        config: USE configuration

    Returns:
        (fused_vector, modality_weights)

    Example:
        >>> fused, weights = compute_coherence_fusion(vectors)
        >>> print(f"Vision weight: {weights['vision']:.3f}")
    """
    config = config or USEConfig()
    names = list(modality_vectors.keys())
    n = len(names)

    if n == 0:
        return np.zeros(12), {}

    if n == 1:
        name = names[0]
        return modality_vectors[name].copy(), {name: 1.0}

    # Compute correlation if not provided
    if correlation_matrix is None:
        correlation_matrix = compute_correlation_matrix(modality_vectors)

    # Compute weights from row means (excluding diagonal)
    weights = {}
    for i, name in enumerate(names):
        # Mean correlation with other modalities
        mask = np.ones(n, dtype=bool)
        mask[i] = False
        mean_corr = np.mean(np.abs(correlation_matrix[i, mask]))

        # Weight = coherence if above threshold, else reduced
        if mean_corr >= config.coherence_threshold:
            weights[name] = mean_corr
        else:
            weights[name] = mean_corr * 0.5  # Reduce weight for inconsistent

    # Normalize weights
    total = sum(weights.values()) + 1e-10
    weights = {k: v / total for k, v in weights.items()}

    # Weighted sum
    fused = np.zeros(12)
    for name, vec in modality_vectors.items():
        fused += weights[name] * vec

    if config.normalize_output:
        norm = np.linalg.norm(fused)
        if norm > 1e-10:
            fused = fused / norm

    return fused, weights


def compute_temporal_alignment(
    current_vector: np.ndarray,
    previous_vector: Optional[np.ndarray],
    alpha: float = 0.3,
) -> np.ndarray:
    """
    Compute U3: Temporal alignment via EMA.

    Formula:
        vₜ' = α · vₜ + (1 - α) · vₜ₋₁

    Smooths sensor readings over time to handle temporal offsets.

    Args:
        current_vector: Current modality vector
        previous_vector: Previous smoothed vector (or None for first)
        alpha: EMA smoothing factor (higher = more responsive)

    Returns:
        Temporally aligned vector
    """
    if previous_vector is None:
        return current_vector.copy()

    return alpha * current_vector + (1 - alpha) * previous_vector


def compute_confidence(
    fused_vector: np.ndarray,
    normalize: bool = True,
) -> float:
    """
    Compute U4: Confidence from entropy.

    Formula:
        conf = 1 - H(p) / log(N)

    Low entropy (focused activation) = high confidence.

    Args:
        fused_vector: Fused 12D representation
        normalize: Whether to treat vector as probability distribution

    Returns:
        Confidence ∈ [0, 1]
    """
    if normalize:
        # Normalize to probability distribution
        v = np.abs(fused_vector) + 1e-10
        p = v / v.sum()
    else:
        p = fused_vector

    # Entropy
    entropy = -np.sum(p * np.log(p + 1e-10))

    # Max entropy for 12 dimensions
    max_entropy = np.log(12)

    # Confidence = 1 - normalized entropy
    confidence = 1.0 - (entropy / max_entropy)

    return float(np.clip(confidence, 0.0, 1.0))


class USEFusion:
    """
    Complete USE fusion system for robotics.

    Integrates U1-U4 for multi-modal sensor fusion.

    Usage:
        fusion = USEFusion()

        # Add sensor readings
        fusion.update('vision', vision_12d)
        fusion.update('proprioception', proprio_12d)
        fusion.update('tactile', tactile_12d)

        # Get fused result
        result = fusion.fuse()
        print(f"Confidence: {result.confidence:.3f}")
        print(f"Coherence: {result.coherence_score:.3f}")
    """

    def __init__(self, config: Optional[USEConfig] = None):
        self.config = config or USEConfig()
        self.current_vectors: Dict[str, np.ndarray] = {}
        self.previous_vectors: Dict[str, np.ndarray] = {}
        self.previous_fused: Optional[np.ndarray] = None

    def update(self, modality: str, vector: np.ndarray) -> None:
        """
        Update a modality vector.

        Applies U3 temporal alignment automatically.
        """
        # U3: Temporal alignment
        aligned = compute_temporal_alignment(
            vector,
            self.previous_vectors.get(modality),
            self.config.temporal_alpha
        )

        self.previous_vectors[modality] = self.current_vectors.get(modality)
        self.current_vectors[modality] = aligned

    def fuse(self) -> FusionResult:
        """
        Perform complete USE fusion.

        Returns:
            FusionResult with fused vector and diagnostics
        """
        if not self.current_vectors:
            return FusionResult(
                fused_vector=np.zeros(12),
                correlation_matrix=np.array([[]]),
                modality_weights={},
                coherence_score=0.0,
                confidence=0.0,
            )

        # U1: Correlation matrix
        R = compute_correlation_matrix(self.current_vectors)

        # U2: Coherence-weighted fusion
        fused, weights = compute_coherence_fusion(
            self.current_vectors, R, self.config
        )

        # U3: Apply temporal smoothing to fused output
        if self.previous_fused is not None:
            fused = compute_temporal_alignment(
                fused, self.previous_fused, self.config.temporal_alpha
            )
        self.previous_fused = fused.copy()

        # U4: Confidence
        confidence = compute_confidence(fused)

        # Overall coherence (mean off-diagonal correlation)
        if R.shape[0] > 1:
            mask = ~np.eye(R.shape[0], dtype=bool)
            coherence = float(np.mean(np.abs(R[mask])))
        else:
            coherence = 1.0

        return FusionResult(
            fused_vector=fused,
            correlation_matrix=R,
            modality_weights=weights,
            coherence_score=coherence,
            confidence=max(confidence, self.config.min_confidence),
        )

    def get_modality_weight(self, modality: str) -> float:
        """Get current weight for a modality."""
        result = self.fuse()
        return result.modality_weights.get(modality, 0.0)

    def detect_sensor_failure(self, threshold: float = 0.2) -> List[str]:
        """
        Detect potential sensor failures from low coherence.

        Returns list of modalities with low coherence.
        """
        result = self.fuse()
        failures = []

        for modality, weight in result.modality_weights.items():
            if weight < threshold:
                failures.append(modality)

        return failures

    def reset(self) -> None:
        """Reset fusion state."""
        self.current_vectors.clear()
        self.previous_vectors.clear()
        self.previous_fused = None
