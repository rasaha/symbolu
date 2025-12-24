"""
Phase-14: Character Deriver
===========================

Derives cross-layer "character" propensities from phonemic structure.

Core Hypothesis:
    A word's phonemic structure creates "character" - propensity weights
    for how strongly that word resonates with each of the 10 ontological layers.

    Example: The word "catalyze" maps primarily to O3_ACTING, but its
    phonemic character gives it secondary resonance with:
    - O2_FORMING (creation aspect)
    - O6_REASONING (causal implication)

Architecture:
    1. Take phoneme sequence from PhonemeAnalysis
    2. Map phoneme categories to layer affinities
    3. Aggregate into cross-layer character profile
    4. Return normalized propensity scores

This is EXPERIMENTAL. The phoneme→layer mappings are hypotheses to be
validated through accumulation. If patterns don't stabilize, these
mappings will need revision.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Tuple

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "phase13_sandbox"))

from k1_schema import OntologicalLayer
from phoneme_extractor import PhonemeAnalysis, PhonemeCategory, get_phoneme_category


# =============================================================================
# Phoneme Category → Layer Affinity Hypothesis
# =============================================================================

"""
Hypothesized mappings from phoneme categories to layer affinities.

These are INITIAL GUESSES based on intuition:
- Plosives (sudden, forceful) → ACTING, DIRECTING
- Fricatives (continuous, controlled) → DIRECTING, REASONING
- Nasals (resonant, connecting) → UNIFYING, THINKING
- Liquids (flowing, smooth) → FORMING, UNIFYING
- Vowels (open, sustained) → THINKING, ABSOLVING

