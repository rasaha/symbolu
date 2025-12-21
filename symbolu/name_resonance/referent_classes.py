"""
Name Resonance System - External Referent Classes (ERC)
========================================================

Provides the S term (Referential Coherence) for canonical matching.

S answers: "Do these two tokens point to the same external invariant?"

Key properties of S:
- Not phonemic
- Not acoustic
- Not statistical
- Deterministic
- Ontology-consistent

This is referential grounding, not semantics in the NLP sense.

Referent Classes:
- LUMINOUS: Sources and carriers of light/energy
- ORGANISM: Living things (plants, animals, humans)
- ARTIFACT: Human-made objects and tools
- NATURAL_BODY: Natural physical entities (celestial, geological)
- SUBSTANCE: Materials and matter
- PROCESS: Actions, events, transformations
- ABSTRACT: Concepts, relations, qualities
- SIGNAL: Communication, information carriers
- TEMPORAL: Time-related concepts
- SPATIAL: Space, location, direction
- EMOTIONAL: Feelings, psychological states
- SOCIAL: Roles, relationships, institutions

Tier: Core/Substrate (Tier 1)
Authority: NONE (referential grounding only)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, Tuple, Set


class ReferentClass(Enum):
    """External referent classes for non-phonemic grounding."""
    LUMINOUS = "luminous"           # Light, energy sources/carriers
    ORGANISM = "organism"           # Living things
    ARTIFACT = "artifact"           # Human-made objects
    NATURAL_BODY = "natural_body"   # Celestial, geological entities
    SUBSTANCE = "substance"         # Materials, matter
    PROCESS = "process"             # Actions, events
    ABSTRACT = "abstract"           # Concepts, relations
    SIGNAL = "signal"               # Communication, information
    TEMPORAL = "temporal"           # Time-related
    SPATIAL = "spatial"             # Space, location
    EMOTIONAL = "emotional"         # Feelings, states
    SOCIAL = "social"               # Roles, relationships
    UNKNOWN = "unknown"             # Unmapped words


# =============================================================================
# Word → Referent Class Mapping
# =============================================================================

# This is a deterministic, finite, explainable mapping.
# Not learned, not statistical - symbolic referential grounding.

WORD_TO_REFERENT: Dict[str, FrozenSet[ReferentClass]] = {
    # LUMINOUS - light, energy, radiance
    "sun": frozenset({ReferentClass.LUMINOUS, ReferentClass.NATURAL_BODY}),
    "light": frozenset({ReferentClass.LUMINOUS, ReferentClass.ABSTRACT}),
    "fire": frozenset({ReferentClass.LUMINOUS, ReferentClass.PROCESS}),
    "flame": frozenset({ReferentClass.LUMINOUS, ReferentClass.PROCESS}),
    "star": frozenset({ReferentClass.LUMINOUS, ReferentClass.NATURAL_BODY}),
    "bright": frozenset({ReferentClass.LUMINOUS, ReferentClass.ABSTRACT}),
    "glow": frozenset({ReferentClass.LUMINOUS, ReferentClass.PROCESS}),
    "shine": frozenset({ReferentClass.LUMINOUS, ReferentClass.PROCESS}),
    "radiance": frozenset({ReferentClass.LUMINOUS, ReferentClass.ABSTRACT}),
    "beam": frozenset({ReferentClass.LUMINOUS, ReferentClass.PROCESS}),

    # ORGANISM - living things
    "tree": frozenset({ReferentClass.ORGANISM, ReferentClass.NATURAL_BODY}),
    "forest": frozenset({ReferentClass.ORGANISM, ReferentClass.SPATIAL}),
    "flower": frozenset({ReferentClass.ORGANISM}),
    "plant": frozenset({ReferentClass.ORGANISM}),
    "animal": frozenset({ReferentClass.ORGANISM}),
    "bird": frozenset({ReferentClass.ORGANISM}),
    "fish": frozenset({ReferentClass.ORGANISM}),
    "human": frozenset({ReferentClass.ORGANISM, ReferentClass.SOCIAL}),
    "man": frozenset({ReferentClass.ORGANISM, ReferentClass.SOCIAL}),
    "woman": frozenset({ReferentClass.ORGANISM, ReferentClass.SOCIAL}),
    "child": frozenset({ReferentClass.ORGANISM, ReferentClass.SOCIAL}),
    "mother": frozenset({ReferentClass.ORGANISM, ReferentClass.SOCIAL}),
    "father": frozenset({ReferentClass.ORGANISM, ReferentClass.SOCIAL}),
    "leaf": frozenset({ReferentClass.ORGANISM}),
    "root": frozenset({ReferentClass.ORGANISM, ReferentClass.ABSTRACT}),
    "seed": frozenset({ReferentClass.ORGANISM}),

    # ARTIFACT - human-made objects
    "computer": frozenset({ReferentClass.ARTIFACT}),
    "table": frozenset({ReferentClass.ARTIFACT}),
    "chair": frozenset({ReferentClass.ARTIFACT}),
    "book": frozenset({ReferentClass.ARTIFACT, ReferentClass.SIGNAL}),
    "pencil": frozenset({ReferentClass.ARTIFACT}),
    "pen": frozenset({ReferentClass.ARTIFACT}),
    "tool": frozenset({ReferentClass.ARTIFACT}),
    "machine": frozenset({ReferentClass.ARTIFACT}),
    "house": frozenset({ReferentClass.ARTIFACT, ReferentClass.SPATIAL}),
    "building": frozenset({ReferentClass.ARTIFACT, ReferentClass.SPATIAL}),
    "car": frozenset({ReferentClass.ARTIFACT}),
    "phone": frozenset({ReferentClass.ARTIFACT, ReferentClass.SIGNAL}),
    "door": frozenset({ReferentClass.ARTIFACT, ReferentClass.SPATIAL}),
    "window": frozenset({ReferentClass.ARTIFACT, ReferentClass.SPATIAL}),
    "wheel": frozenset({ReferentClass.ARTIFACT}),

    # NATURAL_BODY - celestial, geological
    "moon": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.LUMINOUS}),
    "earth": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
    "mountain": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
    "ocean": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SUBSTANCE}),
    "river": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SUBSTANCE}),
    "sky": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
    "cloud": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SUBSTANCE}),
    "stone": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SUBSTANCE}),
    "rock": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SUBSTANCE}),
    "sand": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SUBSTANCE}),
    "island": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
    "valley": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
    "hill": frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),

    # SUBSTANCE - materials, matter
    "water": frozenset({ReferentClass.SUBSTANCE}),
    "air": frozenset({ReferentClass.SUBSTANCE}),
    "gold": frozenset({ReferentClass.SUBSTANCE}),
    "iron": frozenset({ReferentClass.SUBSTANCE}),
    "wood": frozenset({ReferentClass.SUBSTANCE, ReferentClass.ORGANISM}),
    "metal": frozenset({ReferentClass.SUBSTANCE}),
    "glass": frozenset({ReferentClass.SUBSTANCE}),
    "ice": frozenset({ReferentClass.SUBSTANCE}),
    "snow": frozenset({ReferentClass.SUBSTANCE, ReferentClass.NATURAL_BODY}),
    "rain": frozenset({ReferentClass.SUBSTANCE, ReferentClass.PROCESS}),
    "blood": frozenset({ReferentClass.SUBSTANCE, ReferentClass.ORGANISM}),
    "oil": frozenset({ReferentClass.SUBSTANCE}),

    # PROCESS - actions, events, transformations
    "walk": frozenset({ReferentClass.PROCESS}),
    "run": frozenset({ReferentClass.PROCESS}),
    "dance": frozenset({ReferentClass.PROCESS}),
    "sing": frozenset({ReferentClass.PROCESS, ReferentClass.SIGNAL}),
    "think": frozenset({ReferentClass.PROCESS, ReferentClass.ABSTRACT}),
    "grow": frozenset({ReferentClass.PROCESS}),
    "change": frozenset({ReferentClass.PROCESS, ReferentClass.ABSTRACT}),
    "move": frozenset({ReferentClass.PROCESS}),
    "flow": frozenset({ReferentClass.PROCESS}),
    "burn": frozenset({ReferentClass.PROCESS, ReferentClass.LUMINOUS}),
    "birth": frozenset({ReferentClass.PROCESS, ReferentClass.TEMPORAL}),
    "death": frozenset({ReferentClass.PROCESS, ReferentClass.TEMPORAL}),
    "sleep": frozenset({ReferentClass.PROCESS}),
    "dream": frozenset({ReferentClass.PROCESS, ReferentClass.ABSTRACT}),
    "war": frozenset({ReferentClass.PROCESS, ReferentClass.SOCIAL}),
    "peace": frozenset({ReferentClass.ABSTRACT, ReferentClass.SOCIAL}),

    # ABSTRACT - concepts, relations, qualities
    "love": frozenset({ReferentClass.EMOTIONAL, ReferentClass.ABSTRACT}),
    "hate": frozenset({ReferentClass.EMOTIONAL, ReferentClass.ABSTRACT}),
    "truth": frozenset({ReferentClass.ABSTRACT}),
    "justice": frozenset({ReferentClass.ABSTRACT, ReferentClass.SOCIAL}),
    "freedom": frozenset({ReferentClass.ABSTRACT, ReferentClass.SOCIAL}),
    "power": frozenset({ReferentClass.ABSTRACT}),
    "beauty": frozenset({ReferentClass.ABSTRACT}),
    "wisdom": frozenset({ReferentClass.ABSTRACT}),
    "knowledge": frozenset({ReferentClass.ABSTRACT, ReferentClass.SIGNAL}),
    "good": frozenset({ReferentClass.ABSTRACT}),
    "evil": frozenset({ReferentClass.ABSTRACT}),
    "right": frozenset({ReferentClass.ABSTRACT}),
    "wrong": frozenset({ReferentClass.ABSTRACT}),
    "hope": frozenset({ReferentClass.EMOTIONAL, ReferentClass.ABSTRACT}),
    "fear": frozenset({ReferentClass.EMOTIONAL, ReferentClass.ABSTRACT}),
    "idea": frozenset({ReferentClass.ABSTRACT}),
    "thought": frozenset({ReferentClass.ABSTRACT, ReferentClass.PROCESS}),
    "mind": frozenset({ReferentClass.ABSTRACT, ReferentClass.ORGANISM}),
    "soul": frozenset({ReferentClass.ABSTRACT}),
    "spirit": frozenset({ReferentClass.ABSTRACT}),

    # EMOTIONAL - feelings, psychological states
    "happy": frozenset({ReferentClass.EMOTIONAL}),
    "sad": frozenset({ReferentClass.EMOTIONAL}),
    "joy": frozenset({ReferentClass.EMOTIONAL}),
    "sorrow": frozenset({ReferentClass.EMOTIONAL}),
    "anger": frozenset({ReferentClass.EMOTIONAL}),
    "calm": frozenset({ReferentClass.EMOTIONAL}),
    "anxiety": frozenset({ReferentClass.EMOTIONAL}),
    "peace": frozenset({ReferentClass.EMOTIONAL, ReferentClass.ABSTRACT}),

    # SOCIAL - roles, relationships
    "king": frozenset({ReferentClass.SOCIAL, ReferentClass.ORGANISM}),
    "queen": frozenset({ReferentClass.SOCIAL, ReferentClass.ORGANISM}),
    "friend": frozenset({ReferentClass.SOCIAL}),
    "enemy": frozenset({ReferentClass.SOCIAL}),
    "hero": frozenset({ReferentClass.SOCIAL}),
    "leader": frozenset({ReferentClass.SOCIAL}),
    "family": frozenset({ReferentClass.SOCIAL}),
    "nation": frozenset({ReferentClass.SOCIAL, ReferentClass.SPATIAL}),
    "community": frozenset({ReferentClass.SOCIAL}),

    # SIGNAL - communication, information
    "word": frozenset({ReferentClass.SIGNAL, ReferentClass.ABSTRACT}),
    "voice": frozenset({ReferentClass.SIGNAL, ReferentClass.ORGANISM}),
    "song": frozenset({ReferentClass.SIGNAL}),
    "music": frozenset({ReferentClass.SIGNAL}),
    "message": frozenset({ReferentClass.SIGNAL}),
    "language": frozenset({ReferentClass.SIGNAL, ReferentClass.ABSTRACT}),
    "name": frozenset({ReferentClass.SIGNAL, ReferentClass.ABSTRACT}),
    "silence": frozenset({ReferentClass.SIGNAL, ReferentClass.ABSTRACT}),

    # TEMPORAL - time-related
    "time": frozenset({ReferentClass.TEMPORAL, ReferentClass.ABSTRACT}),
    "day": frozenset({ReferentClass.TEMPORAL}),
    "night": frozenset({ReferentClass.TEMPORAL, ReferentClass.LUMINOUS}),
    "year": frozenset({ReferentClass.TEMPORAL}),
    "moment": frozenset({ReferentClass.TEMPORAL}),
    "past": frozenset({ReferentClass.TEMPORAL, ReferentClass.ABSTRACT}),
    "future": frozenset({ReferentClass.TEMPORAL, ReferentClass.ABSTRACT}),
    "now": frozenset({ReferentClass.TEMPORAL}),
    "ancient": frozenset({ReferentClass.TEMPORAL}),
    "new": frozenset({ReferentClass.TEMPORAL}),
    "old": frozenset({ReferentClass.TEMPORAL}),
    "young": frozenset({ReferentClass.TEMPORAL, ReferentClass.ORGANISM}),

    # SPATIAL - space, location, direction
    "place": frozenset({ReferentClass.SPATIAL}),
    "space": frozenset({ReferentClass.SPATIAL, ReferentClass.ABSTRACT}),
    "path": frozenset({ReferentClass.SPATIAL}),
    "road": frozenset({ReferentClass.SPATIAL, ReferentClass.ARTIFACT}),
    "world": frozenset({ReferentClass.SPATIAL}),
    "home": frozenset({ReferentClass.SPATIAL, ReferentClass.SOCIAL}),
    "distance": frozenset({ReferentClass.SPATIAL, ReferentClass.ABSTRACT}),
    "height": frozenset({ReferentClass.SPATIAL, ReferentClass.ABSTRACT}),
    "depth": frozenset({ReferentClass.SPATIAL, ReferentClass.ABSTRACT}),

    # Additional common words
    "heart": frozenset({ReferentClass.ORGANISM, ReferentClass.EMOTIONAL}),
    "hand": frozenset({ReferentClass.ORGANISM}),
    "eye": frozenset({ReferentClass.ORGANISM}),
    "body": frozenset({ReferentClass.ORGANISM}),
    "face": frozenset({ReferentClass.ORGANISM, ReferentClass.SOCIAL}),
    "head": frozenset({ReferentClass.ORGANISM}),
    "life": frozenset({ReferentClass.ABSTRACT, ReferentClass.PROCESS}),
    "art": frozenset({ReferentClass.ABSTRACT, ReferentClass.ARTIFACT}),
    "science": frozenset({ReferentClass.ABSTRACT}),
    "nature": frozenset({ReferentClass.ABSTRACT, ReferentClass.NATURAL_BODY}),
    "god": frozenset({ReferentClass.ABSTRACT, ReferentClass.SOCIAL}),
    "dark": frozenset({ReferentClass.LUMINOUS, ReferentClass.ABSTRACT}),
    "darkness": frozenset({ReferentClass.LUMINOUS, ReferentClass.ABSTRACT}),
    "banana": frozenset({ReferentClass.ORGANISM, ReferentClass.SUBSTANCE}),
    "apple": frozenset({ReferentClass.ORGANISM, ReferentClass.SUBSTANCE}),
    "orange": frozenset({ReferentClass.ORGANISM, ReferentClass.SUBSTANCE}),
    "food": frozenset({ReferentClass.SUBSTANCE}),
}


# =============================================================================
# Referent Coherence Computation
# =============================================================================

@dataclass(frozen=True)
class ReferentAnalysis:
    """Result of referent coherence analysis."""
    coherence: float  # S ∈ [0, 1]
    word_a: str
    word_b: str
    classes_a: FrozenSet[ReferentClass]
    classes_b: FrozenSet[ReferentClass]
    shared_classes: FrozenSet[ReferentClass]
    jaccard_similarity: float
    is_grounded: bool  # Both words have known referents


def get_referent_classes(word: str) -> FrozenSet[ReferentClass]:
    """
    Get referent classes for a word.

    Args:
        word: The word to look up

    Returns:
        FrozenSet of ReferentClass values
    """
    word_lower = word.lower().strip()

    if word_lower in WORD_TO_REFERENT:
        return WORD_TO_REFERENT[word_lower]

    # Unknown word
    return frozenset({ReferentClass.UNKNOWN})


def compute_referent_coherence(word_a: str, word_b: str) -> ReferentAnalysis:
    """
    Compute referential coherence (S) between two words.

    S answers: "Do these two tokens point to the same external invariant?"

    Key properties:
    - Not phonemic
    - Not acoustic
    - Deterministic
    - Returns 0 if referents don't overlap

    Args:
        word_a: First word
        word_b: Second word

    Returns:
        ReferentAnalysis with coherence score
    """
    classes_a = get_referent_classes(word_a)
    classes_b = get_referent_classes(word_b)

    # Check if both words are grounded (not UNKNOWN)
    is_a_known = ReferentClass.UNKNOWN not in classes_a
    is_b_known = ReferentClass.UNKNOWN not in classes_b
    is_grounded = is_a_known and is_b_known

    # If either word is unknown, we can't compute meaningful coherence
    if not is_grounded:
        # Return neutral score for unknown words
        return ReferentAnalysis(
            coherence=0.5,  # Neutral - we don't know
            word_a=word_a,
            word_b=word_b,
            classes_a=classes_a,
            classes_b=classes_b,
            shared_classes=frozenset(),
            jaccard_similarity=0.0,
            is_grounded=False,
        )

    # Compute Jaccard similarity of referent class sets
    shared = classes_a & classes_b
    union = classes_a | classes_b

    if not union:
        jaccard = 0.0
    else:
        jaccard = len(shared) / len(union)

    # Coherence is based on Jaccard but with boost for shared classes
    # If they share ANY class, there's some coherence
    if shared:
        # Base coherence from Jaccard
        coherence = jaccard

        # Boost for having shared classes (minimum coherence if any overlap)
        coherence = max(coherence, 0.3 * len(shared))

        # Cap at 1.0
        coherence = min(1.0, coherence)
    else:
        # No shared classes = no referential coherence
        coherence = 0.0

    return ReferentAnalysis(
        coherence=round(coherence, 4),
        word_a=word_a,
        word_b=word_b,
        classes_a=classes_a,
        classes_b=classes_b,
        shared_classes=shared,
        jaccard_similarity=round(jaccard, 4),
        is_grounded=True,
    )


def format_referent_analysis(analysis: ReferentAnalysis) -> str:
    """Format referent analysis for display."""
    classes_a_str = ", ".join(c.value for c in analysis.classes_a)
    classes_b_str = ", ".join(c.value for c in analysis.classes_b)
    shared_str = ", ".join(c.value for c in analysis.shared_classes) or "none"

    return (
        f"{analysis.word_a} [{classes_a_str}] ↔ {analysis.word_b} [{classes_b_str}]\n"
        f"  Shared: {shared_str}\n"
        f"  Jaccard: {analysis.jaccard_similarity:.3f}\n"
        f"  Coherence (S): {analysis.coherence:.3f}"
    )


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    "ReferentClass",
    "ReferentAnalysis",
    "WORD_TO_REFERENT",
    "get_referent_classes",
    "compute_referent_coherence",
    "format_referent_analysis",
]
