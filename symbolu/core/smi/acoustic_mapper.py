"""
Acoustic Mapper - Consonant to Acoustic Feature Mapping
=======================================================

Maps consonants to their acoustic features based on Sanskrit phonetics
and the kosha layer system.

Acoustic features include:
- Articulation type (stop, fricative, nasal, approximant)
- Voicing (voiced/unvoiced)
- Aspiration (aspirated/unaspirated)
- Place of articulation (labial, dental, palatal, velar, etc.)
- Energy profile (high/medium/low)

Each kosha layer has a characteristic acoustic quality:
- ANNAMAYA → Heavy, grounded, viscous
- PRANAMAYA → Explosive, turbulent, pushing
- MANOMAYA → Sharp, cutting, emotional
- VIJNANAMAYA → Penetrating, sibilant, discriminating
- ANANDAMAYA → Pure vibration, vowel-only

Usage:
    from symbolu.core.smi.acoustic_mapper import AcousticMapper

    mapper = AcousticMapper()
    features = mapper.get_acoustic_features("ka")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum, unique

from symbolu.core.smi.smi_engine import extract_consonant, get_kosha_level, syllabify
from symbolu.core.constants import KOSHA_DESCRIPTIONS, CANONICAL_KOSHA_LAYERS


# =============================================================================
# ARTICULATION ENUMS
# =============================================================================


@unique
class ArticulationType(str, Enum):
    """Types of consonant articulation."""
    STOP = "stop"                # Complete closure (p, b, t, d, k, g)
    FRICATIVE = "fricative"      # Turbulent airflow (s, sh, f, h)
    AFFRICATE = "affricate"      # Stop + fricative (ch, j)
    NASAL = "nasal"              # Nasal resonance (m, n, ng)
    APPROXIMANT = "approximant"  # Glide (y, r, l, w)
    VOWEL = "vowel"              # Pure vowel (no consonant)


@unique
class VoicingType(str, Enum):
    """Voicing of consonants."""
    VOICED = "voiced"          # Vocal cords vibrate
    UNVOICED = "unvoiced"      # No vocal cord vibration
    NEUTRAL = "neutral"        # For vowels


@unique
class PlaceOfArticulation(str, Enum):
    """Place where consonant is articulated."""
    LABIAL = "labial"          # Lips (p, b, m)
    DENTAL = "dental"          # Teeth (t, d, n)
    PALATAL = "palatal"        # Palate (ch, j, sh)
    VELAR = "velar"            # Velum (k, g, ng)
    GLOTTAL = "glottal"        # Glottis (h)
    RETROFLEX = "retroflex"    # Curled tongue (ṭ, ḍ)
    NONE = "none"              # For vowels


# =============================================================================
# ACOUSTIC FEATURE DATACLASS
# =============================================================================


@dataclass
class AcousticFeatures:
    """Acoustic features of a consonant.

    Attributes:
        consonant: The analyzed consonant
        articulation: Type of articulation
        voicing: Voicing type
        aspiration: Whether aspirated
        place: Place of articulation
        energy: Energy level (0.0-1.0)
        kosha_level: Associated kosha layer
        acoustic_quality: Descriptive quality from kosha
    """
    consonant: Optional[str]
    articulation: ArticulationType
    voicing: VoicingType
    aspiration: bool
    place: PlaceOfArticulation
    energy: float
    kosha_level: int
    acoustic_quality: str

    def as_dict(self) -> Dict[str, Any]:
        """Return features as dictionary."""
        return {
            "consonant": self.consonant,
            "articulation": self.articulation.value,
            "voicing": self.voicing.value,
            "aspiration": self.aspiration,
            "place": self.place.value,
            "energy": self.energy,
            "kosha_level": self.kosha_level,
            "acoustic_quality": self.acoustic_quality,
        }


# =============================================================================
# CONSONANT FEATURE DATABASE
# =============================================================================

# Mapping of canonical consonants to their acoustic features
CONSONANT_FEATURES: Dict[str, Dict[str, Any]] = {
    # ANNAMAYA (Level 1) - Heavy, grounded
    "ba": {"articulation": "stop", "voicing": "voiced", "aspiration": False, "place": "labial", "energy": 0.3},
    "bha": {"articulation": "stop", "voicing": "voiced", "aspiration": True, "place": "labial", "energy": 0.35},
    "ma": {"articulation": "nasal", "voicing": "voiced", "aspiration": False, "place": "labial", "energy": 0.25},
    "ya": {"articulation": "approximant", "voicing": "voiced", "aspiration": False, "place": "palatal", "energy": 0.2},
    "ra": {"articulation": "approximant", "voicing": "voiced", "aspiration": False, "place": "retroflex", "energy": 0.3},
    "la": {"articulation": "approximant", "voicing": "voiced", "aspiration": False, "place": "dental", "energy": 0.25},

    # PRANAMAYA (Level 2) - Explosive, turbulent
    "ka": {"articulation": "stop", "voicing": "unvoiced", "aspiration": False, "place": "velar", "energy": 0.5},
    "kha": {"articulation": "stop", "voicing": "unvoiced", "aspiration": True, "place": "velar", "energy": 0.6},
    "ga": {"articulation": "stop", "voicing": "voiced", "aspiration": False, "place": "velar", "energy": 0.45},
    "gha": {"articulation": "stop", "voicing": "voiced", "aspiration": True, "place": "velar", "energy": 0.55},
    "ca": {"articulation": "affricate", "voicing": "unvoiced", "aspiration": False, "place": "palatal", "energy": 0.5},
    "cha": {"articulation": "affricate", "voicing": "unvoiced", "aspiration": True, "place": "palatal", "energy": 0.6},

    # MANOMAYA (Level 3) - Sharp, cutting
    "ta": {"articulation": "stop", "voicing": "unvoiced", "aspiration": False, "place": "dental", "energy": 0.55},
    "tha": {"articulation": "stop", "voicing": "unvoiced", "aspiration": True, "place": "dental", "energy": 0.65},
    "da": {"articulation": "stop", "voicing": "voiced", "aspiration": False, "place": "dental", "energy": 0.5},
    "dha": {"articulation": "stop", "voicing": "voiced", "aspiration": True, "place": "dental", "energy": 0.6},
    "na": {"articulation": "nasal", "voicing": "voiced", "aspiration": False, "place": "dental", "energy": 0.35},
    "pa": {"articulation": "stop", "voicing": "unvoiced", "aspiration": False, "place": "labial", "energy": 0.5},
    "pha": {"articulation": "fricative", "voicing": "unvoiced", "aspiration": True, "place": "labial", "energy": 0.55},

    # VIJNANAMAYA (Level 4) - Penetrating, sibilant
    "ja": {"articulation": "affricate", "voicing": "voiced", "aspiration": False, "place": "palatal", "energy": 0.6},
    "jha": {"articulation": "affricate", "voicing": "voiced", "aspiration": True, "place": "palatal", "energy": 0.7},
    "sha": {"articulation": "fricative", "voicing": "unvoiced", "aspiration": False, "place": "palatal", "energy": 0.65},
    "sa": {"articulation": "fricative", "voicing": "unvoiced", "aspiration": False, "place": "dental", "energy": 0.6},
}


def _get_articulation_type(type_str: str) -> ArticulationType:
    """Convert string to ArticulationType."""
    mapping = {
        "stop": ArticulationType.STOP,
        "fricative": ArticulationType.FRICATIVE,
        "affricate": ArticulationType.AFFRICATE,
        "nasal": ArticulationType.NASAL,
        "approximant": ArticulationType.APPROXIMANT,
        "vowel": ArticulationType.VOWEL,
    }
    return mapping.get(type_str, ArticulationType.STOP)


def _get_voicing_type(type_str: str) -> VoicingType:
    """Convert string to VoicingType."""
    mapping = {
        "voiced": VoicingType.VOICED,
        "unvoiced": VoicingType.UNVOICED,
        "neutral": VoicingType.NEUTRAL,
    }
    return mapping.get(type_str, VoicingType.NEUTRAL)


def _get_place_type(type_str: str) -> PlaceOfArticulation:
    """Convert string to PlaceOfArticulation."""
    mapping = {
        "labial": PlaceOfArticulation.LABIAL,
        "dental": PlaceOfArticulation.DENTAL,
        "palatal": PlaceOfArticulation.PALATAL,
        "velar": PlaceOfArticulation.VELAR,
        "glottal": PlaceOfArticulation.GLOTTAL,
        "retroflex": PlaceOfArticulation.RETROFLEX,
        "none": PlaceOfArticulation.NONE,
    }
    return mapping.get(type_str, PlaceOfArticulation.NONE)


# =============================================================================
# ACOUSTIC MAPPER
# =============================================================================


class AcousticMapper:
    """Maps consonants to acoustic features.

    Provides detailed acoustic analysis of consonants based on:
    - Articulation type (stop, fricative, nasal, etc.)
    - Voicing (voiced/unvoiced)
    - Aspiration
    - Place of articulation
    - Energy level
    - Associated kosha layer and quality

    Usage:
        mapper = AcousticMapper()
        features = mapper.get_acoustic_features("ka")
        signature = mapper.compute_acoustic_signature(["ka", "ra", "ma"])
    """

    def __init__(self) -> None:
        """Initialize the acoustic mapper."""
        self._cache: Dict[str, AcousticFeatures] = {}

    def extract_consonant(self, syllable: str) -> Optional[str]:
        """Extract primary consonant from syllable.

        Args:
            syllable: The syllable to analyze

        Returns:
            Canonical consonant form or None for pure vowels
        """
        return extract_consonant(syllable)

    def get_acoustic_features(self, consonant: str) -> Dict[str, float]:
        """Get acoustic feature vector for consonant.

        Args:
            consonant: Canonical consonant (e.g., "ka", "sha")

        Returns:
            Dictionary with acoustic features
        """
        features = self._compute_features(consonant)
        return features.as_dict()

    def get_acoustic_features_detailed(self, consonant: str) -> AcousticFeatures:
        """Get detailed acoustic features for consonant.

        Args:
            consonant: Canonical consonant

        Returns:
            AcousticFeatures dataclass
        """
        return self._compute_features(consonant)

    def compute_acoustic_signature(self, syllables: List[str]) -> List[float]:
        """Compute aggregate acoustic signature for syllable sequence.

        Returns a 6-dimensional signature:
        [avg_energy, stop_ratio, fricative_ratio, voiced_ratio, aspiration_ratio, avg_kosha]

        Args:
            syllables: List of syllables

        Returns:
            6-element acoustic signature
        """
        if not syllables:
            return [0.5, 0.5, 0.0, 0.5, 0.0, 3.0]

        features_list = [self._compute_features(s) for s in syllables]

        # Compute aggregates
        avg_energy = sum(f.energy for f in features_list) / len(features_list)

        stop_count = sum(1 for f in features_list if f.articulation == ArticulationType.STOP)
        fricative_count = sum(1 for f in features_list if f.articulation == ArticulationType.FRICATIVE)
        voiced_count = sum(1 for f in features_list if f.voicing == VoicingType.VOICED)
        aspirated_count = sum(1 for f in features_list if f.aspiration)

        n = len(features_list)
        avg_kosha = sum(f.kosha_level for f in features_list) / n

        return [
            round(avg_energy, 3),
            round(stop_count / n, 3),
            round(fricative_count / n, 3),
            round(voiced_count / n, 3),
            round(aspirated_count / n, 3),
            round(avg_kosha, 2),
        ]

    def compute_word_signature(self, word: str) -> List[float]:
        """Compute acoustic signature for a word.

        Args:
            word: The word to analyze

        Returns:
            6-element acoustic signature
        """
        syllables = syllabify(word)
        return self.compute_acoustic_signature(syllables)

    def _compute_features(self, syllable: str) -> AcousticFeatures:
        """Compute acoustic features for a syllable."""
        if syllable in self._cache:
            return self._cache[syllable]

        consonant = extract_consonant(syllable)
        kosha_level = get_kosha_level(consonant)
        kosha_name = CANONICAL_KOSHA_LAYERS.get(kosha_level, "MANOMAYA")
        acoustic_quality = KOSHA_DESCRIPTIONS.get(kosha_name, {}).get(
            "acoustic_quality", "Unknown"
        )

        if consonant and consonant in CONSONANT_FEATURES:
            info = CONSONANT_FEATURES[consonant]
            features = AcousticFeatures(
                consonant=consonant,
                articulation=_get_articulation_type(info["articulation"]),
                voicing=_get_voicing_type(info["voicing"]),
                aspiration=info["aspiration"],
                place=_get_place_type(info["place"]),
                energy=info["energy"],
                kosha_level=kosha_level,
                acoustic_quality=acoustic_quality,
            )
        else:
            # Default for unknown consonants or vowels
            features = AcousticFeatures(
                consonant=consonant,
                articulation=ArticulationType.VOWEL if not consonant else ArticulationType.STOP,
                voicing=VoicingType.NEUTRAL if not consonant else VoicingType.VOICED,
                aspiration=False,
                place=PlaceOfArticulation.NONE if not consonant else PlaceOfArticulation.DENTAL,
                energy=0.5,
                kosha_level=kosha_level,
                acoustic_quality=acoustic_quality,
            )

        self._cache[syllable] = features
        return features

    def clear_cache(self) -> None:
        """Clear the computation cache."""
        self._cache.clear()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_consonant_features(consonant: str) -> Dict[str, Any]:
    """Convenience function to get acoustic features.

    Args:
        consonant: The consonant to analyze

    Returns:
        Dictionary with acoustic features
    """
    mapper = AcousticMapper()
    return mapper.get_acoustic_features(consonant)


def compute_word_acoustic_signature(word: str) -> List[float]:
    """Convenience function to compute word acoustic signature.

    Args:
        word: The word to analyze

    Returns:
        6-element acoustic signature
    """
    mapper = AcousticMapper()
    return mapper.compute_word_signature(word)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AcousticMapper",
    "AcousticFeatures",
    "ArticulationType",
    "VoicingType",
    "PlaceOfArticulation",
    "CONSONANT_FEATURES",
    "get_consonant_features",
    "compute_word_acoustic_signature",
]