Validation: These mappings should stabilize through RAG exposure.
If they don't, we'll know the hypothesis needs revision.
"""

# Layer affinity weights by phoneme category
# Format: {PhonemeCategory: {OntologicalLayer: affinity_weight}}
# Weights are 0.0 to 1.0, where 1.0 = strong affinity

CATEGORY_LAYER_AFFINITY: Dict[PhonemeCategory, Dict[OntologicalLayer, float]] = {
    PhonemeCategory.PLOSIVE: {
        OntologicalLayer.O1_THINKING: 0.2,
        OntologicalLayer.O2_FORMING: 0.4,
        OntologicalLayer.O3_ACTING: 0.9,       # High - sudden action
        OntologicalLayer.O4_TAGGING: 0.3,
        OntologicalLayer.O5_DIRECTING: 0.7,    # Medium-high - commanding
        OntologicalLayer.O6_REASONING: 0.3,
        OntologicalLayer.O7_PURPOSING: 0.4,
        OntologicalLayer.O8_META_OBSERVING: 0.2,
        OntologicalLayer.O9_UNIFYING: 0.2,
        OntologicalLayer.O10_ABSOLVING: 0.1,
    },
    PhonemeCategory.FRICATIVE: {
        OntologicalLayer.O1_THINKING: 0.4,
        OntologicalLayer.O2_FORMING: 0.5,
        OntologicalLayer.O3_ACTING: 0.5,
        OntologicalLayer.O4_TAGGING: 0.4,
        OntologicalLayer.O5_DIRECTING: 0.8,    # High - sustained control
        OntologicalLayer.O6_REASONING: 0.7,    # Medium-high - process
        OntologicalLayer.O7_PURPOSING: 0.5,
        OntologicalLayer.O8_META_OBSERVING: 0.5,
        OntologicalLayer.O9_UNIFYING: 0.3,
        OntologicalLayer.O10_ABSOLVING: 0.3,
    },
    PhonemeCategory.AFFRICATE: {
        OntologicalLayer.O1_THINKING: 0.3,
        OntologicalLayer.O2_FORMING: 0.6,      # Medium-high - complex creation
        OntologicalLayer.O3_ACTING: 0.8,       # High - combined action
        OntologicalLayer.O4_TAGGING: 0.3,
        OntologicalLayer.O5_DIRECTING: 0.7,
        OntologicalLayer.O6_REASONING: 0.5,
        OntologicalLayer.O7_PURPOSING: 0.5,
        OntologicalLayer.O8_META_OBSERVING: 0.3,
        OntologicalLayer.O9_UNIFYING: 0.4,
        OntologicalLayer.O10_ABSOLVING: 0.2,
    },
    PhonemeCategory.NASAL: {
        OntologicalLayer.O1_THINKING: 0.7,     # High - resonant reflection
        OntologicalLayer.O2_FORMING: 0.5,
        OntologicalLayer.O3_ACTING: 0.3,
        OntologicalLayer.O4_TAGGING: 0.4,
        OntologicalLayer.O5_DIRECTING: 0.3,
        OntologicalLayer.O6_REASONING: 0.5,
        OntologicalLayer.O7_PURPOSING: 0.5,
        OntologicalLayer.O8_META_OBSERVING: 0.6,
        OntologicalLayer.O9_UNIFYING: 0.8,     # High - connecting resonance
        OntologicalLayer.O10_ABSOLVING: 0.5,
    },
    PhonemeCategory.LIQUID: {
        OntologicalLayer.O1_THINKING: 0.5,
        OntologicalLayer.O2_FORMING: 0.7,      # High - flowing creation
        OntologicalLayer.O3_ACTING: 0.4,
        OntologicalLayer.O4_TAGGING: 0.3,
        OntologicalLayer.O5_DIRECTING: 0.4,
        OntologicalLayer.O6_REASONING: 0.5,
        OntologicalLayer.O7_PURPOSING: 0.5,
        OntologicalLayer.O8_META_OBSERVING: 0.5,
        OntologicalLayer.O9_UNIFYING: 0.7,     # High - bridging
        OntologicalLayer.O10_ABSOLVING: 0.6,
    },
    PhonemeCategory.GLIDE: {
        OntologicalLayer.O1_THINKING: 0.5,
        OntologicalLayer.O2_FORMING: 0.6,
        OntologicalLayer.O3_ACTING: 0.4,
        OntologicalLayer.O4_TAGGING: 0.3,
        OntologicalLayer.O5_DIRECTING: 0.4,
        OntologicalLayer.O6_REASONING: 0.4,
        OntologicalLayer.O7_PURPOSING: 0.5,
        OntologicalLayer.O8_META_OBSERVING: 0.5,
        OntologicalLayer.O9_UNIFYING: 0.6,
        OntologicalLayer.O10_ABSOLVING: 0.5,
    },
    PhonemeCategory.VOWEL_SHORT: {
        OntologicalLayer.O1_THINKING: 0.6,     # Medium-high - quick thought
        OntologicalLayer.O2_FORMING: 0.5,
        OntologicalLayer.O3_ACTING: 0.5,
        OntologicalLayer.O4_TAGGING: 0.6,      # Categorizing
        OntologicalLayer.O5_DIRECTING: 0.4,
        OntologicalLayer.O6_REASONING: 0.5,
        OntologicalLayer.O7_PURPOSING: 0.4,
        OntologicalLayer.O8_META_OBSERVING: 0.5,
        OntologicalLayer.O9_UNIFYING: 0.4,
        OntologicalLayer.O10_ABSOLVING: 0.4,
    },
    PhonemeCategory.VOWEL_LONG: {
        OntologicalLayer.O1_THINKING: 0.8,     # High - sustained reflection
        OntologicalLayer.O2_FORMING: 0.6,
        OntologicalLayer.O3_ACTING: 0.3,
        OntologicalLayer.O4_TAGGING: 0.4,
        OntologicalLayer.O5_DIRECTING: 0.4,
        OntologicalLayer.O6_REASONING: 0.6,
        OntologicalLayer.O7_PURPOSING: 0.6,
        OntologicalLayer.O8_META_OBSERVING: 0.7,   # High - contemplation
        OntologicalLayer.O9_UNIFYING: 0.6,
        OntologicalLayer.O10_ABSOLVING: 0.8,   # High - release, openness
    },
}


# =============================================================================
# Position Weights
# =============================================================================

"""
Phonemes at different positions contribute differently to character.
Initial phonemes have more impact on "first impression".
Final phonemes have more impact on "conclusion/resolution".
"""

def get_position_weight(position: int, total: int) -> Tuple[float, float, float]:
    """
    Get position-based weight multipliers.

    Returns (initial_weight, middle_weight, final_weight)
    """
    if total == 0:
        return (0.0, 0.0, 0.0)
    if total == 1:
        return (1.0, 0.0, 0.0)  # Single phoneme counts as initial

    normalized_pos = position / (total - 1)

    if normalized_pos < 0.25:
        return (1.5, 0.5, 0.0)   # Initial: boost attack-like layers
    elif normalized_pos > 0.75:
        return (0.0, 0.5, 1.5)   # Final: boost resolution-like layers
    else:
        return (0.0, 1.0, 0.0)   # Middle: neutral


# Layer position modifiers: how much initial/final position affects each layer
LAYER_POSITION_MODIFIER: Dict[OntologicalLayer, Tuple[float, float]] = {
    # (initial_bonus, final_bonus)
    OntologicalLayer.O1_THINKING: (0.1, 0.2),       # Thinking slightly boosted by reflection (final)
    OntologicalLayer.O2_FORMING: (0.2, 0.1),        # Forming boosted by initiation
    OntologicalLayer.O3_ACTING: (0.3, 0.0),         # Acting strongly boosted by initial (attack)
    OntologicalLayer.O4_TAGGING: (0.1, 0.1),        # Neutral
    OntologicalLayer.O5_DIRECTING: (0.2, 0.1),      # Directing boosted by initial (command)
    OntologicalLayer.O6_REASONING: (0.0, 0.2),      # Reasoning boosted by conclusion
    OntologicalLayer.O7_PURPOSING: (0.1, 0.2),      # Purpose often emerges at end
    OntologicalLayer.O8_META_OBSERVING: (0.0, 0.2), # Observation/reflection at end
    OntologicalLayer.O9_UNIFYING: (0.0, 0.2),       # Unification at conclusion
    OntologicalLayer.O10_ABSOLVING: (0.0, 0.3),     # Release/resolution strongly final
}


# =============================================================================
# Character Profile
# =============================================================================

@dataclass(frozen=True)
class CharacterProfile:
    """
    Cross-layer character propensity profile.

    Represents how strongly a word resonates with each ontological layer
    based on its phonemic structure.
    """
    word: str
    primary_layer: OntologicalLayer           # From layer assignment
    propensities: Dict[str, float]            # Layer name → propensity (0.0-1.0)
    dominant_secondary: OntologicalLayer      # Strongest non-primary layer
    phoneme_influence: Dict[str, float]       # Category → contribution
    profile_hash: str

    def get_propensity(self, layer: OntologicalLayer) -> float:
        """Get propensity for a specific layer."""
        return self.propensities.get(layer.value, 0.0)

    def get_top_layers(self, n: int = 3) -> Tuple[Tuple[OntologicalLayer, float], ...]:
        """Get top N layers by propensity."""
        sorted_props = sorted(
            [(OntologicalLayer(k), v) for k, v in self.propensities.items()],
            key=lambda x: x[1],
            reverse=True
        )
        return tuple(sorted_props[:n])

    def get_resonance_layers(self, threshold: float = 0.5) -> Tuple[OntologicalLayer, ...]:
        """Get layers with propensity above threshold."""
        return tuple(
            OntologicalLayer(k) for k, v in self.propensities.items()
            if v >= threshold
        )


def compute_profile_hash(word: str, propensities: Dict[str, float]) -> str:
    """Compute deterministic hash for profile."""
    # Sort propensities for deterministic ordering
    sorted_props = sorted(propensities.items())
    content = f"{word.lower()}|" + "|".join(f"{k}:{v:.3f}" for k, v in sorted_props)
    return hashlib.sha256(content.encode()).hexdigest()[:12]


# =============================================================================
# Character Deriver
# =============================================================================

@dataclass(frozen=True)
class CharacterDeriver:
    """
    Derives cross-layer character profiles from phonemic analysis.

    This implements the core hypothesis: phonemic structure creates
    "character" that resonates across ontological layers.
    """

    def derive(
        self,
        analysis: PhonemeAnalysis,
        primary_layer: OntologicalLayer
    ) -> CharacterProfile:
        """
        Derive character profile from phonemic analysis.

        Args:
            analysis: PhonemeAnalysis from phoneme extractor
            primary_layer: Primary layer from layer assigner

        Returns:
            CharacterProfile with cross-layer propensities
        """
        phonemes = analysis.phonemes
        total_phonemes = len(phonemes)

        # Initialize layer scores
        layer_scores: Dict[OntologicalLayer, float] = {
            layer: 0.0 for layer in OntologicalLayer
        }

        # Track category contributions
        category_contributions: Dict[PhonemeCategory, float] = {}

        # Process each phoneme
        for i, phoneme in enumerate(phonemes):
            category = get_phoneme_category(phoneme)
            affinities = CATEGORY_LAYER_AFFINITY.get(category, {})

            # Get position weights
            init_w, mid_w, final_w = get_position_weight(i, total_phonemes)

            # Add to layer scores
            for layer, base_affinity in affinities.items():
                # Apply position modifiers
                init_mod, final_mod = LAYER_POSITION_MODIFIER[layer]
                position_modifier = 1.0 + (init_w * init_mod) + (final_w * final_mod)

                contribution = base_affinity * position_modifier
                layer_scores[layer] += contribution

            # Track category contribution
            category_contributions[category] = (
                category_contributions.get(category, 0.0) + 1.0
            )

        # Normalize scores to 0.0-1.0
        if total_phonemes > 0:
            max_score = max(layer_scores.values()) if layer_scores else 1.0
            if max_score > 0:
                propensities = {
                    layer.value: min(1.0, score / max_score)
                    for layer, score in layer_scores.items()
                }
            else:
                propensities = {layer.value: 0.5 for layer in OntologicalLayer}
        else:
            propensities = {layer.value: 0.5 for layer in OntologicalLayer}

        # Boost primary layer slightly (it was assigned for good reason)
        propensities[primary_layer.value] = min(1.0, propensities.get(primary_layer.value, 0.5) * 1.1)

        # Find dominant secondary layer (highest non-primary)
        secondary_scores = [
            (layer, score) for layer, score in propensities.items()
            if layer != primary_layer.value
        ]
        if secondary_scores:
            dominant_secondary = OntologicalLayer(
                max(secondary_scores, key=lambda x: x[1])[0]
            )
        else:
            dominant_secondary = primary_layer

        # Normalize category contributions
        total_contrib = sum(category_contributions.values()) or 1.0
        phoneme_influence = {
            cat.value: contrib / total_contrib
            for cat, contrib in category_contributions.items()
        }

        profile_hash = compute_profile_hash(analysis.word, propensities)

        return CharacterProfile(
            word=analysis.word,
            primary_layer=primary_layer,
            propensities=propensities,
            dominant_secondary=dominant_secondary,
            phoneme_influence=phoneme_influence,
            profile_hash=profile_hash,
        )

    def derive_batch(
        self,
        analyses: Tuple[PhonemeAnalysis, ...],
        assignments: Tuple[OntologicalLayer, ...]
    ) -> Tuple[CharacterProfile, ...]:
        """Derive character profiles for multiple words."""
        if len(analyses) != len(assignments):
            raise ValueError("Analyses and assignments must have same length")
        return tuple(
            self.derive(a, l) for a, l in zip(analyses, assignments)
        )


# =============================================================================
# Factory Functions
# =============================================================================

def create_deriver() -> CharacterDeriver:
    """Create character deriver."""
    return CharacterDeriver()


# =============================================================================
# Analysis Utilities
# =============================================================================

def compare_characters(
    profile1: CharacterProfile,
    profile2: CharacterProfile
) -> float:
    """
    Compute similarity between two character profiles.

    Returns cosine similarity (0.0-1.0) of propensity vectors.
    """
    layers = [layer.value for layer in OntologicalLayer]

    vec1 = [profile1.propensities.get(l, 0.0) for l in layers]
    vec2 = [profile2.propensities.get(l, 0.0) for l in layers]

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    mag1 = sum(a * a for a in vec1) ** 0.5
    mag2 = sum(b * b for b in vec2) ** 0.5

    if mag1 == 0 or mag2 == 0:
        return 0.0

    return dot_product / (mag1 * mag2)


def get_layer_resonance_words(
    profiles: Tuple[CharacterProfile, ...],
    layer: OntologicalLayer,
    threshold: float = 0.6
) -> Tuple[str, ...]:
    """Get words that resonate with a specific layer above threshold."""
    return tuple(
        p.word for p in profiles
        if p.get_propensity(layer) >= threshold
    )


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Data classes
    "CharacterProfile",
    # Main class
    "CharacterDeriver",
    # Functions
    "create_deriver",
    "compare_characters",
    "get_layer_resonance_words",
    "compute_profile_hash",
    "get_position_weight",
    # Constants
    "CATEGORY_LAYER_AFFINITY",
    "LAYER_POSITION_MODIFIER",
]
