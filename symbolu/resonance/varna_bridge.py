"""
Varṇa Bridge Integration
========================

Integrates Sanskrit Varṇa-based acoustic data with the resonance engine.

Converts varṇa layer descriptions and bridge meanings to 12D ontological
vectors for use with the existing resonance computation infrastructure.

Data Sources (from formulas/data/):
- varna_bridge_map_v1.json: Core varṇa → bridge_meaning + layer descriptions
- varna_layer_interaction_v1.json: Polarity (positive/negative manifestations)
- varna_polarity_map_v1.json: Polarity vectors
- varna_distortion_map_v1.json: Distortion/sublimation vectors

Key Advantages over ARPABET:
- 43+ varṇas vs 39 ARPABET phonemes
- Semantic layer descriptions (not just numeric affinities)
- Polarity awareness (positive/negative)
- Distortion/sublimation directional vectors
- Grounded in Sanskrit acoustic tradition
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, Optional, List, Any

from symbolu.resonance.types import (
    WordVector,
    OntologicalLayer,
    LAYER_NAMES,
)


# =============================================================================
# Data Paths
# =============================================================================

_MODULE_DIR = Path(__file__).parent
_FORMULAS_DATA = _MODULE_DIR.parent / "formulas" / "data"

_BRIDGE_MAP_PATH = _FORMULAS_DATA / "varna_bridge_map_v1.json"
_LAYER_INTERACTION_PATH = _FORMULAS_DATA / "varna_layer_interaction_v1.json"
_POLARITY_MAP_PATH = _FORMULAS_DATA / "varna_polarity_map_v1.json"


# =============================================================================
# Layer Affinity Keywords
# =============================================================================

# Keywords that indicate high affinity for specific layers
# Used to convert semantic descriptions to numeric affinities

LAYER_KEYWORDS: Dict[str, Dict[str, float]] = {
    "O1_POTENTIAL": {
        "dormant": 0.9, "latent": 0.9, "capacity": 0.8, "potential": 0.9,
        "seed": 0.7, "nascent": 0.8, "hidden": 0.7, "underlying": 0.7,
    },
    "O2_IDENTITY": {
        "identity": 0.9, "labeling": 0.8, "tagging": 0.9, "classification": 0.8,
        "role": 0.8, "name": 0.7, "category": 0.7, "marking": 0.7,
    },
    "O3_EXECUTION": {
        "activation": 0.9, "action": 0.9, "kinetic": 0.8, "momentum": 0.7,
        "force": 0.7, "execution": 0.9, "doing": 0.8, "movement": 0.7,
    },
    "O4_STRUCTURE": {
        "shaping": 0.9, "forming": 0.9, "structure": 0.9, "embodiment": 0.8,
        "pattern": 0.7, "creation": 0.8, "building": 0.7, "coherent": 0.6,
    },
    "O5_COGNITION": {
        "cognition": 0.9, "perception": 0.9, "attention": 0.8, "emotion": 0.8,
        "awareness": 0.7, "sensing": 0.7, "feeling": 0.7, "mental": 0.7,
    },
    "O6_AGENCY": {
        "directing": 0.9, "control": 0.8, "intent": 0.8, "agency": 0.9,
        "steering": 0.7, "guidance": 0.8, "leading": 0.7, "deciding": 0.7,
    },
    "O7_REASONING": {
        "sequencing": 0.8, "reasoning": 0.9, "logic": 0.9, "discrimination": 0.8,
        "analysis": 0.7, "deduction": 0.8, "inference": 0.8, "discernment": 0.7,
    },
    "O8_PURPOSE": {
        "meaning": 0.9, "motivation": 0.9, "purpose": 0.9, "why": 0.8,
        "intent": 0.7, "aim": 0.7, "objective": 0.7, "goal": 0.7,
    },
    "O9_WITNESSES": {
        "tracking": 0.8, "observing": 0.9, "witnessing": 0.9, "meta": 0.8,
        "awareness": 0.8, "watching": 0.7, "consciousness": 0.8, "seeing": 0.7,
    },
    "O10_UNIFYING": {
        "integration": 0.8, "unifying": 0.9, "coherence": 0.9, "synthesis": 0.8,
        "connection": 0.7, "bonding": 0.7, "harmony": 0.8, "wholeness": 0.7,
    },
    "O11_INTEGRATION": {
        "resolution": 0.9, "consolidation": 0.9, "integration": 0.9, "merging": 0.8,
        "completion": 0.7, "settling": 0.7, "combining": 0.7, "uniting": 0.7,
    },
    "O12_ABSOLVING": {
        "dissolution": 0.9, "termination": 0.9, "absolving": 0.9, "release": 0.8,
        "transcendence": 0.8, "ending": 0.8, "completion": 0.7, "finality": 0.7,
    },
}

# Bridge meaning keywords → layer affinities
BRIDGE_MEANING_AFFINITIES: Dict[str, Tuple[float, ...]] = {
    # Vowel bridge meanings
    "birth_of_cognition": (0.8, 0.5, 0.3, 0.4, 0.3, 0.4, 0.4, 0.5, 0.4, 0.3),
    "expansion_continuity": (0.4, 0.7, 0.3, 0.3, 0.5, 0.4, 0.5, 0.4, 0.6, 0.4),
    "self_doing": (0.5, 0.5, 0.7, 0.4, 0.5, 0.4, 0.6, 0.4, 0.4, 0.3),
    "specialized_identity": (0.6, 0.4, 0.5, 0.6, 0.4, 0.5, 0.5, 0.5, 0.4, 0.3),
    "contraction_focus": (0.5, 0.4, 0.4, 0.5, 0.6, 0.5, 0.5, 0.4, 0.3, 0.3),
    "sustained_hold": (0.4, 0.5, 0.3, 0.4, 0.5, 0.4, 0.5, 0.4, 0.5, 0.4),
    "practical_cognition": (0.7, 0.5, 0.5, 0.5, 0.5, 0.6, 0.5, 0.4, 0.4, 0.3),
    "integrative_understanding": (0.6, 0.5, 0.3, 0.4, 0.4, 0.7, 0.5, 0.5, 0.7, 0.4),
    "closure_completion": (0.4, 0.5, 0.4, 0.4, 0.4, 0.4, 0.6, 0.4, 0.5, 0.7),
    "surrender_transition": (0.3, 0.4, 0.3, 0.3, 0.3, 0.3, 0.4, 0.5, 0.6, 0.8),
    "purgative_repulsion": (0.3, 0.4, 0.5, 0.4, 0.4, 0.3, 0.4, 0.4, 0.3, 0.6),
    "dissolutive_attraction": (0.4, 0.4, 0.3, 0.3, 0.3, 0.3, 0.4, 0.5, 0.5, 0.7),

    # Consonant bridge meanings (selected)
    "hope_pressure": (0.5, 0.6, 0.6, 0.4, 0.6, 0.5, 0.7, 0.4, 0.5, 0.3),
    "worry_pressure": (0.6, 0.4, 0.5, 0.5, 0.6, 0.6, 0.5, 0.6, 0.3, 0.3),
    "action_pressure": (0.4, 0.5, 0.9, 0.4, 0.5, 0.4, 0.6, 0.4, 0.5, 0.3),
    "attachment_pressure": (0.4, 0.5, 0.4, 0.4, 0.4, 0.3, 0.4, 0.4, 0.7, 0.4),
    "conscience_pressure": (0.6, 0.5, 0.4, 0.5, 0.6, 0.6, 0.5, 0.6, 0.4, 0.4),
    "ego_pressure": (0.5, 0.5, 0.6, 0.6, 0.5, 0.5, 0.6, 0.5, 0.3, 0.3),
    "inertia_pressure": (0.4, 0.6, 0.3, 0.4, 0.4, 0.4, 0.4, 0.4, 0.5, 0.5),
    "irritability_pressure": (0.4, 0.4, 0.7, 0.5, 0.5, 0.4, 0.4, 0.5, 0.3, 0.4),
    "craving_pressure": (0.4, 0.4, 0.5, 0.4, 0.6, 0.4, 0.6, 0.4, 0.5, 0.3),
    "revulsion_pressure": (0.3, 0.4, 0.6, 0.5, 0.5, 0.4, 0.4, 0.4, 0.2, 0.5),
    "fear_pressure": (0.5, 0.4, 0.5, 0.5, 0.6, 0.5, 0.5, 0.6, 0.3, 0.4),
    "indifference_pressure": (0.3, 0.3, 0.2, 0.3, 0.3, 0.3, 0.3, 0.4, 0.4, 0.6),
    "delusion_pressure": (0.5, 0.4, 0.4, 0.3, 0.4, 0.3, 0.4, 0.3, 0.4, 0.4),
    "indulgence_pressure": (0.4, 0.4, 0.5, 0.4, 0.4, 0.3, 0.5, 0.4, 0.5, 0.4),
    "distrust_pressure": (0.5, 0.4, 0.4, 0.5, 0.5, 0.6, 0.4, 0.6, 0.3, 0.3),
    "destruction_pressure": (0.3, 0.3, 0.7, 0.4, 0.5, 0.4, 0.4, 0.4, 0.2, 0.7),
    "cruelty_pressure": (0.3, 0.4, 0.7, 0.4, 0.5, 0.4, 0.4, 0.4, 0.2, 0.5),
    "external_dharma_pressure": (0.4, 0.5, 0.4, 0.5, 0.6, 0.5, 0.5, 0.5, 0.5, 0.4),
    "material_greed_pressure": (0.4, 0.5, 0.5, 0.5, 0.5, 0.4, 0.6, 0.4, 0.4, 0.3),
    "escape_pressure": (0.4, 0.4, 0.6, 0.4, 0.6, 0.5, 0.5, 0.5, 0.3, 0.5),
    "ignorance_pressure": (0.3, 0.3, 0.3, 0.3, 0.3, 0.2, 0.3, 0.3, 0.3, 0.5),
    "false_knowledge_pressure": (0.4, 0.3, 0.4, 0.4, 0.4, 0.3, 0.4, 0.4, 0.3, 0.4),
    "lust_confusion_pressure": (0.4, 0.4, 0.5, 0.4, 0.5, 0.3, 0.5, 0.4, 0.4, 0.4),
    "nasal_marker_pressure": (0.4, 0.4, 0.3, 0.5, 0.4, 0.4, 0.4, 0.4, 0.6, 0.4),
    "nervous_breakdown_pressure": (0.3, 0.3, 0.6, 0.4, 0.4, 0.3, 0.3, 0.5, 0.2, 0.6),
    "greed_pressure": (0.4, 0.5, 0.5, 0.5, 0.5, 0.4, 0.6, 0.4, 0.4, 0.3),
    "hypocrisy_pressure": (0.4, 0.4, 0.4, 0.5, 0.4, 0.4, 0.4, 0.5, 0.3, 0.4),
    "overstatement_pressure": (0.4, 0.5, 0.5, 0.5, 0.5, 0.4, 0.5, 0.4, 0.4, 0.4),
    "repentance_pressure": (0.5, 0.4, 0.4, 0.4, 0.4, 0.5, 0.4, 0.5, 0.4, 0.5),
    "shyness_pressure": (0.4, 0.3, 0.3, 0.4, 0.4, 0.4, 0.3, 0.5, 0.4, 0.4),
    "sadistic_cruelty_pressure": (0.3, 0.4, 0.8, 0.4, 0.5, 0.4, 0.4, 0.4, 0.2, 0.5),
    "envy_pressure": (0.4, 0.4, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.3, 0.3),
    "melancholy_pressure": (0.4, 0.3, 0.3, 0.4, 0.3, 0.4, 0.3, 0.5, 0.4, 0.5),

    # Default for unknown
    "unknown": (0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3),
}


# =============================================================================
# Varṇa Data Loader
# =============================================================================

@dataclass
class VarnaData:
    """Loaded varṇa data from JSON files."""
    bridge_map: Dict[str, Any]
    layer_interactions: Dict[str, Any]
    polarity_map: Dict[str, Any]

    @classmethod
    def load(cls) -> "VarnaData":
        """Load all varṇa data from JSON files."""
        bridge_map = {}
        layer_interactions = {}
        polarity_map = {}

        if _BRIDGE_MAP_PATH.exists():
            with open(_BRIDGE_MAP_PATH, "r", encoding="utf-8") as f:
                bridge_map = json.load(f)

        if _LAYER_INTERACTION_PATH.exists():
            with open(_LAYER_INTERACTION_PATH, "r", encoding="utf-8") as f:
                layer_interactions = json.load(f)

        if _POLARITY_MAP_PATH.exists():
            with open(_POLARITY_MAP_PATH, "r", encoding="utf-8") as f:
                polarity_map = json.load(f)

        return cls(
            bridge_map=bridge_map,
            layer_interactions=layer_interactions,
            polarity_map=polarity_map,
        )


# Singleton instance
_varna_data: Optional[VarnaData] = None


def get_varna_data() -> VarnaData:
    """Get or load the varṇa data singleton."""
    global _varna_data
    if _varna_data is None:
        _varna_data = VarnaData.load()
    return _varna_data


# =============================================================================
# Varṇa to 10D Vector Conversion
# =============================================================================

def varna_to_10d_vector(varna: str) -> Tuple[float, ...]:
    """
    Convert a varṇa symbol to a 10D ontological vector.

    Uses bridge_meaning to look up pre-computed affinities,
    then refines with layer descriptions if available.

    Args:
        varna: Sanskrit varṇa symbol (e.g., "sa", "a", "ka")

    Returns:
        10D tuple of layer affinities (normalized)
    """
    data = get_varna_data()

    # Look up in vowels first, then consonants
    vowels = data.bridge_map.get("vowels", {})
    consonants = data.bridge_map.get("consonants", {})

    varna_info = vowels.get(varna) or consonants.get(varna)

    if varna_info is None:
        # Unknown varṇa
        return BRIDGE_MEANING_AFFINITIES["unknown"]

    # Get bridge meaning
    bridge_meaning = varna_info.get("bridge_meaning", "unknown")

    # Look up pre-computed affinities
    if bridge_meaning in BRIDGE_MEANING_AFFINITIES:
        base_vector = list(BRIDGE_MEANING_AFFINITIES[bridge_meaning])
    else:
        base_vector = list(BRIDGE_MEANING_AFFINITIES["unknown"])

    # Refine with layer descriptions if available
    layers = varna_info.get("layers", {})
    for i, layer_name in enumerate(LAYER_NAMES):
        if layer_name in layers:
            description = layers[layer_name].lower()
            # Boost affinity based on keywords
            keywords = LAYER_KEYWORDS.get(layer_name, {})
            for keyword, weight in keywords.items():
                if keyword in description:
                    base_vector[i] = min(1.0, base_vector[i] + weight * 0.1)

    # Normalize
    return _normalize_vector(tuple(base_vector))


def _normalize_vector(vec: Tuple[float, ...]) -> Tuple[float, ...]:
    """Normalize vector to unit length."""
    magnitude = math.sqrt(sum(v * v for v in vec))
    if magnitude == 0:
        return vec
    return tuple(v / magnitude for v in vec)


# =============================================================================
# English to Varṇa Mapping
# =============================================================================

# Map English phonemes (ARPABET-like) to closest varṇa
ENGLISH_TO_VARNA: Dict[str, str] = {
    # Vowels
    "AH": "a", "AA": "ā", "IH": "i", "IY": "ī", "UH": "u", "UW": "ū",
    "EH": "e", "EY": "e", "AE": "a", "AO": "o", "OW": "o", "OY": "ai",
    "AY": "ai", "AW": "au", "ER": "a",

    # Plosives
    "K": "ka", "G": "ga", "T": "ta", "D": "da", "P": "pa", "B": "ba",

    # Aspirated (map to aspirated varṇa)
    "KH": "kha", "GH": "gha", "TH": "tha", "DH": "dha", "PH": "pha", "BH": "bha",

    # Nasals
    "M": "ma", "N": "na", "NG": "nga",

    # Sibilants
    "S": "sa", "Z": "sa", "SH": "sha", "ZH": "sha",

    # Liquids
    "L": "la", "R": "ra",

    # Glides
    "W": "va", "Y": "ya",

    # Fricatives
    "F": "pha", "V": "va", "HH": "ha",

    # Affricates
    "CH": "ca", "JH": "ja",
}


def english_phoneme_to_varna(phoneme: str) -> Optional[str]:
    """
    Map an English/ARPABET phoneme to closest Sanskrit varṇa.

    Args:
        phoneme: ARPABET phoneme (e.g., "K", "AH", "S")

    Returns:
        Varṇa symbol or None if no mapping exists
    """
    # Strip stress markers
    clean = phoneme.rstrip("012").upper()
    return ENGLISH_TO_VARNA.get(clean)


def phonemes_to_varnas(phonemes: Tuple[str, ...]) -> Tuple[str, ...]:
    """Convert a sequence of English phonemes to varṇas."""
    varnas = []
    for p in phonemes:
        v = english_phoneme_to_varna(p)
        if v:
            varnas.append(v)
    return tuple(varnas)


# =============================================================================
# Varṇa-Based Word Vector
# =============================================================================

def varna_word_to_vector(
    word: str,
    phonemes: Tuple[str, ...],
) -> WordVector:
    """
    Convert a word to 10D vector using varṇa-based affinities.

    This is the varṇa-enhanced version of word_to_vector.

    Args:
        word: The original word
        phonemes: ARPABET phoneme sequence

    Returns:
        WordVector with varṇa-derived 10D projection
    """
    if not phonemes:
        zero_vec = tuple(0.0 for _ in range(10))
        return WordVector(
            word=word,
            phonemes=phonemes,
            vector=zero_vec,
            trajectory=(),
            dominant_layer=LAYER_NAMES[0],
            dominant_score=0.0,
        )

    # Convert phonemes to varṇas
    varnas = phonemes_to_varnas(phonemes)

    # Accumulate weighted affinities
    accumulated = [0.0] * 10
    trajectory = []

    # Position weights (first phoneme has more impact)
    position_weights = (1.5, 1.25, 1.0)

    for i, varna in enumerate(varnas):
        affinities = varna_to_10d_vector(varna)

        # Position weight
        weight = position_weights[i] if i < len(position_weights) else 1.0

        for j in range(10):
            accumulated[j] += affinities[j] * weight

        # Track trajectory
        magnitude = math.sqrt(sum(a * a for a in affinities))
        trajectory.append(magnitude * weight)

    # Normalize
    normalized = _normalize_vector(tuple(accumulated))

    # Find dominant layer
    max_idx = 0
    max_val = normalized[0]
    for i in range(1, 10):
        if normalized[i] > max_val:
            max_val = normalized[i]
            max_idx = i

    return WordVector(
        word=word,
        phonemes=phonemes,
        vector=normalized,
        trajectory=tuple(trajectory),
        dominant_layer=LAYER_NAMES[max_idx],
        dominant_score=max_val,
    )


# =============================================================================
# Public API
# =============================================================================

def get_varna_affinities(varna: str) -> Tuple[float, ...]:
    """Get 10D affinities for a varṇa symbol."""
    return varna_to_10d_vector(varna)


def get_bridge_meaning(varna: str) -> str:
    """Get the bridge meaning for a varṇa."""
    data = get_varna_data()
    vowels = data.bridge_map.get("vowels", {})
    consonants = data.bridge_map.get("consonants", {})

    varna_info = vowels.get(varna) or consonants.get(varna)
    if varna_info:
        return varna_info.get("bridge_meaning", "unknown")
    return "unknown"


def list_varnas() -> Tuple[str, ...]:
    """Return all known varṇa symbols."""
    data = get_varna_data()
    vowels = set(data.bridge_map.get("vowels", {}).keys())
    consonants = set(data.bridge_map.get("consonants", {}).keys())
    return tuple(sorted(vowels | consonants))


__all__ = [
    "VarnaData",
    "get_varna_data",
    "varna_to_10d_vector",
    "varna_word_to_vector",
    "english_phoneme_to_varna",
    "phonemes_to_varnas",
    "get_varna_affinities",
    "get_bridge_meaning",
    "list_varnas",
    "ENGLISH_TO_VARNA",
    "BRIDGE_MEANING_AFFINITIES",
]
