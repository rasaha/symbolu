"""
Aspect Mapping - Word to Ontology Aspect Distribution
=====================================================

Maps words to 10-dimensional aspect distributions based on the ontological
layer system and applies vritti-aspect coupling.

The 10 ontological aspects (manifestation breadth):
1. Execution - Karma, action, physical manifestation
2. Identity - Self-tagging, labels, roles
3. Form - Body, shape, physical appearance
4. Cognition - Mind, thinking, mental processes
5. Agency - Ego, control, willpower
6. Reasoning - Intellect, analysis, discrimination
7. Purpose - Soul-direction, meaning, intention
8. Observation - Witness, awareness, observation
9. Core - Atman, essence, true self
10. Universal - Brahman, cosmic, universal principles

The coupling matrix R[v,a] bridges vritti (5-dim) to aspect (10-dim):
    aspect_dist = R @ vritti_dist

Usage:
    from agentic.core.smi.aspect_mapping import AspectMapper

    mapper = AspectMapper()
    aspects = mapper.map_word_to_aspect("think")  # [0.0, 0.0, 0.0, 0.5, ...]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from enum import Enum, unique

from agentic.core.smi.smi_engine import get_ontology_level
from agentic.core.constants import ONTOLOGICAL_LAYERS


# =============================================================================
# ASPECT ENUM
# =============================================================================


@unique
class AspectType(str, Enum):
    """The 10 ontological aspects."""
    EXECUTION = "execution"      # Level 1 - Karma, action
    IDENTITY = "identity"        # Level 2 - Labels, roles
    FORM = "form"                # Level 3 - Body, shape
    COGNITION = "cognition"      # Level 4 - Mind, thinking
    AGENCY = "agency"            # Level 5 - Ego, control
    REASONING = "reasoning"      # Level 6 - Intellect
    PURPOSE = "purpose"          # Level 7 - Meaning, intention
    OBSERVATION = "observation"  # Level 8 - Witness, awareness
    CORE = "core"                # Level 9 - Essence, atman
    UNIVERSAL = "universal"      # Level 10 - Cosmic, brahman


ASPECT_ORDER = [
    AspectType.EXECUTION,
    AspectType.IDENTITY,
    AspectType.FORM,
    AspectType.COGNITION,
    AspectType.AGENCY,
    AspectType.REASONING,
    AspectType.PURPOSE,
    AspectType.OBSERVATION,
    AspectType.CORE,
    AspectType.UNIVERSAL,
]


# =============================================================================
# VRITTI-ASPECT COUPLING MATRIX
# =============================================================================

# R[v,a] coupling matrix: maps 5D vritti to 10D aspect
# Rows: pramana, viparyaya, vikalpa, smrti, nidra
# Cols: execution, identity, form, cognition, agency, reasoning, purpose, observation, core, universal
#
# Each vritti has affinity for certain aspects:
# - Pramana (valid cognition) → Reasoning, Observation, Core, Universal
# - Viparyaya (misperception) → Form, Cognition, Agency (distorted)
# - Vikalpa (imagination) → Identity, Cognition, Purpose (creative)
# - Smrti (memory) → Identity, Form, Execution (habitual)
# - Nidra (dormancy) → Execution, Form (inert)

VRITTI_ASPECT_COUPLING_MATRIX: List[List[float]] = [
    # Pramana → Higher aspects (reasoning, observation, core, universal)
    [0.02, 0.03, 0.03, 0.10, 0.05, 0.20, 0.12, 0.20, 0.15, 0.10],

    # Viparyaya → Middle aspects with distortion (form, cognition, agency)
    [0.05, 0.08, 0.20, 0.25, 0.20, 0.10, 0.05, 0.03, 0.02, 0.02],

    # Vikalpa → Creative aspects (identity, cognition, purpose)
    [0.05, 0.15, 0.08, 0.20, 0.12, 0.10, 0.18, 0.07, 0.03, 0.02],

    # Smrti → Habitual aspects (identity, form, execution)
    [0.15, 0.20, 0.20, 0.15, 0.10, 0.08, 0.05, 0.04, 0.02, 0.01],

    # Nidra → Inert aspects (execution, form)
    [0.30, 0.10, 0.25, 0.10, 0.08, 0.05, 0.05, 0.03, 0.02, 0.02],
]


# =============================================================================
# ASPECT DISTRIBUTION DATACLASS
# =============================================================================


@dataclass
class AspectDistributionResult:
    """Result of aspect distribution computation.

    Attributes:
        distribution: 10-element list matching ASPECT_ORDER
        dominant: The dominant aspect type
        dominant_weight: Weight of the dominant aspect
        source_ontology: The ontology level that influenced this
        word: Original word analyzed
    """
    distribution: List[float]
    dominant: AspectType
    dominant_weight: float
    source_ontology: int
    word: str

    def as_dict(self) -> Dict[AspectType, float]:
        """Return distribution as a dictionary."""
        return dict(zip(ASPECT_ORDER, self.distribution))

    def get(self, aspect: AspectType) -> float:
        """Get weight for a specific aspect."""
        idx = ASPECT_ORDER.index(aspect)
        return self.distribution[idx]


# =============================================================================
# ASPECT MAPPER
# =============================================================================


class AspectMapper:
    """Maps words to ontology aspect distributions.

    Provides:
    1. Direct word → aspect mapping based on semantic keywords
    2. Vritti → aspect transformation via coupling matrix

    The coupling matrix R[v,a] allows bridging from the 5D vritti space
    (consciousness modes) to the 10D aspect space (manifestation layers).

    Usage:
        mapper = AspectMapper()

        # Direct word mapping
        aspects = mapper.map_word_to_aspect("think")

        # Vritti-to-aspect coupling
        vritti = [0.5, 0.1, 0.2, 0.1, 0.1]  # pramana-dominant
        aspects = mapper.apply_coupling_matrix(vritti)
    """

    def __init__(self) -> None:
        """Initialize the aspect mapper."""
        self._cache: Dict[str, AspectDistributionResult] = {}

    def map_word_to_aspect(self, word: str) -> List[float]:
        """Map word to 10-dimensional aspect distribution.

        Args:
            word: The word to map

        Returns:
            10-element list: weights for each aspect in ASPECT_ORDER
        """
        result = self._compute_distribution(word)
        return result.distribution

    def map_word_detailed(self, word: str) -> AspectDistributionResult:
        """Map word with full details.

        Args:
            word: The word to map

        Returns:
            AspectDistributionResult with distribution and metadata
        """
        return self._compute_distribution(word)

    def apply_coupling_matrix(
        self,
        vritti_dist: List[float],
        coupling_matrix: Optional[List[List[float]]] = None,
    ) -> List[float]:
        """Apply Vṛtti-Aspect coupling matrix.

        Transforms a 5D vritti distribution to a 10D aspect distribution
        using the coupling matrix R:

            aspect = R^T @ vritti

        Args:
            vritti_dist: 5-element vritti distribution [pramana, viparyaya, vikalpa, smrti, nidra]
            coupling_matrix: Optional custom 5x10 matrix (uses default if None)

        Returns:
            10-element aspect distribution
        """
        if len(vritti_dist) != 5:
            raise ValueError("vritti_dist must have 5 elements")

        matrix = coupling_matrix or VRITTI_ASPECT_COUPLING_MATRIX

        # Matrix multiplication: aspect[j] = sum_i(vritti[i] * R[i,j])
        aspect_dist = [0.0] * 10
        for j in range(10):
            for i in range(5):
                aspect_dist[j] += vritti_dist[i] * matrix[i][j]

        # Normalize to sum to 1
        total = sum(aspect_dist)
        if total > 0:
            aspect_dist = [a / total for a in aspect_dist]

        return aspect_dist

    def get_dominant_aspect(self, distribution: List[float]) -> tuple:
        """Get the dominant aspect from a distribution.

        Args:
            distribution: 10-element aspect distribution

        Returns:
            Tuple of (AspectType, weight)
        """
        if len(distribution) != 10:
            return (AspectType.AGENCY, 0.1)

        max_idx = distribution.index(max(distribution))
        return (ASPECT_ORDER[max_idx], distribution[max_idx])

    def aggregate_aspects(self, distributions: List[List[float]]) -> List[float]:
        """Aggregate multiple aspect distributions.

        Args:
            distributions: List of 10-element aspect distributions

        Returns:
            Aggregated 10-element distribution
        """
        if not distributions:
            return [0.1] * 10

        aggregated = [0.0] * 10
        for dist in distributions:
            for i, val in enumerate(dist):
                aggregated[i] += val

        total = sum(aggregated)
        if total > 0:
            aggregated = [a / total for a in aggregated]

        return aggregated

    def _compute_distribution(self, word: str) -> AspectDistributionResult:
        """Compute aspect distribution for a word."""
        if word in self._cache:
            return self._cache[word]

        # Get primary ontology level from semantic analysis
        ontology_level = get_ontology_level(word)

        # Create distribution peaked at that level
        distribution = self._create_peaked_distribution(ontology_level)

        # Find dominant
        dominant, dominant_weight = self.get_dominant_aspect(distribution)

        result = AspectDistributionResult(
            distribution=distribution,
            dominant=dominant,
            dominant_weight=dominant_weight,
            source_ontology=ontology_level,
            word=word,
        )

        self._cache[word] = result
        return result

    def _create_peaked_distribution(self, peak_level: int) -> List[float]:
        """Create a distribution peaked at the given level.

        Uses a Gaussian-like falloff from the peak.
        """
        distribution = []
        for level in range(1, 11):
            distance = abs(level - peak_level)
            # Gaussian-like weight: peak at 0 distance, falls off
            weight = 1.0 / (1.0 + distance * 0.5)
            distribution.append(weight)

        # Normalize
        total = sum(distribution)
        return [w / total for w in distribution]

    def clear_cache(self) -> None:
        """Clear the computation cache."""
        self._cache.clear()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def map_word_to_aspect(word: str) -> List[float]:
    """Convenience function to map word to aspect distribution.

    Args:
        word: The word to map

    Returns:
        10-element aspect distribution
    """
    mapper = AspectMapper()
    return mapper.map_word_to_aspect(word)


def apply_vritti_aspect_coupling(vritti_dist: List[float]) -> List[float]:
    """Convenience function to apply vritti-aspect coupling.

    Args:
        vritti_dist: 5-element vritti distribution

    Returns:
        10-element aspect distribution
    """
    mapper = AspectMapper()
    return mapper.apply_coupling_matrix(vritti_dist)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AspectMapper",
    "AspectDistributionResult",
    "AspectType",
    "ASPECT_ORDER",
    "VRITTI_ASPECT_COUPLING_MATRIX",
    "map_word_to_aspect",
    "apply_vritti_aspect_coupling",
]
