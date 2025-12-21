"""
Name Resonance System - Ontological Bridge
==========================================

Bridge between 10D Ontological Layers and 12D Experiential Dimensions.

This unifies:
- 10D: Consciousness depth (THINKING, FORMING, ACTING... ABSOLVING)
- 12D: Structural quality (force, flow, balance, connectivity...)

The bridge allows phonemes to contribute to BOTH projections,
enriching the structural profile with ontological resonance.
"""

from typing import Tuple, Dict

from symbolu.resonance.analyzer import analyze_word
from symbolu.resonance.types import WordVector, LAYER_NAMES
from symbolu.name_resonance.types import DIMENSION_NAMES


# =============================================================================
# 10D → 12D Mapping Matrix
# =============================================================================

# How each ontological layer contributes to experiential dimensions
# Values represent contribution weight (can be negative for inverse relationships)

ONTOLOGICAL_TO_EXPERIENTIAL: Dict[str, Dict[str, float]] = {
    # O1_THINKING → contemplation, cognition
    "O1_THINKING": {
        "force": -0.2,        # Thinking is not forceful
        "stability": 0.3,     # Thinking requires stability
        "duration": 0.4,      # Thinking is sustained
        "initiation": -0.1,   # Not explosive
        "flow": 0.2,          # Moderate flow
        "termination": -0.2,  # Open-ended
        "complexity": 0.5,    # High complexity
        "density": 0.2,       # Moderate density
        "balance": 0.3,       # Balanced
        "openness": 0.3,      # Receptive
        "depth": 0.5,         # Deep
        "connectivity": 0.2,  # Moderate connection
    },

    # O2_FORMING → structure, creation
    "O2_FORMING": {
        "force": 0.3,
        "stability": 0.4,
        "duration": 0.3,
        "initiation": 0.3,
        "flow": 0.4,
        "termination": 0.2,
        "complexity": 0.5,
        "density": 0.4,
        "balance": 0.5,
        "openness": 0.2,
        "depth": 0.3,
        "connectivity": 0.3,
    },

    # O3_ACTING → action, force
    "O3_ACTING": {
        "force": 0.7,         # High force
        "stability": 0.2,
        "duration": 0.1,
        "initiation": 0.6,    # Explosive start
        "flow": 0.1,
        "termination": 0.5,   # Decisive end
        "complexity": 0.2,
        "density": 0.4,
        "balance": 0.2,
        "openness": 0.1,
        "depth": 0.2,
        "connectivity": 0.1,
    },

    # O4_TAGGING → classification, labeling
    "O4_TAGGING": {
        "force": 0.2,
        "stability": 0.5,
        "duration": 0.2,
        "initiation": 0.3,
        "flow": 0.2,
        "termination": 0.4,
        "complexity": 0.4,
        "density": 0.3,
        "balance": 0.4,
        "openness": 0.2,
        "depth": 0.2,
        "connectivity": 0.2,
    },

    # O5_DIRECTING → guidance, control
    "O5_DIRECTING": {
        "force": 0.5,
        "stability": 0.4,
        "duration": 0.3,
        "initiation": 0.5,
        "flow": 0.3,
        "termination": 0.4,
        "complexity": 0.3,
        "density": 0.3,
        "balance": 0.4,
        "openness": 0.2,
        "depth": 0.3,
        "connectivity": 0.3,
    },

    # O6_REASONING → logic, analysis
    "O6_REASONING": {
        "force": 0.2,
        "stability": 0.5,
        "duration": 0.4,
        "initiation": 0.2,
        "flow": 0.3,
        "termination": 0.3,
        "complexity": 0.6,
        "density": 0.4,
        "balance": 0.5,
        "openness": 0.3,
        "depth": 0.5,
        "connectivity": 0.2,
    },

    # O7_PURPOSING → intent, goals
    "O7_PURPOSING": {
        "force": 0.4,
        "stability": 0.4,
        "duration": 0.5,
        "initiation": 0.4,
        "flow": 0.4,
        "termination": 0.3,
        "complexity": 0.4,
        "density": 0.3,
        "balance": 0.4,
        "openness": 0.3,
        "depth": 0.5,
        "connectivity": 0.4,
    },

    # O8_META_OBSERVING → awareness, perception
    "O8_META_OBSERVING": {
        "force": 0.0,
        "stability": 0.5,
        "duration": 0.5,
        "initiation": 0.1,
        "flow": 0.4,
        "termination": 0.1,
        "complexity": 0.4,
        "density": 0.2,
        "balance": 0.5,
        "openness": 0.6,
        "depth": 0.6,
        "connectivity": 0.3,
    },

    # O9_UNIFYING → connection, harmony
    "O9_UNIFYING": {
        "force": 0.1,
        "stability": 0.4,
        "duration": 0.5,
        "initiation": 0.2,
        "flow": 0.6,          # High flow
        "termination": 0.1,
        "complexity": 0.3,
        "density": 0.2,
        "balance": 0.6,       # High balance
        "openness": 0.5,
        "depth": 0.4,
        "connectivity": 0.7,  # High connectivity
    },

    # O10_ABSOLVING → release, transcendence
    "O10_ABSOLVING": {
        "force": 0.0,
        "stability": 0.3,
        "duration": 0.6,
        "initiation": 0.0,
        "flow": 0.5,
        "termination": 0.0,   # No hard ending
        "complexity": 0.2,
        "density": 0.1,
        "balance": 0.5,
        "openness": 0.7,      # Very open
        "depth": 0.6,
        "connectivity": 0.5,
    },
}


