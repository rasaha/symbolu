"""
Name Resonance System - External Referent Classes (ERC)
========================================================

Provides the S term (Semantic Contextual Meaning) for canonical matching.

S answers: "Do these two tokens share semantic contextual meaning?"

Key properties of S:
- Not phonemic (source-independent from C and R)
- Context-aware (considers surrounding semantic context)
- Deterministic (given same context, same result)
- Ontology-consistent (grounded in referent classes)

S now incorporates SEMANTIC CONTEXTUAL MEANING:
- Primary: Context-based semantic similarity (when context provided)
- Secondary: Referent class overlap (fallback when no context)
- Hybrid mode: Weighted combination of both

Referent Classes (refined per ChatGPT feedback):
- LUMINOUS: Sources and carriers of light/energy
- BIOLOGICAL_ORGANISM: Living things (plants, animals) - NOT roles
- ROLE_BEARER: Social agents who bear roles (king, doctor)
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
- ENERGY_SOURCE: Things that produce/emit energy
- PHENOMENON: Observable occurrences (not sources)

Primary vs Secondary Referent Classes:
- Primary: What the word IS (its core identity)
- Secondary: What it produces/enables/affects

S computation:
- Primary overlap → high coherence (0.7-1.0)
- Secondary overlap only → partial coherence (0.3-0.5)
- No overlap → zero coherence

Tier: Core/Substrate (Tier 1)
Authority: NONE (referential grounding only)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, Tuple, NamedTuple, Optional, List


# =============================================================================
# Semantic Context Configuration
# =============================================================================

@dataclass
class SemanticContextConfig:
    """Configuration for semantic contextual S computation."""
    # Weight for contextual vs class-based coherence (0.0 = class only, 1.0 = context only)
    context_weight: float = 0.6
    # Minimum context similarity to boost S
    context_threshold: float = 0.3
    # Enable contextual semantic analysis
    use_contextual: bool = True


DEFAULT_CONTEXT_CONFIG = SemanticContextConfig()


class ReferentClass(Enum):
    """External referent classes for non-phonemic grounding."""
    # Core categories
    LUMINOUS = "luminous"                     # Light, radiance
    BIOLOGICAL_ORGANISM = "biological"        # Living things (plants, animals)
    ROLE_BEARER = "role_bearer"               # Social agents bearing roles
    ARTIFACT = "artifact"                     # Human-made objects
    NATURAL_BODY = "natural_body"             # Celestial, geological entities
    SUBSTANCE = "substance"                   # Materials, matter
    PROCESS = "process"                       # Actions, events
    ABSTRACT = "abstract"                     # Concepts, relations
    SIGNAL = "signal"                         # Communication, information
    TEMPORAL = "temporal"                     # Time-related
    SPATIAL = "spatial"                       # Space, location
    EMOTIONAL = "emotional"                   # Feelings, states
    SOCIAL = "social"                         # Roles, relationships

    # Refined categories (per ChatGPT)
    ENERGY_SOURCE = "energy_source"           # Things that produce energy
    PHENOMENON = "phenomenon"                 # Observable occurrences

    # Special
    UNKNOWN = "unknown"                       # Unmapped words


class ReferentProfile(NamedTuple):
    """Primary and secondary referent classes for a word."""
    primary: FrozenSet[ReferentClass]
    secondary: FrozenSet[ReferentClass]


# =============================================================================
# Word → Referent Class Mapping (Primary/Secondary)
# =============================================================================

# This is a deterministic, finite, explainable mapping.
# Primary = what it IS, Secondary = what it produces/enables

WORD_TO_REFERENT: Dict[str, ReferentProfile] = {
    # LUMINOUS - light, energy, radiance
    "sun": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.ENERGY_SOURCE}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "light": ReferentProfile(
        primary=frozenset({ReferentClass.PHENOMENON}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "fire": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS, ReferentClass.ENERGY_SOURCE}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "flame": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "star": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.ENERGY_SOURCE}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "bright": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "glow": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "shine": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "radiance": ReferentProfile(
        primary=frozenset({ReferentClass.PHENOMENON}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "beam": ReferentProfile(
        primary=frozenset({ReferentClass.PHENOMENON}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "dark": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "darkness": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT, ReferentClass.PHENOMENON}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),

    # BIOLOGICAL_ORGANISM - living things (NOT roles)
    "tree": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset({ReferentClass.NATURAL_BODY}),
    ),
    "forest": ReferentProfile(
        primary=frozenset({ReferentClass.SPATIAL}),
        secondary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
    ),
    "flower": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "plant": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "animal": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "bird": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "fish": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "leaf": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "root": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset({ReferentClass.ABSTRACT}),
    ),
    "seed": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "banana": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM, ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "apple": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM, ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "orange": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM, ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),

    # ROLE_BEARER - social agents (humans in roles)
    "human": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM, ReferentClass.ROLE_BEARER}),
        secondary=frozenset({ReferentClass.SOCIAL}),
    ),
    "man": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM, ReferentClass.ROLE_BEARER}),
        secondary=frozenset({ReferentClass.SOCIAL}),
    ),
    "woman": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM, ReferentClass.ROLE_BEARER}),
        secondary=frozenset({ReferentClass.SOCIAL}),
    ),
    "child": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset({ReferentClass.SOCIAL}),
    ),
    "mother": ReferentProfile(
        primary=frozenset({ReferentClass.ROLE_BEARER}),
        secondary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM, ReferentClass.SOCIAL}),
    ),
    "father": ReferentProfile(
        primary=frozenset({ReferentClass.ROLE_BEARER}),
        secondary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM, ReferentClass.SOCIAL}),
    ),
    "king": ReferentProfile(
        primary=frozenset({ReferentClass.ROLE_BEARER, ReferentClass.SOCIAL}),
        secondary=frozenset(),
    ),
    "queen": ReferentProfile(
        primary=frozenset({ReferentClass.ROLE_BEARER, ReferentClass.SOCIAL}),
        secondary=frozenset(),
    ),
    "doctor": ReferentProfile(
        primary=frozenset({ReferentClass.ROLE_BEARER}),
        secondary=frozenset({ReferentClass.SOCIAL}),
    ),
    "hero": ReferentProfile(
        primary=frozenset({ReferentClass.ROLE_BEARER, ReferentClass.SOCIAL}),
        secondary=frozenset(),
    ),
    "leader": ReferentProfile(
        primary=frozenset({ReferentClass.ROLE_BEARER, ReferentClass.SOCIAL}),
        secondary=frozenset(),
    ),

    # ARTIFACT - human-made objects
    "computer": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset({ReferentClass.SIGNAL}),
    ),
    "table": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset(),
    ),
    "chair": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset(),
    ),
    "book": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT, ReferentClass.SIGNAL}),
        secondary=frozenset(),
    ),
    "pencil": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset(),
    ),
    "pen": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset(),
    ),
    "tool": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset(),
    ),
    "machine": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset(),
    ),
    "house": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT, ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "building": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT, ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "car": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset(),
    ),
    "vehicle": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset(),
    ),
    "phone": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT, ReferentClass.SIGNAL}),
        secondary=frozenset(),
    ),
    "door": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset({ReferentClass.SPATIAL}),
    ),
    "window": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset({ReferentClass.SPATIAL}),
    ),
    "wheel": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT}),
        secondary=frozenset(),
    ),
    "hospital": ReferentProfile(
        primary=frozenset({ReferentClass.ARTIFACT, ReferentClass.SPATIAL}),
        secondary=frozenset({ReferentClass.SOCIAL}),
    ),

    # NATURAL_BODY - celestial, geological
    "moon": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "earth": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "mountain": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "ocean": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY}),
        secondary=frozenset({ReferentClass.SUBSTANCE}),
    ),
    "river": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY}),
        secondary=frozenset({ReferentClass.SUBSTANCE}),
    ),
    "sky": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "cloud": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY}),
        secondary=frozenset({ReferentClass.SUBSTANCE}),
    ),
    "stone": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "rock": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "sand": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "island": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "valley": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "hill": ReferentProfile(
        primary=frozenset({ReferentClass.NATURAL_BODY, ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),

    # SUBSTANCE - materials, matter
    "water": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "air": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "gold": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "iron": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "wood": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
    ),
    "metal": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "glass": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "ice": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "snow": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE, ReferentClass.NATURAL_BODY}),
        secondary=frozenset(),
    ),
    "rain": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS, ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "blood": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
    ),
    "oil": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),
    "food": ReferentProfile(
        primary=frozenset({ReferentClass.SUBSTANCE}),
        secondary=frozenset(),
    ),

    # PROCESS - actions, events, transformations
    "walk": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset(),
    ),
    "run": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset(),
    ),
    "dance": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset(),
    ),
    "sing": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset({ReferentClass.SIGNAL}),
    ),
    "think": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset({ReferentClass.ABSTRACT}),
    ),
    "grow": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset(),
    ),
    "change": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "move": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset(),
    ),
    "flow": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset(),
    ),
    "burn": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "birth": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS, ReferentClass.TEMPORAL}),
        secondary=frozenset(),
    ),
    "death": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS, ReferentClass.TEMPORAL}),
        secondary=frozenset(),
    ),
    "sleep": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset(),
    ),
    "dream": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "war": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS, ReferentClass.SOCIAL}),
        secondary=frozenset(),
    ),
    "oxidation": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset(),
    ),
    "burning": ReferentProfile(
        primary=frozenset({ReferentClass.PROCESS}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),

    # ABSTRACT - concepts, relations, qualities
    "love": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "hate": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "truth": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "justice": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT, ReferentClass.SOCIAL}),
        secondary=frozenset(),
    ),
    "freedom": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT, ReferentClass.SOCIAL}),
        secondary=frozenset(),
    ),
    "power": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "beauty": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "wisdom": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "knowledge": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset({ReferentClass.SIGNAL}),
    ),
    "good": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "evil": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "right": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "wrong": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "hope": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "fear": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "idea": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "thought": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT, ReferentClass.PROCESS}),
        secondary=frozenset(),
    ),
    "mind": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
    ),
    "soul": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "spirit": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "peace": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT, ReferentClass.SOCIAL}),
        secondary=frozenset({ReferentClass.EMOTIONAL}),
    ),

    # EMOTIONAL - feelings, psychological states
    "happy": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL}),
        secondary=frozenset(),
    ),
    "sad": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL}),
        secondary=frozenset(),
    ),
    "joy": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL}),
        secondary=frozenset(),
    ),
    "sorrow": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL}),
        secondary=frozenset(),
    ),
    "anger": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL}),
        secondary=frozenset(),
    ),
    "calm": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL}),
        secondary=frozenset(),
    ),
    "anxiety": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL}),
        secondary=frozenset(),
    ),
    "sadness": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL}),
        secondary=frozenset(),
    ),
    "emotion": ReferentProfile(
        primary=frozenset({ReferentClass.EMOTIONAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),

    # SOCIAL - roles, relationships, institutions
    "friend": ReferentProfile(
        primary=frozenset({ReferentClass.SOCIAL, ReferentClass.ROLE_BEARER}),
        secondary=frozenset(),
    ),
    "enemy": ReferentProfile(
        primary=frozenset({ReferentClass.SOCIAL, ReferentClass.ROLE_BEARER}),
        secondary=frozenset(),
    ),
    "family": ReferentProfile(
        primary=frozenset({ReferentClass.SOCIAL}),
        secondary=frozenset(),
    ),
    "nation": ReferentProfile(
        primary=frozenset({ReferentClass.SOCIAL, ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "community": ReferentProfile(
        primary=frozenset({ReferentClass.SOCIAL}),
        secondary=frozenset(),
    ),

    # SIGNAL - communication, information
    "word": ReferentProfile(
        primary=frozenset({ReferentClass.SIGNAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "voice": ReferentProfile(
        primary=frozenset({ReferentClass.SIGNAL}),
        secondary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
    ),
    "song": ReferentProfile(
        primary=frozenset({ReferentClass.SIGNAL}),
        secondary=frozenset(),
    ),
    "music": ReferentProfile(
        primary=frozenset({ReferentClass.SIGNAL}),
        secondary=frozenset(),
    ),
    "message": ReferentProfile(
        primary=frozenset({ReferentClass.SIGNAL}),
        secondary=frozenset(),
    ),
    "language": ReferentProfile(
        primary=frozenset({ReferentClass.SIGNAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "name": ReferentProfile(
        primary=frozenset({ReferentClass.SIGNAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "silence": ReferentProfile(
        primary=frozenset({ReferentClass.SIGNAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),

    # TEMPORAL - time-related
    "time": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "day": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL}),
        secondary=frozenset(),
    ),
    "night": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL}),
        secondary=frozenset({ReferentClass.LUMINOUS}),
    ),
    "year": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL}),
        secondary=frozenset(),
    ),
    "moment": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL}),
        secondary=frozenset(),
    ),
    "past": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "future": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "now": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL}),
        secondary=frozenset(),
    ),
    "ancient": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL}),
        secondary=frozenset(),
    ),
    "new": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL}),
        secondary=frozenset(),
    ),
    "old": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL}),
        secondary=frozenset(),
    ),
    "young": ReferentProfile(
        primary=frozenset({ReferentClass.TEMPORAL}),
        secondary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
    ),

    # SPATIAL - space, location, direction
    "place": ReferentProfile(
        primary=frozenset({ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "space": ReferentProfile(
        primary=frozenset({ReferentClass.SPATIAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "path": ReferentProfile(
        primary=frozenset({ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "road": ReferentProfile(
        primary=frozenset({ReferentClass.SPATIAL, ReferentClass.ARTIFACT}),
        secondary=frozenset(),
    ),
    "world": ReferentProfile(
        primary=frozenset({ReferentClass.SPATIAL}),
        secondary=frozenset(),
    ),
    "home": ReferentProfile(
        primary=frozenset({ReferentClass.SPATIAL, ReferentClass.SOCIAL}),
        secondary=frozenset(),
    ),
    "distance": ReferentProfile(
        primary=frozenset({ReferentClass.SPATIAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "height": ReferentProfile(
        primary=frozenset({ReferentClass.SPATIAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "depth": ReferentProfile(
        primary=frozenset({ReferentClass.SPATIAL, ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),

    # Body parts and related
    "heart": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset({ReferentClass.EMOTIONAL}),
    ),
    "hand": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "eye": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "body": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "face": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset({ReferentClass.SOCIAL}),
    ),
    "head": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "feather": ReferentProfile(
        primary=frozenset({ReferentClass.BIOLOGICAL_ORGANISM}),
        secondary=frozenset(),
    ),
    "heavy": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),

    # Additional abstract/complex
    "life": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT, ReferentClass.PROCESS}),
        secondary=frozenset(),
    ),
    "art": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset({ReferentClass.ARTIFACT}),
    ),
    "science": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset(),
    ),
    "nature": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset({ReferentClass.NATURAL_BODY}),
    ),
    "god": ReferentProfile(
        primary=frozenset({ReferentClass.ABSTRACT}),
        secondary=frozenset({ReferentClass.SOCIAL}),
    ),
}


# =============================================================================
# Referent Coherence Computation (Primary/Secondary aware)
# =============================================================================

@dataclass(frozen=True)
class ReferentAnalysis:
    """Result of referent coherence analysis."""
    coherence: float  # S ∈ [0, 1]
    word_a: str
    word_b: str
    primary_a: FrozenSet[ReferentClass]
    primary_b: FrozenSet[ReferentClass]
    secondary_a: FrozenSet[ReferentClass]
    secondary_b: FrozenSet[ReferentClass]
    shared_primary: FrozenSet[ReferentClass]
    shared_secondary: FrozenSet[ReferentClass]
    is_grounded: bool  # Both words have known referents
    is_unknown: bool   # Flag for UNKNOWN_REFERENT


def get_referent_profile(word: str) -> ReferentProfile:
    """
    Get referent profile (primary + secondary classes) for a word.

    Args:
        word: The word to look up

    Returns:
        ReferentProfile with primary and secondary classes
    """
    word_lower = word.lower().strip()

    if word_lower in WORD_TO_REFERENT:
        return WORD_TO_REFERENT[word_lower]

    # Unknown word
    return ReferentProfile(
        primary=frozenset({ReferentClass.UNKNOWN}),
        secondary=frozenset(),
    )


def compute_referent_coherence(word_a: str, word_b: str) -> ReferentAnalysis:
    """
    Compute referential coherence (S) between two words.

    S computation (per ChatGPT refinement):
    - Primary overlap → high coherence (0.7-1.0)
    - Secondary overlap only → partial coherence (0.3-0.5)
    - No overlap → zero coherence

    Key properties:
    - Not phonemic
    - Not acoustic
    - Deterministic
    - Properly handles primary vs secondary distinction

    Args:
        word_a: First word
        word_b: Second word

    Returns:
        ReferentAnalysis with coherence score
    """
    profile_a = get_referent_profile(word_a)
    profile_b = get_referent_profile(word_b)

    # Check if both words are grounded (not UNKNOWN)
    is_a_known = ReferentClass.UNKNOWN not in profile_a.primary
    is_b_known = ReferentClass.UNKNOWN not in profile_b.primary
    is_grounded = is_a_known and is_b_known
    is_unknown = not is_grounded

    # If either word is unknown, flag it properly
    if is_unknown:
        return ReferentAnalysis(
            coherence=0.5,  # Epistemic uncertainty, not neutrality
            word_a=word_a,
            word_b=word_b,
            primary_a=profile_a.primary,
            primary_b=profile_b.primary,
            secondary_a=profile_a.secondary,
            secondary_b=profile_b.secondary,
            shared_primary=frozenset(),
            shared_secondary=frozenset(),
            is_grounded=False,
            is_unknown=True,
        )

    # Compute primary overlap
    shared_primary = profile_a.primary & profile_b.primary

    # Compute secondary overlap (including cross primary-secondary)
    # a's secondary with b's primary/secondary, and vice versa
    all_secondary_a = profile_a.secondary | profile_a.primary
    all_secondary_b = profile_b.secondary | profile_b.primary
    shared_secondary = (profile_a.secondary & all_secondary_b) | \
                       (profile_b.secondary & all_secondary_a)
    # Remove what's already in primary overlap
    shared_secondary = shared_secondary - shared_primary

    # Compute coherence score
    if shared_primary:
        # Primary overlap → high coherence
        # Base: 0.7, boost by number of shared primary classes
        coherence = 0.7 + (0.3 * min(len(shared_primary), 2) / 2)
    elif shared_secondary:
        # Secondary overlap only → partial coherence
        # Base: 0.3, boost by number of shared secondary classes
        coherence = 0.3 + (0.2 * min(len(shared_secondary), 2) / 2)
    else:
        # No overlap → zero coherence
        coherence = 0.0

    # Cap at 1.0
    coherence = min(1.0, coherence)

    return ReferentAnalysis(
        coherence=round(coherence, 4),
        word_a=word_a,
        word_b=word_b,
        primary_a=profile_a.primary,
        primary_b=profile_b.primary,
        secondary_a=profile_a.secondary,
        secondary_b=profile_b.secondary,
        shared_primary=shared_primary,
        shared_secondary=shared_secondary,
        is_grounded=True,
        is_unknown=False,
    )


def format_referent_analysis(analysis: ReferentAnalysis) -> str:
    """Format referent analysis for display."""
    primary_a_str = ", ".join(c.value for c in analysis.primary_a)
    primary_b_str = ", ".join(c.value for c in analysis.primary_b)
    shared_p_str = ", ".join(c.value for c in analysis.shared_primary) or "none"
    shared_s_str = ", ".join(c.value for c in analysis.shared_secondary) or "none"

    unknown_flag = " [UNKNOWN_REFERENT]" if analysis.is_unknown else ""

    return (
        f"{analysis.word_a} [P: {primary_a_str}] ↔ {analysis.word_b} [P: {primary_b_str}]{unknown_flag}\n"
        f"  Shared Primary: {shared_p_str}\n"
        f"  Shared Secondary: {shared_s_str}\n"
        f"  Coherence (S): {analysis.coherence:.3f}"
    )


# =============================================================================
# Semantic Contextual Coherence (Enhanced S)
# =============================================================================

# Semantic context keywords that modify meaning
CONTEXT_SEMANTIC_GROUPS: Dict[str, FrozenSet[str]] = {
    "royalty": frozenset({"king", "queen", "prince", "princess", "throne", "crown", "palace", "royal", "monarch"}),
    "chess": frozenset({"king", "queen", "bishop", "knight", "rook", "pawn", "checkmate", "board", "move"}),
    "nature": frozenset({"tree", "forest", "river", "mountain", "ocean", "sky", "sun", "moon", "earth",
                         "stream", "meadow", "grassy", "peaceful", "sunset", "sunrise", "garden", "flower",
                         "birds", "bird", "dawn", "dusk", "spring", "summer", "autumn", "winter", "season",
                         "lake", "pond", "field", "valley", "hills", "countryside", "nature", "outdoor"}),
    "emotion": frozenset({"love", "hate", "joy", "sorrow", "fear", "hope", "anger", "happy", "sad"}),
    "family": frozenset({"mother", "father", "child", "family", "home", "parent", "sibling", "son", "daughter"}),
    "technology": frozenset({"computer", "phone", "machine", "digital", "software", "data", "network", "code",
                            "test", "deploy", "database", "migration", "server", "system", "algorithm"}),
    "food": frozenset({"apple", "banana", "food", "eat", "taste", "sweet", "fruit", "vegetable", "cook"}),
    "body": frozenset({"heart", "hand", "eye", "head", "body", "blood", "face", "arm", "leg"}),
    "light": frozenset({"sun", "light", "bright", "glow", "shine", "fire", "flame", "star", "radiance"}),
    "time": frozenset({"time", "day", "night", "year", "moment", "past", "future", "now", "ancient"}),
    "space": frozenset({"place", "space", "path", "road", "world", "home", "distance", "location", "area"}),
    "conflict": frozenset({"war", "peace", "fight", "battle", "enemy", "conflict", "struggle", "victory"}),
    "knowledge": frozenset({"wisdom", "knowledge", "truth", "idea", "thought", "mind", "learn", "study"}),
    # NEW: Finance context for "bank" homonym disambiguation
    "finance": frozenset({"bank", "money", "deposit", "account", "balance", "loan", "credit", "debit",
                         "payment", "transaction", "financial", "interest", "savings", "withdraw", "transfer"}),
    # NEW: Physical/mechanical context for "spring", "run" disambiguation
    # Note: "spring" alone is ambiguous - require mechanical context words
    "physical": frozenset({"mechanism", "repair", "mechanical", "coil",
                          "tension", "force", "physics", "velocity", "mass", "motor", "gear", "device"}),
}


def _extract_semantic_context(text: str) -> List[str]:
    """Extract semantic context groups from text."""
    text_lower = text.lower()
    words = set(text_lower.split())

    matching_groups = []
    for group_name, group_words in CONTEXT_SEMANTIC_GROUPS.items():
        if words & group_words:  # If any overlap
            matching_groups.append(group_name)

    return matching_groups


def _compute_context_similarity(context_a: List[str], context_b: List[str]) -> float:
    """Compute similarity between two semantic contexts."""
    if not context_a or not context_b:
        return 0.0

    set_a = set(context_a)
    set_b = set(context_b)

    # Jaccard similarity
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    return intersection / union if union > 0 else 0.0


def _get_word_semantic_context(word: str) -> List[str]:
    """Get semantic context groups that a word belongs to."""
    word_lower = word.lower().strip()
    groups = []

    for group_name, group_words in CONTEXT_SEMANTIC_GROUPS.items():
        if word_lower in group_words:
            groups.append(group_name)

    return groups


@dataclass(frozen=True)
class SemanticContextAnalysis:
    """Result of semantic contextual analysis."""
    semantic_coherence: float  # S based on semantic context
    class_coherence: float     # S based on referent classes
    combined_coherence: float  # Weighted combination
    word_a: str
    word_b: str
    context_a: Tuple[str, ...]  # Semantic groups for word_a
    context_b: Tuple[str, ...]  # Semantic groups for word_b
    shared_context: Tuple[str, ...]  # Shared semantic groups
    provided_context: Optional[str]  # User-provided context if any


def compute_semantic_contextual_coherence(
    word_a: str,
    word_b: str,
    context: Optional[str] = None,
    config: Optional[SemanticContextConfig] = None,
) -> SemanticContextAnalysis:
    """
    Compute semantic contextual coherence (enhanced S).

    This is the new S = Semantic Contextual Meaning.

    Args:
        word_a: First word
        word_b: Second word
        context: Optional context string to disambiguate meaning
        config: Configuration for context weighting

    Returns:
        SemanticContextAnalysis with semantic, class, and combined coherence

    Example:
        >>> # Without context - uses word's inherent semantic groups
        >>> result = compute_semantic_contextual_coherence("king", "queen")
        >>> print(result.combined_coherence)  # High - both in royalty context

        >>> # With context - "king" in chess context
        >>> result = compute_semantic_contextual_coherence("king", "queen", context="chess move checkmate")
        >>> print(result.combined_coherence)  # High - both in chess context

        >>> # Mismatch - "king" (royalty) vs "banana" (food)
        >>> result = compute_semantic_contextual_coherence("king", "banana")
        >>> print(result.combined_coherence)  # Low - no shared context
    """
    if config is None:
        config = DEFAULT_CONTEXT_CONFIG

    # Get referent class coherence (original S)
    referent_analysis = compute_referent_coherence(word_a, word_b)
    class_coherence = referent_analysis.coherence

    # Get semantic context for each word
    context_a = _get_word_semantic_context(word_a)
    context_b = _get_word_semantic_context(word_b)

    # If user provided context, extract additional semantic groups
    if context:
        provided_groups = _extract_semantic_context(context)
        # Boost word contexts if they match provided context
        for group in provided_groups:
            if group not in context_a and word_a.lower() in CONTEXT_SEMANTIC_GROUPS.get(group, set()):
                context_a.append(group)
            if group not in context_b and word_b.lower() in CONTEXT_SEMANTIC_GROUPS.get(group, set()):
                context_b.append(group)

    # Compute semantic context similarity
    shared_context = list(set(context_a) & set(context_b))

    if shared_context:
        # High semantic coherence - words share context
        semantic_coherence = 0.7 + (0.3 * min(len(shared_context), 3) / 3)
    elif context_a and context_b:
        # Both have contexts but don't overlap
        semantic_coherence = 0.1
    else:
        # No context info - rely on class coherence
        semantic_coherence = class_coherence

    # Combine semantic and class coherence
    if config.use_contextual and (context_a or context_b):
        combined_coherence = (
            config.context_weight * semantic_coherence +
            (1 - config.context_weight) * class_coherence
        )
    else:
        # No contextual info available, use class coherence
        combined_coherence = class_coherence

    return SemanticContextAnalysis(
        semantic_coherence=round(semantic_coherence, 4),
        class_coherence=class_coherence,
        combined_coherence=round(min(1.0, combined_coherence), 4),
        word_a=word_a,
        word_b=word_b,
        context_a=tuple(context_a),
        context_b=tuple(context_b),
        shared_context=tuple(shared_context),
        provided_context=context,
    )


def format_semantic_context_analysis(analysis: SemanticContextAnalysis) -> str:
    """Format semantic context analysis for display."""
    ctx_a = ", ".join(analysis.context_a) or "none"
    ctx_b = ", ".join(analysis.context_b) or "none"
    shared = ", ".join(analysis.shared_context) or "none"

    lines = [
        f"{analysis.word_a} ↔ {analysis.word_b}",
        f"  Context A: {ctx_a}",
        f"  Context B: {ctx_b}",
        f"  Shared Context: {shared}",
        f"  Semantic S: {analysis.semantic_coherence:.3f}",
        f"  Class S: {analysis.class_coherence:.3f}",
        f"  Combined S: {analysis.combined_coherence:.3f}",
    ]

    if analysis.provided_context:
        lines.insert(1, f"  Provided Context: \"{analysis.provided_context}\"")

    return "\n".join(lines)


# =============================================================================
# Public API
# =============================================================================

__all__ = [
    # Configuration
    "SemanticContextConfig",
    "DEFAULT_CONTEXT_CONFIG",
    # Classes
    "ReferentClass",
    "ReferentProfile",
    "ReferentAnalysis",
    "SemanticContextAnalysis",
    # Data
    "WORD_TO_REFERENT",
    "CONTEXT_SEMANTIC_GROUPS",
    # Functions - Class-based (legacy)
    "get_referent_profile",
    "compute_referent_coherence",
    "format_referent_analysis",
    # Functions - Semantic Contextual (new)
    "compute_semantic_contextual_coherence",
    "format_semantic_context_analysis",
]
