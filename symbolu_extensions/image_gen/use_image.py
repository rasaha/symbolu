#!/usr/bin/env python3
"""
USE Image Engine: Universal Synchronization Engine for Image Generation
=========================================================================

Implements USE patent formulas for phase-based coherence in image generation.

Core Formulas:
    U1: C[i,j] = (1/W) * sum_k cos(phi_i[k] - phi_j[k])
    U2: C_total = sum_{i<j} C[i,j]
    U3: dC_total/d_phi_i = -sum_{j!=i} sin(phi_i - phi_j)
    U4: Delta_phi_i = alpha * dC_total/d_phi_i

Key Features for Images:
1. Extract phases from layer hidden states
2. Compute cross-layer phase correlation (12x12 matrix)
3. Synchronize phases to maximize coherence
4. Apply phase-based corrections to latents

Usage:
------
    from symbolu_extensions.image_gen.use_image import USEImageEngine

    engine = USEImageEngine()

    # Extract phases from layer states
    phases = engine.extract_phases(layer_states)

    # Compute correlation matrix
    correlation = engine.compute_correlation_matrix(phases)

    # Compute total coherence
    coherence = engine.compute_total_coherence(phases)

    # Synchronize phases for better coherence
    synced_phases = engine.synchronize(phases, num_steps=3)
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

from symbolu_extensions.image_gen.config import USEImageConfig


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class PhaseCorrelationResult:
    """Result of phase correlation computation."""
    correlation_matrix: Any  # 12x12 matrix
    total_coherence: float   # C_total
    mean_correlation: float
    min_correlation: float
    max_correlation: float
    weakest_pairs: List[Tuple[int, int]]  # Pairs with lowest correlation


@dataclass
class PhaseSyncResult:
    """Result of phase synchronization."""
    initial_coherence: float
    final_coherence: float
    improvement: float
    num_steps: int
    synchronized_phases: Dict[int, Any]


# =============================================================================
# PHASE EXTRACTION
# =============================================================================

class PhaseExtractor:
    """
    Extracts phase vectors from layer hidden states.

    Phases are computed using the Hilbert transform or learned projections
    to represent the "temporal position" of each layer in the generation.
    """

    def __init__(self, phase_dim: int = 64):
        self.phase_dim = phase_dim
        self._projection = None  # Lazy init

    def _ensure_projection(self, input_dim: int, device: Any = None) -> None:
        """Lazily initialize projection layer."""
        if self._projection is None and PYTORCH_AVAILABLE:
            self._projection = nn.Linear(input_dim, self.phase_dim)
            if device is not None:
                self._projection = self._projection.to(device)

    def extract_phase_from_state(
        self,
        hidden_state: Any,
    ) -> Any:
        """
        Extract phase vector from a hidden state tensor.

        Args:
            hidden_state: Layer hidden state [B, C, H, W] or [B, N, D]

        Returns:
            Phase vector [B, phase_dim] in [0, 2pi]
        """
        if not PYTORCH_AVAILABLE or hidden_state is None:
            # Return random phase if no PyTorch
            return np.random.uniform(0, 2 * np.pi, self.phase_dim)

        if isinstance(hidden_state, torch.Tensor):
            # Flatten spatial dimensions
            if hidden_state.dim() == 4:
                # [B, C, H, W] -> [B, C*H*W]
                b = hidden_state.shape[0]
                flat = hidden_state.view(b, -1)
            elif hidden_state.dim() == 3:
                # [B, N, D] -> [B, N*D]
                b = hidden_state.shape[0]
                flat = hidden_state.view(b, -1)
            else:
                flat = hidden_state.flatten().unsqueeze(0)

            # Use Hilbert-inspired phase extraction
            # Take first phase_dim dimensions
            if flat.shape[-1] >= self.phase_dim:
                truncated = flat[..., :self.phase_dim]
            else:
                # Pad if needed
                truncated = F.pad(flat, (0, self.phase_dim - flat.shape[-1]))

            # Convert to phase [0, 2pi] using atan2 on pairs
            even = truncated[..., 0::2]
            odd = truncated[..., 1::2]

            # Match dimensions
            min_dim = min(even.shape[-1], odd.shape[-1])
            even = even[..., :min_dim]
            odd = odd[..., :min_dim]

            phases = torch.atan2(odd, even) + np.pi  # [0, 2pi]

            return phases

        # NumPy fallback
        if isinstance(hidden_state, np.ndarray):
            flat = hidden_state.flatten()
            if len(flat) >= self.phase_dim:
                truncated = flat[:self.phase_dim]
            else:
                truncated = np.pad(flat, (0, self.phase_dim - len(flat)))

            even = truncated[0::2]
            odd = truncated[1::2]
            min_dim = min(len(even), len(odd))
            phases = np.arctan2(odd[:min_dim], even[:min_dim]) + np.pi

            return phases

        return np.random.uniform(0, 2 * np.pi, self.phase_dim)

    def extract_all_phases(
        self,
        layer_states: Dict[int, Any],
    ) -> Dict[int, Any]:
        """
        Extract phases for all layers.

        Args:
            layer_states: Dict mapping layer index to hidden state

        Returns:
            Dict mapping layer index to phase vector
        """
        phases = {}
        for layer_idx, state in layer_states.items():
            phases[layer_idx] = self.extract_phase_from_state(state)
        return phases


# =============================================================================
# PHASE CORRELATION (U1-U2)
# =============================================================================

class PhaseCorrelation:
    """
    Computes phase correlation between layers.

    U1: C[i,j] = (1/d) * sum_k cos(phi_i[k] - phi_j[k])
    U2: C_total = sum_{i<j} C[i,j]
    """

    def __init__(self):
        pass

    def pairwise_correlation(
        self,
        phase_i: Any,
        phase_j: Any,
    ) -> float:
        """
        Compute correlation between two phase vectors.

        Formula U1: C[i,j] = (1/d) * sum_k cos(phi_i[k] - phi_j[k])

        Args:
            phase_i: Phase vector for layer i
            phase_j: Phase vector for layer j

        Returns:
            Correlation value in [-1, 1]
        """
        if PYTORCH_AVAILABLE and isinstance(phase_i, torch.Tensor):
            phase_diff = phase_i - phase_j
            correlation = torch.cos(phase_diff).mean().item()
            return float(correlation)

        if isinstance(phase_i, np.ndarray):
            phase_diff = phase_i - phase_j
            correlation = np.cos(phase_diff).mean()
            return float(correlation)

        return 0.0

    def compute_correlation_matrix(
        self,
        phases: Dict[int, Any],
    ) -> Any:
        """
        Compute 12x12 correlation matrix between all layer pairs.

        Args:
            phases: Dict mapping layer index (1-12) to phase vector

        Returns:
            12x12 correlation matrix
        """
        matrix = np.zeros((12, 12))

        for i in range(1, 13):
            for j in range(1, 13):
                if i == j:
                    matrix[i-1, j-1] = 1.0
                elif i in phases and j in phases:
                    matrix[i-1, j-1] = self.pairwise_correlation(
                        phases[i], phases[j]
                    )

        return matrix

    def compute_total_coherence(
        self,
        phases: Dict[int, Any],
        coupling_matrix: Optional[Any] = None,
    ) -> float:
        """
        Compute total coherence (U2).

        Formula: C_total = sum_{i<j} M[i,j] * C[i,j]

        Args:
            phases: Dict mapping layer index to phase vector
            coupling_matrix: Optional 12x12 coupling strength matrix

        Returns:
            Total coherence value
        """
        correlation_matrix = self.compute_correlation_matrix(phases)

        if coupling_matrix is None:
            coupling_matrix = np.ones((12, 12))

        # Sum upper triangle with coupling weights
        C_total = 0.0
        for i in range(12):
            for j in range(i + 1, 12):
                C_total += coupling_matrix[i, j] * correlation_matrix[i, j]

        # Normalize by number of pairs
        num_pairs = 12 * 11 / 2
        return float(C_total / num_pairs)

    def get_correlation_result(
        self,
        phases: Dict[int, Any],
        coupling_matrix: Optional[Any] = None,
    ) -> PhaseCorrelationResult:
        """
        Get complete correlation analysis.

        Args:
            phases: Dict mapping layer index to phase vector
            coupling_matrix: Optional coupling matrix

        Returns:
            PhaseCorrelationResult with full analysis
        """
        corr_matrix = self.compute_correlation_matrix(phases)
        total_coherence = self.compute_total_coherence(phases, coupling_matrix)

        # Statistics (excluding diagonal)
        upper_triangle = []
        for i in range(12):
            for j in range(i + 1, 12):
                upper_triangle.append(corr_matrix[i, j])

        # Find weakest pairs
        indexed_pairs = [
            ((i+1, j+1), corr_matrix[i, j])
            for i in range(12)
            for j in range(i + 1, 12)
        ]
        sorted_pairs = sorted(indexed_pairs, key=lambda x: x[1])
        weakest = [p[0] for p in sorted_pairs[:3]]

        return PhaseCorrelationResult(
            correlation_matrix=corr_matrix,
            total_coherence=total_coherence,
            mean_correlation=float(np.mean(upper_triangle)) if upper_triangle else 0.0,
            min_correlation=float(np.min(upper_triangle)) if upper_triangle else 0.0,
            max_correlation=float(np.max(upper_triangle)) if upper_triangle else 0.0,
            weakest_pairs=weakest,
        )


# =============================================================================
# PHASE SYNCHRONIZATION (U3-U4)
# =============================================================================

class PhaseSynchronizer:
    """
    Synchronizes phases to maximize coherence.

    U3: dC_total/d_phi_i = -sum_{j!=i} sin(phi_i - phi_j)
    U4: Delta_phi_i = alpha * dC_total/d_phi_i

    Uses mean-field approximation for O(n) complexity:
        sum_j sin(phi_i - phi_j) ≈ N * sin(phi_i - phi_mean)
    """

    def __init__(self, config: Optional[USEImageConfig] = None):
        self.config = config or USEImageConfig()

    def compute_gradient(
        self,
        phases: Dict[int, Any],
        layer_idx: int,
        use_mean_field: bool = True,
    ) -> Any:
        """
        Compute synchronization gradient for a layer.

        Formula U3: dC_total/d_phi_i = -sum_{j!=i} sin(phi_i - phi_j)

        Args:
            phases: Dict mapping layer index to phase vector
            layer_idx: Layer to compute gradient for
            use_mean_field: Use O(n) approximation

        Returns:
            Gradient vector
        """
        if layer_idx not in phases:
            return None

        phi_i = phases[layer_idx]

        if use_mean_field:
            # Mean-field approximation: O(n)
            other_phases = [phases[j] for j in phases if j != layer_idx]
            if not other_phases:
                return np.zeros_like(phi_i) if isinstance(phi_i, np.ndarray) else torch.zeros_like(phi_i)

            # Compute mean phase
            if PYTORCH_AVAILABLE and isinstance(phi_i, torch.Tensor):
                stacked = torch.stack(other_phases)
                phi_mean = stacked.mean(dim=0)
                N = len(other_phases)
                gradient = -N * torch.sin(phi_i - phi_mean)
            else:
                stacked = np.stack(other_phases)
                phi_mean = stacked.mean(axis=0)
                N = len(other_phases)
                gradient = -N * np.sin(phi_i - phi_mean)

            return gradient

        else:
            # Full computation: O(n^2)
            if PYTORCH_AVAILABLE and isinstance(phi_i, torch.Tensor):
                gradient = torch.zeros_like(phi_i)
                for j, phi_j in phases.items():
                    if j != layer_idx:
                        gradient -= torch.sin(phi_i - phi_j)
            else:
                gradient = np.zeros_like(phi_i)
                for j, phi_j in phases.items():
                    if j != layer_idx:
                        gradient -= np.sin(phi_i - phi_j)

            return gradient

    def synchronize_step(
        self,
        phases: Dict[int, Any],
        alpha: Optional[float] = None,
    ) -> Dict[int, Any]:
        """
        Perform one synchronization step.

        Formula U4: phi_i = phi_i + alpha * dC_total/d_phi_i

        Args:
            phases: Current phases
            alpha: Learning rate (default from config)

        Returns:
            Updated phases
        """
        alpha = alpha or self.config.sync_alpha
        use_mean_field = self.config.use_mean_field_approximation

        new_phases = {}
        for layer_idx in phases:
            gradient = self.compute_gradient(phases, layer_idx, use_mean_field)
            if gradient is not None:
                if PYTORCH_AVAILABLE and isinstance(phases[layer_idx], torch.Tensor):
                    new_phase = phases[layer_idx] + alpha * gradient
                    # Keep in [0, 2pi]
                    new_phase = new_phase % (2 * np.pi)
                else:
                    new_phase = phases[layer_idx] + alpha * gradient
                    new_phase = new_phase % (2 * np.pi)
                new_phases[layer_idx] = new_phase
            else:
                new_phases[layer_idx] = phases[layer_idx]

        return new_phases

    def synchronize(
        self,
        phases: Dict[int, Any],
        num_steps: Optional[int] = None,
        coupling_matrix: Optional[Any] = None,
    ) -> PhaseSyncResult:
        """
        Synchronize phases over multiple steps.

        Args:
            phases: Initial phases
            num_steps: Number of synchronization steps
            coupling_matrix: Optional coupling matrix for coherence computation

        Returns:
            PhaseSyncResult with before/after comparison
        """
        num_steps = num_steps or self.config.sync_steps
        correlator = PhaseCorrelation()

        # Initial coherence
        initial_coherence = correlator.compute_total_coherence(
            phases, coupling_matrix
        )

        # Synchronize
        current_phases = dict(phases)
        for _ in range(num_steps):
            current_phases = self.synchronize_step(current_phases)

        # Final coherence
        final_coherence = correlator.compute_total_coherence(
            current_phases, coupling_matrix
        )

        return PhaseSyncResult(
            initial_coherence=initial_coherence,
            final_coherence=final_coherence,
            improvement=final_coherence - initial_coherence,
            num_steps=num_steps,
            synchronized_phases=current_phases,
        )


# =============================================================================
# USE IMAGE ENGINE
# =============================================================================

class USEImageEngine:
    """
    Complete USE engine for image generation.

    Combines phase extraction, correlation, and synchronization.
    """

    def __init__(self, config: Optional[USEImageConfig] = None):
        self.config = config or USEImageConfig()
        self.extractor = PhaseExtractor(self.config.phase_dim)
        self.correlator = PhaseCorrelation()
        self.synchronizer = PhaseSynchronizer(self.config)

    def extract_phases(
        self,
        layer_states: Dict[int, Any],
    ) -> Dict[int, Any]:
        """Extract phases from layer hidden states."""
        return self.extractor.extract_all_phases(layer_states)

    def compute_correlation_matrix(
        self,
        phases: Dict[int, Any],
    ) -> Any:
        """Compute 12x12 phase correlation matrix."""
        return self.correlator.compute_correlation_matrix(phases)

    def compute_total_coherence(
        self,
        phases: Optional[Dict[int, Any]] = None,
        layer_states: Optional[Dict[int, Any]] = None,
        coupling_matrix: Optional[Any] = None,
    ) -> float:
        """
        Compute total phase coherence.

        Args:
            phases: Pre-extracted phases (optional)
            layer_states: Layer hidden states (if phases not provided)
            coupling_matrix: Optional coupling weights

        Returns:
            Total coherence value
        """
        if phases is None:
            if layer_states is None:
                return 0.0
            phases = self.extract_phases(layer_states)

        return self.correlator.compute_total_coherence(phases, coupling_matrix)

    def get_correlation_result(
        self,
        phases: Optional[Dict[int, Any]] = None,
        layer_states: Optional[Dict[int, Any]] = None,
        coupling_matrix: Optional[Any] = None,
    ) -> PhaseCorrelationResult:
        """Get full correlation analysis."""
        if phases is None:
            if layer_states is None:
                raise ValueError("Must provide phases or layer_states")
            phases = self.extract_phases(layer_states)

        return self.correlator.get_correlation_result(phases, coupling_matrix)

    def synchronize(
        self,
        phases: Optional[Dict[int, Any]] = None,
        layer_states: Optional[Dict[int, Any]] = None,
        num_steps: Optional[int] = None,
        coupling_matrix: Optional[Any] = None,
    ) -> PhaseSyncResult:
        """
        Synchronize phases to maximize coherence.

        Args:
            phases: Pre-extracted phases (optional)
            layer_states: Layer hidden states (if phases not provided)
            num_steps: Number of synchronization steps
            coupling_matrix: Optional coupling weights

        Returns:
            PhaseSyncResult with synchronized phases
        """
        if phases is None:
            if layer_states is None:
                raise ValueError("Must provide phases or layer_states")
            phases = self.extract_phases(layer_states)

        return self.synchronizer.synchronize(
            phases, num_steps, coupling_matrix
        )

    def apply_synchronization_to_latents(
        self,
        latents: Any,
        layer_states: Dict[int, Any],
        sync_result: Optional[PhaseSyncResult] = None,
        strength: float = 0.1,
    ) -> Any:
        """
        Apply phase synchronization correction to latents.

        This modulates the latents to be more coherent with the
        synchronized phase representation.

        Args:
            latents: Current image latents
            layer_states: Layer hidden states
            sync_result: Pre-computed sync result (optional)
            strength: How strongly to apply correction

        Returns:
            Corrected latents
        """
        if sync_result is None:
            sync_result = self.synchronize(layer_states=layer_states)

        # Only apply if there's improvement and PyTorch available
        if sync_result.improvement <= 0 or not PYTORCH_AVAILABLE:
            return latents

        if not isinstance(latents, torch.Tensor):
            return latents

        # Simple correction: modulate latents by coherence improvement
        # This is a simplified version - full implementation would use
        # the phase information more directly
        correction_factor = 1.0 + strength * sync_result.improvement
        corrected = latents * correction_factor

        return corrected

    def check_coherence_threshold(
        self,
        layer_states: Dict[int, Any],
        threshold: float = 0.7,
        coupling_matrix: Optional[Any] = None,
    ) -> Tuple[bool, float]:
        """
        Check if coherence exceeds threshold.

        Args:
            layer_states: Layer hidden states
            threshold: Coherence threshold
            coupling_matrix: Optional coupling weights

        Returns:
            (passed, coherence_value)
        """
        phases = self.extract_phases(layer_states)
        coherence = self.compute_total_coherence(phases, coupling_matrix=coupling_matrix)
        return coherence >= threshold, coherence


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_use_engine(
    config: Optional[USEImageConfig] = None
) -> USEImageEngine:
    """Create a USE image engine with optional config."""
    return USEImageEngine(config)


def quick_coherence(
    layer_states: Dict[int, Any],
) -> float:
    """Quick coherence computation with defaults."""
    engine = USEImageEngine()
    return engine.compute_total_coherence(layer_states=layer_states)