# =============================================================================
# Bridge Functions
# =============================================================================

def get_ontological_vector(name: str) -> Tuple[Tuple[str, float], ...]:
    """
    Get the 10D ontological vector for a name using existing resonance engine.

    Args:
        name: The name to analyze

    Returns:
        Tuple of (layer_name, value) pairs
    """
    # Use existing resonance analyzer
    word_vec = analyze_word(name.lower())

    # Return as named tuples
    return tuple(
        (LAYER_NAMES[i], word_vec.vector[i])
        for i in range(10)
    )


def project_ontological_to_experiential(
    ontological_vector: Tuple[Tuple[str, float], ...]
) -> Dict[str, float]:
    """
    Project 10D ontological vector into 12D experiential space.

    Args:
        ontological_vector: 10D ontological layer values

    Returns:
        Dict of 12D experiential dimension contributions
    """
    experiential = {dim: 0.0 for dim in DIMENSION_NAMES}

    for layer_name, layer_value in ontological_vector:
        if layer_name in ONTOLOGICAL_TO_EXPERIENTIAL:
            mapping = ONTOLOGICAL_TO_EXPERIENTIAL[layer_name]
            for dim, weight in mapping.items():
                experiential[dim] += layer_value * weight

    return experiential


def compute_bridged_profile(
    phonetic_profile: Dict[str, float],
    ontological_contribution: Dict[str, float],
    phonetic_weight: float = 0.6,
    ontological_weight: float = 0.4,
) -> Dict[str, float]:
    """
    Combine phonetic and ontological projections into unified profile.

    Args:
        phonetic_profile: 12D from phonetic analysis (current system)
        ontological_contribution: 12D from ontological bridge
        phonetic_weight: Weight for phonetic component (default 0.6)
        ontological_weight: Weight for ontological component (default 0.4)

    Returns:
        Combined 12D profile
    """
    combined = {}

    for dim in DIMENSION_NAMES:
        phonetic_val = phonetic_profile.get(dim, 0.5)
        onto_val = ontological_contribution.get(dim, 0.0)

        # Weighted combination
        combined[dim] = (
            phonetic_val * phonetic_weight +
            onto_val * ontological_weight
        )

        # Clamp to [0, 1]
        combined[dim] = max(0.0, min(1.0, combined[dim]))

    return combined


# =============================================================================
# Enhanced Analysis Function
# =============================================================================

def analyze_name_bridged(name: str) -> dict:
    """
    Analyze a name using both phonetic and ontological projections.

    This combines:
    - 12D phonetic structural analysis (existing)
    - 10D ontological analysis → bridged to 12D

    Args:
        name: The name to analyze

    Returns:
        Dict with phonetic, ontological, and bridged profiles
    """
    from symbolu.name_resonance.extractor import normalize_input, extract_signals
    from symbolu.name_resonance.projector import project_to_structural_profile

    # Phonetic path (existing)
    normalized = normalize_input(name)
    signals = extract_signals(normalized)
    phonetic_profile = project_to_structural_profile(signals)

    # Ontological path (new bridge)
    ontological_vector = get_ontological_vector(name)
    ontological_contribution = project_ontological_to_experiential(ontological_vector)

    # Combine
    phonetic_dict = phonetic_profile.to_dict()
    bridged = compute_bridged_profile(phonetic_dict, ontological_contribution)

    return {
        "name": name,
        "phonetic_profile": phonetic_dict,
        "ontological_vector": dict(ontological_vector),
        "ontological_contribution": ontological_contribution,
        "bridged_profile": bridged,
        "dominant_ontological_layer": max(ontological_vector, key=lambda x: x[1]),
    }
