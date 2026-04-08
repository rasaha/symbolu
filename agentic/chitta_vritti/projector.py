"""Representation projectors for cross-layer coherence computation.

All representations must be projected to a common D-dimensional space
with L2 normalization before coherence computation. This module defines
the projection protocol and provides adapters for different representation types.

Invariants:
- INV-CV-2: Scale invariance (pre-L2-norm scaling doesn't affect similarity)
- All projected vectors have the same dimensionality D
- All projected vectors are L2-normalized
"""

from abc import ABC, abstractmethod
from typing import Protocol, Optional
import numpy as np


class RepresentationProjector(Protocol):
    """Protocol for representation projectors.

    Each projector maps a native representation to a D-dimensional
    L2-normalized vector for cross-layer coherence computation.
    """

    @property
    def output_dim(self) -> int:
        """The output dimensionality D."""
        ...

    def project(self, rep: np.ndarray) -> np.ndarray:
        """Project representation to common space.

        Args:
            rep: Native representation (any dimensionality)

        Returns:
            L2-normalized D-dimensional vector
        """
        ...


def l2_normalize(vec: np.ndarray) -> np.ndarray:
    """L2-normalize a vector, handling zero vectors gracefully."""
    norm = np.linalg.norm(vec)
    if norm < 1e-10:
        # Return zero vector if input is (nearly) zero
        return np.zeros_like(vec)
    return vec / norm


class LinearProjector(ABC):
    """Base class for linear projectors with random initialization.

    Uses a fixed random seed for determinism (INV-CV-6).
    """

    def __init__(self, input_dim: int, output_dim: int, seed: int = 42) -> None:
        """Initialize projector with random projection matrix.

        Args:
            input_dim: Native representation dimensionality
            output_dim: Target dimensionality D
            seed: Random seed for determinism
        """
        self._input_dim = input_dim
        self._output_dim = output_dim

        # Create deterministic random projection matrix
        rng = np.random.default_rng(seed)
        # Use orthogonal random projection for better preservation
        self._matrix = rng.standard_normal((output_dim, input_dim))
        # Normalize rows for stability
        row_norms = np.linalg.norm(self._matrix, axis=1, keepdims=True)
        self._matrix = self._matrix / (row_norms + 1e-10)

    @property
    def output_dim(self) -> int:
        return self._output_dim

    def project(self, rep: np.ndarray) -> np.ndarray:
        """Project and L2-normalize.

        Args:
            rep: Native representation

        Returns:
            L2-normalized D-dimensional vector
        """
        if rep.shape[0] != self._input_dim:
            raise ValueError(
                f"Expected input dim {self._input_dim}, got {rep.shape[0]}"
            )

        # Linear projection
        projected = self._matrix @ rep

        # L2 normalize
        return l2_normalize(projected)


class PhonemeProjector(LinearProjector):
    """Projector for phonemic/acoustic representations.

    Assumes phonemic representations are derived from acoustic features
    or phoneme embeddings.
    """

    def __init__(self, input_dim: int = 64, output_dim: int = 32) -> None:
        super().__init__(input_dim, output_dim, seed=42001)


class SemanticProjector(LinearProjector):
    """Projector for semantic embeddings.

    Handles typical embedding dimensions (768 for BERT-like, 384 for smaller).
    """

    def __init__(self, input_dim: int = 768, output_dim: int = 32) -> None:
        super().__init__(input_dim, output_dim, seed=42002)


class StructuralProjector(LinearProjector):
    """Projector for structural/ontology representations.

    Maps from ontology dimension space (typically 10-12D) to common space.
    """

    def __init__(self, input_dim: int = 12, output_dim: int = 32) -> None:
        super().__init__(input_dim, output_dim, seed=42003)


class TemporalProjector(LinearProjector):
    """Projector for temporal state difference vectors.

    Maps temporal delta representations to common space.
    """

    def __init__(self, input_dim: int = 32, output_dim: int = 32) -> None:
        super().__init__(input_dim, output_dim, seed=42004)


class IdentityProjector:
    """Identity projector for pre-normalized representations.

    Use when representations are already in the target dimensionality.
    Still applies L2 normalization.
    """

    def __init__(self, dim: int = 32) -> None:
        self._dim = dim

    @property
    def output_dim(self) -> int:
        return self._dim

    def project(self, rep: np.ndarray) -> np.ndarray:
        """Apply L2 normalization only."""
        if rep.shape[0] != self._dim:
            raise ValueError(f"Expected dim {self._dim}, got {rep.shape[0]}")
        return l2_normalize(rep)


class ProjectorRegistry:
    """Registry of projectors for each layer type.

    Caches projectors at startup for efficiency.
    """

    def __init__(self, output_dim: int = 32) -> None:
        """Initialize projector registry.

        Args:
            output_dim: Common projection dimensionality D
        """
        self._output_dim = output_dim
        self._projectors: dict[str, RepresentationProjector] = {}

    def register(self, layer_name: str, projector: RepresentationProjector) -> None:
        """Register a projector for a layer type."""
        if projector.output_dim != self._output_dim:
            raise ValueError(
                f"Projector output_dim {projector.output_dim} != registry dim {self._output_dim}"
            )
        self._projectors[layer_name] = projector

    def get(self, layer_name: str) -> Optional[RepresentationProjector]:
        """Get projector for a layer type."""
        return self._projectors.get(layer_name)

    def project(self, layer_name: str, rep: np.ndarray) -> np.ndarray:
        """Project a representation using the registered projector."""
        projector = self.get(layer_name)
        if projector is None:
            raise ValueError(f"No projector registered for layer '{layer_name}'")
        return projector.project(rep)


def create_default_registry(output_dim: int = 32) -> ProjectorRegistry:
    """Create a registry with default projectors for all layer types.

    Args:
        output_dim: Common projection dimensionality D

    Returns:
        Configured projector registry
    """
    registry = ProjectorRegistry(output_dim)

    # Register default projectors
    # Using identity projectors for simplicity - in production, these would
    # be calibrated to actual representation dimensions
    registry.register("phonemic", IdentityProjector(output_dim))
    registry.register("semantic", IdentityProjector(output_dim))
    registry.register("structural", IdentityProjector(output_dim))
    registry.register("temporal", IdentityProjector(output_dim))

    return registry
