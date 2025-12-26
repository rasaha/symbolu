#!/usr/bin/env python3
"""
SCC Image Engine: Semantic Coherence Controller for Image Generation
======================================================================

Implements SCC patent formulas for semantic coherence monitoring during
image generation.

Core Formulas:
    S1: C_i(t) = alpha * S_i + beta * R_i + gamma * (1-E_i) + delta * P_i
    S2: C_global(t) = sum_i w_i * C_i(t) + sum_{i<j} M_ij * Corr(C_i, C_j)
    S3: L_coherence = L_task + lambda * L_align + mu * L_consistency

Where:
    S_i: Semantic consistency (internal consistency of layer)
    R_i: Resonance (alignment with neighboring layers)
    E_i: Entropy (information disorder - lower is better)
    P_i: Predictability (how expected is layer state)
    M_ij: Bhava relationship matrix (144 relationships)

Usage:
------
    from symbolu.image_gen.scc_image import SCCImageEngine

    engine = SCCImageEngine()

    # Compute per-layer coherence
    layer_coherences = engine.compute_layer_coherences(layer_states)

    # Compute global coherence
    global_coherence = engine.compute_global_coherence(layer_states)

    # Check for coherence issues
    issues = engine.diagnose_coherence_issues(layer_states)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
import math

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    torch = None
    nn = None
    F = None

import numpy as np

from symbolu.image_gen.config import SCCImageConfig, CoherenceMatrixConfig
from symbolu.image_gen.layer_mapper import LAYER_NAMES, LAYER_BHAVA


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class LayerCoherenceResult:
    """
    Coherence result for a single layer.

    Formula S1: C_i = alpha*S_i + beta*R_i + gamma*(1-E_i) + delta*P_i
    """
    layer_index: int
    layer_name: str
    coherence: float          # C_i in [0, 1]

    # S1 components
    semantic_consistency: float  # S_i
    resonance: float             # R_i
    entropy: float               # E_i (raw, not inverted)
    predictability: float        # P_i

    # Derived
    activation_mean: float
    activation_std: float

    @property
    def is_coherent(self) -> bool:
        return self.coherence >= 0.5

    @property
    def quality(self) -> str:
        if self.coherence >= 0.8:
            return "excellent"
        elif self.coherence >= 0.6:
            return "good"
        elif self.coherence >= 0.4:
            return "fair"
        else:
            return "poor"


@dataclass
class GlobalCoherenceResult:
    """
    Global coherence result across all 12 layers.

    Formula S2: C_global = sum_i w_i*C_i + sum_{i<j} M_ij*Corr(C_i, C_j)
    """
    global_coherence: float           # C_global in [0, 1]
    weighted_layer_sum: float         # sum_i w_i*C_i
    cross_layer_coupling: float       # sum_{i<j} M_ij*Corr(C_i, C_j)

    layer_results: Dict[int, LayerCoherenceResult]

    # Statistics
    mean_coherence: float
    min_coherence: float
    max_coherence: float
    coherence_std: float

    # Weak points
    weakest_layers: List[int]
    strongest_layers: List[int]

    @property
    def is_globally_coherent(self) -> bool:
        return self.global_coherence >= 0.5

    @property
    def quality(self) -> str:
        if self.global_coherence >= 0.8:
            return "excellent"
        elif self.global_coherence >= 0.6:
            return "good"
        elif self.global_coherence >= 0.4:
            return "fair"
        else:
            return "poor"


@dataclass
class CoherenceIssue:
    """Describes a coherence issue detected during generation."""
    layer_index: int
    layer_name: str
    issue_type: str  # "low_coherence", "high_entropy", "poor_resonance", etc.
    severity: str    # "critical", "warning", "info"
    message: str
    suggested_action: str


# =============================================================================
# S1: PER-LAYER COHERENCE
# =============================================================================

class LayerCoherenceComputer:
    """
    Computes per-layer coherence using formula S1.

    C_i(t) = alpha * S_i + beta * R_i + gamma * (1-E_i) + delta * P_i
    """

    def __init__(self, config: Optional[SCCImageConfig] = None):
        self.config = config or SCCImageConfig()

    def compute_semantic_consistency(
        self,
        hidden_state: Any,
    ) -> float:
        """
        Compute semantic consistency S_i for a layer.

        Uses internal variance of the hidden state.
        Low variance = high consistency (focused representation).
        """
        if hidden_state is None:
            return 0.5

        if PYTORCH_AVAILABLE and isinstance(hidden_state, torch.Tensor):
            # Spatial consistency: variance across spatial dimensions
            if hidden_state.dim() >= 3:
                variance = hidden_state.var().item()
                # Normalize - lower variance = higher consistency
                consistency = 1.0 / (1.0 + variance)
                return float(np.clip(consistency, 0.0, 1.0))

        if isinstance(hidden_state, np.ndarray):
            variance = hidden_state.var()
            consistency = 1.0 / (1.0 + variance)
            return float(np.clip(consistency, 0.0, 1.0))

        return 0.5

    def compute_resonance(
        self,
        layer_idx: int,
        layer_states: Dict[int, Any],
        coupling_matrix: Optional[np.ndarray] = None,
    ) -> float:
        """
        Compute resonance R_i - alignment with neighboring layers.

        Uses correlation with adjacent layers weighted by coupling matrix.
        """
        if layer_idx not in layer_states:
            return 0.5

        current_state = layer_states[layer_idx]

        # Get neighbor indices
        neighbors = []
        if layer_idx > 1 and (layer_idx - 1) in layer_states:
            neighbors.append(layer_idx - 1)
        if layer_idx < 12 and (layer_idx + 1) in layer_states:
            neighbors.append(layer_idx + 1)

        if not neighbors:
            return 0.5

        # Compute correlation with neighbors
        correlations = []
        for neighbor_idx in neighbors:
            neighbor_state = layer_states[neighbor_idx]
            corr = self._compute_state_correlation(current_state, neighbor_state)

            # Weight by coupling matrix if provided
            weight = 1.0
            if coupling_matrix is not None:
                weight = coupling_matrix[layer_idx - 1, neighbor_idx - 1]

            correlations.append(weight * corr)

        # Average resonance
        resonance = sum(correlations) / len(correlations)
        return float(np.clip(resonance, 0.0, 1.0))

    def _compute_state_correlation(
        self,
        state1: Any,
        state2: Any,
    ) -> float:
        """Compute correlation between two hidden states."""
        if state1 is None or state2 is None:
            return 0.5

        if PYTORCH_AVAILABLE and isinstance(state1, torch.Tensor):
            # Flatten and compute cosine similarity
            flat1 = state1.flatten().float()
            flat2 = state2.flatten().float()

            # Match dimensions
            min_len = min(len(flat1), len(flat2))
            flat1 = flat1[:min_len]
            flat2 = flat2[:min_len]

            # Normalize
            norm1 = F.normalize(flat1.unsqueeze(0), dim=-1)
            norm2 = F.normalize(flat2.unsqueeze(0), dim=-1)

            # Cosine similarity
            sim = (norm1 @ norm2.T).item()
            return float((sim + 1) / 2)  # Map to [0, 1]

        if isinstance(state1, np.ndarray) and isinstance(state2, np.ndarray):
            flat1 = state1.flatten()
            flat2 = state2.flatten()
            min_len = min(len(flat1), len(flat2))

            norm1 = flat1[:min_len] / (np.linalg.norm(flat1[:min_len]) + 1e-8)
            norm2 = flat2[:min_len] / (np.linalg.norm(flat2[:min_len]) + 1e-8)

            sim = np.dot(norm1, norm2)
            return float((sim + 1) / 2)

        return 0.5

    def compute_entropy(
        self,
        hidden_state: Any,
    ) -> float:
        """
        Compute entropy E_i of the layer representation.

        Higher entropy = more disorder = lower coherence.
        """
        if hidden_state is None:
            return 0.5

        if PYTORCH_AVAILABLE and isinstance(hidden_state, torch.Tensor):
            # Use softmax to get distribution, then compute entropy
            flat = hidden_state.flatten().float()
            probs = F.softmax(flat, dim=0)
            log_probs = torch.log(probs + 1e-10)
            entropy = -(probs * log_probs).sum().item()

            # Normalize by max possible entropy
            max_entropy = np.log(len(flat))
            normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0

            return float(np.clip(normalized_entropy, 0.0, 1.0))

        if isinstance(hidden_state, np.ndarray):
            flat = hidden_state.flatten()
            # Shift to positive for softmax
            flat = flat - flat.min() + 1e-10
            probs = flat / flat.sum()
            entropy = -np.sum(probs * np.log(probs + 1e-10))

            max_entropy = np.log(len(flat))
            normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0

            return float(np.clip(normalized_entropy, 0.0, 1.0))

        return 0.5

    def compute_predictability(
        self,
        layer_idx: int,
        hidden_state: Any,
        previous_state: Optional[Any] = None,
    ) -> float:
        """
        Compute predictability P_i - how expected is this layer.

        Uses stability of activations (variance over time if available).
        """
        if hidden_state is None:
            return 0.5

        # If we have previous state, compute temporal consistency
        if previous_state is not None:
            return self._compute_state_correlation(hidden_state, previous_state)

        # Otherwise, use activation statistics as proxy
        if PYTORCH_AVAILABLE and isinstance(hidden_state, torch.Tensor):
            mean = hidden_state.mean().abs().item()
            # Well-defined activations = high predictability
            predictability = 1.0 - np.exp(-mean)
            return float(np.clip(predictability, 0.0, 1.0))

        if isinstance(hidden_state, np.ndarray):
            mean = np.abs(hidden_state.mean())
            predictability = 1.0 - np.exp(-mean)
            return float(np.clip(predictability, 0.0, 1.0))

        return 0.5

    def compute_layer_coherence(
        self,
        layer_idx: int,
        layer_states: Dict[int, Any],
        coupling_matrix: Optional[np.ndarray] = None,
    ) -> LayerCoherenceResult:
        """
        Compute full S1 coherence for a layer.

        Formula: C_i = alpha*S_i + beta*R_i + gamma*(1-E_i) + delta*P_i
        """
        hidden_state = layer_states.get(layer_idx)

        # Compute S1 components
        S_i = self.compute_semantic_consistency(hidden_state)
        R_i = self.compute_resonance(layer_idx, layer_states, coupling_matrix)
        E_i = self.compute_entropy(hidden_state)
        P_i = self.compute_predictability(layer_idx, hidden_state)

        # Combine using configured weights
        # Note: gamma is applied to (1 - E_i) since low entropy = high coherence
        C_i = (
            self.config.alpha * S_i +
            self.config.beta * R_i +
            self.config.gamma * (1.0 - E_i) +
            self.config.delta * P_i
        )

        # Compute activation statistics
        if PYTORCH_AVAILABLE and isinstance(hidden_state, torch.Tensor):
            mean = hidden_state.mean().item()
            std = hidden_state.std().item()
        elif isinstance(hidden_state, np.ndarray):
            mean = float(hidden_state.mean())
            std = float(hidden_state.std())
        else:
            mean, std = 0.0, 0.0

        return LayerCoherenceResult(
            layer_index=layer_idx,
            layer_name=LAYER_NAMES.get(layer_idx, f"Layer{layer_idx}"),
            coherence=float(np.clip(C_i, 0.0, 1.0)),
            semantic_consistency=S_i,
            resonance=R_i,
            entropy=E_i,
            predictability=P_i,
            activation_mean=mean,
            activation_std=std,
        )


# =============================================================================
# S2: GLOBAL COHERENCE
# =============================================================================

class GlobalCoherenceComputer:
    """
    Computes global coherence using formula S2.

    C_global = sum_i w_i*C_i + sum_{i<j} M_ij*Corr(C_i, C_j)
    """

    def __init__(
        self,
        config: Optional[SCCImageConfig] = None,
        matrix_config: Optional[CoherenceMatrixConfig] = None,
    ):
        self.config = config or SCCImageConfig()
        self.matrix_config = matrix_config or CoherenceMatrixConfig()
        self.layer_computer = LayerCoherenceComputer(config)
        self._coupling_matrix = None

    def _get_coupling_matrix(self) -> np.ndarray:
        """Get or build the 12x12 coupling matrix."""
        if self._coupling_matrix is None:
            self._coupling_matrix = np.array(
                self.matrix_config.build_default_matrix()
            )
        return self._coupling_matrix

    def compute_layer_coherences(
        self,
        layer_states: Dict[int, Any],
    ) -> Dict[int, LayerCoherenceResult]:
        """Compute coherence for all available layers."""
        coupling_matrix = self._get_coupling_matrix()
        results = {}

        for layer_idx in range(1, 13):
            if layer_idx in layer_states:
                results[layer_idx] = self.layer_computer.compute_layer_coherence(
                    layer_idx, layer_states, coupling_matrix
                )

        return results

    def compute_global_coherence(
        self,
        layer_states: Dict[int, Any],
    ) -> GlobalCoherenceResult:
        """
        Compute global coherence across all layers.

        Formula S2: C_global = sum_i w_i*C_i + sum_{i<j} M_ij*Corr(C_i, C_j)
        """
        coupling_matrix = self._get_coupling_matrix()
        layer_weights = self.config.layer_weights

        # Compute per-layer coherences
        layer_results = self.compute_layer_coherences(layer_states)

        if not layer_results:
            return GlobalCoherenceResult(
                global_coherence=0.0,
                weighted_layer_sum=0.0,
                cross_layer_coupling=0.0,
                layer_results={},
                mean_coherence=0.0,
                min_coherence=0.0,
                max_coherence=0.0,
                coherence_std=0.0,
                weakest_layers=[],
                strongest_layers=[],
            )

        # Term 1: Weighted sum of layer coherences
        weighted_sum = 0.0
        for layer_idx, result in layer_results.items():
            weight = layer_weights[layer_idx - 1] if layer_weights else 1/12
            weighted_sum += weight * result.coherence

        # Term 2: Cross-layer coupling
        cross_coupling = 0.0
        coherence_values = {idx: r.coherence for idx, r in layer_results.items()}

        for i in range(1, 13):
            for j in range(i + 1, 13):
                if i in coherence_values and j in coherence_values:
                    M_ij = coupling_matrix[i-1, j-1]
                    # Correlation of coherence values (simplified)
                    corr = coherence_values[i] * coherence_values[j]
                    cross_coupling += M_ij * corr

        # Normalize cross-coupling
        num_pairs = 12 * 11 / 2
        cross_coupling /= num_pairs

        # Global coherence
        global_coherence = weighted_sum + 0.3 * cross_coupling  # Weight cross-coupling

        # Statistics
        coherence_list = [r.coherence for r in layer_results.values()]
        sorted_layers = sorted(layer_results.keys(), key=lambda x: layer_results[x].coherence)

        return GlobalCoherenceResult(
            global_coherence=float(np.clip(global_coherence, 0.0, 1.0)),
            weighted_layer_sum=weighted_sum,
            cross_layer_coupling=cross_coupling,
            layer_results=layer_results,
            mean_coherence=float(np.mean(coherence_list)),
            min_coherence=float(np.min(coherence_list)),
            max_coherence=float(np.max(coherence_list)),
            coherence_std=float(np.std(coherence_list)),
            weakest_layers=sorted_layers[:3],
            strongest_layers=sorted_layers[-3:],
        )


# =============================================================================
# COHERENCE RESTORER
# =============================================================================

class CoherenceRestorer:
    """
    Restores coherence when issues are detected.

    Applies corrections to latents/states based on detected issues.
    """

    def __init__(self, config: Optional[SCCImageConfig] = None):
        self.config = config or SCCImageConfig()

    def restore_semantic_coherence(
        self,
        latents: Any,
        text_embeddings: Any,
        strength: float = 0.1,
    ) -> Any:
        """
        Restore semantic coherence by projecting toward text embeddings.

        Args:
            latents: Current image latents
            text_embeddings: Text encoder embeddings
            strength: How strongly to apply correction

        Returns:
            Corrected latents
        """
        if not PYTORCH_AVAILABLE:
            return latents

        if not isinstance(latents, torch.Tensor):
            return latents

        if text_embeddings is None:
            return latents

        # Simple correction: move latents toward text direction
        if isinstance(text_embeddings, torch.Tensor):
            # Match dimensions for correction
            latent_flat = latents.flatten()
            text_flat = text_embeddings.flatten()

            min_len = min(len(latent_flat), len(text_flat))
            text_direction = text_flat[:min_len]

            # Compute correction
            correction = text_direction - latent_flat[:min_len].mean()
            correction = correction / (correction.norm() + 1e-8)

            # Apply correction (reshape to match latents)
            # This is simplified - full implementation would be more sophisticated
            corrected = latents + strength * correction.mean()

            return corrected

        return latents

    def diagnose_and_restore(
        self,
        latents: Any,
        layer_states: Dict[int, Any],
        text_embeddings: Any,
        threshold: float = 0.5,
    ) -> Tuple[Any, List[CoherenceIssue]]:
        """
        Diagnose issues and apply restorations.

        Args:
            latents: Current latents
            layer_states: Layer hidden states
            text_embeddings: Text embeddings
            threshold: Coherence threshold

        Returns:
            (corrected_latents, issues)
        """
        # Compute coherence
        computer = GlobalCoherenceComputer(self.config)
        result = computer.compute_global_coherence(layer_states)

        issues = []
        corrected = latents

        # Check each layer
        for layer_idx, layer_result in result.layer_results.items():
            if layer_result.coherence < threshold:
                issue = CoherenceIssue(
                    layer_index=layer_idx,
                    layer_name=layer_result.layer_name,
                    issue_type="low_coherence",
                    severity="warning" if layer_result.coherence >= 0.3 else "critical",
                    message=f"Layer {layer_idx} coherence is {layer_result.coherence:.2f}",
                    suggested_action="Apply semantic restoration",
                )
                issues.append(issue)

            if layer_result.entropy > 0.7:
                issue = CoherenceIssue(
                    layer_index=layer_idx,
                    layer_name=layer_result.layer_name,
                    issue_type="high_entropy",
                    severity="warning",
                    message=f"Layer {layer_idx} has high entropy ({layer_result.entropy:.2f})",
                    suggested_action="Reduce feature disorder",
                )
                issues.append(issue)

        # Apply restoration if issues found
        if issues:
            corrected = self.restore_semantic_coherence(
                latents, text_embeddings, strength=0.1 * len(issues)
            )

        return corrected, issues


# =============================================================================
# SCC IMAGE ENGINE
# =============================================================================

class SCCImageEngine:
    """
    Complete SCC engine for image generation.

    Combines per-layer coherence, global coherence, and restoration.
    """

    def __init__(
        self,
        config: Optional[SCCImageConfig] = None,
        matrix_config: Optional[CoherenceMatrixConfig] = None,
    ):
        self.config = config or SCCImageConfig()
        self.matrix_config = matrix_config or CoherenceMatrixConfig()
        self.layer_computer = LayerCoherenceComputer(self.config)
        self.global_computer = GlobalCoherenceComputer(self.config, self.matrix_config)
        self.restorer = CoherenceRestorer(self.config)

    def compute_layer_coherence(
        self,
        layer_idx: int,
        layer_states: Dict[int, Any],
    ) -> LayerCoherenceResult:
        """Compute coherence for a single layer."""
        coupling_matrix = np.array(self.matrix_config.build_default_matrix())
        return self.layer_computer.compute_layer_coherence(
            layer_idx, layer_states, coupling_matrix
        )

    def compute_layer_coherences(
        self,
        layer_states: Dict[int, Any],
    ) -> Dict[int, LayerCoherenceResult]:
        """Compute coherence for all layers."""
        return self.global_computer.compute_layer_coherences(layer_states)

    def compute_global_coherence(
        self,
        layer_states: Dict[int, Any],
    ) -> GlobalCoherenceResult:
        """Compute global coherence across all layers."""
        return self.global_computer.compute_global_coherence(layer_states)

    def semantic_entropy(
        self,
        hidden_state: Any,
    ) -> float:
        """Compute semantic entropy of a hidden state."""
        return self.layer_computer.compute_entropy(hidden_state)

    def restore_coherence(
        self,
        latents: Any,
        text_embeddings: Any,
        strength: float = 0.1,
    ) -> Any:
        """Apply coherence restoration to latents."""
        return self.restorer.restore_semantic_coherence(
            latents, text_embeddings, strength
        )

    def diagnose_issues(
        self,
        layer_states: Dict[int, Any],
        threshold: float = 0.5,
    ) -> List[CoherenceIssue]:
        """Diagnose coherence issues across all layers."""
        result = self.compute_global_coherence(layer_states)
        issues = []

        for layer_idx, layer_result in result.layer_results.items():
            if layer_result.coherence < threshold:
                severity = "critical" if layer_result.coherence < 0.3 else "warning"
                issues.append(CoherenceIssue(
                    layer_index=layer_idx,
                    layer_name=layer_result.layer_name,
                    issue_type="low_coherence",
                    severity=severity,
                    message=f"Low coherence ({layer_result.coherence:.2f})",
                    suggested_action="Apply semantic restoration",
                ))

            if layer_result.entropy > 0.7:
                issues.append(CoherenceIssue(
                    layer_index=layer_idx,
                    layer_name=layer_result.layer_name,
                    issue_type="high_entropy",
                    severity="warning",
                    message=f"High entropy ({layer_result.entropy:.2f})",
                    suggested_action="Reduce feature disorder",
                ))

            if layer_result.resonance < 0.3:
                issues.append(CoherenceIssue(
                    layer_index=layer_idx,
                    layer_name=layer_result.layer_name,
                    issue_type="poor_resonance",
                    severity="warning",
                    message=f"Poor layer resonance ({layer_result.resonance:.2f})",
                    suggested_action="Improve cross-layer alignment",
                ))

        return issues

    def check_threshold(
        self,
        layer_states: Dict[int, Any],
        threshold: float = 0.7,
    ) -> Tuple[bool, GlobalCoherenceResult]:
        """
        Check if global coherence exceeds threshold.

        Returns:
            (passed, result)
        """
        result = self.compute_global_coherence(layer_states)
        return result.global_coherence >= threshold, result


# =============================================================================
# S6: INTEGRATED INFORMATION
# =============================================================================

@dataclass
class IntegratedInformationResult:
    """Result of integrated information computation (S6)."""
    phi: float  # Integrated information value
    pairwise_contributions: Dict[Tuple[int, int], float]  # (i,j) -> contribution
    mutual_information_matrix: Any  # 12x12 MI matrix
    coherence_weighted: bool


class IntegratedInformationComputer:
    """
    Computes Integrated Information (S6).

    Formula: Φ = ∫ I(Lᵢ; Lⱼ) × coherence(Lᵢ, Lⱼ) dL

    Discrete approximation:
        Φ ≈ Σᵢ<ⱼ I(Lᵢ; Lⱼ) × C[i,j]

    Where I(Lᵢ; Lⱼ) = H(Lᵢ) + H(Lⱼ) - H(Lᵢ, Lⱼ) is mutual information.
    """

    def __init__(self, config: Optional[SCCImageConfig] = None):
        self.config = config or SCCImageConfig()
        self._layer_computer = LayerCoherenceComputer(config)

    def compute_entropy(self, state: Any) -> float:
        """Compute entropy of a single state."""
        return self._layer_computer.compute_entropy(state)

    def compute_joint_entropy(self, state_i: Any, state_j: Any) -> float:
        """
        Compute joint entropy H(Lᵢ, Lⱼ).

        Uses concatenated distribution approximation.
        """
        if state_i is None or state_j is None:
            return 0.5

        if PYTORCH_AVAILABLE and isinstance(state_i, torch.Tensor):
            # Concatenate flattened states
            flat_i = state_i.flatten().float()
            flat_j = state_j.flatten().float()

            # Take min length for alignment
            min_len = min(len(flat_i), len(flat_j))
            joint = torch.cat([flat_i[:min_len], flat_j[:min_len]])

            # Convert to probability distribution
            probs = F.softmax(joint, dim=0)
            log_probs = torch.log(probs + 1e-10)
            entropy = -(probs * log_probs).sum().item()

            # Normalize
            max_entropy = np.log(len(joint))
            normalized = entropy / max_entropy if max_entropy > 0 else 0

            return float(np.clip(normalized, 0.0, 1.0))

        if isinstance(state_i, np.ndarray) and isinstance(state_j, np.ndarray):
            flat_i = state_i.flatten()
            flat_j = state_j.flatten()
            min_len = min(len(flat_i), len(flat_j))

            joint = np.concatenate([flat_i[:min_len], flat_j[:min_len]])
            joint = joint - joint.min() + 1e-10
            probs = joint / joint.sum()

            entropy = -np.sum(probs * np.log(probs + 1e-10))
            max_entropy = np.log(len(joint))
            normalized = entropy / max_entropy if max_entropy > 0 else 0

            return float(np.clip(normalized, 0.0, 1.0))

        return 0.5

    def compute_mutual_information(
        self,
        state_i: Any,
        state_j: Any,
    ) -> float:
        """
        Compute mutual information I(Lᵢ; Lⱼ).

        Formula: I(Lᵢ; Lⱼ) = H(Lᵢ) + H(Lⱼ) - H(Lᵢ, Lⱼ)
        """
        H_i = self.compute_entropy(state_i)
        H_j = self.compute_entropy(state_j)
        H_ij = self.compute_joint_entropy(state_i, state_j)

        # MI = H(i) + H(j) - H(i,j)
        # Note: Can be negative due to estimation errors, clip to 0
        I_ij = H_i + H_j - H_ij
        return float(max(0.0, I_ij))

    def compute_integrated_information(
        self,
        layer_states: Dict[int, Any],
        coherence_matrix: Optional[np.ndarray] = None,
    ) -> IntegratedInformationResult:
        """
        Compute integrated information Φ.

        Formula S6: Φ = Σᵢ<ⱼ I(Lᵢ; Lⱼ) × C[i,j]

        Args:
            layer_states: Hidden states for each layer
            coherence_matrix: 12x12 coherence/coupling matrix

        Returns:
            IntegratedInformationResult with Φ and details
        """
        n = 12
        Phi = 0.0
        pairwise_contributions = {}
        mi_matrix = np.zeros((n, n))

        # Compute pairwise mutual information
        for i in range(1, n + 1):
            for j in range(i + 1, n + 1):
                if i in layer_states and j in layer_states:
                    # Mutual information
                    I_ij = self.compute_mutual_information(
                        layer_states[i], layer_states[j]
                    )
                    mi_matrix[i-1, j-1] = I_ij
                    mi_matrix[j-1, i-1] = I_ij  # Symmetric

                    # Coherence weight
                    if coherence_matrix is not None:
                        C_ij = coherence_matrix[i-1, j-1]
                    else:
                        C_ij = 1.0

                    # Contribution to Φ
                    contribution = I_ij * C_ij
                    pairwise_contributions[(i, j)] = contribution
                    Phi += contribution

        # Normalize by number of pairs
        num_pairs = n * (n - 1) / 2
        if num_pairs > 0:
            Phi /= num_pairs

        return IntegratedInformationResult(
            phi=float(Phi),
            pairwise_contributions=pairwise_contributions,
            mutual_information_matrix=mi_matrix,
            coherence_weighted=(coherence_matrix is not None),
        )


# =============================================================================
# S7: BIDIRECTIONAL CONSISTENCY
# =============================================================================

@dataclass
class BidirectionalConsistencyResult:
    """Result of bidirectional consistency computation (S7)."""
    layer_index: int
    layer_name: str
    R: float  # Bidirectional consistency score
    C_up: float  # Bottom-up consistency
    C_down: float  # Top-down consistency


class BidirectionalConsistencyComputer:
    """
    Computes Bidirectional Consistency (S7).

    Formula: R[i] = (C_up[i] + C_down[i]) / 2

    Where:
        C_up[i] = average coherence with lower layers (bottom-up)
        C_down[i] = average coherence with higher layers (top-down)
    """

    def __init__(self):
        pass

    def compute_bidirectional_consistency(
        self,
        layer_idx: int,
        coherence_matrix: np.ndarray,
    ) -> BidirectionalConsistencyResult:
        """
        Compute bidirectional consistency for a single layer.

        Formula S7: R[i] = (C_up[i] + C_down[i]) / 2

        Args:
            layer_idx: Layer index (1-12)
            coherence_matrix: 12x12 coherence matrix

        Returns:
            BidirectionalConsistencyResult
        """
        n = 12
        i = layer_idx - 1  # Convert to 0-indexed

        # Bottom-up: average coherence with lower layers
        if i > 0:
            lower_coherences = [coherence_matrix[i, j] for j in range(i)]
            C_up = float(np.mean(lower_coherences))
        else:
            C_up = 1.0  # Base case: no lower layers

        # Top-down: average coherence with higher layers
        if i < n - 1:
            higher_coherences = [coherence_matrix[i, j] for j in range(i + 1, n)]
            C_down = float(np.mean(higher_coherences))
        else:
            C_down = 1.0  # Base case: no higher layers

        # Bidirectional average
        R = (C_up + C_down) / 2

        return BidirectionalConsistencyResult(
            layer_index=layer_idx,
            layer_name=LAYER_NAMES.get(layer_idx, f"Layer{layer_idx}"),
            R=float(np.clip(R, 0.0, 1.0)),
            C_up=float(np.clip(C_up, 0.0, 1.0)),
            C_down=float(np.clip(C_down, 0.0, 1.0)),
        )

    def compute_all_layers(
        self,
        coherence_matrix: np.ndarray,
    ) -> Dict[int, BidirectionalConsistencyResult]:
        """Compute bidirectional consistency for all 12 layers."""
        results = {}
        for layer_idx in range(1, 13):
            results[layer_idx] = self.compute_bidirectional_consistency(
                layer_idx, coherence_matrix
            )
        return results


# =============================================================================
# S8-S9: CONSTRAINT CHECKING
# =============================================================================

@dataclass
class StabilityCheckResult:
    """Result of stability constraint check (S8)."""
    is_stable: bool
    entropy_change: float  # dH/dt
    current_entropy: float
    previous_entropy: Optional[float]
    tolerance: float


@dataclass
class DriftCheckResult:
    """Result of drift constraint check (S9)."""
    within_bounds: bool
    drift_rate: float  # |dM/dt|
    current_mean: float
    previous_mean: Optional[float]
    delta_threshold: float


@dataclass
class ConstraintCheckResult:
    """Combined constraint check result."""
    stability: StabilityCheckResult
    drift: DriftCheckResult
    all_satisfied: bool
    violations: List[str]


class ConstraintChecker:
    """
    Checks stability (S8) and drift (S9) constraints.

    S8: dHₛₑₘ/dt ≤ 0 (entropy should decrease or stay flat)
    S9: |dM/dt| ≤ δ (semantic state change bounded)
    """

    def __init__(
        self,
        entropy_tolerance: float = 0.01,
        drift_delta: float = 0.05,
    ):
        """
        Initialize constraint checker.

        Args:
            entropy_tolerance: Max allowed entropy increase (S8)
            drift_delta: Max allowed drift rate (S9)
        """
        self.entropy_tolerance = entropy_tolerance
        self.drift_delta = drift_delta

        # History tracking
        self._entropy_history: List[float] = []
        self._mean_history: List[float] = []
        self._layer_computer = LayerCoherenceComputer()

    def reset(self) -> None:
        """Reset history for new generation."""
        self._entropy_history.clear()
        self._mean_history.clear()

    def record_state(self, layer_states: Dict[int, Any]) -> None:
        """Record current state for constraint tracking."""
        # Compute global entropy
        total_entropy = 0.0
        total_mean = 0.0
        count = 0

        for layer_idx, state in layer_states.items():
            entropy = self._layer_computer.compute_entropy(state)
            total_entropy += entropy

            if PYTORCH_AVAILABLE and isinstance(state, torch.Tensor):
                total_mean += state.mean().item()
            elif isinstance(state, np.ndarray):
                total_mean += float(state.mean())
            count += 1

        if count > 0:
            self._entropy_history.append(total_entropy / count)
            self._mean_history.append(total_mean / count)

    def check_stability(self) -> StabilityCheckResult:
        """
        Check stability constraint (S8).

        Formula: dHₛₑₘ/dt ≤ ε (entropy should not increase significantly)

        Returns:
            StabilityCheckResult
        """
        if len(self._entropy_history) < 2:
            return StabilityCheckResult(
                is_stable=True,
                entropy_change=0.0,
                current_entropy=self._entropy_history[-1] if self._entropy_history else 0.0,
                previous_entropy=None,
                tolerance=self.entropy_tolerance,
            )

        current = self._entropy_history[-1]
        previous = self._entropy_history[-2]
        dH_dt = current - previous

        # Stable if entropy decreased or increased within tolerance
        is_stable = dH_dt <= self.entropy_tolerance

        return StabilityCheckResult(
            is_stable=is_stable,
            entropy_change=dH_dt,
            current_entropy=current,
            previous_entropy=previous,
            tolerance=self.entropy_tolerance,
        )

    def check_drift(self) -> DriftCheckResult:
        """
        Check drift constraint (S9).

        Formula: |dM/dt| ≤ δ (semantic state change bounded)

        Returns:
            DriftCheckResult
        """
        if len(self._mean_history) < 2:
            return DriftCheckResult(
                within_bounds=True,
                drift_rate=0.0,
                current_mean=self._mean_history[-1] if self._mean_history else 0.0,
                previous_mean=None,
                delta_threshold=self.drift_delta,
            )

        current = self._mean_history[-1]
        previous = self._mean_history[-2]

        # Relative drift rate
        drift_rate = abs(current - previous) / (abs(previous) + 1e-10)

        within_bounds = drift_rate <= self.drift_delta

        return DriftCheckResult(
            within_bounds=within_bounds,
            drift_rate=drift_rate,
            current_mean=current,
            previous_mean=previous,
            delta_threshold=self.drift_delta,
        )

    def check_all_constraints(
        self,
        layer_states: Optional[Dict[int, Any]] = None,
    ) -> ConstraintCheckResult:
        """
        Check all constraints (S8 and S9).

        Args:
            layer_states: If provided, records state before checking

        Returns:
            ConstraintCheckResult with all checks
        """
        if layer_states is not None:
            self.record_state(layer_states)

        stability = self.check_stability()
        drift = self.check_drift()

        violations = []
        if not stability.is_stable:
            violations.append(
                f"S8 violated: entropy increased by {stability.entropy_change:.4f} "
                f"(tolerance: {stability.tolerance})"
            )
        if not drift.within_bounds:
            violations.append(
                f"S9 violated: drift rate {drift.drift_rate:.4f} "
                f"exceeds threshold {drift.delta_threshold}"
            )

        return ConstraintCheckResult(
            stability=stability,
            drift=drift,
            all_satisfied=(stability.is_stable and drift.within_bounds),
            violations=violations,
        )

    def get_history_summary(self) -> Dict[str, Any]:
        """Get summary of tracked history."""
        return {
            "num_recordings": len(self._entropy_history),
            "entropy_history": self._entropy_history.copy(),
            "mean_history": self._mean_history.copy(),
            "entropy_trend": self._compute_trend(self._entropy_history),
            "mean_trend": self._compute_trend(self._mean_history),
        }

    def _compute_trend(self, history: List[float]) -> str:
        """Compute trend direction from history."""
        if len(history) < 2:
            return "stable"
        diff = history[-1] - history[0]
        if diff > 0.05:
            return "increasing"
        elif diff < -0.05:
            return "decreasing"
        return "stable"


# =============================================================================
# EXTENDED SCC IMAGE ENGINE
# =============================================================================

class ExtendedSCCImageEngine(SCCImageEngine):
    """
    Extended SCC engine with S6-S9 support.

    Adds:
    - S6: Integrated Information (Φ)
    - S7: Bidirectional Consistency (R[i])
    - S8: Stability Constraint
    - S9: Drift Constraint
    """

    def __init__(
        self,
        config: Optional[SCCImageConfig] = None,
        matrix_config: Optional[CoherenceMatrixConfig] = None,
        entropy_tolerance: float = 0.01,
        drift_delta: float = 0.05,
    ):
        super().__init__(config, matrix_config)

        # S6: Integrated Information
        self.ii_computer = IntegratedInformationComputer(config)

        # S7: Bidirectional Consistency
        self.bidir_computer = BidirectionalConsistencyComputer()

        # S8-S9: Constraint Checking
        self.constraint_checker = ConstraintChecker(
            entropy_tolerance=entropy_tolerance,
            drift_delta=drift_delta,
        )

    def compute_integrated_information(
        self,
        layer_states: Dict[int, Any],
        use_coherence_weighting: bool = True,
    ) -> IntegratedInformationResult:
        """
        Compute integrated information Φ (S6).

        Args:
            layer_states: Hidden states for each layer
            use_coherence_weighting: Weight MI by coherence matrix

        Returns:
            IntegratedInformationResult
        """
        coherence_matrix = None
        if use_coherence_weighting:
            coherence_matrix = np.array(self.matrix_config.build_default_matrix())

        return self.ii_computer.compute_integrated_information(
            layer_states, coherence_matrix
        )

    def compute_bidirectional_consistency(
        self,
        layer_states: Dict[int, Any],
        layer_idx: Optional[int] = None,
    ) -> Union[BidirectionalConsistencyResult, Dict[int, BidirectionalConsistencyResult]]:
        """
        Compute bidirectional consistency (S7).

        Args:
            layer_states: Hidden states for each layer
            layer_idx: Specific layer (None = all layers)

        Returns:
            Single result or dict of all layer results
        """
        # Build coherence matrix from layer states
        layer_results = self.compute_layer_coherences(layer_states)
        coherence_matrix = np.zeros((12, 12))

        for i in range(1, 13):
            for j in range(1, 13):
                if i == j:
                    coherence_matrix[i-1, j-1] = 1.0
                elif i in layer_results and j in layer_results:
                    # Use product of coherences as pairwise measure
                    coherence_matrix[i-1, j-1] = (
                        layer_results[i].coherence * layer_results[j].coherence
                    )

        if layer_idx is not None:
            return self.bidir_computer.compute_bidirectional_consistency(
                layer_idx, coherence_matrix
            )
        else:
            return self.bidir_computer.compute_all_layers(coherence_matrix)

    def check_constraints(
        self,
        layer_states: Dict[int, Any],
    ) -> ConstraintCheckResult:
        """
        Check stability (S8) and drift (S9) constraints.

        Args:
            layer_states: Current layer states

        Returns:
            ConstraintCheckResult
        """
        return self.constraint_checker.check_all_constraints(layer_states)

    def reset_constraint_tracking(self) -> None:
        """Reset constraint history for new generation."""
        self.constraint_checker.reset()

    def full_analysis(
        self,
        layer_states: Dict[int, Any],
    ) -> Dict[str, Any]:
        """
        Perform full SCC analysis including S1-S9.

        Returns comprehensive analysis dict.
        """
        # S1-S2: Standard coherence
        global_result = self.compute_global_coherence(layer_states)

        # S6: Integrated Information
        ii_result = self.compute_integrated_information(layer_states)

        # S7: Bidirectional Consistency
        bidir_results = self.compute_bidirectional_consistency(layer_states)

        # S8-S9: Constraints
        constraint_result = self.check_constraints(layer_states)

        # Diagnose issues
        issues = self.diagnose_issues(layer_states)

        return {
            "global_coherence": global_result.global_coherence,
            "layer_coherences": {
                idx: r.coherence for idx, r in global_result.layer_results.items()
            },
            "integrated_information": {
                "phi": ii_result.phi,
                "num_contributions": len(ii_result.pairwise_contributions),
            },
            "bidirectional_consistency": {
                idx: {
                    "R": r.R,
                    "C_up": r.C_up,
                    "C_down": r.C_down,
                }
                for idx, r in bidir_results.items()
            },
            "constraints": {
                "all_satisfied": constraint_result.all_satisfied,
                "stability": {
                    "is_stable": constraint_result.stability.is_stable,
                    "entropy_change": constraint_result.stability.entropy_change,
                },
                "drift": {
                    "within_bounds": constraint_result.drift.within_bounds,
                    "drift_rate": constraint_result.drift.drift_rate,
                },
                "violations": constraint_result.violations,
            },
            "issues": [
                {"layer": i.layer_name, "type": i.issue_type, "message": i.message}
                for i in issues
            ],
            "quality": global_result.quality,
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_scc_engine(
    config: Optional[SCCImageConfig] = None
) -> SCCImageEngine:
    """Create an SCC image engine with optional config."""
    return SCCImageEngine(config)


def create_extended_scc_engine(
    config: Optional[SCCImageConfig] = None,
    entropy_tolerance: float = 0.01,
    drift_delta: float = 0.05,
) -> ExtendedSCCImageEngine:
    """Create an extended SCC engine with S6-S9 support."""
    return ExtendedSCCImageEngine(
        config=config,
        entropy_tolerance=entropy_tolerance,
        drift_delta=drift_delta,
    )


def quick_coherence(
    layer_states: Dict[int, Any],
) -> float:
    """Quick global coherence computation with defaults."""
    engine = SCCImageEngine()
    result = engine.compute_global_coherence(layer_states)
    return result.global_coherence
