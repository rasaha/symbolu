"""
Vritti Mapping - Syllable to Vritti Distribution
================================================

PHONEMIC/SYLLABLE-LEVEL VRITTI (complementary to canonical runtime vritti)
=========================================================================
This module computes vritti distributions at the phonemic level:
syllable → consonant → kosha → vritti tendency.

This is NOT the canonical runtime vritti authority for cross-layer coherence.
The canonical runtime vritti authority is: symbolu/chitta_vritti/
(ChittaVrittiEngine computes vritti from cross-layer representational coherence.)

This module is complementary — it provides syllable-level vritti tendencies
that feed into SMI computation. Both sources are valid at their respective
abstraction levels.

Original description:
Maps syllables to their corresponding vṛtti probability distributions
based on the consonant → kosha → vritti tendency chain.

The 5 vṛttis:
1. Pramāṇa - Valid cognition, clear knowing
2. Viparyaya - Misperception, emotional distortion
3. Vikalpa - Conceptual imagination, restless branching
4. Smṛti - Memory, recall, continuity
5. Nidrā - Dormancy, sleep, absence

Each kosha layer has a dominant vritti tendency:
- ANNAMAYA (physical) → Nidrā
- PRANAMAYA (energy) → Vikalpa
- MANOMAYA (mind) → Viparyaya
- VIJNANAMAYA (wisdom) → Pramāṇa
- ANANDAMAYA (bliss) → Pramāṇa (pure)

Usage:
    from symbolu.core.smi.vritti_mapping import VrittiMapper

    mapper = VrittiMapper()
    dist = mapper.map_syllable_to_vritti("ka")  # [0.125, 0.125, 0.5, 0.125, 0.125]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
from enum import Enum, unique

from symbolu.core.smi.smi_engine import (
    extract_consonant,
    get_kosha_level,
    compute_vritti_distribution,
)


# =============================================================================
# VRITTI ENUM
# =============================================================================


@unique
class VrittiType(str, Enum):
    """The five vṛtti types from Yoga Sutras."""
    PRAMANA = "pramana"      # Valid cognition
    VIPARYAYA = "viparyaya"  # Misperception
    VIKALPA = "vikalpa"      # Conceptual imagination
    SMRTI = "smrti"          # Memory
    NIDRA = "nidra"          # Dormancy


VRITTI_ORDER = [
    VrittiType.PRAMANA,
    VrittiType.VIPARYAYA,
    VrittiType.VIKALPA,
    VrittiType.SMRTI,
    VrittiType.NIDRA,
]

VRITTI_DESCRIPTIONS = {
    VrittiType.PRAMANA: "Valid cognition through direct perception, inference, or testimony",
    VrittiType.VIPARYAYA: "Misperception or wrong knowledge, distorted cognition",
    VrittiType.VIKALPA: "Conceptual imagination, verbal knowledge without corresponding reality",
    VrittiType.SMRTI: "Memory, recall of past experiences",
    VrittiType.NIDRA: "Sleep, dormancy, absence of mental content",
}


# =============================================================================
# VRITTI DISTRIBUTION DATACLASS
# =============================================================================


@dataclass
class VrittiDistributionResult:
    """Result of vritti distribution computation.

    Attributes:
        distribution: 5-element list [pramana, viparyaya, vikalpa, smrti, nidra]
        dominant: The dominant vritti type
        dominant_weight: Weight of the dominant vritti
        source_kosha: The kosha level that determined this distribution
        syllable: Original syllable analyzed
    """
    distribution: List[float]
    dominant: VrittiType
    dominant_weight: float
    source_kosha: int
    syllable: str

    def as_dict(self) -> Dict[VrittiType, float]:
        """Return distribution as a dictionary."""
        return dict(zip(VRITTI_ORDER, self.distribution))

    def get(self, vritti: VrittiType) -> float:
        """Get weight for a specific vritti."""
        idx = VRITTI_ORDER.index(vritti)
        return self.distribution[idx]


# =============================================================================
# VRITTI MAPPER
# =============================================================================


class VrittiMapper:
    """Maps syllables to Vṛtti probability distributions.

    The mapping follows the chain:
    syllable → consonant → kosha → vritti tendency

    Each kosha has a dominant vritti:
    - ANNAMAYA (1) → Nidrā (dormancy)
    - PRANAMAYA (2) → Vikalpa (restless imagination)
    - MANOMAYA (3) → Viparyaya (emotional distortion)
    - VIJNANAMAYA (4) → Pramāṇa (valid cognition)
    - ANANDAMAYA (5) → Pramāṇa (pure awareness)

    Usage:
        mapper = VrittiMapper()
        dist = mapper.map_syllable_to_vritti("ka")
        # Returns: [0.125, 0.125, 0.5, 0.125, 0.125] (vikalpa dominant)
    """

    def __init__(self) -> None:
        """Initialize the vritti mapper."""
        self._cache: Dict[str, VrittiDistributionResult] = {}

    def map_syllable_to_vritti(self, syllable: str) -> List[float]:
        """Map syllable to 5-dimensional Vṛtti distribution.

        Args:
            syllable: The syllable to map

        Returns:
            5-element list: [pramana, viparyaya, vikalpa, smrti, nidra]
            Values sum to 1.0
        """
        result = self._compute_distribution(syllable)
        return result.distribution

    def map_syllable_detailed(self, syllable: str) -> VrittiDistributionResult:
        """Map syllable with full details.

        Args:
            syllable: The syllable to map

        Returns:
            VrittiDistributionResult with distribution and metadata
        """
        return self._compute_distribution(syllable)

    def aggregate_vritti(self, distributions: List[List[float]]) -> List[float]:
        """Aggregate multiple Vṛtti distributions into one.

        Uses weighted averaging with equal weights.

        Args:
            distributions: List of 5-element vritti distributions

        Returns:
            Aggregated 5-element distribution
        """
        if not distributions:
            return [0.2, 0.2, 0.2, 0.2, 0.2]

        # Sum each vritti dimension
        aggregated = [0.0] * 5
        for dist in distributions:
            for i, val in enumerate(dist):
                aggregated[i] += val

        # Normalize to sum to 1
        total = sum(aggregated)
        if total > 0:
            aggregated = [v / total for v in aggregated]

        return aggregated

    def get_dominant_vritti(self, distribution: List[float]) -> Tuple[VrittiType, float]:
        """Get the dominant vritti from a distribution.

        Args:
            distribution: 5-element vritti distribution

        Returns:
            Tuple of (VrittiType, weight)
        """
        if len(distribution) != 5:
            return (VrittiType.PRAMANA, 0.2)

        max_idx = distribution.index(max(distribution))
        return (VRITTI_ORDER[max_idx], distribution[max_idx])

    def _compute_distribution(self, syllable: str) -> VrittiDistributionResult:
        """Compute vritti distribution for syllable."""
        if syllable in self._cache:
            return self._cache[syllable]

        # Extract consonant and get kosha level
        consonant = extract_consonant(syllable)
        kosha_level = get_kosha_level(consonant)

        # Get vritti distribution from kosha
        distribution = compute_vritti_distribution(kosha_level)

        # Find dominant vritti
        dominant, dominant_weight = self.get_dominant_vritti(distribution)

        result = VrittiDistributionResult(
            distribution=distribution,
            dominant=dominant,
            dominant_weight=dominant_weight,
            source_kosha=kosha_level,
            syllable=syllable,
        )

        self._cache[syllable] = result
        return result

    def clear_cache(self) -> None:
        """Clear the computation cache."""
        self._cache.clear()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def map_syllable_to_vritti(syllable: str) -> List[float]:
    """Convenience function to map syllable to vritti distribution.

    Args:
        syllable: The syllable to map

    Returns:
        5-element vritti distribution
    """
    mapper = VrittiMapper()
    return mapper.map_syllable_to_vritti(syllable)


def aggregate_vritti_distributions(distributions: List[List[float]]) -> List[float]:
    """Convenience function to aggregate vritti distributions.

    Args:
        distributions: List of vritti distributions

    Returns:
        Aggregated distribution
    """
    mapper = VrittiMapper()
    return mapper.aggregate_vritti(distributions)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VrittiMapper",
    "VrittiDistributionResult",
    "VrittiType",
    "VRITTI_ORDER",
    "VRITTI_DESCRIPTIONS",
    "map_syllable_to_vritti",
    "aggregate_vritti_distributions",
]
