"""Cross-layer coherence computation.

Computes pairwise similarity across representation layers and aggregates
into a coherence score with fracture profile.

Invariants:
- INV-CV-1: Order independence (coherence(A,B,C) == coherence(C,A,B))
- INV-CV-3: Identity (identical projections → coherence=1)
- INV-CV-5: Bounded output (all values ∈ [0,1])
"""

from typing import Optional
import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs
from symbolu.chitta_vritti.projector import l2_normalize


# Layer names for fracture keys
LAYER_NAMES = ["phonemic", "semantic", "structural", "temporal"]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two L2-normalized vectors.

    Args:
        a: First L2-normalized vector
        b: Second L2-normalized vector

    Returns:
        Cosine similarity in [-1, 1]
    """
    # For L2-normalized vectors, cosine similarity is just the dot product
    return float(np.dot(a, b))


def compute_pairwise_similarities(
    projections: dict[str, np.ndarray]
) -> dict[tuple[str, str], float]:
    """Compute pairwise cosine similarities between all projection pairs.

    Args:
        projections: Dict mapping layer names to projected vectors

    Returns:
        Dict mapping (layer_i, layer_j) pairs to similarity values
    """
    similarities: dict[tuple[str, str], float] = {}
    layer_names = list(projections.keys())

    for i, name_i in enumerate(layer_names):
        for name_j in layer_names[i + 1:]:
            sim = cosine_similarity(projections[name_i], projections[name_j])
            # Use sorted tuple for consistent key ordering (INV-CV-1)
            key = tuple(sorted([name_i, name_j]))
            similarities[key] = sim

    return similarities


def compute_fractures(
    similarities: dict[tuple[str, str], float]
) -> dict[tuple[str, str], float]:
    """Convert similarities to fractures (1 - similarity).

    Fractures are normalized to [0, 1] by clamping.

    Args:
        similarities: Pairwise similarity dict

    Returns:
        Pairwise fracture dict
    """
    fractures = {}
    for pair, sim in similarities.items():
        # Fracture = 1 - similarity, clamped to [0, 1]
        # Note: similarity can be negative (anti-correlation)
        fracture = max(0.0, min(1.0, (1.0 - sim) / 2.0))
        # Simpler: fracture in [0,1] where 0=identical, 1=opposite
        # For cosine sim in [-1,1]: fracture = (1 - sim) / 2
        fractures[pair] = fracture

    return fractures


def compute_aggregate_coherence(fractures: dict[tuple[str, str], float]) -> float:
    """Compute aggregate coherence from fracture profile.

    Coherence = 1 - mean(fractures)

    Args:
        fractures: Pairwise fracture dict

    Returns:
        Aggregate coherence in [0, 1]
    """
    if not fractures:
        return 1.0  # No pairs = vacuously coherent

    mean_fracture = sum(fractures.values()) / len(fractures)
    return max(0.0, min(1.0, 1.0 - mean_fracture))


def find_primary_fracture(
    fractures: dict[tuple[str, str], float]
) -> Optional[tuple[str, str]]:
    """Find the layer pair with the largest fracture.

    Args:
        fractures: Pairwise fracture dict

    Returns:
        Tuple of layer names with highest fracture, or None if empty
    """
    if not fractures:
        return None

    return max(fractures.keys(), key=lambda k: fractures[k])


def project_inputs(
    inputs: ChittaVrittiInputs,
    projection_dim: int = 32
) -> dict[str, np.ndarray]:
    """Project available input representations to common space.

    Args:
        inputs: Raw input representations
        projection_dim: Target dimensionality

    Returns:
        Dict of layer name → projected vector (only for present layers)
    """
    projections = {}

    # For each present layer, project to common space
    # In production, these would use the ProjectorRegistry
    # For now, we use simple padding/truncation + L2 normalization

    if inputs.phonemic_rep is not None:
        projections["phonemic"] = _project_to_dim(inputs.phonemic_rep, projection_dim)

    if inputs.semantic_rep is not None:
        projections["semantic"] = _project_to_dim(inputs.semantic_rep, projection_dim)

    if inputs.structural_rep is not None:
        projections["structural"] = _project_to_dim(inputs.structural_rep, projection_dim)

    if inputs.temporal_rep is not None:
        projections["temporal"] = _project_to_dim(inputs.temporal_rep, projection_dim)

    return projections


def _project_to_dim(vec: np.ndarray, target_dim: int) -> np.ndarray:
    """Project vector to target dimension with L2 normalization.

    Simple projection: truncate or pad, then normalize.
    In production, use trained projection matrices.

    Args:
        vec: Input vector
        target_dim: Target dimensionality

    Returns:
        L2-normalized vector of target_dim
    """
    current_dim = vec.shape[0]

    if current_dim == target_dim:
        result = vec.copy()
    elif current_dim > target_dim:
        # Truncate
        result = vec[:target_dim].copy()
    else:
        # Pad with zeros
        result = np.zeros(target_dim)
        result[:current_dim] = vec

    return l2_normalize(result)


def quick_opposition_check(inputs: ChittaVrittiInputs) -> float:
    """Lightweight check for semantic inversion without full fracture analysis.

    Used for fast-path safety gate to detect coherent inversions.

    Args:
        inputs: Input representations

    Returns:
        Estimated viparyaya signal [0, 1]
    """
    if inputs.semantic_rep is None or inputs.structural_rep is None:
        return 0.0  # Can't detect opposition without both layers

    # Project to common space
    sem_proj = _project_to_dim(inputs.semantic_rep, 32)
    struct_proj = _project_to_dim(inputs.structural_rep, 32)

    # Quick cosine similarity
    sim = cosine_similarity(sem_proj, struct_proj)

    # If similarity is negative (anti-correlation), return magnitude
    if sim < -0.3:  # Early warning threshold
        return abs(sim)

    return 0.0


class CoherenceComputer:
    """Stateless coherence computation engine.

    Computes cross-layer coherence and fracture profiles from
    projected representations.
    """

    def __init__(self, projection_dim: int = 32) -> None:
        """Initialize coherence computer.

        Args:
            projection_dim: Common projection dimensionality
        """
        self._projection_dim = projection_dim

    def compute(
        self, inputs: ChittaVrittiInputs
    ) -> tuple[float, dict[tuple[str, str], float], Optional[tuple[str, str]]]:
        """Compute coherence, fractures, and primary fracture.

        Args:
            inputs: Input representations

        Returns:
            Tuple of (coherence, fractures, primary_fracture)
        """
        # Project to common space
        projections = project_inputs(inputs, self._projection_dim)

        if len(projections) < 2:
            # Need at least 2 layers to compute coherence
            return 1.0, {}, None

        # Compute pairwise similarities
        similarities = compute_pairwise_similarities(projections)

        # Convert to fractures
        fractures = compute_fractures(similarities)

        # Aggregate coherence
        coherence = compute_aggregate_coherence(fractures)

        # Find primary fracture
        primary_fracture = find_primary_fracture(fractures)

        return coherence, fractures, primary_fracture
